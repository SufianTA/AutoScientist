from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, ClawProject
from tools import claw_project


@pytest.fixture()
def cli_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine)
    monkeypatch.setattr(claw_project, "SessionLocal", testing_session)
    monkeypatch.setattr(claw_project, "init_db", lambda: None)
    yield testing_session
    Base.metadata.drop_all(engine)


def _project_by_title(session_factory: sessionmaker[Session], title: str) -> ClawProject:
    db = session_factory()
    try:
        project = db.query(ClawProject).filter(ClawProject.title == title).one()
        db.expunge(project)
        return project
    finally:
        db.close()


def test_claw_project_cli_create_pause_resume_snapshot_and_export(
    cli_db: sessionmaker[Session],
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        claw_project.main(
            [
                "create",
                "--title",
                "CLI durable project",
                "--objective",
                "Investigate a generic durable project.",
                "--mode",
                "deep_investigation",
            ]
        )
        == 0
    )
    created_output = capsys.readouterr().out
    assert "deep_investigation" in created_output
    project = _project_by_title(cli_db, "CLI durable project")

    assert claw_project.main(["pause", "--project", project.slug, "--reason", "test pause"]) == 0
    paused_output = capsys.readouterr().out
    assert '"status": "paused"' in paused_output

    assert claw_project.main(["resume-project", "--project", project.slug, "--reason", "test resume"]) == 0
    resumed_output = capsys.readouterr().out
    assert '"status": "active"' in resumed_output

    assert claw_project.main(["snapshot", "--project", project.slug, "--summary", "CLI snapshot"]) == 0
    snapshot_output = capsys.readouterr().out
    assert '"version": "v0.1"' in snapshot_output

    export_path = tmp_path / "project.json"
    assert claw_project.main(["export", "--project", project.slug, "--output", str(export_path)]) == 0
    assert export_path.exists()


def test_claw_project_cli_cloud_campaign_aliases(
    cli_db: sessionmaker[Session],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        claw_project.main(
            [
                "cloud-start",
                "--title",
                "CLI cloud project",
                "--objective",
                "Investigate a generic cloud campaign project.",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert '"mode": "cloud_campaign"' in output
    assert '"cloud_enabled": true' in output

    project = _project_by_title(cli_db, "CLI cloud project")
    assert claw_project.main(["cloud-pause", "--project", project.slug]) == 0
    assert '"status": "paused"' in capsys.readouterr().out

    assert claw_project.main(["cloud-resume", "--project", project.slug]) == 0
    resumed_output = capsys.readouterr().out
    assert project.slug in resumed_output
