from types import SimpleNamespace

from tools.run_autoscientist_bench import (
    apply_ablation,
    benchmark_run_config,
    benchmark_value_score,
    evaluate_realness_gates,
    expand_tasks,
    load_manifest,
    validate_runtime_request,
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
        "offline_public_context": False,
        "qworld_model": "",
        "qworld_api_key_env_var": "",
        "disable_qworld": True,
        "require_real_llm": False,
        "medea_python": "",
        "disable_medea": True,
        "medea_smoke_only": True,
        "forbid_medea_smoke": False,
        "medea_debate_rounds": 0,
        "medea_timeout_seconds": 120,
        "medea_subprocess_timeout_seconds": 30,
        "enable_sciflow_policy": True,
        "sciflow_policy_model_id": "",
        "sciflow_policy_model_path": "",
        "sciflow_policy_min_score": 0.15,
        "strict_real_run": False,
        "train_neural_policy": False,
        "min_full_completion_rate": 0.0,
        "min_full_mean_score": 0.0,
        "require_full_integrations": [],
        "require_expected_integrations": False,
        "min_neural_holdout_top1": 0.0,
        "min_state_graph_nodes": 0,
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


def test_manifest_can_target_medea_case_and_template() -> None:
    manifest = load_manifest()

    tasks = expand_tasks(
        manifest,
        limit=3,
        offline_public_context=True,
        case_ids=["il6_rheumatoid_arthritis"],
        template_ids=["experiment_design"],
    )

    assert len(tasks) == 1
    assert tasks[0]["case_id"] == "il6_rheumatoid_arthritis"
    assert tasks[0]["template_id"] == "experiment_design"
    assert "medea" in tasks[0]["expected_capabilities"]


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


def test_realness_gates_fail_missing_expected_medea() -> None:
    args = _args(require_expected_integrations=True)
    result = {
        "ablation": "full",
        "status": "completed",
        "run_id": "run_1",
        "task": {"id": "task_1", "expected_capabilities": ["medea", "tooluniverse", "sciflow_policy"]},
        "artifact_path": "task_1.json",
        "integrations": {
            "medea": {"executed": False},
            "tooluniverse": {"executed": True},
            "public_biomedical": {"executed": True},
            "local_board": {"executed": True},
        },
        "replay": {"available": True},
        "sciflow_policy": {"status": "success"},
        "value_assessment": {"score": 95},
    }
    summary = {
        "summary_by_ablation": {
            "full": {"runs": 1, "completed": 1, "mean_score": 95},
        },
        "neural_policy": {"metrics": {"top1_holdout_accuracy": 0.8}},
        "state_graph": {"summary": {"nodes": 10}},
        "package": {"zip_path": "policy.zip"},
    }

    gates = evaluate_realness_gates(summary, [result], args)

    assert gates["passed"] is False
    assert gates["result_failures"][0]["missing"] == ["medea"]


def test_strict_real_request_rejects_smoke_medea() -> None:
    args = _args(
        strict_real_run=True,
        llm_provider="anthropic",
        require_real_llm=True,
        disable_medea=False,
        medea_python="/opt/medea-py310/bin/python",
        medea_smoke_only=True,
        train_neural_policy=True,
    )

    try:
        validate_runtime_request(args)
    except SystemExit as exc:
        assert "Medea smoke mode is not allowed" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("strict real validation should reject smoke-mode Medea")
