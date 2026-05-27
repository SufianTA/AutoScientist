from types import SimpleNamespace

from tools.run_integration_benchmark import build_run_config, summarize_integrations, value_score


def _args(**overrides: object) -> SimpleNamespace:
    values = {
        "llm_provider": "auto",
        "llm_api_key_env_var": "",
        "llm_model": "",
        "agent_count": 2,
        "max_runtime_minutes": 5,
        "tool_budget_usd": 1.0,
        "llm_max_tokens": 64,
        "require_real_llm": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_explicit_llm_provider_is_preserved() -> None:
    config = build_run_config(_args(llm_provider="anthropic"))

    assert config["llm_provider"] == "anthropic"
    assert config["llm_model"] == "claude-sonnet-4-6"
    assert config["llm_api_key_env_var"] == "ANTHROPIC_API_KEY"


def test_auto_llm_provider_falls_back_to_mock_without_keys(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    config = build_run_config(_args(llm_provider="auto"))

    assert config["llm_provider"] == "mock"
    assert config["llm_model"] == "mock-scientist"


def test_auto_llm_provider_accepts_anthropic_key_alias(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_KEY", "test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    config = build_run_config(_args(llm_provider="auto"))

    assert config["llm_provider"] == "anthropic"
    assert config["llm_api_key_env_var"] == "ANTHROPIC_KEY"


def test_strategy_repair_config_is_preserved() -> None:
    config = build_run_config(_args(strategy_repair_enabled=False, strategy_repair_max_queries=4))

    assert config["strategy_repair_enabled"] is False
    assert config["strategy_repair_max_queries"] == 4


def test_value_score_rewards_executed_integrations_and_provenance() -> None:
    result = {
        "status": "completed",
        "report": {
            "hypothesis": {"title": "Target hypothesis", "text": "Mechanistic hypothesis."},
            "evidence": [
                {"source": "NCBI Gene", "support_score": 0.5},
                {"source": "Open Targets", "support_score": 0.3},
            ],
            "experiments": [{"name": "Perturbation assay"}],
            "guardrails": ["Requires validation."],
            "board_posts": [{"post_type": "hypothesis"}],
        },
        "provenance": {
            "agent_steps": [
                {"state_name": "PLAN_RESEARCH", "output": {}},
                {"state_name": "LLM_CALL_COMPLETED", "output": {}},
            ],
            "tool_calls": [
                {"tool_name": "opentargets_search", "tool_source": "tooluniverse", "status": "success"},
                {"tool_name": "ncbi_gene_profile_tool", "tool_source": "live_public_biomedical", "status": "success"},
            ],
        },
    }
    health = {
        "tooluniverse": {"available": True},
        "open_scientist": {
            "clawinstitute_board": {"available": True},
        },
    }

    integrations = summarize_integrations(result, health)
    assessment = value_score(result, integrations)

    assert integrations["tooluniverse"]["executed"] is True
    assert integrations["public_biomedical"]["executed"] is True
    assert assessment["score"] >= 85
    assert assessment["checks"]["auditable_trace"] is True
