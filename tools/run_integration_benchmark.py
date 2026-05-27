from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from app.env import load_environment
from app.db.session import SessionLocal
from app.services.local_runner import run_question
from app.services.open_scientist_adapters import OpenScientistCapabilityRegistry
from app.services.scientific_memory import train_workflow_policy_model
from app.services.tooluniverse_adapter import ToolUniverseAdapter


DEFAULT_OBJECTIVE = (
    "Use AutoScientist to prioritize therapeutic target hypotheses for rheumatoid "
    "arthritis in CD4+ T cells using single-cell transcriptomics, public biomedical "
    "evidence, mechanistic plausibility, safety concerns, and experiment proposals."
)


def build_run_config(args: argparse.Namespace) -> dict[str, Any]:
    provider = args.llm_provider
    api_key_env_var = args.llm_api_key_env_var
    model = args.llm_model
    default_models = {
        "mock": "mock-scientist",
        "openai": "gpt-4.1",
        "anthropic": "claude-sonnet-4-6",
        "gemini": "gemini-3-flash-preview",
        "openai_compatible": "local-model",
        "local_http": "local-http-model",
    }
    default_key_envs = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openai_compatible": "OPENAI_COMPATIBLE_API_KEY",
    }
    if provider == "auto":
        if os.getenv("ANTHROPIC_KEY") or os.getenv("ANTHROPIC_API_KEY"):
            provider = "anthropic"
            api_key_env_var = api_key_env_var or ("ANTHROPIC_KEY" if os.getenv("ANTHROPIC_KEY") else "ANTHROPIC_API_KEY")
            model = model or default_models[provider]
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
            api_key_env_var = api_key_env_var or "OPENAI_API_KEY"
            model = model or default_models[provider]
        elif os.getenv("GEMINI_API_KEY"):
            provider = "gemini"
            api_key_env_var = api_key_env_var or "GEMINI_API_KEY"
            model = model or default_models[provider]
        else:
            provider = "mock"
            model = model or default_models[provider]
    else:
        provider = provider or "mock"
        model = model or default_models.get(provider, "")
        api_key_env_var = api_key_env_var or default_key_envs.get(provider, "")
    return {
        "execution_mode": "inline",
        "agent_count": args.agent_count,
        "max_runtime_minutes": args.max_runtime_minutes,
        "tool_budget_usd": args.tool_budget_usd,
        "evidence_strictness": "strict",
        "real_data_enabled": True,
        "llm_provider": provider,
        "llm_model": model or "",
        "llm_api_key_env_var": api_key_env_var or "",
        "llm_max_tokens": args.llm_max_tokens,
        "require_real_llm": args.require_real_llm,
        "txagent_enabled": False,
        "persist_memory_enabled": getattr(args, "persist_memory_enabled", True),
        "sciflow_policy_enabled": getattr(args, "sciflow_policy_enabled", False),
        "sciflow_policy_model_id": getattr(args, "sciflow_policy_model_id", "") or "",
        "sciflow_policy_model_path": getattr(args, "sciflow_policy_model_path", "") or "",
        "sciflow_policy_min_score": getattr(args, "sciflow_policy_min_score", 0.15),
        "strategy_repair_enabled": getattr(args, "strategy_repair_enabled", True),
        "strategy_repair_max_queries": getattr(args, "strategy_repair_max_queries", 2),
    }


def result_tool_calls(result: dict[str, Any]) -> list[dict[str, Any]]:
    calls = result.get("provenance", {}).get("tool_calls") or result.get("tool_calls") or []
    return calls if isinstance(calls, list) else []


def result_agent_steps(result: dict[str, Any]) -> list[dict[str, Any]]:
    steps = result.get("provenance", {}).get("agent_steps") or result.get("agent_steps") or []
    return steps if isinstance(steps, list) else []


