from app.services.scientific_planning import (
    build_abstention_assessment,
    build_claim_graph,
    classify_objective,
    evaluate_report_against_criteria,
    fallback_evaluation_criteria,
    type_evidence_items,
)
from agents.app.langgraph_workflow import LangGraphScientificWorkflow


def test_objective_classifier_routes_therapeutic_safety_to_txagent() -> None:
    classification = classify_objective(
        "Assess drug contraindications and dosage safety for ACVR1-driven FOP.",
        {"primary_genes": ["ACVR1"], "diseases": ["FOP"], "candidate_interventions": ["palovarotene"]},
    ).model_dump()

    assert classification["primary_task"] == "therapeutic_reasoning"
    assert "drug_safety" in classification["task_types"]
    assert "txagent" in classification["required_capabilities"]
    assert "qworld" in classification["required_capabilities"]
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
