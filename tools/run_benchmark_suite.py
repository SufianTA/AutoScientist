from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.db.session import SessionLocal
from app.services.scientific_memory import memory_summary, predict_next_actions, train_workflow_policy_model

from tools.run_integration_benchmark import build_artifact, write_artifact


BENCHMARK_CASES = [
    {
        "id": "ra_cd4_target_prioritization",
        "title": "RA CD4 T-cell target prioritization",
        "objective": (
            "Prioritize therapeutic target hypotheses for rheumatoid arthritis in CD4+ T cells "
            "using single-cell transcriptomics reasoning, public biomedical evidence, safety "
            "concerns, and next experiment proposals."
        ),
        "expected_capabilities": ["medea", "tooluniverse", "public_biomedical", "qworld"],
    },
    {
        "id": "pcsk9_fh_drug_repurposing",
        "title": "PCSK9 familial hypercholesterolemia intervention reasoning",
        "objective": (
            "Evaluate PCSK9-centered therapeutic hypotheses for familial hypercholesterolemia, "
            "including drug repurposing evidence, mechanism, contraindication risks, and validation experiments."
        ),
        "expected_capabilities": ["tooluniverse", "public_biomedical", "qworld"],
    },
    {
        "id": "acvr1_fop_failed_hypothesis",
        "title": "ACVR1/FOP failed-hypothesis rejection",
        "objective": (
            "Generate and critique therapeutic hypotheses for ACVR1-driven fibrodysplasia ossificans "
            "progressiva, explicitly identifying weak or failed hypothesis branches and safer next experiments."
        ),
        "expected_capabilities": ["tooluniverse", "public_biomedical", "qworld"],
    },
    {
        "id": "cftr_cystic_fibrosis_evidence",
        "title": "CFTR cystic fibrosis evidence synthesis",
        "objective": (
            "Synthesize CFTR therapeutic hypothesis evidence for cystic fibrosis, rank evidence quality, "
            "and propose experiments that would reduce uncertainty."
        ),
        "expected_capabilities": ["tooluniverse", "public_biomedical", "qworld"],
    },
    {
        "id": "tnf_ibd_safety",
        "title": "TNF inflammatory bowel disease safety validation",
        "objective": (
            "Assess TNF-pathway intervention hypotheses for inflammatory bowel disease with attention to "
            "mechanistic support, safety limitations, literature provenance, and validation strategy."
        ),
        "expected_capabilities": ["tooluniverse", "public_biomedical", "qworld"],
    },
]


def suite_args(base: argparse.Namespace, case: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        objective=case["objective"],
        output_dir=base.output_dir,
        llm_provider=base.llm_provider,
        llm_model=base.llm_model,
        llm_api_key_env_var=base.llm_api_key_env_var,
        llm_max_tokens=base.llm_max_tokens,
        qworld_model=base.qworld_model,
        qworld_api_key_env_var=base.qworld_api_key_env_var,
        disable_qworld=base.disable_qworld,
        agent_count=base.agent_count,
        max_runtime_minutes=base.max_runtime_minutes,
        tool_budget_usd=base.tool_budget_usd,
        require_real_llm=base.require_real_llm,
        medea_python=base.medea_python,
        disable_medea=base.disable_medea,
        medea_smoke_only=base.medea_smoke_only,
        medea_debate_rounds=base.medea_debate_rounds,
        medea_timeout_seconds=base.medea_timeout_seconds,
        medea_subprocess_timeout_seconds=base.medea_subprocess_timeout_seconds,
        skip_policy_training=True,
        policy_model_name=base.policy_model_name,
        policy_artifact_dir=base.policy_artifact_dir,
    )