def summarize_integrations(result: dict[str, Any], health: dict[str, Any]) -> dict[str, Any]:
    tool_calls = result_tool_calls(result)
    steps = result_agent_steps(result)
    names = {call.get("tool_name") for call in tool_calls}
    sources = {call.get("tool_source") for call in tool_calls}
    public_calls = [call for call in tool_calls if call.get("tool_source") == "live_public_biomedical"]
    tooluniverse_calls = [call for call in tool_calls if call.get("tool_source") == "tooluniverse"]
    return {
        "anthropic_llm": {
            "configured": bool(os.getenv("ANTHROPIC_KEY") or os.getenv("ANTHROPIC_API_KEY")),
            "executed": any(step.get("state_name") == "LLM_CALL_COMPLETED" for step in steps),
        },
        "tooluniverse": {
            "healthy": bool(health.get("tooluniverse", {}).get("available")),
            "executed": "tooluniverse" in sources,
            "call_count": len(tooluniverse_calls),
            "success_count": sum(1 for call in tooluniverse_calls if call.get("status") in {"success", "partial"}),
            "failure_count": sum(1 for call in tooluniverse_calls if call.get("status") == "failure"),
        },
        "public_biomedical": {
            "executed": "live_public_biomedical" in sources,
            "call_count": len(public_calls),
            "success_count": sum(1 for call in public_calls if call.get("status") in {"success", "partial"}),
            "failure_count": sum(1 for call in public_calls if call.get("status") == "failure"),
        },
        "local_board": {
            "healthy": bool(
                health.get("open_scientist", {}).get("clawinstitute_board", {}).get("available")
            ),
            "executed": bool(result.get("report", {}).get("board_posts")),
        },
    }


