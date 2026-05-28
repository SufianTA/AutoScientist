from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    AgentStep,
    BoardPost,
    ClawProject,
    EvidenceItem,
    Hypothesis,
    Objective,
    ProjectCheckpoint,
    ProjectHumanReview,
    ProjectTask,
    ProjectVersion,
    Run,
    ToolCall,
)


PROJECT_MODES = {"quick_triage", "deep_investigation", "campaign", "cloud_campaign"}
PROJECT_STATUSES = {"active", "paused", "completed", "archived"}


def create_project(
    db: Session,
    *,
    title: str,
    objective_text: str,
    mode: str = "quick_triage",
    created_by: str | None = None,
    config: dict[str, Any] | None = None,
    budget: dict[str, Any] | None = None,
    cloud_enabled: bool = False,
) -> ClawProject:
    normalized_mode = mode if mode in PROJECT_MODES else "quick_triage"
    slug = unique_project_slug(db, title)
    project = ClawProject(
        slug=slug,
        title=title.strip() or slug,
        objective_text=objective_text.strip(),
        mode=normalized_mode,
        cloud_enabled=bool(cloud_enabled or normalized_mode == "cloud_campaign"),
        config_json=config or {},
        budget_json=budget or default_budget_for_mode(normalized_mode),
        state_json={
            "phase": "created",
            "open_questions": [],
            "pending_actions": [],
            "last_checkpoint_id": None,
        },
        created_by=created_by,
    )
    db.add(project)
    db.flush()
    objective = Objective(
        title=project.title[:120],
        objective_text=project.objective_text,
        constraints_json={"project_id": project.id, "project_mode": project.mode},
        created_by=created_by,
        project_id=project.id,
    )
    db.add(objective)
    db.flush()
    record_checkpoint(
        db,
        project,
        checkpoint_type="project_created",
        phase="created",
        state={"objective_id": objective.id, "mode": project.mode},
    )
    db.commit()
    db.refresh(project)
    return project


def default_budget_for_mode(mode: str) -> dict[str, Any]:
    if mode == "cloud_campaign":
        return {
            "max_tool_calls": 10000,
            "max_wall_time_hours": 72,
            "max_cost_usd": 200.0,
            "max_failed_calls": 500,
            "max_irrelevant_evidence_rate": 0.7,
            "max_api_retries": 3,
            "min_claim_coverage": 0.85,
            "min_contradiction_search_coverage": 0.8,
            "min_evidence_relevance": 0.35,
            "pause_every_tool_calls": 500,
            "human_review_required": True,
        }
    if mode == "campaign":
        return {
            "max_tool_calls": 5000,
            "max_wall_time_hours": 24,
            "max_cost_usd": 100.0,
            "max_failed_calls": 250,
            "max_irrelevant_evidence_rate": 0.65,
            "max_api_retries": 3,
            "min_claim_coverage": 0.8,
            "min_contradiction_search_coverage": 0.75,
            "min_evidence_relevance": 0.35,
            "pause_every_tool_calls": 500,
            "human_review_required": True,
        }
    if mode == "deep_investigation":
        return {
            "max_tool_calls": 1000,
            "max_wall_time_hours": 6,
            "max_cost_usd": 50.0,
            "max_failed_calls": 100,
            "max_irrelevant_evidence_rate": 0.6,
            "max_api_retries": 3,
            "min_claim_coverage": 0.75,
            "min_contradiction_search_coverage": 0.7,
            "min_evidence_relevance": 0.35,
            "pause_every_tool_calls": 200,
            "human_review_required": True,
        }
    return {
        "max_tool_calls": 100,
        "max_wall_time_hours": 1,
        "max_cost_usd": 10.0,
        "max_failed_calls": 25,
        "max_irrelevant_evidence_rate": 0.75,
        "max_api_retries": 2,
        "min_claim_coverage": 0.4,
        "min_contradiction_search_coverage": 0.25,
        "min_evidence_relevance": 0.25,
        "pause_every_tool_calls": 100,
        "human_review_required": False,
    }


def unique_project_slug(db: Session, title: str) -> str:
    base = slugify(title) or "project"
    slug = base
    counter = 2
    while db.query(ClawProject).filter(ClawProject.slug == slug).first() is not None:
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug[:120].strip("-")


def get_project(db: Session, project_id_or_slug: str) -> ClawProject | None:
    return (
        db.query(ClawProject)
        .filter((ClawProject.id == project_id_or_slug) | (ClawProject.slug == project_id_or_slug))
        .first()
    )


def attach_run_to_project(db: Session, run: Run, project: ClawProject) -> None:
    run.project_id = project.id
    run.run_config_json = {**(run.run_config_json or {}), "project_id": project.id, "project_slug": project.slug}
    run.current_state = run.current_state or "project_attached"
    project.updated_at = datetime.utcnow()
    record_checkpoint(
        db,
        project,
        run_id=run.id,
        checkpoint_type="run_attached",
        phase=run.current_state,
        state={"run_id": run.id, "status": run.status},
        commit=False,
    )


