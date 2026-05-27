from app.services.scientific_planning import (
    build_abstention_assessment,
    build_claim_graph,
    build_claim_retrieval_plan,
    build_evidence_coverage_matrix,
    build_quality_dashboard,
    classify_objective,
    compile_case_profile,
    evaluate_report_against_criteria,
    fallback_evaluation_criteria,
    map_evidence_to_claims,
    score_experiment_gates,
    type_evidence_items,
)
from app.services.scientific_strategy import calibrate_scientific_strategy_with_review
from agents.app.langgraph_workflow import LangGraphScientificWorkflow
from agents.app.state import ResearchRunState


def test_objective_classifier_routes_therapeutic_safety_to_txagent() -> None:
    classification = classify_objective(
        "Assess drug contraindications and dosage safety for ACVR1-driven FOP.",
        {"primary_genes": ["ACVR1"], "diseases": ["FOP"], "candidate_interventions": ["palovarotene"]},
    ).model_dump()

    assert classification["primary_task"] == "therapeutic_reasoning"
    assert "drug_safety" in classification["task_types"]
    assert "txagent" in classification["required_capabilities"]
    assert "qworld" not in classification["required_capabilities"]
    assert classification["risk_level"] == "high"


def test_objective_classifier_routes_omics_to_public_biomedical_context() -> None:
    classification = classify_objective(
        "Nominate a target from single-cell transcriptomics for rheumatoid arthritis synovial fibroblasts.",
        {"primary_genes": [], "diseases": ["rheumatoid arthritis"]},
    ).model_dump()

    assert "omics_analysis" in classification["task_types"]
    assert "public_biomedical" in classification["required_capabilities"]
    assert "tooluniverse" in classification["required_capabilities"]


def test_workflow_heuristic_extracts_lowercase_public_benchmark_diseases() -> None:
    workflow = LangGraphScientificWorkflow()

    context = workflow._heuristic_context(
        "Design the next experiments to test a bounded CFTR hypothesis in cystic fibrosis; "
        "include expected information gain, failure modes, provenance, and public evidence requirements."
    )

    assert context["primary_genes"] == ["CFTR"]
    assert context["diseases"] == ["cystic fibrosis"]


def test_workflow_rejects_serialized_context_as_pubmed_query() -> None:
    workflow = LangGraphScientificWorkflow()

    context = workflow._normalize_context(
        {
            "primary_genes": ["TNF"],
            "diseases": ["rheumatoid arthritis"],
            "pubmed_queries": ['{"primary_genes": ["TNF"], "diseases": ["rheumatoid arthritis"]}'],
        },
        "Assess TNF in rheumatoid arthritis using public evidence.",
    )

    assert context["pubmed_queries"]
    assert all(not query.strip().startswith("{") for query in context["pubmed_queries"])
    assert context["pubmed_queries"][0].startswith("TNF rheumatoid arthritis")


def test_workflow_cleans_llm_task_fragments_from_disease_entities() -> None:
    workflow = LangGraphScientificWorkflow()

    context = workflow._normalize_context(
        {
            "primary_genes": ["EGFR"],
            "diseases": ["EGFR-mutant NSCLC and produce a ranked", "non-small cell lung cancer"],
            "candidate_interventions": ["osimertinib"],
            "pubmed_queries": [],
        },
        "Analyze EGFR-mutant NSCLC and produce a ranked resistance strategy.",
    )

    assert context["diseases"][0] == "non-small cell lung cancer"
    assert all("produce" not in disease for disease in context["diseases"])


def test_workflow_splits_composite_cancer_disease_entities() -> None:
    workflow = LangGraphScientificWorkflow()

    context = workflow._normalize_context(
        {
            "primary_genes": ["RET"],
            "diseases": ["papillary thyroid cancer and RET-mutant medullary thyroid cancer"],
            "candidate_interventions": ["selpercatinib"],
            "pubmed_queries": [],
        },
        "Review RET in papillary thyroid cancer and RET-mutant medullary thyroid cancer.",
    )

    assert context["diseases"] == ["papillary thyroid cancer", "medullary thyroid cancer"]


