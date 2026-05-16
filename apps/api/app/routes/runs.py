from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import AgentStep, Objective, Run, ToolCall
from app.db.session import get_db
from app.services.billing_service import (
    DEMO_ACCOUNT_EMAIL,
    InsufficientCreditsError,
    get_or_create_account,
    reserve_credits,
)
from app.services.run_executor import (
    create_run_record,
    estimate_run_cost,
    execute_run,
    execute_run_by_id,
    normalize_run_config,
)

router = APIRouter(prefix="/runs", tags=["runs"])


class RunCreate(BaseModel):
    objective_id: str
    execute_demo: bool = True
    run_config: dict[str, Any] = Field(default_factory=dict)
    owner_email: str = DEMO_ACCOUNT_EMAIL


class RunEstimateRequest(BaseModel):
    run_config: dict[str, Any] = Field(default_factory=dict)


class RunExecuteRequest(BaseModel):
    force: bool = False


@router.post("/estimate")
def estimate_run(payload: RunEstimateRequest) -> dict:
    return estimate_run_cost(payload.run_config)


@router.post("")
def create_run(
    payload: RunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    objective = db.get(Objective, payload.objective_id)
    if objective is None:
        raise HTTPException(status_code=404, detail="Objective not found")

    config = normalize_run_config(payload.run_config)
    run = create_run_record(db, objective, config)
    account = get_or_create_account(db, owner_email=payload.owner_email)
    try:
        reserve_credits(db, account, run)
        db.commit()
    except InsufficientCreditsError as exc:
        run.status = "payment_required"
        run.payment_status = "insufficient_credits"
        db.commit()
        raise HTTPException(status_code=402, detail=str(exc)) from exc

    if payload.execute_demo and config["execution_mode"] == "inline":
        run = execute_run(db, run, objective)
    elif payload.execute_demo and config["execution_mode"] == "background":
        background_tasks.add_task(execute_run_by_id, run.id)

    db.refresh(run)
    return serialize_run(run)


@router.get("")
def list_runs(db: Session = Depends(get_db)) -> dict:
    runs = db.query(Run).order_by(Run.queued_at.desc().nullslast(), Run.started_at.desc().nullslast()).all()
    return {"runs": [serialize_run(run) for run in runs]}


@router.get("/queue")
def get_queue(db: Session = Depends(get_db)) -> dict:
    runs = db.query(Run).filter(Run.status.in_(["queued", "running"])).order_by(Run.queued_at.asc()).all()
    return {"runs": [serialize_run(run) for run in runs]}


@router.post("/{run_id}/execute")
def execute_queued_run(
    run_id: str,
    payload: RunExecuteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status not in {"queued", "failed"} and not payload.force:
        raise HTTPException(status_code=409, detail=f"Run is {run.status}, not queued")
    background_tasks.add_task(execute_run_by_id, run.id)
    return {"id": run.id, "status": "dispatching"}


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
        "run_config": run.run_config_json,
        "agent_count": run.agent_count,
        "max_runtime_minutes": run.max_runtime_minutes,
        "estimated_cost_usd": run.estimated_cost_usd,
        "account_id": run.account_id,
        "payment_status": run.payment_status,
        "queued_at": run.queued_at.isoformat() if run.queued_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "final_confidence": run.final_confidence,
    }
