from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, EvidenceItem, Objective, ProjectCheckpoint, Run, ToolCall
from app.services.project_workspace import (
    PROJECT_MODES,
    create_project,
    create_project_version,
    default_budget_for_mode,
    enqueue_project_task,
    export_project,
    project_status,
    record_checkpoint,
    record_human_review,
    update_project_status,
)
from app.services.run_executor import create_run_record, normalize_run_config


def _db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


@pytest.mark.parametrize(
    ("mode", "expected_tool_calls", "cloud_enabled", "review_required"),
    [
        ("quick_triage", 100, False, False),
        ("deep_investigation", 1000, False, True),
        ("campaign", 5000, False, True),
        ("cloud_campaign", 10000, True, True),
    ],
)
def test_all_project_modes_have_generic_budgets_and_checkpoint_state(
    mode: str,
    expected_tool_calls: int,
    cloud_enabled: bool,
    review_required: bool,
) -> None:
    db = _db()
    project = create_project(
        db,
        title=f"{mode} project",
        objective_text=f"Investigate a generic scientific question in {mode}.",
        mode=mode,
    )

    assert project.mode == mode
    assert project.cloud_enabled is cloud_enabled
    assert project.budget_json == default_budget_for_mode(mode)
    assert project.budget_json["max_tool_calls"] == expected_tool_calls
    assert project.budget_json["human_review_required"] is review_required
    assert project.budget_json["max_failed_calls"] > 0
    assert "min_claim_coverage" in project.budget_json
    assert "min_contradiction_search_coverage" in project.budget_json
    assert "min_evidence_relevance" in project.budget_json

    objective = db.query(Objective).filter(Objective.project_id == project.id).one()
    checkpoint = (
        db.query(ProjectCheckpoint)
        .filter(
            ProjectCheckpoint.project_id == project.id,
            ProjectCheckpoint.checkpoint_type == "project_created",
        )
        .one()
    )
    assert checkpoint.state_json == {"objective_id": objective.id, "mode": mode}


def test_unknown_project_mode_falls_back_to_quick_triage_without_domain_bias() -> None:
    db = _db()
    project = create_project(
        db,
        title="Unrecognized mode project",
        objective_text="Investigate a generic objective.",
        mode="not_a_mode",
    )

    assert project.mode == "quick_triage"
    assert project.budget_json == default_budget_for_mode("quick_triage")
    assert PROJECT_MODES == {"quick_triage", "deep_investigation", "campaign", "cloud_campaign"}


def test_project_pause_resume_records_status_checkpoints() -> None:
    db = _db()
    project = create_project(
        db,
        title="Pause resume project",
        objective_text="Test durable pause and resume.",
        mode="campaign",
    )

    update_project_status(db, project, status="paused", reason="provider quota reached", actor="tester")
    update_project_status(db, project, status="active", reason="quota reset", actor="tester")

    status = project_status(db, project)
    assert status["project"]["status"] == "active"
    assert status["project"]["state"]["previous_status"] == "paused"
    checkpoint_types = [checkpoint["checkpoint_type"] for checkpoint in status["recent_checkpoints"]]
    assert "project_paused" in checkpoint_types
    assert "project_active" in checkpoint_types


def test_project_status_rejects_unknown_state() -> None:
    db = _db()
    project = create_project(
        db,
        title="Invalid state project",
        objective_text="Test validation.",
        mode="quick_triage",
    )

    with pytest.raises(ValueError):
        update_project_status(db, project, status="sleeping")


def test_project_workspace_tracks_runs_checkpoints_tasks_reviews_and_exports(tmp_path: Path) -> None:
    db = _db()
    project = create_project(
        db,
        title="EGFR resistance project",
        objective_text="Investigate EGFR osimertinib resistance in NSCLC.",
        mode="deep_investigation",
        created_by="tester",
    )
    objective = db.query(Objective).filter(Objective.project_id == project.id).first()
    assert objective is not None
    assert project.budget_json["max_failed_calls"] == 100
    assert project.budget_json["min_contradiction_search_coverage"] == 0.7
    project_created = (
        db.query(ProjectCheckpoint)
        .filter(
            ProjectCheckpoint.project_id == project.id,
            ProjectCheckpoint.checkpoint_type == "project_created",
        )
        .one()
    )
    assert project_created.state_json["objective_id"] == objective.id

    run = create_run_record(
        db,
        objective,
        normalize_run_config({"execution_mode": "queued", "project_id": project.id}),
    )
    assert run.project_id == project.id

    task = enqueue_project_task(
        db,
        project,
        task_type="tool_call",
        input_json={"tool": "pubmed_literature_search_tool", "query": "EGFR C797S osimertinib"},
        run_id=run.id,
        commit=True,
    )
    same_task = enqueue_project_task(
        db,
        project,
        task_type="tool_call",
        input_json={"tool": "pubmed_literature_search_tool", "query": "EGFR C797S osimertinib"},
        run_id=run.id,
        commit=True,
    )
    assert same_task.id == task.id

    db.add(
        ToolCall(
            project_id=project.id,
            run_id=run.id,
            tool_name="pubmed_literature_search_tool",
            tool_source="live_public_biomedical",
            input_json={"query": "EGFR C797S osimertinib"},
            output_json={"status": "success", "runtime_ms": 12},
            status="success",
            latency_ms=12,
        )
    )
    db.add(
        EvidenceItem(
            project_id=project.id,
            run_id=run.id,
            source="PubMed",
            evidence_text="EGFR C797S resistance evidence.",
            structured_json={},
            support_label="strong_support",
            support_score=0.8,
        )
    )
    record_checkpoint(
        db,
        project,
        run_id=run.id,
        checkpoint_type="batch_completed",
        phase="evidence_collection",
        state={"batch": 1},
        commit=True,
    )
    review = record_human_review(
        db,
        project,
        reviewer="expert",
        comment="Follow variant-specific evidence next.",
        decision="redirect",
    )
    update_project_status(db, project, status="paused", reason="expert review required")
    update_project_status(db, project, status="active", reason="review complete")
    version = create_project_version(db, project, summary="Initial project state.")

    status = project_status(db, project)
    assert status["project"]["status"] == "active"
    assert status["counts"]["runs"] == 1
    assert status["counts"]["tool_calls"] == 1
    assert status["counts"]["evidence_items"] == 1
    assert status["versions"][0]["version"] == version.version
    assert status["recent_human_reviews"][0]["id"] == review.id

    export_path = export_project(db, project, tmp_path / "project.json")
    assert export_path.exists()
    assert "EGFR resistance project" in export_path.read_text(encoding="utf-8")
