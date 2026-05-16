from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import AgentStep, BoardPost, EvidenceItem, Hypothesis, Objective, Run, ToolCall
from app.db.session import get_db
from app.services.agent_orchestrator import AgentOrchestrator

router = APIRouter(prefix="/runs", tags=["runs"])


class RunCreate(BaseModel):
    objective_id: str
    execute_demo: bool = True


@router.post("")
def create_run(payload: RunCreate, db: Session = Depends(get_db)) -> dict:
    objective = db.get(Objective, payload.objective_id)
    if objective is None:
        raise HTTPException(status_code=404, detail="Objective not found")

    run = Run(objective_id=objective.id, status="running", started_at=datetime.utcnow())
    db.add(run)
    db.commit()
    db.refresh(run)

    if payload.execute_demo:
        orchestrator = AgentOrchestrator()
        state, trace = orchestrator.run_demo(run.id, objective.id, objective.objective_text)
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
        run.status = "completed"
        run.current_state = state.current_state.value
        run.completed_at = datetime.utcnow()
        run.final_confidence = state.report["confidence"]
        db.commit()

    db.refresh(run)
    return serialize_run(run)


@router.get("/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return serialize_run(run)


@router.get("/{run_id}/trace")
def get_trace(run_id: str, db: Session = Depends(get_db)) -> dict:
    steps = db.query(AgentStep).filter(AgentStep.run_id == run_id).order_by(AgentStep.started_at.asc()).all()
    calls = db.query(ToolCall).filter(ToolCall.run_id == run_id).order_by(ToolCall.created_at.asc()).all()
    return {
        "steps": [
            {
                "id": step.id,
                "agent_name": step.agent_name,
                "state_name": step.state_name,
                "input": step.input_json,
                "output": step.output_json,
                "started_at": step.started_at.isoformat(),
                "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                "error": step.error,
            }
            for step in steps
        ],
        "tool_calls": [
            {
                "id": call.id,
                "tool_name": call.tool_name,
                "status": call.status,
                "latency_ms": call.latency_ms,
                "input": call.input_json,
                "output": call.output_json,
            }
            for call in calls
        ],
    }


def serialize_run(run: Run) -> dict:
    return {
        "id": run.id,
        "objective_id": run.objective_id,
        "status": run.status,
        "current_state": run.current_state,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "final_confidence": run.final_confidence,
    }

