from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def project_client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine)

    def override_get_db() -> Iterator[Session]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)


@pytest.mark.parametrize(
    ("mode", "expected_tool_calls", "cloud_enabled"),
    [
        ("quick_triage", 100, False),
        ("deep_investigation", 1000, False),
        ("campaign", 5000, False),
        ("cloud_campaign", 10000, True),
    ],
)
def test_project_api_creates_all_modes(
    project_client: TestClient,
    mode: str,
    expected_tool_calls: int,
    cloud_enabled: bool,
) -> None:
    response = project_client.post(
        "/projects",
        json={
            "title": f"{mode} API project",
            "objective_text": "Investigate a generic project through the API.",
            "mode": mode,
        },
    )

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["mode"] == mode
    assert project["cloud_enabled"] is cloud_enabled
    assert project["budget"]["max_tool_calls"] == expected_tool_calls
    assert "min_contradiction_search_coverage" in project["budget"]


def test_project_api_pause_resume_review_snapshot_and_export(project_client: TestClient) -> None:
    created = project_client.post(
        "/projects",
        json={
            "title": "API durable project",
            "objective_text": "Track pause resume review snapshot and export.",
            "mode": "campaign",
        },
    )
    assert created.status_code == 200
    slug = created.json()["project"]["slug"]

    paused = project_client.post(
        f"/projects/{slug}/pause",
        json={"reason": "waiting for expert review", "actor": "tester"},
    )
    assert paused.status_code == 200
    assert paused.json()["project"]["status"] == "paused"

    resumed = project_client.post(
        f"/projects/{slug}/resume",
        json={"reason": "expert review complete", "actor": "tester"},
    )
    assert resumed.status_code == 200
    assert resumed.json()["project"]["status"] == "active"

    review = project_client.post(
        f"/projects/{slug}/reviews",
        json={"comment": "Looks ready for another exploration wave.", "decision": "continue"},
    )
    assert review.status_code == 200
    assert review.json()["review_id"].startswith("hreview_")

    version = project_client.post(
        f"/projects/{slug}/versions",
        json={"summary": "API snapshot", "created_by": "tester"},
    )
    assert version.status_code == 200
    assert version.json()["version"] == "v0.1"

    status = project_client.get(f"/projects/{slug}")
    assert status.status_code == 200
    checkpoint_types = [item["checkpoint_type"] for item in status.json()["recent_checkpoints"]]
    assert "project_paused" in checkpoint_types
    assert "project_active" in checkpoint_types
    assert status.json()["recent_human_reviews"][0]["decision"] == "continue"

    exported = project_client.post(f"/projects/{slug}/export")
    assert exported.status_code == 200
    assert exported.json()["path"].endswith("project_export.json")
