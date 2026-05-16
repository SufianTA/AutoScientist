from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AgentStep, BoardPost, EvidenceItem, Hypothesis, Objective, Run, ToolCall
from app.db.session import SessionLocal
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.billing_service import settle_run_payment


DEFAULT_RUN_CONFIG: dict[str, Any] = {
    "agent_count": 6,
    "max_runtime_minutes": 30,
    "tool_budget_usd": 10.0,
    "evidence_strictness": "balanced",
    "human_review_required": True,
    "execution_mode": "inline",
    "payment_mode": "internal_credits",
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


def execute_run(db: Session, run: Run, objective: Objective) -> Run:
    run.status = "running"
    run.started_at = run.started_at or datetime.utcnow()
    db.commit()
    try:
        orchestrator = AgentOrchestrator()
        state, trace = orchestrator.run_demo(
            run.id,
            objective.id,
            objective.objective_text,
            run_config=run.run_config_json,
        )
        persist_orchestrator_result(db, run, state, trace)
        run.status = "completed"
        run.current_state = state.current_state.value
        run.completed_at = datetime.utcnow()
        run.final_confidence = state.report["confidence"]
    except Exception as exc:
        run.status = "failed"
        run.completed_at = datetime.utcnow()
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
    settle_run_payment(db, run, run.status)
    db.commit()
    db.refresh(run)
    return run


def persist_orchestrator_result(db: Session, run: Run, state: Any, trace: list[dict[str, Any]]) -> None:
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
                tool_source="custom",
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
    db.add(
        BoardPost(
            post_type="hypothesis",
            run_id=run.id,
            hypothesis_id=hypothesis.id,
            agent_author="publisher_agent",
            content_json={
                **state.hypothesis_card,
                "next_experiments": state.experiments,
                "critique": state.critique,
                "run_config": run.run_config_json,
            },
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