def test_workflow_filters_disease_acronyms_from_gene_entities() -> None:
    workflow = LangGraphScientificWorkflow()

    context = workflow._normalize_context(
        {
            "primary_genes": ["EGFR", "NSCLC", "C797S", "T790M"],
            "diseases": ["NSCLC"],
            "candidate_interventions": ["osimertinib"],
            "pubmed_queries": [],
        },
        "Analyze EGFR-mutant NSCLC with C797S and T790M resistance.",
    )

    assert "NSCLC" not in context["primary_genes"]
    assert "C797S" not in context["primary_genes"]
    assert "T790M" not in context["primary_genes"]
    assert context["variants"] == ["C797S", "T790M"]
    assert context["diseases"][0] == "non-small cell lung cancer"


def test_workflow_merges_benchmark_task_context_into_entities() -> None:
    workflow = LangGraphScientificWorkflow()

    context = workflow._merge_configured_benchmark_context(
        {
            "primary_genes": [],
            "diseases": [],
            "candidate_interventions": [],
            "pathways": [],
            "pubmed_queries": [],
            "analysis_goal": "Explain mechanism and safety.",
        },
        {
            "benchmark_task": {
                "id": "il6_rheumatoid_arthritis__mechanism_safety_review__r1",
                "gene_symbol": "IL6",
                "disease_name": "rheumatoid arthritis",
                "expected_capabilities": ["public_biomedical", "tooluniverse"],
            }
        },
    )

    assert context["primary_genes"] == ["IL6"]
    assert context["diseases"] == ["rheumatoid arthritis"]
    assert any(query.startswith("IL6 rheumatoid arthritis") for query in context["pubmed_queries"])
    assert context["benchmark_task"]["expected_capabilities"] == ["public_biomedical", "tooluniverse"]


def test_evidence_claim_abstention_and_report_evaluation_flow() -> None:
    evidence = type_evidence_items(
        [
            {
                "source": "local_objective_context",
                "text": "The objective mentions ACVR1 and FOP, but no external evidence was retrieved.",
                "structured": {},
            }
        ]
    )
    hypothesis = {
        "hypothesis": "Modulating ACVR1-linked mechanisms may be relevant to FOP as a candidate hypothesis."
    }
    claim_graph = build_claim_graph(hypothesis, evidence)
    classification = classify_objective("Generate a therapeutic hypothesis for ACVR1-driven FOP.").model_dump()
    abstention = build_abstention_assessment(classification, evidence, claim_graph)
    criteria = fallback_evaluation_criteria("Generate a therapeutic hypothesis for ACVR1-driven FOP.", classification)
    evaluation = evaluate_report_against_criteria(
        {
            "title": "ACVR1 / FOP Candidate Hypothesis Report",
            "summary": hypothesis["hypothesis"],
            "guardrails": ["Candidate hypothesis only.", "Requires experimental validation."],
            "next_experiments": [{"name": "cell assay"}],
        },
        criteria,
    )

    assert evidence[0]["evidence_type"] == "local_context"
    assert claim_graph["claims"][0]["evidence_gaps"] == ["local_objective_context"]
    assert abstention["abstention_required"] is True
    assert evaluation["total_points"] > 0
    assert 0 <= evaluation["score"] <= 1


