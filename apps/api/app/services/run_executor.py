from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AgentStep, BoardPost, EvidenceItem, Hypothesis, ModelTool, Objective, Run, ToolCall
from app.db.session import SessionLocal
from app.services.open_scientist_adapters import OpenScientistCapabilityRegistry
from app.services.scientific_memory import persist_scientific_memory
from app.security import validate_env_var_name
from agents.app.runtime import build_agent_runtime


DEFAULT_RUN_CONFIG: dict[str, Any] = {
    "agent_count": 6,
    "max_runtime_minutes": 30,
    "tool_budget_usd": 10.0,
    "evidence_strictness": "balanced",
    "human_review_required": True,
    "execution_mode": "inline",
    "execution_backend": "local_process",
    "agent_framework": "langgraph",
    "openclaw_enabled": False,
    "llm_provider": "mock",
    "llm_model": "mock-scientist",
    "llm_api_key_env_var": "",
    "llm_base_url": "",
    "llm_max_tokens": 1200,
    "require_real_llm": False,
    "model_tool_names": [],
    "real_data_enabled": False,
    "txagent_enabled": False,
    "persist_memory_enabled": True,
    "sciflow_policy_enabled": False,
    "sciflow_policy_model_id": "",
    "sciflow_policy_model_path": "",
    "sciflow_policy_min_score": 0.15,
    "strategy_repair_enabled": True,
    "strategy_repair_max_queries": 2,
}


def normalize_run_config(config: dict[str, Any] | None) -> dict[str, Any]:
    normalized = {**DEFAULT_RUN_CONFIG, **(config or {})}
    normalized["agent_count"] = max(1, min(int(normalized["agent_count"]), 12))
    normalized["max_runtime_minutes"] = max(5, min(int(normalized["max_runtime_minutes"]), 240))
    normalized["tool_budget_usd"] = max(0.0, min(float(normalized["tool_budget_usd"]), 500.0))
    if normalized["evidence_strictness"] not in {"exploratory", "balanced", "strict"}:
        normalized["evidence_strictness"] = "balanced"
    if normalized["execution_mode"] not in {"inline", "background", "queued"}:
        normalized["execution_mode"] = "inline"
    if normalized["execution_backend"] not in {"local_process", "docker", "cloud_run_job", "cloud_batch"}:
        normalized["execution_backend"] = "local_process"
    if normalized["agent_framework"] not in {"langgraph", "custom_state_machine", "openclaw"}:
        normalized["agent_framework"] = "langgraph"
    if normalized["llm_provider"] not in {"mock", "openai", "anthropic", "gemini", "openai_compatible", "local_http"}:
        normalized["llm_provider"] = "mock"
    normalized["llm_api_key_env_var"] = validate_env_var_name(
        normalized.get("llm_api_key_env_var"),
        "llm_api_key_env_var",
    )
    normalized["llm_base_url"] = str(normalized.get("llm_base_url") or "")
    normalized["llm_max_tokens"] = max(64, min(int(normalized.get("llm_max_tokens", 1200)), 4000))
    normalized["require_real_llm"] = bool(normalized.get("require_real_llm", False))
    if not isinstance(normalized["model_tool_names"], list):
        normalized["model_tool_names"] = []
    normalized["real_data_enabled"] = bool(normalized.get("real_data_enabled", False))
    normalized["txagent_enabled"] = bool(normalized.get("txagent_enabled", False))
    normalized["persist_memory_enabled"] = bool(normalized.get("persist_memory_enabled", True))
    normalized["sciflow_policy_enabled"] = bool(normalized.get("sciflow_policy_enabled", False))
    normalized["sciflow_policy_model_id"] = str(normalized.get("sciflow_policy_model_id") or "")
    normalized["sciflow_policy_model_path"] = str(normalized.get("sciflow_policy_model_path") or "")
    normalized["sciflow_policy_min_score"] = max(
        0.0,
        min(float(normalized.get("sciflow_policy_min_score", 0.15)), 1.0),
    )
    normalized["strategy_repair_enabled"] = bool(normalized.get("strategy_repair_enabled", True))
    normalized["strategy_repair_max_queries"] = max(
        0,
        min(int(normalized.get("strategy_repair_max_queries", 2)), 5),
    )
    return normalized


