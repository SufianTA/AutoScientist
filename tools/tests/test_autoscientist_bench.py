from types import SimpleNamespace

from tools.run_autoscientist_bench import (
    apply_ablation,
    benchmark_run_config,
    benchmark_value_score,
    decision_calibration,
    evaluate_realness_gates,
    extract_strategy_repair,
    expand_tasks,
    load_manifest,
    summarize_result_group,
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


def test_manifest_can_target_specific_case_and_template() -> None:
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
    assert tasks[0]["expected_capabilities"] == ["public_biomedical", "sciflow_policy", "tooluniverse"]


def test_template_expected_capabilities_are_added_to_task() -> None:
    manifest = {
        "task_templates": [
            {
                "id": "omics_task",
                "objective_template": "Analyze {gene_symbol} in {disease_name}.",
                "expected_capabilities": ["public_biomedical"],
            }
        ],
        "seed_cases": [
            {
                "id": "case_1",
                "gene_symbol": "IL6",
                "disease_name": "rheumatoid arthritis",
                "expected_capabilities": ["tooluniverse"],
                "gold_label": "strong_support",
                "expected_decision": "support_allowed",
                "expected_evidence": ["clinical_trials"],
                "public_labels": {"open_targets_association_score": 0.82},
                "benchmark_tags": ["open_targets_matched"],
            }
        ],
        "rubric_path": "benchmarks/biotruth_rubric_v0_1.json",
    }

    tasks = expand_tasks(manifest, offline_public_context=True)

    assert tasks[0]["expected_capabilities"] == ["public_biomedical", "tooluniverse"]
    assert tasks[0]["public_labels"]["open_targets_association_score"] == 0.82
    assert tasks[0]["gold_label"] == "strong_support"
    assert tasks[0]["expected_decision"] == "support_allowed"
    assert tasks[0]["expected_evidence"] == ["clinical_trials"]
    assert tasks[0]["benchmark_tags"] == ["open_targets_matched"]
    assert tasks[0]["rubric_path"] == "benchmarks/biotruth_rubric_v0_1.json"


def test_ablation_config_disables_memory_and_sciflow() -> None:
    config = benchmark_run_config(_args())

    apply_ablation(config, "no_memory")

    assert config["persist_memory_enabled"] is False
    assert config["sciflow_policy_enabled"] is False


def test_ablation_config_disables_public_tools() -> None:
    config = benchmark_run_config(_args())

    apply_ablation(config, "no_public_tools")

    assert config["real_data_enabled"] is False


def test_plain_llm_ablation_disables_runtime_differentiators() -> None:
    config = benchmark_run_config(_args())

    apply_ablation(config, "plain_llm")

    assert config["real_data_enabled"] is False
    assert config["persist_memory_enabled"] is False
    assert config["sciflow_policy_enabled"] is False
    assert config["qworld_enabled"] is False
    assert config["strategy_repair_enabled"] is False


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
                {
                    "state_name": "FIND_TOOLS",
                    "output": {"sciflow_policy": {"status": "success"}},
                },
                {
                    "state_name": "EXECUTE_EVIDENCE_COLLECTION",
                    "output": {
                        "sciflow_policy_application": {
                            "status": "applied",
                            "applied": True,
                            "effects": ["add_policy_followup_pubmed_queries"],
                            "policy_followup_pubmed_queries": ["IL6 rheumatoid arthritis target validation"],
                        }
                    },
                },
            ],
            "tool_calls": [{"tool_name": "pubmed_literature_search_tool", "tool_source": "live_public_biomedical"}],
        },
    }
    integrations = {
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
    assert assessment["checks"]["controller_applied"] is True
    assert assessment["controller_impact"]["applied"] is True
    assert assessment["controller_impact"]["policy_followup_pubmed_queries"]
    assert assessment["checks"]["open_targets_context"] is True
    assert assessment["checks"]["public_context_prefetched"] is True
    assert assessment["checks"]["pubmed_context"] is True
    assert assessment["checks"]["clean_tool_inputs"] is True
    assert assessment["scientific_quality"]["score"] == 79
    assert assessment["score"] == 100


def test_no_public_tools_ablation_is_capped_below_strong_score() -> None:
    result = {
        "status": "completed",
        "run_id": None,
        "report": {
            "hypothesis": {"title": "Candidate target", "text": "Bounded hypothesis."},
            "evidence": [{"source": "local", "support_score": 0.5}, {"source": "local", "support_score": 0.4}],
            "experiments": [{"name": "Perturbation assay"}],
            "guardrails": ["No clinical claim."],
            "board_posts": [{"post_type": "hypothesis"}],
        },
        "provenance": {
            "agent_steps": [{"state_name": "FIND_TOOLS", "output": {"sciflow_policy": {"status": "success"}}}],
            "tool_calls": [{"tool_name": "evidence_quality_scorer_tool", "tool_source": "custom"}],
        },
    }
    integrations = {
        "qworld": {"executed": False},
        "public_biomedical": {"executed": False},
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

    assessment = benchmark_value_score(result, integrations, task, "no_public_tools")

    assert assessment["score"] == 65
    assert assessment["ablation_score_cap"] == 65


def test_benchmark_penalizes_serialized_pubmed_query_inputs() -> None:
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
            "agent_steps": [],
            "tool_calls": [
                {
                    "tool_name": "pubmed_literature_search_tool",
                    "tool_source": "live_public_biomedical",
                    "input": {"query": '{"primary_genes": ["IL6"], "diseases": ["rheumatoid arthritis"]}'},
                }
            ],
        },
    }
    integrations = {
        "qworld": {"executed": False},
        "public_biomedical": {"executed": True},
        "tooluniverse": {"executed": False},
        "local_board": {"executed": True},
    }
    task = {"public_context": {"mode": "offline", "open_targets_target": {}, "pubmed_gene_disease": {}}}

    assessment = benchmark_value_score(result, integrations, task, "full")

    assert assessment["checks"]["clean_tool_inputs"] is False
    assert assessment["scientific_quality"]["checks"]["clean_tool_inputs"] is False


