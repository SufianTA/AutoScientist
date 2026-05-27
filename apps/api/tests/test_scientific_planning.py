from app.services.scientific_planning import (
    build_abstention_assessment,
    build_claim_graph,
    build_evidence_coverage_matrix,
    classify_objective,
    compile_case_profile,
    evaluate_report_against_criteria,
    fallback_evaluation_criteria,
    score_experiment_gates,
    type_evidence_items,
)
from app.services.scientific_strategy import calibrate_scientific_strategy_with_review
from agents.app.langgraph_workflow import LangGraphScientificWorkflow


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
