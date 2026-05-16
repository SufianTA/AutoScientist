from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_inventory_contains_custom_tools() -> None:
    response = client.get("/tools/inventory")
    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["tools"]}
    assert "acvr1_target_profile_tool" in names
    assert "evidence_quality_scorer_tool" in names


def test_tool_health_is_reported() -> None:
    response = client.get("/tools/health")
    assert response.status_code == 200
    assert "tooluniverse" in response.json()
    assert "available" in response.json()["tooluniverse"]


def test_demo_run_generates_report() -> None:
    objective = client.post(
        "/objectives",
        json={
            "title": "ACVR1/FOP therapeutic hypothesis generation",
            "objective": "Generate a therapeutic hypothesis for ACVR1-driven FOP.",
            "constraints": {"require_critic": True},
        },
    )
    assert objective.status_code == 200
    run = client.post("/runs", json={"objective_id": objective.json()["id"], "execute_demo": True})
    assert run.status_code == 200
    run_id = run.json()["id"]
    report = client.get(f"/reports/{run_id}")
    assert report.status_code == 200
    assert "ACVR1" in report.json()["hypothesis"]["title"]
