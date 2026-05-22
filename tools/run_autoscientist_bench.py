from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.db.models import RunReplay, WorkflowPolicyModel
from app.db.session import SessionLocal
from app.env import load_environment
from app.services.local_runner import run_question
from app.services.open_scientist_adapters import OpenScientistCapabilityRegistry
from app.services.scientific_memory import build_scientific_state_graph, train_workflow_policy_model
from app.services.tooluniverse_adapter import ToolUniverseAdapter

from tools.package_policy_model import package_model
from tools.run_integration_benchmark import (
    build_run_config,
    report_experiments,
    result_tool_calls,
    summarize_integrations,
    value_score,
)


DEFAULT_MANIFEST = Path("benchmarks/autoscientist_bench_v0_1.json")
OPEN_TARGETS_GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"
NCBI_EUTILS_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
SUPPORTED_ABLATIONS = {"full", "no_memory", "no_public_tools", "no_sciflow"}


def load_manifest(path: str | Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Benchmark manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def expand_tasks(
    manifest: dict[str, Any],
    *,
    limit: int | None = None,
    replicates_per_case: int = 1,
    offline_public_context: bool = False,
    public_timeout_seconds: int = 8,
    case_ids: list[str] | None = None,
    template_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    templates = manifest.get("task_templates", [])
    seed_cases = manifest.get("seed_cases", [])
    if not templates or not seed_cases:
        raise ValueError("Manifest must contain task_templates and seed_cases.")
    selected_case_ids = set(case_ids or [])
    selected_template_ids = set(template_ids or [])
    if selected_case_ids:
        seed_cases = [case for case in seed_cases if case.get("id") in selected_case_ids]
    if selected_template_ids:
        templates = [template for template in templates if template.get("id") in selected_template_ids]
    if not seed_cases:
        raise ValueError(f"No seed cases matched requested case ids: {sorted(selected_case_ids)}")
    if not templates:
        raise ValueError(f"No task templates matched requested template ids: {sorted(selected_template_ids)}")
    tasks: list[dict[str, Any]] = []
    replicate_count = max(1, int(replicates_per_case))
    for case in seed_cases:
        public_context = fetch_public_context(
            case,
            offline=offline_public_context,
            timeout_seconds=public_timeout_seconds,
        )
        for replicate in range(replicate_count):
            for template in templates:
                objective = template["objective_template"].format(**case)
                if replicate:
                    objective = (
                        f"{objective} Repeat index {replicate + 1}: vary evidence retrieval order, "
                        "but keep claims bounded and provenance explicit."
                    )
                tasks.append(
                    {
                        "id": f"{case['id']}__{template['id']}__r{replicate + 1}",
                        "case_id": case["id"],
                        "template_id": template["id"],
                        "replicate": replicate + 1,
                        "domain": case.get("domain"),
                        "priority": case.get("priority"),
                        "gene_symbol": case.get("gene_symbol"),
                        "disease_name": case.get("disease_name"),
                        "target_ensembl_id": case.get("target_ensembl_id"),
                        "disease_efo_id": case.get("disease_efo_id"),
                        "expected_capabilities": sorted(
                            set(case.get("expected_capabilities", []))
                            | set(template.get("expected_capabilities", []))
                        ),
                        "objective": objective,
                        "public_context": public_context,
                    }
                )
                if limit and len(tasks) >= limit:
                    return tasks
    return tasks


def fetch_public_context(case: dict[str, Any], *, offline: bool, timeout_seconds: int) -> dict[str, Any]:
    if offline:
        return {"mode": "offline", "warnings": ["Public context fetch skipped by --offline-public-context."]}
    context = {"mode": "live", "warnings": []}
    gene = str(case.get("gene_symbol") or "")
    disease = str(case.get("disease_name") or "")
    target_id = str(case.get("target_ensembl_id") or "")
    context["ncbi_gene"] = fetch_ncbi_count(
        f"{gene}[Gene Name] AND Homo sapiens[Organism]",
        db="gene",
        timeout_seconds=timeout_seconds,
    )
    context["pubmed_gene_disease"] = fetch_ncbi_count(
        f"{gene} {disease}",
        db="pubmed",
        timeout_seconds=timeout_seconds,
    )
    if target_id:
        context["open_targets_target"] = fetch_open_targets_target(target_id, timeout_seconds=timeout_seconds)
    return context


def fetch_ncbi_count(query: str, *, db: str, timeout_seconds: int) -> dict[str, Any]:
    params = urllib.parse.urlencode({"db": db, "term": query, "retmode": "json", "retmax": "0"})
    url = f"{NCBI_EUTILS_URL}?{params}"
    try:
        data = json_get(url, timeout_seconds=timeout_seconds)
        result = data.get("esearchresult", {})
        return {
            "status": "success",
            "query": query,
            "db": db,
            "count": int(result.get("count", 0)),
            "url": url,
        }
    except Exception as exc:
        return {"status": "failure", "query": query, "db": db, "error": str(exc)[:300], "url": url}


def fetch_open_targets_target(target_ensembl_id: str, *, timeout_seconds: int) -> dict[str, Any]:
    query = """
    query Target($ensemblId: String!) {
      target(ensemblId: $ensemblId) {
        id
        approvedSymbol
        approvedName
        biotype
        tractability {
          label
          modality
          value
        }
      }
    }
    """
    payload = {"query": query, "variables": {"ensemblId": target_ensembl_id}}
    try:
        data = json_post(OPEN_TARGETS_GRAPHQL_URL, payload, timeout_seconds=timeout_seconds)
        target = data.get("data", {}).get("target")
        return {
            "status": "success" if target else "partial",
            "target_ensembl_id": target_ensembl_id,
            "target": target,
            "url": OPEN_TARGETS_GRAPHQL_URL,
            "errors": data.get("errors", []),
        }
    except Exception as exc:
        return {
            "status": "failure",
            "target_ensembl_id": target_ensembl_id,
            "error": str(exc)[:300],
            "url": OPEN_TARGETS_GRAPHQL_URL,
        }


def json_get(url: str, *, timeout_seconds: int) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "AutoScientist-Bench/0.1"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def json_post(url: str, payload: dict[str, Any], *, timeout_seconds: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "AutoScientist-Bench/0.1"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    load_environment()
    validate_runtime_request(args)
    started = time.time()
    output_dir = Path(args.output_dir) / time.strftime("%Y%m%d_%H%M%S", time.gmtime(started))
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(args.manifest)
    tasks = expand_tasks(
        manifest,
        limit=args.limit,
        replicates_per_case=args.replicates_per_case,
        offline_public_context=args.offline_public_context,
        public_timeout_seconds=args.public_timeout_seconds,
        case_ids=args.case_ids,
        template_ids=args.template_ids,
    )
    tasks_path = output_dir / "benchmark_tasks.json"
    tasks_path.write_text(json.dumps({"manifest": manifest, "tasks": tasks}, indent=2), encoding="utf-8")
    if args.prepare_only:
        summary = {
            "schema": "autosci.benchmark_run.v0.1",
            "status": "prepared",
            "task_count": len(tasks),
            "tasks_path": str(tasks_path),
        }
        (output_dir / "benchmark_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    ablations = validate_ablations(args.ablations)
    health = benchmark_health()
    results = []
    for task in tasks:
        for ablation in ablations:
            result = run_task(task, ablation, args, health)
            result_path = output_dir / f"{task['id']}__{ablation}.json"
            result_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
            result["artifact_path"] = str(result_path)
            results.append(result)

    trained_policy = train_policy_if_requested(args, output_dir)
    neural_policy = train_neural_policy_if_requested(args, output_dir)
    state_graph = export_state_graph(output_dir, limit=args.graph_limit)
    package = package_latest_policy_if_requested(args, output_dir)
    summary = build_benchmark_summary(
        manifest=manifest,
        tasks=tasks,
        results=results,
        health=health,
        trained_policy=trained_policy,
        neural_policy=neural_policy,
        state_graph=state_graph,
        package=package,
        output_dir=output_dir,
        elapsed_seconds=time.time() - started,
    )
    summary["realness_gates"] = evaluate_realness_gates(summary, results, args)
    if not summary["realness_gates"]["passed"]:
        summary["status"] = "failed_gates"
    summary_path = output_dir / "benchmark_summary.json"
    summary_md_path = output_dir / "benchmark_summary.md"
    summary["summary_path"] = str(summary_path)
    summary["summary_markdown_path"] = str(summary_md_path)
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    summary_md_path.write_text(render_summary_markdown(summary), encoding="utf-8")
    return summary


def validate_runtime_request(args: argparse.Namespace) -> None:
    errors = []
    if args.strict_real_run:
        if args.llm_provider == "mock":
            errors.append(
                "--strict-real-run requires --llm-provider auto/openai/anthropic/gemini/"
                "local_http/openai_compatible, not mock."
            )
        if not args.require_real_llm:
            errors.append("--strict-real-run requires --require-real-llm.")
        if args.offline_public_context:
            errors.append("--strict-real-run requires live public context; remove --offline-public-context.")
        if not args.enable_sciflow_policy:
            errors.append("--strict-real-run requires --enable-sciflow-policy.")
        if not args.train_neural_policy:
            errors.append("--strict-real-run requires --train-neural-policy.")
    if errors:
        raise SystemExit("Real-run configuration failed:\n- " + "\n- ".join(errors))


def validate_ablations(ablations: list[str]) -> list[str]:
    selected = list(dict.fromkeys(ablations or ["full"]))
    unknown = sorted(set(selected) - SUPPORTED_ABLATIONS)
    if unknown:
        raise SystemExit(f"Unknown ablations: {', '.join(unknown)}")
    return selected


def benchmark_health() -> dict[str, Any]:
    registry = OpenScientistCapabilityRegistry()
    return {
        "tooluniverse": ToolUniverseAdapter().tooluniverse_health(),
        "open_scientist": registry.health(),
    }


def run_task(
    task: dict[str, Any],
    ablation: str,
    args: argparse.Namespace,
    health: dict[str, Any],
) -> dict[str, Any]:
    config = benchmark_run_config(args)
    apply_ablation(config, ablation)
    started = time.time()
    result = run_question(task["objective"], config)
    integrations = summarize_integrations(result, health)
    assessment = benchmark_value_score(result, integrations, task, ablation)
    replay = replay_status(result.get("run_id"))
    return {
        "schema": "autosci.benchmark_task_result.v0.1",
        "created_at_unix": int(started),
        "elapsed_seconds": round(time.time() - started, 2),
        "task": task,
        "ablation": ablation,
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "final_confidence": result.get("final_confidence"),
        "run_config": redact_benchmark_config(config),
        "health": health,
        "integrations": integrations,
        "value_assessment": assessment,
        "replay": replay,
        "sciflow_policy": extract_sciflow_advice(result),
        "sciflow_application": extract_sciflow_application(result),
        "trace_summary": result.get("trace_summary"),
        "report": result.get("report", {}),
        "hypothesis": result.get("report", {}).get("hypothesis", {}),
        "evidence_count": len(result.get("report", {}).get("evidence", [])),
        "guardrails": result.get("report", {}).get("guardrails", []),
        "experiments": report_experiments(result.get("report", {})),
        "tool_calls": result.get("provenance", {}).get("tool_calls", []),
    }


def benchmark_run_config(args: argparse.Namespace) -> dict[str, Any]:
    base = SimpleNamespace(
        llm_provider=args.llm_provider,
        llm_api_key_env_var=args.llm_api_key_env_var,
        llm_model=args.llm_model,
        agent_count=args.agent_count,
        max_runtime_minutes=args.max_runtime_minutes,
        tool_budget_usd=args.tool_budget_usd,
        llm_max_tokens=args.llm_max_tokens,
        qworld_model=args.qworld_model,
        qworld_api_key_env_var=args.qworld_api_key_env_var,
        disable_qworld=args.disable_qworld,
        require_real_llm=args.require_real_llm,
        persist_memory_enabled=True,
        sciflow_policy_enabled=args.enable_sciflow_policy,
        sciflow_policy_model_id=args.sciflow_policy_model_id,
        sciflow_policy_model_path=args.sciflow_policy_model_path,
        sciflow_policy_min_score=args.sciflow_policy_min_score,
    )
    config = build_run_config(base)
    config["benchmark_suite"] = "AutoScientist-Bench v0.1"
    return config


def apply_ablation(config: dict[str, Any], ablation: str) -> None:
    if ablation == "no_memory":
        config["persist_memory_enabled"] = False
        config["sciflow_policy_enabled"] = False
    elif ablation == "no_public_tools":
        config["real_data_enabled"] = False
    elif ablation == "no_sciflow":
        config["sciflow_policy_enabled"] = False


def benchmark_value_score(
    result: dict[str, Any],
    integrations: dict[str, Any],
    task: dict[str, Any],
    ablation: str,
) -> dict[str, Any]:
    base = value_score(result, integrations)
    replay = replay_status(result.get("run_id"))
    sciflow = extract_sciflow_advice(result)
    sciflow_application = extract_sciflow_application(result)
    public_context = task.get("public_context", {})
    checks = {
        **base["checks"],
        "memory_or_replay": bool(replay.get("available")) if ablation != "no_memory" else False,
        "controller_advice": sciflow.get("status") == "success" if ablation not in {"no_memory", "no_sciflow"} else False,
        "controller_applied": bool(sciflow_application.get("applied"))
        if ablation not in {"no_memory", "no_sciflow"}
        else False,
        "public_context_prefetched": public_context.get("mode") in {"live", "offline"},
        "open_targets_context": public_context.get("open_targets_target", {}).get("status") in {"success", "partial"},
        "pubmed_context": public_context.get("pubmed_gene_disease", {}).get("status") == "success",
    }
    bonus_weights = {
        "memory_or_replay": 7,
        "controller_advice": 6,
        "public_context_prefetched": 2,
        "open_targets_context": 3,
        "pubmed_context": 2,
    }
    bonus = sum(weight for name, weight in bonus_weights.items() if checks[name])
    score = min(100, base["score"] + bonus)
    impact = controller_impact(result, sciflow_application)
    return {
        "score": score,
        "base_score": base["score"],
        "max_score": 100,
        "checks": checks,
        "scientific_quality": scientific_quality_score(result, integrations, checks, impact),
        "controller_impact": impact,
        "interpretation": interpret_benchmark_score(score, ablation),
    }


def scientific_quality_score(
    result: dict[str, Any],
    integrations: dict[str, Any],
    checks: dict[str, bool],
    impact: dict[str, Any],
) -> dict[str, Any]:
    report = result.get("report", {})
    evidence = report.get("evidence", [])
    experiments = report_experiments(report)
    quality_checks = {
        "completed_run": result.get("status") == "completed",
        "nonempty_hypothesis": bool(report.get("hypothesis", {}).get("title") and report.get("hypothesis", {}).get("text")),
        "evidence_depth": len(evidence) >= 5,
        "scored_evidence": any(item.get("support_score") is not None for item in evidence),
        "experiments_proposed": len(experiments) >= 1,
        "clean_tool_inputs": bool(checks.get("clean_tool_inputs")),
        "auditable_trace": bool(checks.get("auditable_trace")),
        "live_public_tools": bool(integrations.get("public_biomedical", {}).get("executed")),
        "tooluniverse": bool(integrations.get("tooluniverse", {}).get("executed")),
        "controller_applied": bool(impact.get("applied")),
    }
    weights = {
        "completed_run": 8,
        "nonempty_hypothesis": 8,
        "evidence_depth": 14,
        "scored_evidence": 8,
        "experiments_proposed": 14,
        "clean_tool_inputs": 16,
        "auditable_trace": 10,
        "live_public_tools": 10,
        "tooluniverse": 7,
        "controller_applied": 5,
    }
    score = sum(weights[name] for name, passed in quality_checks.items() if passed)
    return {
        "score": score,
        "max_score": sum(weights.values()),
        "checks": quality_checks,
        "interpretation": interpret_scientific_quality(score),
    }


def interpret_scientific_quality(score: int) -> str:
    if score >= 85:
        return "strong: credible scientific artifact with live evidence, clean tool use, provenance, and experiments"
    if score >= 70:
        return "promising: useful artifact, but one or more scientific quality gates still need tightening"
    if score >= 50:
        return "partial: runtime value is visible, but scientific value is not yet strong enough to claim"
    return "weak: result is mainly orchestration or logging, not a credible scientific output yet"


def interpret_benchmark_score(score: int, ablation: str) -> str:
    if score >= 85 and ablation == "full":
        return "strong full-runtime result: public tools, provenance, memory, and controller traces are inspectable"
    if score >= 75:
        return "promising: run is useful, but compare against full/no-memory deltas before claiming value"
    if score >= 55:
        return "partial: workflow completed, but value still looks like orchestration rather than scientific infrastructure"
    return "weak: result lacks enough evidence, traceability, or integration coverage"


def replay_status(run_id: str | None) -> dict[str, Any]:
    if not run_id:
        return {"available": False}
    db = SessionLocal()
    try:
        replay = db.query(RunReplay).filter(RunReplay.run_id == run_id).first()
        if replay is None:
            return {"available": False}
        return {"available": True, "replay_hash": replay.replay_hash, "created_at": replay.created_at.isoformat()}
    finally:
        db.close()


def extract_sciflow_advice(result: dict[str, Any]) -> dict[str, Any]:
    if isinstance(result.get("sciflow_policy"), dict):
        return result["sciflow_policy"]
    for step in result.get("provenance", {}).get("agent_steps", []):
        if step.get("state_name") != "FIND_TOOLS":
            continue
        advice = step.get("output", {}).get("sciflow_policy")
        if isinstance(advice, dict):
            return advice
    return {"enabled": False, "status": "not_recorded", "predictions": []}


def extract_sciflow_application(result: dict[str, Any]) -> dict[str, Any]:
    if isinstance(result.get("sciflow_application"), dict):
        return result["sciflow_application"]
    for step in result.get("provenance", {}).get("agent_steps", []):
        if step.get("state_name") != "EXECUTE_EVIDENCE_COLLECTION":
            continue
        application = step.get("output", {}).get("sciflow_policy_application")
        if isinstance(application, dict):
            return application
    return {"status": "not_recorded", "applied": False, "effects": []}


def controller_impact(result: dict[str, Any], application: dict[str, Any]) -> dict[str, Any]:
    tool_calls = result_tool_calls(result)
    evidence = result.get("report", {}).get("evidence", [])
    return {
        "applied": bool(application.get("applied")),
        "status": application.get("status", "not_recorded"),
        "effects": application.get("effects", []),
        "policy_followup_pubmed_queries": application.get("policy_followup_pubmed_queries", []),
        "tool_call_count": len(tool_calls),
        "evidence_count": len(evidence),
        "public_biomedical_call_count": sum(
            1 for call in tool_calls if call.get("tool_source") == "live_public_biomedical"
        ),
        "tooluniverse_call_count": sum(1 for call in tool_calls if call.get("tool_source") == "tooluniverse"),
    }


def train_policy_if_requested(args: argparse.Namespace, output_dir: Path) -> dict[str, Any] | None:
    if args.skip_policy_training:
        return None
    db = SessionLocal()
    try:
        model = train_workflow_policy_model(
            db,
            name=args.policy_model_name,
            artifact_dir=output_dir / "models",
        )
        db.commit()
        db.refresh(model)
        return serialize_policy_model(model)
    finally:
        db.close()


def train_neural_policy_if_requested(args: argparse.Namespace, output_dir: Path) -> dict[str, Any] | None:
    if not args.train_neural_policy:
        return None
    try:
        from app.services.neural_workflow_policy import train_neural_workflow_policy_model
    except Exception as exc:
        return {"status": "skipped", "reason": f"PyTorch neural policy unavailable: {str(exc)[:300]}"}
    db = SessionLocal()
    try:
        model = train_neural_workflow_policy_model(
            db,
            name=args.neural_policy_model_name,
            artifact_dir=output_dir / "models",
            epochs=args.neural_epochs,
            hidden_dim=args.neural_hidden_dim,
            batch_size=args.neural_batch_size,
        )
        db.commit()
        db.refresh(model)
        return serialize_policy_model(model)
    except Exception as exc:
        db.rollback()
        return {"status": "skipped", "reason": str(exc)[:500]}
    finally:
        db.close()


def serialize_policy_model(model: WorkflowPolicyModel) -> dict[str, Any]:
    return {
        "id": model.id,
        "name": model.name,
        "version": model.version,
        "model_type": model.model_type,
        "artifact_path": model.artifact_path,
        "training_summary": model.training_summary_json,
        "metrics": model.metrics_json,
        "created_at": model.created_at.isoformat(),
    }


def export_state_graph(output_dir: Path, *, limit: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        graph = build_scientific_state_graph(db, limit=limit)
        path = output_dir / "scistate_graph.json"
        path.write_text(json.dumps(graph, indent=2, default=str), encoding="utf-8")
        return {"path": str(path), "summary": graph.get("summary", {})}
    finally:
        db.close()


def package_latest_policy_if_requested(args: argparse.Namespace, output_dir: Path) -> dict[str, Any] | None:
    if args.skip_package:
        return None
    try:
        return package_model(
            SimpleNamespace(
                model_id="",
                output_dir=str(output_dir / "packages"),
                replay_limit=args.replay_limit,
                graph_limit=args.graph_limit,
            )
        )
    except SystemExit as exc:
        return {"status": "skipped", "reason": str(exc)}
    except Exception as exc:
        return {"status": "skipped", "reason": str(exc)[:500]}


def build_benchmark_summary(
    *,
    manifest: dict[str, Any],
    tasks: list[dict[str, Any]],
    results: list[dict[str, Any]],
    health: dict[str, Any],
    trained_policy: dict[str, Any] | None,
    neural_policy: dict[str, Any] | None,
    state_graph: dict[str, Any],
    package: dict[str, Any] | None,
    output_dir: Path,
    elapsed_seconds: float,
) -> dict[str, Any]:
    by_ablation: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        by_ablation.setdefault(result["ablation"], []).append(result)
    ablation_summary = {
        ablation: summarize_result_group(items)
        for ablation, items in sorted(by_ablation.items())
    }
    deltas = compare_against_full(ablation_summary)
    return {
        "schema": "autosci.benchmark_run.v0.1",
        "name": manifest.get("name"),
        "version": manifest.get("version"),
        "status": "completed",
        "created_at_unix": int(time.time()),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "output_dir": str(output_dir),
        "task_count": len(tasks),
        "result_count": len(results),
        "health": health,
        "summary_by_ablation": ablation_summary,
        "full_vs_ablation_deltas": deltas,
        "trained_policy": trained_policy,
        "neural_policy": neural_policy,
        "state_graph": state_graph,
        "package": package,
        "top_full_results": top_results(results, ablation="full"),
        "recommended_gpu_command": recommended_gpu_command(),
    }


def evaluate_realness_gates(
    summary: dict[str, Any],
    results: list[dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    required_integrations = set(args.require_full_integrations or [])
    if args.strict_real_run:
        required_integrations.update({"public_biomedical", "tooluniverse", "local_board", "sciflow_policy", "memory_replay"})
    full_results = [item for item in results if item.get("ablation") == "full"]
    full_summary = summary.get("summary_by_ablation", {}).get("full", {})
    runs = max(1, int(full_summary.get("runs") or len(full_results) or 1))
    completion_rate = float(full_summary.get("completed", 0)) / runs
    min_completion = args.min_full_completion_rate
    min_score = args.min_full_mean_score
    min_top1 = args.min_neural_holdout_top1
    min_nodes = args.min_state_graph_nodes
    if args.strict_real_run:
        min_completion = max(min_completion, 1.0)
        min_score = max(min_score, 85.0)
        min_top1 = max(min_top1, 0.5)
        min_nodes = max(min_nodes, 1)

    failures: list[str] = []
    result_failures: list[dict[str, Any]] = []
    mean_score = float(full_summary.get("mean_score") or 0.0)
    if completion_rate < min_completion:
        failures.append(f"Full-run completion rate {completion_rate:.3f} is below required {min_completion:.3f}.")
    if mean_score < min_score:
        failures.append(f"Full-run mean score {mean_score:.2f} is below required {min_score:.2f}.")

    for result in full_results:
        missing = missing_required_integrations(result, required_integrations)
        if args.require_expected_integrations:
            missing.extend(missing_expected_integrations(result))
        missing = sorted(set(missing))
        if missing:
            result_failures.append(
                {
                    "task_id": result.get("task", {}).get("id"),
                    "run_id": result.get("run_id"),
                    "missing": missing,
                    "artifact_path": result.get("artifact_path"),
                }
            )
    if result_failures:
        failures.append(f"{len(result_failures)} full result(s) are missing required integrations.")

    neural_policy = summary.get("neural_policy") or {}
    metrics = neural_policy.get("metrics") or {}
    top1 = metrics.get("top1_holdout_accuracy")
    if min_top1 > 0:
        if top1 is None:
            failures.append("Neural SciFlow Policy metrics are missing.")
        elif float(top1) < min_top1:
            failures.append(f"Neural SciFlow Policy holdout top-1 {float(top1):.4f} is below required {min_top1:.4f}.")

    state_nodes = int(summary.get("state_graph", {}).get("summary", {}).get("nodes") or 0)
    if state_nodes < min_nodes:
        failures.append(f"SciState Graph node count {state_nodes} is below required {min_nodes}.")

    package = summary.get("package") or {}
    if args.strict_real_run and package.get("status") == "skipped":
        failures.append(f"Policy package was skipped: {package.get('reason')}")

    return {
        "passed": not failures,
        "strict_real_run": bool(args.strict_real_run),
        "required_full_integrations": sorted(required_integrations),
        "require_expected_integrations": bool(args.require_expected_integrations),
        "min_full_completion_rate": min_completion,
        "observed_full_completion_rate": round(completion_rate, 4),
        "min_full_mean_score": min_score,
        "observed_full_mean_score": mean_score,
        "min_neural_holdout_top1": min_top1,
        "observed_neural_holdout_top1": top1,
        "min_state_graph_nodes": min_nodes,
        "observed_state_graph_nodes": state_nodes,
        "failures": failures,
        "result_failures": result_failures,
    }


def missing_required_integrations(result: dict[str, Any], required_integrations: set[str]) -> list[str]:
    integrations = result.get("integrations", {})
    missing = []
    for name in sorted(required_integrations):
        if name == "public_biomedical":
            if not integrations.get("public_biomedical", {}).get("executed"):
                missing.append(name)
        elif name == "tooluniverse":
            if not integrations.get("tooluniverse", {}).get("executed"):
                missing.append(name)
        elif name == "qworld":
            if not integrations.get("qworld", {}).get("executed"):
                missing.append(name)
        elif name == "local_board":
            if not integrations.get("local_board", {}).get("executed"):
                missing.append(name)
        elif name == "sciflow_policy":
            if result.get("sciflow_policy", {}).get("status") != "success" or not result.get(
                "sciflow_application", {}
            ).get("applied"):
                missing.append(name)
        elif name == "memory_replay":
            if not result.get("replay", {}).get("available"):
                missing.append(name)
        else:
            missing.append(f"unknown:{name}")
    return missing


def missing_expected_integrations(result: dict[str, Any]) -> list[str]:
    expected = set(result.get("task", {}).get("expected_capabilities") or [])
    mapped = set()
    if "public_biomedical" in expected:
        mapped.add("public_biomedical")
    if "tooluniverse" in expected:
        mapped.add("tooluniverse")
    if "qworld" in expected:
        mapped.add("qworld")
    if "sciflow_policy" in expected:
        mapped.add("sciflow_policy")
    return missing_required_integrations(result, mapped)


def summarize_result_group(results: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [item["value_assessment"]["score"] for item in results]
    completed = [item for item in results if item.get("status") == "completed"]
    impacts = [item.get("value_assessment", {}).get("controller_impact", {}) for item in results]
    return {
        "runs": len(results),
        "completed": len(completed),
        "mean_score": round(statistics.mean(scores), 2) if scores else 0,
        "min_score": min(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "mean_confidence": round(
            statistics.mean([float(item.get("final_confidence") or 0.0) for item in completed]),
            4,
        )
        if completed
        else 0.0,
        "memory_replay_runs": sum(1 for item in results if item.get("replay", {}).get("available")),
        "controller_advice_runs": sum(1 for item in results if item.get("sciflow_policy", {}).get("status") == "success"),
        "controller_applied_runs": sum(1 for impact in impacts if impact.get("applied")),
        "mean_tool_calls": round(
            statistics.mean([int(impact.get("tool_call_count") or 0) for impact in impacts]),
            2,
        )
        if impacts
        else 0.0,
        "mean_evidence_count": round(
            statistics.mean([int(impact.get("evidence_count") or 0) for impact in impacts]),
            2,
        )
        if impacts
        else 0.0,
        "mean_public_biomedical_calls": round(
            statistics.mean([int(impact.get("public_biomedical_call_count") or 0) for impact in impacts]),
            2,
        )
        if impacts
        else 0.0,
        "mean_tooluniverse_calls": round(
            statistics.mean([int(impact.get("tooluniverse_call_count") or 0) for impact in impacts]),
            2,
        )
        if impacts
        else 0.0,
        "public_tool_runs": sum(
            1
            for item in results
            if item.get("integrations", {}).get("public_biomedical", {}).get("executed")
            or item.get("integrations", {}).get("tooluniverse", {}).get("executed")
        ),
    }


def compare_against_full(summary_by_ablation: dict[str, dict[str, Any]]) -> dict[str, Any]:
    full = summary_by_ablation.get("full")
    if not full:
        return {}
    deltas = {}
    for name, item in summary_by_ablation.items():
        if name == "full":
            continue
        deltas[name] = {
            "mean_score_delta_vs_full": round(full["mean_score"] - item["mean_score"], 2),
            "controller_runs_delta_vs_full": full["controller_advice_runs"] - item["controller_advice_runs"],
            "controller_applied_runs_delta_vs_full": full["controller_applied_runs"] - item["controller_applied_runs"],
            "replay_runs_delta_vs_full": full["memory_replay_runs"] - item["memory_replay_runs"],
            "public_tool_runs_delta_vs_full": full["public_tool_runs"] - item["public_tool_runs"],
            "mean_tool_calls_delta_vs_full": round(full["mean_tool_calls"] - item["mean_tool_calls"], 2),
            "mean_evidence_count_delta_vs_full": round(
                full["mean_evidence_count"] - item["mean_evidence_count"],
                2,
            ),
            "mean_public_biomedical_calls_delta_vs_full": round(
                full["mean_public_biomedical_calls"] - item["mean_public_biomedical_calls"],
                2,
            ),
            "mean_tooluniverse_calls_delta_vs_full": round(
                full["mean_tooluniverse_calls"] - item["mean_tooluniverse_calls"],
                2,
            ),
        }
    return deltas


def top_results(results: list[dict[str, Any]], *, ablation: str) -> list[dict[str, Any]]:
    selected = [item for item in results if item.get("ablation") == ablation]
    ranked = sorted(selected, key=lambda item: item["value_assessment"]["score"], reverse=True)
    return [
        {
            "task_id": item["task"]["id"],
            "run_id": item["run_id"],
            "score": item["value_assessment"]["score"],
            "confidence": item.get("final_confidence"),
            "artifact_path": item.get("artifact_path"),
            "hypothesis_title": item.get("hypothesis", {}).get("title"),
        }
        for item in ranked[:10]
    ]


def recommended_gpu_command() -> str:
    return (
        "python tools/run_autoscientist_bench.py --limit 100 --replicates-per-case 3 "
        "--ablations full no_memory no_public_tools no_sciflow "
        "--llm-provider anthropic --llm-model claude-sonnet-4-6 --llm-api-key-env-var ANTHROPIC_API_KEY "
        "--enable-sciflow-policy --train-neural-policy --neural-epochs 120 --require-real-llm --strict-real-run "
        "--require-expected-integrations --min-full-completion-rate 1.0 --min-full-mean-score 85 "
        "--min-neural-holdout-top1 0.5 --min-state-graph-nodes 1"
    )


def redact_benchmark_config(config: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(config)
    for key, value in list(redacted.items()):
        lowered = key.lower()
        if ("key" in lowered or "token" in lowered or "secret" in lowered) and value:
            redacted[key] = str(value)
    return redacted


def render_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# AutoScientist-Bench v0.1 Run",
        "",
        f"Status: `{summary['status']}`",
        f"Tasks: `{summary['task_count']}`",
        f"Results: `{summary['result_count']}`",
        f"Elapsed seconds: `{summary['elapsed_seconds']}`",
        "",
        "## Ablation Summary",
        "",
        "| Ablation | Runs | Completed | Mean score | Replay runs | Controller advice | Controller applied | Mean evidence | Mean tool calls | Public-tool runs |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, item in summary["summary_by_ablation"].items():
        lines.append(
            f"| {name} | {item['runs']} | {item['completed']} | {item['mean_score']} | "
            f"{item['memory_replay_runs']} | {item['controller_advice_runs']} | "
            f"{item['controller_applied_runs']} | {item['mean_evidence_count']} | "
            f"{item['mean_tool_calls']} | {item['public_tool_runs']} |"
        )
    lines.extend(["", "## Full vs Ablation Deltas", "", "```json"])
    lines.append(json.dumps(summary.get("full_vs_ablation_deltas", {}), indent=2))
    lines.extend(["```", "", "## Realness Gates", ""])
    gates = summary.get("realness_gates", {})
    if gates:
        lines.append(f"- Passed: `{gates.get('passed')}`")
        lines.append(f"- Strict real run: `{gates.get('strict_real_run')}`")
        lines.append(f"- Required full integrations: `{', '.join(gates.get('required_full_integrations', [])) or 'none'}`")
        lines.append(
            "- Full completion: "
            f"`{gates.get('observed_full_completion_rate')}` / required `{gates.get('min_full_completion_rate')}`"
        )
        lines.append(
            "- Full mean score: "
            f"`{gates.get('observed_full_mean_score')}` / required `{gates.get('min_full_mean_score')}`"
        )
        if gates.get("min_neural_holdout_top1"):
            lines.append(
                "- Neural holdout top-1: "
                f"`{gates.get('observed_neural_holdout_top1')}` / required `{gates.get('min_neural_holdout_top1')}`"
            )
        if gates.get("failures"):
            lines.append("")
            lines.append("Gate failures:")
            lines.extend(f"- {failure}" for failure in gates["failures"])
        if gates.get("result_failures"):
            lines.append("")
            lines.append("Result-level failures:")
            for failure in gates["result_failures"][:20]:
                lines.append(
                    f"- `{failure.get('task_id')}` / `{failure.get('run_id')}` missing "
                    f"`{', '.join(failure.get('missing', []))}`"
                )
    else:
        lines.append("- No hard gates requested.")
    lines.extend(["", "## Policy Package", ""])
    if summary.get("trained_policy"):
        policy = summary["trained_policy"]
        lines.append(f"- Transparent policy: `{policy['artifact_path']}`")
        lines.append(f"- Examples: `{policy['training_summary'].get('num_examples')}`")
    if summary.get("neural_policy"):
        neural = summary["neural_policy"]
        if neural.get("artifact_path"):
            lines.append(f"- Neural policy: `{neural['artifact_path']}`")
        else:
            lines.append(f"- Neural policy: `{neural.get('status')}` - {neural.get('reason')}")
    if summary.get("package"):
        lines.append(f"- Package: `{summary['package'].get('zip_path') or summary['package'].get('status')}`")
    lines.extend(
        [
            "",
            "## State Graph",
            "",
            f"- Export: `{summary['state_graph']['path']}`",
            f"- Summary: `{json.dumps(summary['state_graph']['summary'], default=str)}`",
            "",
            "## Top Full Results",
            "",
            "| Task | Run | Score | Confidence | Artifact |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for item in summary.get("top_full_results", []):
        lines.append(
            f"| {item['task_id']} | `{item['run_id']}` | {item['score']} | "
            f"{item.get('confidence')} | `{item.get('artifact_path')}` |"
        )
    lines.extend(["", "## GPU Scale-Up Command", "", "```bash", summary["recommended_gpu_command"], "```"])
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AutoScientist-Bench v0.1 locally before GPU scale-up.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-dir", default="outputs/autoscientist_bench")
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--replicates-per-case", type=int, default=1)
    parser.add_argument("--case-ids", nargs="*", default=[])
    parser.add_argument("--template-ids", nargs="*", default=[])
    parser.add_argument("--ablations", nargs="*", default=["full", "no_memory", "no_public_tools"])
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--offline-public-context", action="store_true")
    parser.add_argument("--public-timeout-seconds", type=int, default=8)
    parser.add_argument("--llm-provider", default="mock")
    parser.add_argument("--llm-model", default="mock-scientist")
    parser.add_argument("--llm-api-key-env-var", default="")
    parser.add_argument("--llm-max-tokens", type=int, default=192)
    parser.add_argument("--qworld-model", default="")
    parser.add_argument("--qworld-api-key-env-var", default="")
    parser.add_argument("--disable-qworld", action="store_true")
    parser.add_argument("--agent-count", type=int, default=3)
    parser.add_argument("--max-runtime-minutes", type=int, default=5)
    parser.add_argument("--tool-budget-usd", type=float, default=1.0)
    parser.add_argument("--require-real-llm", action="store_true")
    parser.add_argument("--enable-sciflow-policy", action="store_true")
    parser.add_argument("--sciflow-policy-model-id", default="")
    parser.add_argument("--sciflow-policy-model-path", default="")
    parser.add_argument("--sciflow-policy-min-score", type=float, default=0.15)
    parser.add_argument("--skip-policy-training", action="store_true")
    parser.add_argument("--policy-model-name", default="scientific_workflow_policy")
    parser.add_argument("--train-neural-policy", action="store_true")
    parser.add_argument("--neural-policy-model-name", default="neural_scientific_workflow_policy")
    parser.add_argument("--neural-epochs", type=int, default=80)
    parser.add_argument("--neural-hidden-dim", type=int, default=128)
    parser.add_argument("--neural-batch-size", type=int, default=64)
    parser.add_argument("--skip-package", action="store_true")
    parser.add_argument("--replay-limit", type=int, default=20)
    parser.add_argument("--graph-limit", type=int, default=1000)
    parser.add_argument("--strict-real-run", action="store_true")
    parser.add_argument("--min-full-completion-rate", type=float, default=0.0)
    parser.add_argument("--min-full-mean-score", type=float, default=0.0)
    parser.add_argument("--require-full-integrations", nargs="*", default=[])
    parser.add_argument("--require-expected-integrations", action="store_true")
    parser.add_argument("--min-neural-holdout-top1", type=float, default=0.0)
    parser.add_argument("--min-state-graph-nodes", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    summary = run_benchmark(parse_args(argv or sys.argv[1:]))
    print(
        json.dumps(
            {
                "status": summary["status"],
                "task_count": summary.get("task_count"),
                "result_count": summary.get("result_count"),
                "summary_path": summary.get("summary_path"),
                "summary_markdown_path": summary.get("summary_markdown_path"),
                "recommended_gpu_command": summary.get("recommended_gpu_command"),
            },
            indent=2,
        )
    )
    return 0 if summary["status"] in {"completed", "prepared"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
