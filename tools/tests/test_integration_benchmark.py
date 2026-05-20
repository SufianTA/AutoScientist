from tools.run_integration_benchmark import summarize_integrations, value_score


def test_value_score_rewards_executed_integrations_and_provenance() -> None:
    result = {
        "status": "completed",
        "report": {
            "hypothesis": {"title": "Target hypothesis", "text": "Mechanistic hypothesis."},
            "evidence": [
                {"source": "NCBI Gene", "support_score": 0.5},
                {"source": "medea_agent", "support_score": 0.3},
            ],
            "experiments": [{"name": "Perturbation assay"}],
            "guardrails": ["Requires validation."],
            "board_posts": [{"post_type": "hypothesis"}],
        },
        "provenance": {
            "agent_steps": [
                {"state_name": "PLAN_RESEARCH", "output": {"qworld": {"mode": "qworld"}}},
                {"state_name": "LLM_CALL_COMPLETED", "output": {}},
            ],
            "tool_calls": [
                {"tool_name": "medea_agent", "tool_source": "open_scientist", "status": "success"},
                {"tool_name": "ncbi_gene_profile_tool", "tool_source": "live_public_biomedical", "status": "success"},
            ],
        },
    }
    health = {
        "tooluniverse": {"available": True},
        "open_scientist": {
            "qworld": {"available": True},
            "medea": {"available": True},
            "clawinstitute_board": {"available": True},
        },
    }

    integrations = summarize_integrations(result, health)
    assessment = value_score(result, integrations)

    assert integrations["medea"]["executed"] is True
    assert integrations["qworld"]["executed"] is True
    assert integrations["public_biomedical"]["executed"] is True
    assert assessment["score"] >= 85
    assert assessment["checks"]["auditable_trace"] is True
