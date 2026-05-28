from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import ClawProject
from app.db.session import get_db
from app.services.project_workspace import (
    create_project,
    create_project_version,
    export_project,
    get_project,
    project_status,
    record_human_review,
    serialize_project,
    update_project_status,
)


router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    title: str
    objective_text: str
    mode: str = "quick_triage"
    cloud_enabled: bool = False
    created_by: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)


class ProjectReviewCreate(BaseModel):
    reviewer: str = "human"
    comment: str
    decision: str = "comment"
    review_type: str = "comment"
    target_type: str = "project"
    target_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectVersionCreate(BaseModel):
    summary: str = ""
    status: str = "snapshot"
    created_by: str = "system"


class ProjectStatusUpdate(BaseModel):
    reason: str = ""
    actor: str = "human"


@router.post("")
def create_project_route(payload: ProjectCreate, db: Session = Depends(get_db)) -> dict:
    project = create_project(
        db,
        title=payload.title,
        objective_text=payload.objective_text,
        mode=payload.mode,
        created_by=payload.created_by,
        config=payload.config,
        budget=payload.budget or None,
        cloud_enabled=payload.cloud_enabled,
    )
    return {"project": serialize_project(project)}


@router.get("")
def list_projects(db: Session = Depends(get_db)) -> dict:
    projects = db.query(ClawProject).order_by(ClawProject.updated_at.desc()).all()
    return {"projects": [serialize_project(project) for project in projects]}


@router.get("/{project_id_or_slug}")
def get_project_route(project_id_or_slug: str, db: Session = Depends(get_db)) -> dict:
    project = get_project(db, project_id_or_slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_status(db, project)


@router.post("/{project_id_or_slug}/pause")
def pause_project_route(
    project_id_or_slug: str,
    payload: ProjectStatusUpdate,
    db: Session = Depends(get_db),
) -> dict:
    project = get_project(db, project_id_or_slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project = update_project_status(
        db,
        project,
        status="paused",
        reason=payload.reason,
        actor=payload.actor,
    )
    return {"project": serialize_project(project)}


@router.post("/{project_id_or_slug}/resume")
def resume_project_route(
    project_id_or_slug: str,
    payload: ProjectStatusUpdate,
    db: Session = Depends(get_db),
) -> dict:
    project = get_project(db, project_id_or_slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project = update_project_status(
        db,
        project,
        status="active",
        reason=payload.reason or "resume requested",
        actor=payload.actor,
    )
    return {"project": serialize_project(project)}


@router.post("/{project_id_or_slug}/versions")
def create_project_version_route(
    project_id_or_slug: str,
    payload: ProjectVersionCreate,
    db: Session = Depends(get_db),
) -> dict:
    project = get_project(db, project_id_or_slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    version = create_project_version(
        db,
        project,
        summary=payload.summary,
        status=payload.status,
        created_by=payload.created_by,
    )
    return {"version": version.version, "id": version.id}


@router.post("/{project_id_or_slug}/reviews")
def add_project_review(
    project_id_or_slug: str,
    payload: ProjectReviewCreate,
    db: Session = Depends(get_db),
) -> dict:
    project = get_project(db, project_id_or_slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    review = record_human_review(
        db,
        project,
        reviewer=payload.reviewer,
        comment=payload.comment,
        decision=payload.decision,
        review_type=payload.review_type,
        target_type=payload.target_type,
        target_id=payload.target_id,
        metadata=payload.metadata,
    )
    return {"review_id": review.id}


@router.post("/{project_id_or_slug}/export")
def export_project_route(project_id_or_slug: str, db: Session = Depends(get_db)) -> dict:
    project = get_project(db, project_id_or_slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    path = Path("outputs/projects") / project.slug / "project_export.json"
    export_project(db, project, path)
    return {"path": str(path)}
