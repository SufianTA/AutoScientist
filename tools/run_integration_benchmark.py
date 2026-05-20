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
    if provider == "auto":
        if os.getenv("ANTHROPIC_API_KEY"):
            provider = "anthropic"
            api_key_env_var = "ANTHROPIC_API_KEY"
            model = model or "claude-sonnet-4-6"
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
            api_key_env_var = "OPENAI_API_KEY"
            model = model or "gpt-4.1"
        elif os.getenv("GEMINI_API_KEY"):
            provider = "gemini"
            api_key_env_var = "GEMINI_API_KEY"
            model = model or "gemini-2.5-flash"
    else:
        provider = "mock"
        model = model or "mock-scientist"
    medea_python = args.medea_python or os.getenv("MEDEA_PYTHON")
    return {
        "execution_mode": "inline",
        "agent_count": args.agent_count,
        "max_runtime_minutes": args.max_runtime_minutes,
        "tool_budget_usd": args.tool_budget_usd,
        "evidence_strictness": "strict",
        "real_data_enabled": True,
        "qworld_enabled": not args.disable_qworld,
        "qworld_model": args.qworld_model or model or "",
        "qworld_api_key_env_var": args.qworld_api_key_env_var or api_key_env_var or "",
        "llm_provider": provider,
        "llm_model": model or "",
        "llm_api_key_env_var": api_key_env_var or "",
        "llm_max_tokens": args.llm_max_tokens,
        "require_real_llm": args.require_real_llm,
        "medea_enabled": bool(medea_python) and not args.disable_medea,
        "medea_python": medea_python or "",
        "medea_smoke_only": args.medea_smoke_only,
        "medea_debate_rounds": args.medea_debate_rounds,
        "medea_timeout_seconds": args.medea_timeout_seconds,
        "medea_subprocess_timeout_seconds": args.medea_subprocess_timeout_seconds,
        "txagent_enabled": False,
    }


def summarize_integrations(result: dict[str, Any], health: dict[str, Any]) -> dict[str, Any]:
    tool_calls = result.get("provenance", {}).get("tool_calls", [])
    steps = result.get("provenance", {}).get("agent_steps", [])
    names = {call.get("tool_name") for call in tool_calls}
    sources = {call.get("tool_source") for call in tool_calls}
    qworld_step = next(
        (
            step
            for step in steps
            if step.get("state_name") == "PLAN_RESEARCH"
            and "qworld" in json.dumps(step.get("output", {}), default=str).lower()
        ),
        None,
    )
    qworld_mode = (qworld_step or {}).get("output", {}).get("qworld", {}).get("mode")
    return {
        "anthropic_llm": {
            "configured": bool(os.getenv("ANTHROPIC_API_KEY")),
            "executed": any(step.get("state_name") == "LLM_CALL_COMPLETED" for step in steps),
        },
        "qworld": {
            "healthy": bool(health.get("open_scientist", {}).get("qworld", {}).get("available")),
            "executed": qworld_step is not None and qworld_mode == "qworld",
            "mode": qworld_mode,
        },
        "medea": {
            "healthy": bool(health.get("open_scientist", {}).get("medea", {}).get("available")),
            "executed": "medea_agent" in names,
            "status": next(
                (call.get("status") for call in tool_calls if call.get("tool_name") == "medea_agent"),
                None,
            ),
        },
        "tooluniverse": {
            "healthy": bool(health.get("tooluniverse", {}).get("available")),
            "executed": "tooluniverse" in sources,
            "call_count": sum(1 for call in tool_calls if call.get("tool_source") == "tooluniverse"),
        },
        "public_biomedical": {
            "executed": "live_public_biomedical" in sources,
            "call_count": sum(1 for call in tool_calls if call.get("tool_source") == "live_public_biomedical"),
        },
        "local_board": {
            "healthy": bool(
                health.get("open_scientist", {}).get("clawinstitute_board", {}).get("available")
            ),
            "executed": bool(result.get("report", {}).get("board_posts")),
        },
    }


def value_score(result: dict[str, Any], integrations: dict[str, Any]) -> dict[str, Any]:
    report = result.get("report", {})
    evidence = report.get("evidence", [])
    hypothesis = report.get("hypothesis", {})
    experiments = report.get("experiments", [])
    guardrails = report.get("guardrails", [])
    trace = result.get("provenance", {})
    checks = {
        "completed_run": result.get("status") == "completed",
        "nonempty_hypothesis": bool(hypothesis.get("title") and hypothesis.get("text")),
        "evidence_collected": len(evidence) >= 2,
        "scored_evidence": any(item.get("support_score") is not None for item in evidence),
        "experiments_proposed": len(experiments) >= 1,
        "guardrails_present": len(guardrails) >= 1,
        "auditable_trace": bool(trace.get("agent_steps") and trace.get("tool_calls")),
        "medea_executed": bool(integrations.get("medea", {}).get("executed")),
        "qworld_executed": bool(integrations.get("qworld", {}).get("executed")),
        "live_data_executed": bool(
            integrations.get("public_biomedical", {}).get("executed")
            or integrations.get("tooluniverse", {}).get("executed")
        ),
        "board_written": bool(integrations.get("local_board", {}).get("executed")),
    }
    weights = {
        "completed_run": 15,
        "nonempty_hypothesis": 10,
        "evidence_collected": 10,
        "scored_evidence": 10,
        "experiments_proposed": 10,
        "guardrails_present": 10,
        "auditable_trace": 10,
        "medea_executed": 8,
        "qworld_executed": 7,
        "live_data_executed": 7,
        "board_written": 3,
    }
    score = sum(weights[name] for name, passed in checks.items() if passed)
    return {
        "score": score,
        "max_score": sum(weights.values()),
        "checks": checks,
        "interpretation": interpret_score(score),
    }


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
        "experiments": result.get("report", {}).get("experiments", []),
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
    parser.add_argument("--qworld-model", default="")
    parser.add_argument("--qworld-api-key-env-var", default="")
    parser.add_argument("--disable-qworld", action="store_true")
    parser.add_argument("--agent-count", type=int, default=6)
    parser.add_argument("--max-runtime-minutes", type=int, default=30)
    parser.add_argument("--tool-budget-usd", type=float, default=10.0)
    parser.add_argument("--require-real-llm", action="store_true")
    parser.add_argument("--medea-python", default="")
    parser.add_argument("--disable-medea", action="store_true")
    parser.add_argument("--medea-smoke-only", action="store_true")
    parser.add_argument("--medea-debate-rounds", type=int, default=0)
    parser.add_argument("--medea-timeout-seconds", type=int, default=1200)
    parser.add_argument("--medea-subprocess-timeout-seconds", type=int, default=180)
    parser.add_argument("--skip-policy-training", action="store_true")
    parser.add_argument("--policy-model-name", default="scientific_workflow_policy")
    parser.add_argument("--policy-artifact-dir", default="outputs/models")
    return parser.parse_args(argv)


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