def update_project_status(
    db: Session,
    project: ClawProject,
    *,
    status: str,
    reason: str = "",
    actor: str = "system",
    commit: bool = True,
) -> ClawProject:
    if status not in PROJECT_STATUSES:
        raise ValueError(f"Unsupported project status: {status}")
    previous_status = project.status
    project.status = status
    project.updated_at = datetime.utcnow()
    project.state_json = {
        **(project.state_json or {}),
        "status": status,
        "previous_status": previous_status,
        "status_reason": reason,
        "status_actor": actor,
        "updated_at": project.updated_at.isoformat(),
    }
    record_checkpoint(
        db,
        project,
        checkpoint_type=f"project_{status}",
        phase=status,
        state={"previous_status": previous_status, "reason": reason, "actor": actor},
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(project)
    else:
        db.flush()
    return project


def record_checkpoint(
    db: Session,
    project: ClawProject,
    *,
    checkpoint_type: str,
    phase: str,
    state: dict[str, Any] | None = None,
    counters: dict[str, Any] | None = None,
    run_id: str | None = None,
    commit: bool = False,
) -> ProjectCheckpoint:
    checkpoint = ProjectCheckpoint(
        project_id=project.id,
        run_id=run_id,
        checkpoint_type=checkpoint_type,
        phase=phase,
        state_json=state or {},
        counters_json=counters or {},
    )
    db.add(checkpoint)
    db.flush()
    state_json = dict(project.state_json or {})
    state_json.update(
        {
            "phase": phase,
            "last_checkpoint_id": checkpoint.id,
            "last_checkpoint_type": checkpoint_type,
            "last_run_id": run_id or state_json.get("last_run_id"),
            "updated_at": datetime.utcnow().isoformat(),
        }
    )
    project.state_json = state_json
    project.updated_at = datetime.utcnow()
    if commit:
        db.commit()
    return checkpoint


def enqueue_project_task(
    db: Session,
    project: ClawProject,
    *,
    task_type: str,
    input_json: dict[str, Any],
    priority: int = 100,
    run_id: str | None = None,
    commit: bool = False,
) -> ProjectTask:
    key = task_idempotency_key(task_type, input_json)
    existing = (
        db.query(ProjectTask)
        .filter(ProjectTask.project_id == project.id, ProjectTask.idempotency_key == key)
        .first()
    )
    if existing is not None:
        return existing
    task = ProjectTask(
        project_id=project.id,
        run_id=run_id,
        task_type=task_type,
        priority=priority,
        idempotency_key=key,
        input_json=input_json,
    )
    db.add(task)
    if commit:
        db.commit()
        db.refresh(task)
    return task


def task_idempotency_key(task_type: str, payload: dict[str, Any]) -> str:
    raw = json.dumps({"task_type": task_type, "payload": payload}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def record_human_review(
    db: Session,
    project: ClawProject,
    *,
    reviewer: str,
    comment: str,
    decision: str = "comment",
    review_type: str = "comment",
    target_type: str = "project",
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProjectHumanReview:
    review = ProjectHumanReview(
        project_id=project.id,
        reviewer=reviewer,
        review_type=review_type,
        target_type=target_type,
        target_id=target_id,
        decision=decision,
        comment=comment,
        metadata_json=metadata or {},
    )
    db.add(review)
    record_checkpoint(
        db,
        project,
        checkpoint_type="human_review_added",
        phase="human_review",
        state={"decision": decision, "review_type": review_type},
        commit=False,
    )
    db.commit()
    db.refresh(review)
    return review


def create_project_version(
    db: Session,
    project: ClawProject,
    *,
    summary: str = "",
    status: str = "snapshot",
    created_by: str = "system",
    commit: bool = True,
) -> ProjectVersion:
    existing_count = db.query(ProjectVersion).filter(ProjectVersion.project_id == project.id).count()
    version = f"v0.{existing_count + 1}"
    snapshot = build_project_snapshot(db, project)
    project_version = ProjectVersion(
        project_id=project.id,
        version=version,
        status=status,
        summary=summary or snapshot.get("summary", ""),
        snapshot_json=snapshot,
        created_by=created_by,
    )
    db.add(project_version)
    record_checkpoint(
        db,
        project,
        checkpoint_type="version_created",
        phase="versioned",
        state={"version": version, "status": status},
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(project_version)
    return project_version


def build_project_snapshot(db: Session, project: ClawProject) -> dict[str, Any]:
    runs = db.query(Run).filter(Run.project_id == project.id).order_by(Run.started_at.asc()).all()
    run_ids = [run.id for run in runs]
    evidence_count = db.query(EvidenceItem).filter(EvidenceItem.project_id == project.id).count()
    tool_call_count = db.query(ToolCall).filter(ToolCall.project_id == project.id).count()
    hypothesis_count = db.query(Hypothesis).filter(Hypothesis.project_id == project.id).count()
    pending_task_count = (
        db.query(ProjectTask)
        .filter(ProjectTask.project_id == project.id, ProjectTask.status == "pending")
        .count()
    )
    completed_task_count = (
        db.query(ProjectTask)
        .filter(ProjectTask.project_id == project.id, ProjectTask.status == "completed")
        .count()
    )
    latest_run = runs[-1] if runs else None
    return {
        "schema": "autosci.claw_project_snapshot.v0.1",
        "project": serialize_project(project),
        "summary": (
            f"{len(runs)} run(s), {tool_call_count} tool call(s), {evidence_count} evidence item(s), "
            f"{hypothesis_count} hypothesis record(s)."
        ),
        "runs": [serialize_run_brief(run) for run in runs],
        "latest_run_id": latest_run.id if latest_run else None,
        "counts": {
            "runs": len(runs),
            "tool_calls": tool_call_count,
            "evidence_items": evidence_count,
            "hypotheses": hypothesis_count,
            "pending_tasks": pending_task_count,
            "completed_tasks": completed_task_count,
        },
        "run_ids": run_ids,
    }


def project_status(db: Session, project: ClawProject) -> dict[str, Any]:
    snapshot = build_project_snapshot(db, project)
    checkpoints = (
        db.query(ProjectCheckpoint)
        .filter(ProjectCheckpoint.project_id == project.id)
        .order_by(ProjectCheckpoint.created_at.desc())
        .limit(5)
        .all()
    )
    versions = (
        db.query(ProjectVersion)
        .filter(ProjectVersion.project_id == project.id)
        .order_by(ProjectVersion.created_at.desc())
        .limit(5)
        .all()
    )
    reviews = (
        db.query(ProjectHumanReview)
        .filter(ProjectHumanReview.project_id == project.id)
        .order_by(ProjectHumanReview.created_at.desc())
        .limit(5)
        .all()
    )
    return {
        **snapshot,
        "recent_checkpoints": [serialize_checkpoint(item) for item in checkpoints],
        "versions": [serialize_version(item) for item in versions],
        "recent_human_reviews": [serialize_review(item) for item in reviews],
    }


def export_project(db: Session, project: ClawProject, path: Path) -> Path:
    payload = project_status(db, project)
    payload["agent_steps"] = [
        {
            "run_id": step.run_id,
            "agent_name": step.agent_name,
            "state_name": step.state_name,
            "input": step.input_json,
            "output": step.output_json,
            "created_at": step.started_at.isoformat(),
            "error": step.error,
        }
        for step in db.query(AgentStep)
        .join(Run, Run.id == AgentStep.run_id)
        .filter(Run.project_id == project.id)
        .order_by(AgentStep.started_at.asc())
        .all()
    ]
    payload["tool_calls"] = [
        {
            "id": call.id,
            "run_id": call.run_id,
            "tool_name": call.tool_name,
            "tool_source": call.tool_source,
            "input": call.input_json,
            "status": call.status,
            "latency_ms": call.latency_ms,
            "created_at": call.created_at.isoformat(),
        }
        for call in db.query(ToolCall)
        .filter(ToolCall.project_id == project.id)
        .order_by(ToolCall.created_at.asc())
        .all()
    ]
    payload["evidence"] = [
        {
            "id": item.id,
            "run_id": item.run_id,
            "source": item.source,
            "text": item.evidence_text,
            "label": item.support_label,
            "score": item.support_score,
        }
        for item in db.query(EvidenceItem)
        .filter(EvidenceItem.project_id == project.id)
        .order_by(EvidenceItem.created_at.asc())
        .all()
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def serialize_project(project: ClawProject) -> dict[str, Any]:
    return {
        "id": project.id,
        "slug": project.slug,
        "title": project.title,
        "objective_text": project.objective_text,
        "mode": project.mode,
        "status": project.status,
        "cloud_enabled": project.cloud_enabled,
        "config": project.config_json,
        "budget": project.budget_json,
        "state": project.state_json,
        "created_by": project.created_by,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


def serialize_run_brief(run: Run) -> dict[str, Any]:
    return {
        "id": run.id,
        "objective_id": run.objective_id,
        "status": run.status,
        "current_state": run.current_state,
        "final_confidence": run.final_confidence,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def serialize_checkpoint(checkpoint: ProjectCheckpoint) -> dict[str, Any]:
    return {
        "id": checkpoint.id,
        "run_id": checkpoint.run_id,
        "checkpoint_type": checkpoint.checkpoint_type,
        "phase": checkpoint.phase,
        "state": checkpoint.state_json,
        "counters": checkpoint.counters_json,
        "created_at": checkpoint.created_at.isoformat() if checkpoint.created_at else None,
    }


def serialize_version(version: ProjectVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "version": version.version,
        "status": version.status,
        "summary": version.summary,
        "created_by": version.created_by,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }


def serialize_review(review: ProjectHumanReview) -> dict[str, Any]:
    return {
        "id": review.id,
        "run_id": review.run_id,
        "reviewer": review.reviewer,
        "review_type": review.review_type,
        "target_type": review.target_type,
        "target_id": review.target_id,
        "decision": review.decision,
        "comment": review.comment,
        "metadata": review.metadata_json,
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }
