from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import (
    AgentRoleMemory,
    ExperimentMemory,
    RunReplay,
    ScientificEntity,
    ScientificHypothesisMemory,
    ToolBenchmark,
    WorkflowPolicyModel,
)
from app.db.session import get_db
from app.services.scientific_memory import (
    build_scientific_state_graph,
    memory_summary,
    predict_next_actions,
    train_workflow_policy_model,
)

router = APIRouter(prefix="/memory", tags=["scientific-memory"])


class PolicyTrainRequest(BaseModel):
    name: str = "scientific_workflow_policy"
    artifact_dir: str = "outputs/models"


class PolicyPredictRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)
    model_id: str | None = None
    top_k: int = 5


@router.get("/summary")
def get_memory_summary(db: Session = Depends(get_db)) -> dict:
    return memory_summary(db)


@router.get("/state-graph")
def get_scientific_state_graph(limit: int = 500, db: Session = Depends(get_db)) -> dict:
    return build_scientific_state_graph(db, limit=max(1, min(limit, 1000)))


@router.get("/runs/{run_id}/state-graph")
def get_run_scientific_state_graph(run_id: str, limit: int = 500, db: Session = Depends(get_db)) -> dict:
    graph = build_scientific_state_graph(db, run_id=run_id, limit=max(1, min(limit, 1000)))
    if graph["summary"]["hypotheses"] == 0 and graph["summary"]["experiments"] == 0:
        raise HTTPException(status_code=404, detail="No scientific state graph data found for run")
    return graph


@router.get("/entities")
def list_entities(limit: int = 100, db: Session = Depends(get_db)) -> dict:
    entities = (
        db.query(ScientificEntity)
        .order_by(ScientificEntity.mention_count.desc(), ScientificEntity.updated_at.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return {
        "entities": [
            {
                "id": entity.id,
                "type": entity.entity_type,
                "name": entity.name,
                "mention_count": entity.mention_count,
                "first_seen_run_id": entity.first_seen_run_id,
                "last_seen_run_id": entity.last_seen_run_id,
                "metadata": entity.metadata_json,
            }
            for entity in entities
        ]
    }


@router.get("/hypotheses")
def list_hypothesis_memory(limit: int = 100, db: Session = Depends(get_db)) -> dict:
    hypotheses = (
        db.query(ScientificHypothesisMemory)
        .order_by(ScientificHypothesisMemory.created_at.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return {
        "hypotheses": [
            {
                "id": hypothesis.id,
                "run_id": hypothesis.run_id,
                "title": hypothesis.title,
                "hypothesis": hypothesis.hypothesis_text,
                "confidence": hypothesis.confidence,
                "status": hypothesis.status,
                "entity_ids": hypothesis.entity_ids_json,
                "evidence_summary": hypothesis.evidence_summary_json,
                "failure_modes": hypothesis.failure_modes_json,
            }
            for hypothesis in hypotheses
        ]
    }


@router.get("/experiments")
def list_experiments(limit: int = 100, db: Session = Depends(get_db)) -> dict:
    experiments = (
        db.query(ExperimentMemory)
        .order_by(ExperimentMemory.created_at.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return {
        "experiments": [
            {
                "id": experiment.id,
                "run_id": experiment.run_id,
                "hypothesis_memory_id": experiment.hypothesis_memory_id,
                "name": experiment.name,
                "type": experiment.experiment_type,
                "expected_information_gain": experiment.expected_information_gain,
                "feasibility": experiment.feasibility,
                "status": experiment.status,
                "protocol": experiment.protocol_json,
                "result": experiment.result_json,
            }
            for experiment in experiments
        ]
    }


@router.get("/tool-benchmarks")
def list_tool_benchmarks(limit: int = 100, db: Session = Depends(get_db)) -> dict:
    benchmarks = (
        db.query(ToolBenchmark)
        .order_by(ToolBenchmark.call_count.desc(), ToolBenchmark.updated_at.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return {
        "tool_benchmarks": [
            {
                "id": benchmark.id,
                "tool_name": benchmark.tool_name,
                "tool_source": benchmark.tool_source,
                "call_count": benchmark.call_count,
                "success_count": benchmark.success_count,
                "failure_count": benchmark.failure_count,
                "success_rate": benchmark.success_count / benchmark.call_count if benchmark.call_count else None,
                "avg_latency_ms": benchmark.avg_latency_ms,
                "avg_usefulness": benchmark.avg_usefulness,
                "last_error": benchmark.last_error,
                "last_run_id": benchmark.last_run_id,
            }
            for benchmark in benchmarks
        ]
    }


@router.get("/agents")
def list_agent_memory(limit: int = 100, db: Session = Depends(get_db)) -> dict:
    memories = (
        db.query(AgentRoleMemory)
        .order_by(AgentRoleMemory.run_count.desc(), AgentRoleMemory.updated_at.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return {
        "agents": [
            {
                "id": memory.id,
                "agent_name": memory.agent_name,
                "role_summary": memory.role_summary,
                "run_count": memory.run_count,
                "last_run_id": memory.last_run_id,
                "memory": memory.memory_json,
            }
            for memory in memories
        ]
    }


@router.get("/runs/{run_id}/replay")
def get_run_replay(run_id: str, db: Session = Depends(get_db)) -> dict:
    replay = db.query(RunReplay).filter(RunReplay.run_id == run_id).first()
    if replay is None:
        raise HTTPException(status_code=404, detail="Replay bundle not found")
    return {
        "id": replay.id,
        "run_id": replay.run_id,
        "replay_hash": replay.replay_hash,
        "created_at": replay.created_at.isoformat(),
        "bundle": replay.bundle_json,
    }


@router.post("/policy/train")
def train_policy(payload: PolicyTrainRequest, db: Session = Depends(get_db)) -> dict:
    model = train_workflow_policy_model(db, name=payload.name, artifact_dir=payload.artifact_dir)
    db.commit()
    db.refresh(model)
    return serialize_policy_model(model)


@router.get("/policy/models")
def list_policy_models(db: Session = Depends(get_db)) -> dict:
    models = db.query(WorkflowPolicyModel).order_by(WorkflowPolicyModel.created_at.desc()).all()
    return {"models": [serialize_policy_model(model) for model in models]}


@router.post("/policy/predict")
def predict_policy(payload: PolicyPredictRequest, db: Session = Depends(get_db)) -> dict:
    model = None
    if payload.model_id:
        model = db.get(WorkflowPolicyModel, payload.model_id)
    if model is None:
        model = db.query(WorkflowPolicyModel).order_by(WorkflowPolicyModel.created_at.desc()).first()
    if model is None:
        raise HTTPException(status_code=404, detail="No workflow policy model has been trained")
    return {
        "model": serialize_policy_model(model),
        "predictions": predict_next_actions(payload.context, model_path=model.artifact_path, top_k=payload.top_k),
    }


def serialize_policy_model(model: WorkflowPolicyModel) -> dict:
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