def test_case_profile_coverage_and_experiment_gate_scoring_for_complex_oncology_case() -> None:
    objective = (
        "Analyze EGFR-mutant NSCLC osimertinib resistance with C797S/T790M phasing, "
        "MET amplification, ERBB2 fusion bypass, AXL EMT state transition, ctDNA, "
        "paired biopsy, CNS sanctuary, safety caveats, and validation experiments."
    )
    classification = classify_objective(
        objective,
        {"primary_genes": ["EGFR"], "diseases": ["non-small cell lung carcinoma"]},
    ).model_dump()
    profile = compile_case_profile(objective, classification, {"primary_genes": ["EGFR"]})

    assert profile["schema"] == "autosci.case_profile.v0.1"
    assert "C797S" in profile["entities"]["variants"]
    assert "T790M" in profile["entities"]["variants"]
    assert "C797S" not in profile["entities"]["genes"]
    branch_ids = {branch["id"] for branch in profile["mechanism_branches"]}
    assert {"on_target_variant", "rtk_bypass", "cell_state", "anatomic_pharmacologic"}.issubset(branch_ids)
    assert "ctDNA clone structure and cis/trans phasing" in profile["validation_assays"]

    evidence = type_evidence_items(
        [
            {"source": "PubMed", "text": "PMID record on EGFR C797S and MET amplification resistance.", "structured": {}},
            {"source": "OpenTargets", "text": "OpenTargets EGFR non-small cell lung carcinoma association.", "structured": {}},
            {"source": "openFDA", "text": "Safety and adverse event context for combination therapy.", "structured": {}},
        ]
    )
    claim_graph = build_claim_graph({"hypothesis": "EGFR resistance is heterogeneous and requires gated validation."}, evidence)
    coverage = build_evidence_coverage_matrix(profile, evidence, claim_graph)

    assert coverage["schema"] == "autosci.evidence_coverage_matrix.v0.1"
    assert coverage["coverage_score"] > 0
    assert any(row["status"] in {"covered", "partial"} for row in coverage["requirements"])

    gated = score_experiment_gates(
        [
            {
                "name": "ctDNA clone phasing with matched paired-biopsy validation controls",
                "type": "clinical_translational",
                "cost": "medium",
                "feasibility": "medium",
                "expected_information_gain": "very_high",
                "decision_gate": "Advance if clone phasing distinguishes driver from bystander resistance.",
                "success_criteria": ["Positive and negative controls pass."],
                "failure_modes": ["No resistant clone is detectable."],
            }
        ],
        profile,
        coverage,
    )

    assert gated[0]["decision_impact_score"] > 0.5
    assert gated[0]["gate_quality"] in {"usable", "strong"}


def test_claim_retrieval_plan_and_matrix_are_entity_driven_not_case_constants() -> None:
    objective = (
        "Analyze ALK fusion lung adenocarcinoma resistance after alectinib with compound mutations, "
        "bypass signaling, safety caveats, and validation experiments."
    )
    context = {
        "primary_genes": ["ALK"],
        "diseases": ["lung adenocarcinoma"],
        "candidate_interventions": ["alectinib"],
        "variants": ["G1202R"],
    }
    classification = classify_objective(objective, context).model_dump()
    profile = compile_case_profile(objective, classification, context)
    plan = build_claim_retrieval_plan(objective, classification, profile, context)

    assert plan["schema"] == "autosci.claim_retrieval_plan.v0.1"
    assert any("ALK" in claim["query"] for claim in plan["claims"])
    assert any(claim["claim_type"] == "variant_or_biomarker" for claim in plan["claims"])
    assert not any("EGFR" in claim["query"] for claim in plan["claims"])

    evidence = type_evidence_items(
        [
            {
                "source": "PubMed: ALK G1202R lung adenocarcinoma variant resistance biomarker",
                "text": "ALK G1202R is discussed as a resistance mutation in lung adenocarcinoma literature.",
                "score": {"label": "strong_support"},
                "structured": {},
            },
            {
                "source": "ClinicalTrials.gov: alectinib lung adenocarcinoma ALK",
                "text": "Clinical trial records provide clinical context for alectinib in ALK positive disease.",
                "score": {"label": "weak_support"},
                "structured": {},
            },
        ]
    )
    matrix = map_evidence_to_claims(evidence, plan, {})

    assert matrix["planned_claim_count"] == len(plan["claims"])
    assert matrix["coverage_score"] > 0
    assert any(row["support_status"] in {"covered", "partial"} for row in matrix["claims"])