def run_suite(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_cases = select_cases(args.case_ids)
    case_artifacts = []
    for case in selected_cases:
        artifact = build_artifact(suite_args(args, case))
        artifact["benchmark_case"] = case
        artifact_path = write_artifact(artifact, output_dir)
        artifact["artifact_path"] = str(artifact_path)
        case_artifacts.append(artifact)

    db = SessionLocal()
    try:
        policy = train_workflow_policy_model(
            db,
            name=args.policy_model_name,
            artifact_dir=args.policy_artifact_dir,
        )
        db.commit()
        db.refresh(policy)
        memory = memory_summary(db)
        predictions = predict_next_actions(
            {
                "objective": "prioritize therapeutic target hypotheses using public biomedical evidence",
                "state_name": "TOOL_SELECTION",
            },
            model_path=policy.artifact_path,
            top_k=5,
        )
    finally:
        db.close()

    summary = build_suite_summary(
        case_artifacts,
        policy={
            "id": policy.id,
            "name": policy.name,
            "version": policy.version,
            "artifact_path": policy.artifact_path,
            "training_summary": policy.training_summary_json,
            "metrics": policy.metrics_json,
        },
        memory=memory,
        predictions=predictions,
        elapsed_seconds=time.time() - started,
    )
    suite_path = output_dir / f"benchmark_suite_{int(started)}.json"
    suite_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    markdown_path = output_dir / f"benchmark_suite_{int(started)}.md"
    markdown_path.write_text(render_suite_markdown(summary), encoding="utf-8")
    summary["suite_artifact_path"] = str(suite_path)
    summary["suite_markdown_path"] = str(markdown_path)
    suite_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


def select_cases(case_ids: list[str] | None) -> list[dict[str, Any]]:
    if not case_ids:
        return BENCHMARK_CASES
    wanted = set(case_ids)
    cases = [case for case in BENCHMARK_CASES if case["id"] in wanted]
    missing = sorted(wanted - {case["id"] for case in cases})
    if missing:
        raise SystemExit(f"Unknown benchmark case ids: {', '.join(missing)}")
    return cases


def build_suite_summary(
    artifacts: list[dict[str, Any]],
    *,
    policy: dict[str, Any],
    memory: dict[str, Any],
    predictions: list[dict[str, Any]],
    elapsed_seconds: float,
) -> dict[str, Any]:
    scores = [item["value_assessment"]["score"] for item in artifacts]
    completed = [item for item in artifacts if item.get("status") == "completed"]
    integrations = aggregate_integrations(artifacts)
    return {
        "schema": "autosci.benchmark_suite.v1",
        "created_at_unix": int(time.time()),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "case_count": len(artifacts),
        "completed_count": len(completed),
        "score": {
            "mean": round(statistics.mean(scores), 2) if scores else 0,
            "min": min(scores) if scores else 0,
            "max": max(scores) if scores else 0,
        },
        "integration_coverage": integrations,
        "cases": [
            {
                "id": item["benchmark_case"]["id"],
                "title": item["benchmark_case"]["title"],
                "run_id": item["run_id"],
                "status": item["status"],
                "score": item["value_assessment"]["score"],
                "final_confidence": item["final_confidence"],
                "artifact_path": item["artifact_path"],
                "policy_model": item.get("policy_model"),
                "integrations": item["integrations"],
                "trace_summary": item["trace_summary"],
                "hypothesis_title": item.get("hypothesis", {}).get("title"),
                "evidence_count": item.get("evidence_count"),
            }
            for item in artifacts
        ],
        "policy_model": policy,
        "policy_predictions": predictions,
        "memory_summary": memory,
        "shareable_artifacts": {
            "case_artifacts": [item["artifact_path"] for item in artifacts],
            "policy_model": policy["artifact_path"],
        },
    }


def aggregate_integrations(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ["anthropic_llm", "qworld", "medea", "tooluniverse", "public_biomedical", "local_board"]
    coverage = {}
    for key in keys:
        executed = 0
        healthy = 0
        for artifact in artifacts:
            item = artifact.get("integrations", {}).get(key, {})
            executed += 1 if item.get("executed") else 0
            healthy += 1 if item.get("healthy") or item.get("configured") else 0
        coverage[key] = {
            "executed_cases": executed,
            "healthy_or_configured_cases": healthy,
            "coverage": round(executed / len(artifacts), 3) if artifacts else 0,
        }
    return coverage


def render_suite_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# AutoScientist Scientific Workflow Benchmark Suite",
        "",
        f"Cases: `{summary['case_count']}`",
        f"Completed: `{summary['completed_count']}`",
        f"Mean score: `{summary['score']['mean']}`",
        f"Score range: `{summary['score']['min']} - {summary['score']['max']}`",
        f"Elapsed seconds: `{summary['elapsed_seconds']}`",
        "",
        "## Integration Coverage",
        "",
        "| Integration | Executed cases | Coverage |",
        "| --- | ---: | ---: |",
    ]
    for name, item in summary["integration_coverage"].items():
        lines.append(f"| {name} | {item['executed_cases']} | {item['coverage']} |")
    lines.extend(["", "## Cases", "", "| Case | Run | Score | Evidence | Hypothesis |", "| --- | --- | ---: | ---: | --- |"])
    for case in summary["cases"]:
        title = str(case.get("hypothesis_title") or "").replace("|", "\\|")
        lines.append(
            f"| {case['title']} | `{case['run_id']}` | {case['score']} | "
            f"{case['evidence_count']} | {title} |"
        )
    model = summary["policy_model"]
    lines.extend(
        [
            "",
            "## Workflow Policy Model",
            "",
            f"- Model id: `{model['id']}`",
            f"- Version: `{model['version']}`",
            f"- Artifact: `{model['artifact_path']}`",
            f"- Examples: `{model['training_summary'].get('num_examples')}`",
            f"- Top-1 training accuracy: `{model['metrics'].get('top1_training_accuracy')}`",
            "",
            "## Next-Action Predictions",
            "",
        ]
    )
    for prediction in summary["policy_predictions"]:
        lines.append(
            f"- `{prediction['action']}` score `{prediction['score']}`, "
            f"reward `{prediction['mean_reward']}`, support `{prediction['support']}`"
        )
    lines.extend(["", "## Memory Summary", "", "```json", json.dumps(summary["memory_summary"], indent=2), "```"])
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a multi-case AutoScientist benchmark suite.")
    parser.add_argument("--case-ids", nargs="*", default=None)
    parser.add_argument("--output-dir", default="outputs/benchmarks")
    parser.add_argument("--llm-provider", default="auto")
    parser.add_argument("--llm-model", default="")
    parser.add_argument("--llm-api-key-env-var", default="")
    parser.add_argument("--llm-max-tokens", type=int, default=192)
    parser.add_argument("--qworld-model", default="")
    parser.add_argument("--qworld-api-key-env-var", default="")
    parser.add_argument("--disable-qworld", action="store_true")
    parser.add_argument("--agent-count", type=int, default=2)
    parser.add_argument("--max-runtime-minutes", type=int, default=5)
    parser.add_argument("--tool-budget-usd", type=float, default=1.0)
    parser.add_argument("--require-real-llm", action="store_true")
    parser.add_argument("--medea-python", default="")
    parser.add_argument("--disable-medea", action="store_true")
    parser.add_argument("--medea-smoke-only", action="store_true")
    parser.add_argument("--medea-debate-rounds", type=int, default=0)
    parser.add_argument("--medea-timeout-seconds", type=int, default=1200)
    parser.add_argument("--medea-subprocess-timeout-seconds", type=int, default=180)
    parser.add_argument("--policy-model-name", default="scientific_workflow_policy")
    parser.add_argument("--policy-artifact-dir", default="outputs/models")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    summary = run_suite(parse_args(argv or sys.argv[1:]))
    print(json.dumps({
        "suite_artifact": summary["suite_artifact_path"],
        "suite_markdown": summary["suite_markdown_path"],
        "case_count": summary["case_count"],
        "completed_count": summary["completed_count"],
        "mean_score": summary["score"]["mean"],
        "policy_model": summary["policy_model"],
    }, indent=2))
    return 0 if summary["completed_count"] == summary["case_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