def report_experiments(
    report: dict[str, Any],
    full_result: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    direct = report.get("experiments") or report.get("next_experiments")
    if isinstance(direct, list) and direct:
        return direct
    for post in report.get("board_posts", []):
        if post.get("post_type") != "hypothesis":
            continue
        content = post.get("content", {})
        experiments = content.get("next_experiments")
        if isinstance(experiments, list) and experiments:
            return experiments
    # Provenance fallback: scan agent step outputs for the PROPOSE_EXPERIMENTS step
    if full_result:
        for step in full_result.get("provenance", {}).get("agent_steps", []):
            if "PROPOSE_EXPERIMENTS" in str(step.get("state_name", "")).upper():
                exps = step.get("output", {}).get("experiments")
                if isinstance(exps, list) and exps:
                    return exps
    return []


def clean_tool_inputs(result: dict[str, Any]) -> bool:
    for call in result_tool_calls(result):
        tool_name = str(call.get("tool_name") or "")
        if "pubmed" not in tool_name.lower():
            continue
        payload = call.get("input") or call.get("args") or call.get("parameters") or {}
        query = payload.get("query") if isinstance(payload, dict) else ""
        if not query:
            continue
        if not isinstance(query, str):
            return False
        stripped = query.strip()
        if not stripped:
            return False
        lowered = stripped.lower()
        if stripped.startswith("{") or stripped.startswith("["):
            return False
        if any(key in lowered for key in ('"primary_genes"', '"diseases"', '"pubmed_queries"')):
            return False
    return True


def value_score(result: dict[str, Any], integrations: dict[str, Any]) -> dict[str, Any]:
    report = result.get("report", {})
    evidence = report.get("evidence", [])
    hypothesis = report.get("hypothesis", {})
    experiments = report_experiments(report, result)
    guardrails = report.get("guardrails", [])
    steps = result_agent_steps(result)
    tool_calls = result_tool_calls(result)
    checks = {
        "completed_run": result.get("status") == "completed",
        "nonempty_hypothesis": bool(hypothesis.get("title") and hypothesis.get("text")),
        "evidence_collected": len(evidence) >= 2,
        "scored_evidence": any(item.get("support_score") is not None for item in evidence),
        "experiments_proposed": len(experiments) >= 1,
        "guardrails_present": len(guardrails) >= 1,
        "auditable_trace": bool(steps and tool_calls),
        "live_data_executed": bool(
            integration_has_success(integrations, "public_biomedical")
            or integration_has_success(integrations, "tooluniverse")
        ),
        "clean_tool_inputs": clean_tool_inputs(result),
        "board_written": bool(integrations.get("local_board", {}).get("executed")),
    }
    weights = {
        "completed_run": 12,
        "nonempty_hypothesis": 8,
        "evidence_collected": 12,
        "scored_evidence": 8,
        "experiments_proposed": 12,
        "guardrails_present": 8,
        "auditable_trace": 12,
        "live_data_executed": 12,
        "clean_tool_inputs": 10,
        "board_written": 6,
    }
    score = sum(weights[name] for name, passed in checks.items() if passed)
    return {
        "score": score,
        "max_score": sum(weights.values()),
        "checks": checks,
        "interpretation": interpret_score(score),
    }


def integration_has_success(integrations: dict[str, Any], name: str) -> bool:
    info = integrations.get(name, {}) if isinstance(integrations, dict) else {}
    if not info.get("executed"):
        return False
    if "success_count" not in info:
        return True
    return int(info.get("success_count") or 0) > 0


def interpret_score(score: int) -> str:
    if score >= 85:
        return "strong: integrated workflow adds clear provenance and evidence value"
    if score >= 65:
        return "promising: useful workflow, but some integrations or evidence depth need work"
    if score >= 45:
        return "partial: framework runs, but value is mostly orchestration rather than discovery"
    return "weak: not enough integrations or evidence quality to justify the version yet"


def build_artifact(args: argparse.Namespace) -> dict[str, Any]:
    load_environment()
    config = build_run_config(args)
    registry = OpenScientistCapabilityRegistry()
    health = {
        "tooluniverse": ToolUniverseAdapter().tooluniverse_health(),
        "open_scientist": registry.health(),
    }
    result = run_question(args.objective, config)
    policy_model = None
    if not args.skip_policy_training:
        db = SessionLocal()
        try:
            policy_model = train_workflow_policy_model(
                db,
                name=args.policy_model_name,
                artifact_dir=args.policy_artifact_dir,
            )
            db.commit()
            db.refresh(policy_model)
        finally:
            db.close()
    integrations = summarize_integrations(result, health)
    score = value_score(result, integrations)
    return {
        "created_at_unix": int(time.time()),
        "objective": args.objective,
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "final_confidence": result.get("final_confidence"),
        "run_config": redact_config(config),
        "health": health,
        "integrations": integrations,
        "value_assessment": score,
        "policy_model": {
            "id": policy_model.id,
            "name": policy_model.name,
            "version": policy_model.version,
            "artifact_path": policy_model.artifact_path,
            "training_summary": policy_model.training_summary_json,
            "metrics": policy_model.metrics_json,
        }
        if policy_model
        else None,
        "trace_summary": result.get("trace_summary"),
        "hypothesis": result.get("report", {}).get("hypothesis", {}),
        "evidence_count": len(result.get("report", {}).get("evidence", [])),
        "guardrails": result.get("report", {}).get("guardrails", []),
        "experiments": report_experiments(result.get("report", {}), result),
        "tool_calls": result.get("provenance", {}).get("tool_calls", []),
    }


def redact_config(config: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(config)
    for key in list(redacted):
        if "key" in key.lower() and redacted[key]:
            redacted[key] = str(redacted[key])
    return redacted


def write_artifact(artifact: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = artifact.get("run_id") or int(time.time())
    path = output_dir / f"integration_benchmark_{run_id}.json"
    path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    return path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a live AutoScientist integration benchmark.")
    parser.add_argument("--objective", default=DEFAULT_OBJECTIVE)
    parser.add_argument("--output-dir", default="outputs/benchmarks")
    parser.add_argument("--llm-provider", default="auto")
    parser.add_argument("--llm-model", default="")
    parser.add_argument("--llm-api-key-env-var", default="")
    parser.add_argument("--llm-max-tokens", type=int, default=256)
    parser.add_argument("--agent-count", type=int, default=6)
    parser.add_argument("--max-runtime-minutes", type=int, default=30)
    parser.add_argument("--tool-budget-usd", type=float, default=10.0)
    parser.add_argument("--require-real-llm", action="store_true")
    parser.add_argument("--skip-policy-training", action="store_true")
    parser.add_argument("--policy-model-name", default="scientific_workflow_policy")
    parser.add_argument("--policy-artifact-dir", default="outputs/models")
    parser.add_argument("--disable-memory", action="store_true")
    parser.add_argument("--enable-sciflow-policy", action="store_true")
    parser.add_argument("--sciflow-policy-model-id", default="")
    parser.add_argument("--sciflow-policy-model-path", default="")
    parser.add_argument("--sciflow-policy-min-score", type=float, default=0.15)
    parser.add_argument("--disable-strategy-repair", action="store_true")
    parser.add_argument("--strategy-repair-max-queries", type=int, default=2)
    parser.set_defaults(persist_memory_enabled=True, sciflow_policy_enabled=False, strategy_repair_enabled=True)
    args = parser.parse_args(argv)
    args.persist_memory_enabled = not args.disable_memory
    args.sciflow_policy_enabled = bool(args.enable_sciflow_policy)
    args.strategy_repair_enabled = not args.disable_strategy_repair
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    artifact = build_artifact(args)
    path = write_artifact(artifact, Path(args.output_dir))
    print(json.dumps({
        "artifact": str(path),
        "run_id": artifact["run_id"],
        "status": artifact["status"],
        "score": artifact["value_assessment"]["score"],
        "interpretation": artifact["value_assessment"]["interpretation"],
        "integrations": artifact["integrations"],
        "policy_model": artifact["policy_model"],
    }, indent=2))
    return 0 if artifact["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
