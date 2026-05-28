#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.db.models import ClawProject, Objective, Run
from app.db.session import SessionLocal, init_db
from app.env import load_environment
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
from app.services.run_executor import create_run_record, execute_run, normalize_run_config


def json_print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, default=str))


def cmd_create(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        project = create_project(
            db,
            title=args.title,
            objective_text=args.objective,
            mode=args.mode,
            cloud_enabled=args.cloud,
            created_by=args.created_by,
            config=load_json_arg(args.config),
            budget=load_json_arg(args.budget) if args.budget else None,
        )
        json_print({"project": serialize_project(project)})
        return 0
    finally:
        db.close()


def cmd_cloud_start(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        project = create_project(
            db,
            title=args.title,
            objective_text=args.objective,
            mode="cloud_campaign",
            cloud_enabled=True,
            created_by=args.created_by,
            config={**load_json_arg(args.config), "local_cloud_mode": True},
            budget=load_json_arg(args.budget) if args.budget else None,
        )
        json_print({"project": serialize_project(project)})
        return 0
    finally:
        db.close()


def cmd_list(_: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        projects = db.query(ClawProject).order_by(ClawProject.updated_at.desc()).all()
        json_print({"projects": [serialize_project(project) for project in projects]})
        return 0
    finally:
        db.close()


def cmd_status(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        project = require_project(db, args.project)
        json_print(project_status(db, project))
        return 0
    finally:
        db.close()


def cmd_pause(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        project = require_project(db, args.project)
        project = update_project_status(
            db,
            project,
            status="paused",
            reason=args.reason,
            actor=args.actor,
        )
        json_print({"project": serialize_project(project)})
        return 0
    finally:
        db.close()


def cmd_resume_project(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        project = require_project(db, args.project)
        project = update_project_status(
            db,
            project,
            status="active",
            reason=args.reason or "resume requested",
            actor=args.actor,
        )
        json_print({"project": serialize_project(project)})
        return 0
    finally:
        db.close()


def cmd_export(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        project = require_project(db, args.project)
        path = Path(args.output or f"outputs/projects/{project.slug}/project_export.json")
        export_project(db, project, path)
        json_print({"project": project.slug, "path": str(path)})
        return 0
    finally:
        db.close()


def cmd_review(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        project = require_project(db, args.project)
        review = record_human_review(
            db,
            project,
            reviewer=args.reviewer,
            comment=args.comment,
            decision=args.decision,
            review_type=args.review_type,
            target_type=args.target_type,
            target_id=args.target_id,
        )
        json_print({"project": project.slug, "review_id": review.id})
        return 0
    finally:
        db.close()


def cmd_snapshot(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        project = require_project(db, args.project)
        version = create_project_version(
            db,
            project,
            summary=args.summary,
            status=args.status,
            created_by=args.created_by,
        )
        json_print({"project": project.slug, "version": version.version, "id": version.id})
        return 0
    finally:
        db.close()


def cmd_run(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        project = require_project(db, args.project)
        if project.status == "paused":
            raise SystemExit(f"Project is paused: {project.slug}. Resume it before starting a run.")
        objective = (
            db.query(Objective)
            .filter(Objective.project_id == project.id)
            .order_by(Objective.created_at.asc())
            .first()
        )
        if objective is None:
            objective = Objective(
                title=project.title[:120],
                objective_text=project.objective_text,
                constraints_json={"project_id": project.id, "project_mode": project.mode},
                project_id=project.id,
            )
            db.add(objective)
            db.commit()
            db.refresh(objective)
        config = normalize_run_config(
            {
                "execution_mode": "inline",
                "project_id": project.id,
                "project_slug": project.slug,
                "project_mode": project.mode,
                "cloud_campaign_enabled": project.cloud_enabled,
                **load_json_arg(args.config),
            }
        )
        run = create_run_record(db, objective, config)
        run.payment_status = "not_required"
        db.commit()
        if args.no_execute:
            json_print({"project": project.slug, "run_id": run.id, "status": run.status})
            return 0
        run = execute_run(db, run, objective)
        json_print(
            {
                "project": project.slug,
                "run_id": run.id,
                "status": run.status,
                "final_confidence": run.final_confidence,
            }
        )
        return 0 if run.status == "completed" else 1
    finally:
        db.close()


def cmd_resume(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        project = require_project(db, args.project)
        if project.status == "paused":
            update_project_status(
                db,
                project,
                status="active",
                reason="run resume requested",
                actor="system",
            )
        run = (
            db.query(Run)
            .filter(Run.project_id == project.id, Run.status.in_(["queued", "failed", "paused"]))
            .order_by(Run.queued_at.desc().nullslast(), Run.started_at.desc().nullslast())
            .first()
        )
        if run is None:
            json_print(
                {
                    "project": project.slug,
                    "status": "no_resumable_run",
                    "next": "Use `python -m tools.claw_project run --project ...` to start a new run.",
                }
            )
            return 0
        objective = db.get(Objective, run.objective_id)
        if objective is None:
            raise SystemExit(f"Run {run.id} has no objective.")
        run = execute_run(db, run, objective)
        json_print({"project": project.slug, "run_id": run.id, "status": run.status})
        return 0 if run.status == "completed" else 1
    finally:
        db.close()


def require_project(db, project_id_or_slug: str):
    project = get_project(db, project_id_or_slug)
    if project is None:
        raise SystemExit(f"Project not found: {project_id_or_slug}")
    return project


def load_json_arg(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    path = Path(value)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local ClawInstitute project workspaces.")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create a local project workspace.")
    create.add_argument("--title", required=True)
    create.add_argument("--objective", required=True)
    create.add_argument("--mode", default="quick_triage", choices=["quick_triage", "deep_investigation", "campaign", "cloud_campaign"])
    create.add_argument("--cloud", action="store_true")
    create.add_argument("--created-by", default="")
    create.add_argument("--config", default="")
    create.add_argument("--budget", default="")
    create.set_defaults(func=cmd_create)

    list_cmd = sub.add_parser("list", help="List local projects.")
    list_cmd.set_defaults(func=cmd_list)

    status = sub.add_parser("status", help="Show project status.")
    status.add_argument("--project", required=True)
    status.set_defaults(func=cmd_status)

    pause = sub.add_parser("pause", help="Pause a project without losing state.")
    pause.add_argument("--project", required=True)
    pause.add_argument("--reason", default="")
    pause.add_argument("--actor", default="human")
    pause.set_defaults(func=cmd_pause)

    resume_project = sub.add_parser("resume-project", help="Mark a paused project active again.")
    resume_project.add_argument("--project", required=True)
    resume_project.add_argument("--reason", default="")
    resume_project.add_argument("--actor", default="human")
    resume_project.set_defaults(func=cmd_resume_project)

    run = sub.add_parser("run", help="Start a run inside a project.")
    run.add_argument("--project", required=True)
    run.add_argument("--config", default="")
    run.add_argument("--no-execute", action="store_true")
    run.set_defaults(func=cmd_run)

    resume = sub.add_parser("resume", help="Resume the latest queued/failed/paused project run.")
    resume.add_argument("--project", required=True)
    resume.set_defaults(func=cmd_resume)

    review = sub.add_parser("review", help="Add a human review note.")
    review.add_argument("--project", required=True)
    review.add_argument("--comment", required=True)
    review.add_argument("--reviewer", default="human")
    review.add_argument("--decision", default="comment")
    review.add_argument("--review-type", default="comment")
    review.add_argument("--target-type", default="project")
    review.add_argument("--target-id", default="")
    review.set_defaults(func=cmd_review)

    snapshot = sub.add_parser("snapshot", help="Create a versioned project snapshot.")
    snapshot.add_argument("--project", required=True)
    snapshot.add_argument("--summary", default="")
    snapshot.add_argument("--status", default="snapshot")
    snapshot.add_argument("--created-by", default="human")
    snapshot.set_defaults(func=cmd_snapshot)

    export = sub.add_parser("export", help="Export project state to JSON.")
    export.add_argument("--project", required=True)
    export.add_argument("--output", default="")
    export.set_defaults(func=cmd_export)

    cloud_start = sub.add_parser(
        "cloud-start",
        help="Create a cloud-campaign project in the local database.",
    )
    cloud_start.add_argument("--title", required=True)
    cloud_start.add_argument("--objective", required=True)
    cloud_start.add_argument("--created-by", default="")
    cloud_start.add_argument("--config", default="")
    cloud_start.add_argument("--budget", default="")
    cloud_start.set_defaults(func=cmd_cloud_start)

    cloud_status = sub.add_parser("cloud-status", help="Show local cloud-campaign status.")
    cloud_status.add_argument("--project", required=True)
    cloud_status.set_defaults(func=cmd_status)

    cloud_pause = sub.add_parser("cloud-pause", help="Pause a local cloud-campaign project.")
    cloud_pause.add_argument("--project", required=True)
    cloud_pause.add_argument("--reason", default="cloud pause requested")
    cloud_pause.add_argument("--actor", default="human")
    cloud_pause.set_defaults(func=cmd_pause)

    cloud_resume = sub.add_parser("cloud-resume", help="Resume local cloud-campaign project work.")
    cloud_resume.add_argument("--project", required=True)
    cloud_resume.add_argument("--reason", default="cloud resume requested")
    cloud_resume.add_argument("--actor", default="human")
    cloud_resume.set_defaults(func=cmd_resume)

    cloud_export = sub.add_parser("cloud-export", help="Export local cloud-campaign project state.")
    cloud_export.add_argument("--project", required=True)
    cloud_export.add_argument("--output", default="")
    cloud_export.set_defaults(func=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    load_environment()
    init_db()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