def test_quality_dashboard_summarizes_relevance_tools_claims_and_flags() -> None:
    evidence = [
        {"source": "PubMed: ALK", "text": "relevant", "score": {"label": "strong_support"}},
        {"source": "PubMed: broad", "text": "off topic", "score": {"label": "irrelevant"}},
    ]
    dashboard = build_quality_dashboard(
        evidence=evidence,
        tool_outputs=[
            {"tool_name": "pubmed_literature_search_tool", "result": {"status": "success"}},
            {"tool_name": "clinical_trials_search_tool", "result": {"status": "failure"}},
        ],
        claim_matrix={"coverage_score": 0.5, "covered_count": 0, "partial_count": 1, "missing_count": 1},
        evidence_coverage={"coverage_score": 0.25, "covered_count": 0, "partial_count": 1, "missing_count": 2},
        scientific_strategy={"readiness": {"score": 55, "tier": "experiment_ready_with_gaps"}},
        critique={"severity": "high"},
        experiments=[{"gate_quality": "strong"}, {"gate_quality": "weak"}],
    )

    assert dashboard["schema"] == "autosci.quality_dashboard.v0.1"
    assert dashboard["evidence"]["relevance_rate"] == 0.5
    assert dashboard["tools"]["success_rate"] == 0.5
    assert dashboard["claims"]["missing"] == 1
    assert dashboard["experiments"]["strong"] == 1
    assert dashboard["flags"]


def test_evidence_coverage_matrix_does_not_count_irrelevant_broad_matches() -> None:
    profile = {
        "evidence_requirements": [
            {"id": "safety", "label": "Safety and toxicity context", "sources": ["openFDA", "PubMed"]},
            {"id": "fusion_copy_number", "label": "Fusion and copy-number detection", "sources": ["ctDNA", "NGS"]},
        ]
    }
    evidence = [
        {
            "source": "ClinicalTrials.gov: EGFR osimertinib",
            "text": "Clinical trial record mentioning therapy but no adverse events or copy-number assay.",
            "score": {"label": "irrelevant"},
        },
        {
            "source": "PubMed: EGFR safety",
            "text": "Safety and tolerability adverse event context for osimertinib combination therapy.",
            "score": {"label": "safety_concern"},
        },
    ]

    coverage = build_evidence_coverage_matrix(profile, evidence, {})
    statuses = {row["id"]: row["status"] for row in coverage["requirements"]}

    assert statuses["safety"] == "partial"
    assert statuses["fusion_copy_number"] == "missing"
    assert coverage["coverage_score"] == 0.25


def test_readiness_calibration_caps_high_severity_reviewer_overclaims() -> None:
    strategy = {
        "readiness": {"score": 89, "tier": "validation_ready", "rationale": "No major gaps."},
        "gaps": [],
        "next_action": {"action": "prepare_validation_plan"},
    }
    evidence = [
        {"source": f"source-{idx}", "score": {"label": "irrelevant" if idx < 3 else "strong_support"}}
        for idx in range(10)
    ]

    calibrated = calibrate_scientific_strategy_with_review(
        strategy,
        evidence=evidence,
        critique={
            "severity": "high",
            "critique": "Quantitative claims exceed direct supporting evidence.",
        },
        abstention_policy={"decision": "support", "abstention_required": False},
        biotruth_critic={"verdict": "support", "weighted_score": 78},
        actionability_profile={"actionability": "medium"},
    )

    assert calibrated["readiness"]["uncalibrated_score"] == 89
    assert calibrated["readiness"]["score"] < 82
    assert calibrated["readiness"]["tier"] == "experiment_ready_with_gaps"
    assert {gap["id"] for gap in calibrated["gaps"]} >= {
        "reviewer_high_severity_concern",
        "evidence_relevance_noise",
    }