def test_strategy_repair_is_exported_and_summarized() -> None:
    result = {
        "provenance": {
            "agent_steps": [
                {
                    "state_name": "EXECUTE_EVIDENCE_COLLECTION",
                    "output": {
                        "strategy_repair": {
                            "enabled": True,
                            "queries": ["TNF rheumatoid arthritis failed trial"],
                            "executed_count": 1,
                        }
                    },
                }
            ]
        }
    }

    repair = extract_strategy_repair(result)
    summary = summarize_result_group(
        [
            {
                "status": "completed",
                "final_confidence": 0.5,
                "replay": {"available": True},
                "sciflow_policy": {"status": "success"},
                "strategy_repair": repair,
                "report": {"scientific_strategy": {"readiness": {"tier": "validation_ready"}}},
                "integrations": {},
                "value_assessment": {
                    "score": 90,
                    "scientific_quality": {"score": 82},
                    "controller_impact": {
                        "applied": True,
                        "tool_call_count": 3,
                        "evidence_count": 2,
                        "public_biomedical_call_count": 1,
                        "tooluniverse_call_count": 1,
                    },
                },
            }
        ]
    )

    assert repair["executed_count"] == 1
    assert summary["mean_scientific_quality"] == 82
    assert summary["strategy_repair_runs"] == 1
    assert summary["validation_ready_runs"] == 1


def test_decision_calibration_scores_expected_runtime_decisions() -> None:
    calibration = decision_calibration(
        [
            {
                "ablation": "full",
                "run_id": "run_1",
                "task": {"id": "task_1", "expected_decision": "support_allowed"},
                "abstention_policy": {"decision": "support_allowed"},
            },
            {
                "ablation": "full",
                "run_id": "run_2",
                "task": {"id": "task_2", "expected_decision": "tentative_only"},
                "report": {
                    "abstention_policy": {"decision": "support_allowed"},
                    "actionability_profile": {"recommended_decision": "tentative_only"},
                },
            },
        ]
    )

    assert calibration["evaluable_runs"] == 2
    assert calibration["matches"] == 1
    assert calibration["accuracy"] == 0.5
    assert calibration["mismatches"][0]["actionability"] == "tentative_only"


def test_realness_gates_fail_missing_expected_public_tool() -> None:
    args = _args(require_expected_integrations=True)
    result = {
        "ablation": "full",
        "status": "completed",
        "run_id": "run_1",
        "task": {"id": "task_1", "expected_capabilities": ["public_biomedical", "tooluniverse", "sciflow_policy"]},
        "artifact_path": "task_1.json",
        "integrations": {
            "tooluniverse": {"executed": True},
            "public_biomedical": {"executed": False},
            "local_board": {"executed": True},
        },
        "replay": {"available": True},
        "sciflow_policy": {"status": "success"},
        "sciflow_application": {"status": "applied", "applied": True},
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
    assert gates["result_failures"][0]["missing"] == ["public_biomedical"]