def estimate_run_cost(config: dict[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_run_config(config)
    strictness_multiplier = {
        "exploratory": 0.8,
        "balanced": 1.0,
        "strict": 1.35,
    }[normalized["evidence_strictness"]]
    platform_fee = 1.25
    agent_cost = normalized["agent_count"] * 0.35
    runtime_cost = normalized["max_runtime_minutes"] * 0.08
    tool_budget = normalized["tool_budget_usd"]
    estimated = round((platform_fee + agent_cost + runtime_cost + tool_budget) * strictness_multiplier, 2)
    return {
        "estimated_cost_usd": estimated,
        "currency": "USD",
        "line_items": [
            {"name": "platform_fee", "amount_usd": platform_fee},
            {"name": "agent_coordination", "amount_usd": round(agent_cost, 2)},
            {"name": "reserved_runtime", "amount_usd": round(runtime_cost, 2)},
            {"name": "tool_budget", "amount_usd": tool_budget},
            {"name": "strictness_multiplier", "value": strictness_multiplier},
        ],
        "config": normalized,
    }


def create_run_record(db: Session, objective: Objective, config: dict[str, Any]) -> Run:
    estimate = estimate_run_cost(config)
    normalized = estimate["config"]
    status = "queued" if normalized["execution_mode"] in {"background", "queued"} else "running"
    run = Run(
        objective_id=objective.id,
        status=status,
        run_config_json=normalized,
        agent_count=normalized["agent_count"],
        max_runtime_minutes=normalized["max_runtime_minutes"],
        estimated_cost_usd=estimate["estimated_cost_usd"],
        queued_at=datetime.utcnow() if status == "queued" else None,
        started_at=datetime.utcnow() if status == "running" else None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def execute_run_by_id(run_id: str) -> None:
    db = SessionLocal()
    try:
        run = db.get(Run, run_id)
        if run is None:
            return
        objective = db.get(Objective, run.objective_id)
        if objective is None:
            run.status = "failed"
            db.commit()
            return
        execute_run(db, run, objective)
    finally:
        db.close()


def execute_run(
    db: Session,
    run: Run,
    objective: Objective,
    progress_callback: Any | None = None,
) -> Run:
    run.status = "running"
    run.started_at = run.started_at or datetime.utcnow()
    run.run_config_json = resolve_model_tool_configs(db, run.run_config_json)
    db.commit()
    orchestrator = None
    try:
        orchestrator = build_agent_runtime(run.run_config_json)
        state, trace = orchestrator.run_demo(
            run.id,
            objective.id,
            objective.objective_text,
            run_config={**run.run_config_json, "_progress_callback": progress_callback},
        )
        persist_orchestrator_result(
            db,
            run,
            state,
            trace,
            persist_memory=bool(run.run_config_json.get("persist_memory_enabled", True)),
        )
        run.status = "completed"
        run.current_state = state.current_state.value
        run.completed_at = datetime.utcnow()
        run.final_confidence = state.report["confidence"]
    except Exception as exc:
        run.status = "failed"
        run.completed_at = datetime.utcnow()
        partial_trace = getattr(orchestrator, "_active_trace", []) if orchestrator is not None else []
        for trace_item in partial_trace:
            db.add(
                AgentStep(
                    run_id=run.id,
                    agent_name=trace_item["agent_name"],
                    state_name=trace_item["state_name"],
                    input_json=trace_item.get("input", {}),
                    output_json=trace_item.get("output", {}),
                    completed_at=datetime.utcnow(),
                )
            )
        db.add(
            AgentStep(
                run_id=run.id,
                agent_name="system",
                state_name=run.current_state,
                input_json={"run_config": run.run_config_json},
                output_json={},
                completed_at=datetime.utcnow(),
                error=str(exc),
            )
        )
    db.commit()
    db.refresh(run)
    return run


def persist_orchestrator_result(
    db: Session,
    run: Run,
    state: Any,
    trace: list[dict[str, Any]],
    *,
    persist_memory: bool = True,
) -> None:
    open_scientist = OpenScientistCapabilityRegistry()
    for trace_item in trace:
        db.add(
            AgentStep(
                run_id=run.id,
                agent_name=trace_item["agent_name"],
                state_name=trace_item["state_name"],
                input_json=trace_item["input"],
                output_json=trace_item["output"],
                completed_at=datetime.utcnow(),
            )
        )
    for output in state.tool_outputs:
        result = output["result"]
        db.add(
            ToolCall(
                run_id=run.id,
                tool_name=output["tool_name"],
                tool_source=output.get("tool_source", "custom"),
                input_json=result["input"],
                output_json=result,
                status=result["status"],
                latency_ms=result["runtime_ms"],
            )
        )
    for evidence in state.evidence:
        db.add(
            EvidenceItem(
                run_id=run.id,
                source=evidence["source"],
                evidence_text=evidence["text"],
                structured_json=evidence,
                support_label=evidence.get("score", {}).get("label"),
                support_score=evidence.get("score", {}).get("score"),
            )
        )
    hypothesis = Hypothesis(
        run_id=run.id,
        title=state.hypothesis_card["title"],
        hypothesis_text=state.hypothesis_card["hypothesis"],
        confidence=state.hypothesis_card["confidence"],
    )
    db.add(hypothesis)
    db.flush()
    hypothesis_content = {
        **state.hypothesis_card,
        "next_experiments": state.experiments,
        "critique": state.critique,
        "objective_classification": state.context.get("objective_classification", {}),
        "case_profile": state.context.get("case_profile", {}),
        "capability_plan": state.context.get("capability_plan", {}),
        "evaluation_criteria": state.context.get("evaluation_criteria", []),
        "report_evaluation": state.report.get("report_evaluation", {}),
        "claim_retrieval_plan": state.context.get("claim_retrieval_plan", {}),
        "claim_evidence_matrix": state.context.get("claim_evidence_matrix", {}),
        "evidence_coverage_matrix": state.context.get("evidence_coverage_matrix", {}),
        "experiment_gate_plan": state.context.get("experiment_gate_plan", {}),
        "quality_dashboard": state.report.get("quality_dashboard", {}),
        "critique_enforced_revision": state.context.get("critique_enforced_revision", {}),
        "critique_repair_lock": state.report.get("critique_repair_lock", {}),
        "abstention": state.context.get("abstention", {}),
        "abstention_policy": state.context.get("abstention_policy", {}),
        "actionability_profile": state.context.get("actionability_profile", {}),
        "adaptive_tool_plan": state.context.get("adaptive_tool_plan", {}),
        "biotruth_critic": state.context.get("biotruth_critic", {}),
        "contradiction_analysis": state.context.get("contradiction_analysis", {}),
        "evidence_hierarchy": state.context.get("evidence_hierarchy", {}),
        "scientific_strategy": state.context.get("scientific_strategy", {}),
        "open_scientist": state.report.get("open_scientist", {}),
        "run_config": run.run_config_json,
    }
    hypothesis_content.update(open_scientist.local_board_post_metadata("hypothesis", hypothesis_content))
    db.add(
        BoardPost(
            post_type="hypothesis",
            run_id=run.id,
            hypothesis_id=hypothesis.id,
            agent_author="publisher_agent",
            content_json=hypothesis_content,
        )
    )
    db.add(
        BoardPost(
            post_type="critique",
            run_id=run.id,
            hypothesis_id=hypothesis.id,
            agent_author="critic_agent",
            content_json=state.critique,
        )
    )
    db.flush()
    if persist_memory:
        persist_scientific_memory(db, run, state)


def resolve_model_tool_configs(db: Session, config: dict[str, Any]) -> dict[str, Any]:
    names = config.get("model_tool_names", [])
    if not names:
        return {**config, "model_tool_configs": []}
    model_tools = db.query(ModelTool).filter(ModelTool.name.in_(names)).all()
    configs = []
    for model_tool in model_tools:
        tool_config = dict(model_tool.tooluniverse_config_json)
        tool_config["name"] = model_tool.name
        tool_config["provider"] = model_tool.provider
        tool_config["endpoint_url"] = model_tool.endpoint_url
        tool_config["api_key_env_var"] = model_tool.api_key_env_var
        configs.append(tool_config)
    found = {tool["name"] for tool in configs}
    missing = sorted(set(names) - found)
    return {
        **config,
        "model_tool_configs": configs,
        "model_tool_resolution": {
            "requested": names,
            "resolved": sorted(found),
            "missing": missing,
        },
    }