def test_critic_enforcement_rewrites_stale_established_target_framing() -> None:
    workflow = LangGraphScientificWorkflow()
    state = ResearchRunState(
        run_id="r1",
        objective_id="o1",
        objective="Review EGFR resistance mechanisms in non-small cell lung cancer.",
    )
    state.context["biomedical_context"] = {
        "primary_genes": ["EGFR"],
        "diseases": ["non-small cell lung cancer"],
    }
    state.context["case_profile"] = {"evidence_requirements": []}
    state.evidence = [
        {
            "source": "OpenTargets",
            "text": "EGFR non-small cell lung cancer association.",
            "structured": {
                "public_labels": {
                    "open_targets_association_status": "matched",
                    "open_targets_association_score": 0.888,
                    "pubmed_gene_disease_count": 5000,
                }
            },
            "score": {"label": "strong_support", "evidence_type": "target_disease_association"},
        },
        {
            "source": "Drug record",
            "text": "Approved drug clinical precedence.",
            "structured": {
                "evidence_type": "clinical_precedence",
                "positive_tractability": [{"value": True}],
            },
            "score": {"label": "mechanistic_relevance", "evidence_type": "clinical_precedence"},
        },
    ]
    state.hypothesis_card = {
        "title": "EGFR candidate review",
        "hypothesis": "EGFR remains an early or insufficiently established hypothesis for non-small cell lung cancer.",
        "confidence": 0.81,
        "clinical_status": {
            "status": "established_or_clinically_precedented",
            "confidence_floor": 0.72,
        },
    }
    state.critique = {
        "severity": "high",
        "critique": "The framing is contradictory and understates established clinical evidence.",
        "recommended_fix": "Reframe as clinically validated and focus on resistance.",
        "claim_boundary": "established clinical-precedence context",
    }

    workflow._enforce_critique_on_hypothesis(state)

    assert "early or insufficiently established" not in state.hypothesis_card["hypothesis"]
    assert "not as a new target discovery" in state.hypothesis_card["hypothesis"]
    assert state.context["critique_enforced_revision"]["previous"]["hypothesis"].startswith("EGFR remains")
    assert state.hypothesis_card["claim_graph"]["claims"]

    state.report = {
        "title": "Stale report",
        "summary": "EGFR remains an early or insufficiently established hypothesis for non-small cell lung cancer.",
        "confidence": 0.81,
    }
    workflow._enforce_critique_lock_on_report(state)

    assert "early or insufficiently established" not in state.report["summary"]
    assert state.report["critique_repair_lock"]["applied"] is True


def test_llm_irrelevant_pubmed_label_gets_conservative_relevance_floor() -> None:
    workflow = LangGraphScientificWorkflow()
    state = ResearchRunState(
        run_id="r1",
        objective_id="o1",
        objective="Review RET fusion papillary thyroid cancer resistance.",
    )
    state.context["biomedical_context"] = {
        "primary_genes": ["RET"],
        "diseases": ["papillary thyroid cancer"],
    }
    item = {
        "source": "PubMed: RET papillary thyroid cancer mechanism pathway resistance signaling",
        "text": (
            "RET Signaling Pathway in Human Cancer: Oncogenic Mechanisms, Selective Inhibitors, "
            "and Emerging Resistance Strategies.; Molecular pathogenesis and therapeutic advances "
            "in RET fusion-positive papillary thyroid carcinoma."
        ),
        "structured": {"articles": [{"title": "RET fusion-positive papillary thyroid carcinoma resistance mechanisms"}]},
    }

    repaired = workflow._apply_relevance_floor(
        item,
        {"label": "irrelevant", "score": 0.2, "warnings": []},
        state,
    )

    assert repaired["label"] in {"mechanistic_relevance", "weak_support", "strong_support"}
    assert repaired["score"] >= 0.52
