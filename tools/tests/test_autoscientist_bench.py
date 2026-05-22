from types import SimpleNamespace

from tools.run_autoscientist_bench import (
    apply_ablation,
    benchmark_run_config,
    benchmark_value_score,
    expand_tasks,
    load_manifest,
)


def _args(**overrides: object) -> SimpleNamespace:
    values = {
        "llm_provider": "mock",
        "llm_api_key_env_var": "",
        "llm_model": "mock-scientist",
        "agent_count": 2,
        "max_runtime_minutes": 5,
        "tool_budget_usd": 1.0,
        "llm_max_tokens": 64,
        "qworld_model": "",
        "qworld_api_key_env_var": "",
        "disable_qworld": True,
        "require_real_llm": False,
        "medea_python": "",
        "disable_medea": True,
        "medea_smoke_only": True,
        "medea_debate_rounds": 0,
        "medea_timeout_seconds": 120,
        "medea_subprocess_timeout_seconds": 30,
        "enable_sciflow_policy": True,
        "sciflow_policy_model_id": "",
        "sciflow_policy_model_path": "",
        "sciflow_policy_min_score": 0.15,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_manifest_expands_to_offline_public_tasks() -> None:
    manifest = load_manifest()

    tasks = expand_tasks(manifest, limit=4, replicates_per_case=2, offline_public_context=True)

    assert len(tasks) == 4
    assert tasks[0]["objective"]
    assert tasks[0]["public_context"]["mode"] == "offline"
    assert tasks[0]["gene_symbol"]
    assert tasks[0]["disease_name"]


def test_ablation_config_disables_memory_and_sciflow() -> None:
    config = benchmark_run_config(_args())

    apply_ablation(config, "no_memory")

    assert config["persist_memory_enabled"] is False
    assert config["sciflow_policy_enabled"] is False


def test_ablation_config_disables_public_tools() -> None:
    config = benchmark_run_config(_args(disable_medea=False, medea_python="/tmp/python"))

    apply_ablation(config, "no_public_tools")

    assert config["real_data_enabled"] is False
    assert config["medea_enabled"] is False


def test_benchmark_value_score_adds_public_context_checks() -> None:
    result = {
        "status": "completed",
        "run_id": None,
        "report": {
            "hypothesis": {"title": "Candidate target", "text": "Bounded hypothesis."},
            "evidence": [{"source": "PubMed", "support_score": 0.5}, {"source": "NCBI", "support_score": 0.4}],
            "experiments": [{"name": "Perturbation assay"}],
            "guardrails": ["No clinical claim."],
            "board_posts": [{"post_type": "hypothesis"}],
        },
        "provenance": {
            "agent_steps": [
                {"state_name": "FIND_TOOLS", "output": {"sciflow_policy": {"status": "success"}}},
            ],
            "tool_calls": [{"tool_name": "pubmed_literature_search_tool", "tool_source": "live_public_biomedical"}],
        },
    }
    integrations = {
        "medea": {"executed": False},
        "qworld": {"executed": False},
        "public_biomedical": {"executed": True},
        "tooluniverse": {"executed": False},
        "local_board": {"executed": True},
    }
    task = {
        "public_context": {
            "mode": "live",
            "open_targets_target": {"status": "success"},
            "pubmed_gene_disease": {"status": "success"},
        }
    }

    assessment = benchmark_value_score(result, integrations, task, "full")

    assert assessment["checks"]["controller_advice"] is True
    assert assessment["checks"]["open_targets_context"] is True
    assert assessment["score"] > assessment["base_score"]
