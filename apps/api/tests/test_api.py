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
    trace = client.get(f"/runs/{run_id}/trace")
    assert trace.status_code == 200
    states = [step["state_name"] for step in trace.json()["steps"]]
    assert "INITIALIZE_FRAMEWORK" in states
    assert "PLAN_RESEARCH" in states
    assert "FIND_TOOLS" in states
    assert "EXECUTE_EVIDENCE_COLLECTION" in states
    assert "SCORE_EVIDENCE" in states


def test_run_estimate_and_queued_submission() -> None:
    estimate = client.post(
        "/runs/estimate",
        json={
            "run_config": {
                "agent_count": 8,
                "max_runtime_minutes": 45,
                "tool_budget_usd": 25,
                "evidence_strictness": "strict",
            }
        },
    )
    assert estimate.status_code == 200
    assert estimate.json()["estimated_cost_usd"] > 0

    objective = client.post(
        "/objectives",
        json={
            "title": "Queued ACVR1/FOP run",
            "objective": "Generate a queued therapeutic hypothesis run for ACVR1-driven FOP.",
            "constraints": {"require_critic": True},
        },
    )
    assert objective.status_code == 200
    run = client.post(
        "/runs",
        json={
            "objective_id": objective.json()["id"],
            "execute_demo": True,
            "run_config": {
                "execution_mode": "queued",
                "agent_count": 4,
                "max_runtime_minutes": 20,
                "tool_budget_usd": 5,
            },
        },
    )
    assert run.status_code == 200
    assert run.json()["status"] == "queued"
    assert run.json()["agent_count"] == 4


def test_background_run_completes() -> None:
    objective = client.post(
        "/objectives",
        json={
            "title": "Background ACVR1/FOP run",
            "objective": "Generate a background therapeutic hypothesis run for ACVR1-driven FOP.",
            "constraints": {"require_critic": True},
        },
    )
    assert objective.status_code == 200
    run = client.post(
        "/runs",
        json={
            "objective_id": objective.json()["id"],
            "execute_demo": True,
            "run_config": {"execution_mode": "background"},
        },
    )
    assert run.status_code == 200
    assert run.json()["status"] in {"queued", "completed"}


def test_billing_checkout_and_ledger() -> None:
    account = client.get("/billing/account")
    assert account.status_code == 200
    starting_balance = account.json()["account"]["balance_usd"]

    checkout = client.post("/billing/checkout", json={"amount_usd": 12.5, "provider": "mock"})
    assert checkout.status_code == 200
    session_id = checkout.json()["checkout_session"]["id"]

    completed = client.post(f"/billing/checkout/{session_id}/complete", json={})
    assert completed.status_code == 200
    assert completed.json()["account"]["balance_usd"] >= starting_balance + 12.5

    ledger = client.get("/billing/ledger")
    assert ledger.status_code == 200
    assert any(entry["entry_type"] == "credit" for entry in ledger.json()["entries"])


def test_inline_run_does_not_require_payment() -> None:
    objective = client.post(
        "/objectives",
        json={
            "title": "Local inline ACVR1/FOP run",
            "objective": "Generate a local inline therapeutic hypothesis run for ACVR1-driven FOP.",
            "constraints": {"require_critic": True},
        },
    )
    run = client.post(
        "/runs",
        json={
            "objective_id": objective.json()["id"],
            "execute_demo": True,
            "run_config": {
                "execution_mode": "inline",
                "agent_count": 2,
                "max_runtime_minutes": 5,
                "tool_budget_usd": 0,
            },
        },
    )
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "completed"
    assert body["payment_status"] == "not_required"
    assert body["account_id"] is None


def test_model_tool_onboarding_generates_tooluniverse_config() -> None:
    response = client.post(
        "/models",
        json={
            "name": "test_evidence_ranker",
            "description": "Ranks evidence snippets for a hypothesis.",
            "provider": "local_http",
            "endpoint_url": "http://localhost:9000/score",
            "api_key_env_var": "LOCAL_EVIDENCE_RANKER_KEY",
        },
    )
    assert response.status_code == 200
    model_tool = response.json()["model_tool"]
    assert model_tool["tooluniverse_config"]["name"] == "test_evidence_ranker"
    assert model_tool["tooluniverse_config"]["type"] == "CustomModelTool"

    listed = client.get("/models")
    assert listed.status_code == 200
    assert any(tool["name"] == "test_evidence_ranker" for tool in listed.json()["model_tools"])


def test_framework_and_provider_metadata() -> None:
    runtimes = client.get("/framework/agent-runtimes")
    assert runtimes.status_code == 200
    assert runtimes.json()["default"] == "langgraph"

    providers = client.get("/framework/llm-providers")
    assert providers.status_code == 200
    provider_ids = {provider["id"] for provider in providers.json()["providers"]}
    assert {"openai", "anthropic", "mock"}.issubset(provider_ids)

    validation = client.get("/framework/llm-providers/mock/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True


def test_openclaw_optional_adapter_trace() -> None:
    objective = client.post(
        "/objectives",
        json={
            "title": "OpenClaw optional adapter trace",
            "objective": "Generate an OpenClaw-adapter trace for ACVR1-driven FOP.",
            "constraints": {"require_critic": True},
        },
    )
    run = client.post(
        "/runs",
        json={
            "objective_id": objective.json()["id"],
            "execute_demo": True,
            "run_config": {
                "execution_mode": "inline",
                "agent_framework": "openclaw",
            },
        },
    )
    assert run.status_code == 200
    trace = client.get(f"/runs/{run.json()['id']}/trace").json()
    framework_step = next(step for step in trace["steps"] if step["state_name"] == "INITIALIZE_FRAMEWORK")
    assert framework_step["output"]["framework"] == "openclaw"
    assert framework_step["output"]["mode"] == "optional_adapter_placeholder"
