from __future__ import annotations

from agents.app.langgraph_workflow import LangGraphScientificWorkflow
from agents.app.state import ResearchRunState
from app.services.abstention_policy import evaluate_abstention_policy
from app.services.contradiction_detector import build_contradiction_queries, detect_contradictions


def test_build_contradiction_queries_uses_target_and_disease() -> None:
    queries = build_contradiction_queries({"gene_symbol": "BRAF", "disease_name": "melanoma"})

    assert "BRAF melanoma failed trial" in queries
    assert "BRAF melanoma no association" in queries
    assert "BRAF melanoma adverse toxicity" in queries


def test_detect_contradictions_flags_negative_and_safety_evidence() -> None:
    result = detect_contradictions(
        task={"gene_symbol": "EGFR", "disease_name": "lung adenocarcinoma"},
        evidence=[
            {
                "source": "PubMed",
                "text": "A failed trial showed no benefit and adverse toxicity.",
                "evidence_type": "literature",
            }
        ],
        tool_calls=[{"tool_name": "pubmed", "input": {"query": "EGFR lung failed trial"}}],
    )

    assert result["schema"] == "autosci.contradiction_analysis.v0.1"
    assert result["finding_count"] == 1
    assert result["contradiction_search_attempted"] is True
    assert result["coverage"]["negative_evidence"] is True


def test_detect_contradictions_ignores_query_terms_without_substantive_negative_text() -> None:
    result = detect_contradictions(
        task={"gene_symbol": "NOD2", "disease_name": "Crohn disease"},
        evidence=[
            {
                "source": "PubMed: NOD2 Crohn disease failed trial not associated",
                "text": "PubMed returned live literature search results for NOD2 Crohn disease failed trial not associated.",
                "evidence_type": "literature",
            }
        ],
        tool_calls=[{"tool_name": "pubmed", "input": {"query": "NOD2 Crohn disease failed trial"}}],
    )

    assert result["finding_count"] == 0
    assert result["contradiction_search_attempted"] is True


def test_detect_contradictions_reports_incomplete_search_when_absent() -> None:
    result = detect_contradictions(
        task={"gene_symbol": "IL6", "disease_name": "rheumatoid arthritis"},
        evidence=[{"source": "PubMed", "text": "IL6 rheumatoid arthritis literature."}],
        tool_calls=[],
    )

    assert result["finding_count"] == 0
    assert result["contradiction_search_attempted"] is False
    assert result["interpretation"] == "contradiction search coverage is incomplete"


def test_abstention_policy_support_allowed_for_strong_clean_case() -> None:
    result = evaluate_abstention_policy(
        critic={"verdict": "support", "weighted_score": 82},
        evidence_hierarchy={"evidence_count": 4, "high_tier_evidence_count": 2, "weak_only": False, "hierarchy_score": 70},
        contradiction_analysis={"finding_count": 0, "contradiction_search_attempted": True},
        existing_abstention={"reasons": []},
    )

    assert result["schema"] == "autosci.abstention_policy.v0.3"
    assert result["decision"] == "support_allowed"
    assert result["abstention_required"] is False


def test_abstention_policy_downgrades_when_actionability_is_only_tentative() -> None:
    result = evaluate_abstention_policy(
        critic={"verdict": "support", "weighted_score": 86},
        evidence_hierarchy={"evidence_count": 8, "high_tier_evidence_count": 3, "weak_only": False, "hierarchy_score": 70},
        contradiction_analysis={"finding_count": 0, "contradiction_search_attempted": True},
        actionability_profile={
            "level": "moderate",
            "recommended_decision": "tentative_only",
            "reasons": ["no_disease_specific_intervention_evidence"],
        },
        existing_abstention={"reasons": []},
    )

    assert result["decision"] == "tentative_only"
    assert "no_disease_specific_intervention_evidence" in result["reasons"]


def test_abstention_policy_abstains_for_weak_or_empty_case() -> None:
    result = evaluate_abstention_policy(
        critic={"verdict": "abstain", "weighted_score": 25},
        evidence_hierarchy={"evidence_count": 0, "high_tier_evidence_count": 0, "weak_only": False, "hierarchy_score": 0},
        contradiction_analysis={"finding_count": 0, "contradiction_search_attempted": False},
        existing_abstention={"reasons": ["Only local planning context or absence-of-evidence records are available."]},
    )

    assert result["decision"] == "abstain"
    assert result["abstention_required"] is True
    assert "no_evidence" in result["reasons"]
    assert "contradiction_search_incomplete" in result["reasons"]


def test_abstention_policy_marks_unresolved_counterevidence_as_conflicting() -> None:
    result = evaluate_abstention_policy(
        critic={"verdict": "weak_support", "weighted_score": 65},
        evidence_hierarchy={"evidence_count": 5, "high_tier_evidence_count": 1, "weak_only": False, "hierarchy_score": 60},
        contradiction_analysis={"finding_count": 2, "contradiction_search_attempted": True},
        existing_abstention={"reasons": []},
    )

    assert result["decision"] == "conflicting"
    assert result["claim_boundary"].startswith("conflicting evidence")


def test_abstention_policy_abstains_when_public_target_disease_support_is_absent() -> None:
    result = evaluate_abstention_policy(
        critic={"verdict": "weak_support", "weighted_score": 86},
        evidence_hierarchy={
            "evidence_count": 38,
            "high_tier_evidence_count": 16,
            "weak_only": False,
            "hierarchy_score": 60.96,
        },
        contradiction_analysis={
            "finding_count": 4,
            "categories": ["context_mismatch", "safety"],
            "contradiction_search_attempted": True,
        },
        actionability_profile={
            "level": "high",
            "recommended_decision": "support_allowed",
            "profile": {
                "disease_specific_positive_intervention_count": 2,
                "structured_positive_intervention_count": 1,
                "query_only_clinical_context_count": 3,
                "query_only_counterevidence_context_count": 1,
            },
            "reasons": [
                "clinical_terms_appear_in_query_context",
                "counterevidence_terms_appear_in_query_context",
                "safety_signals_require_translation_caution",
            ],
        },
        public_labels={
            "open_targets_association_status": "not_found",
            "open_targets_association_score": None,
            "open_targets_association_rank": None,
            "pubmed_gene_disease_count": 235,
            "evidence_availability": "low",
        },
    )

    assert result["decision"] == "abstain"
    assert "public_target_disease_support_absent" in result["reasons"]
    assert "open_targets_target_disease_not_matched" in result["reasons"]


def test_abstention_policy_only_downgrades_when_public_support_is_weak_but_not_absent() -> None:
    result = evaluate_abstention_policy(
        critic={"verdict": "support", "weighted_score": 82},
        evidence_hierarchy={
            "evidence_count": 12,
            "high_tier_evidence_count": 4,
            "weak_only": False,
            "hierarchy_score": 58,
        },
        contradiction_analysis={"finding_count": 0, "contradiction_search_attempted": True},
        actionability_profile={
            "level": "high",
            "recommended_decision": "support_allowed",
            "profile": {
                "disease_specific_positive_intervention_count": 1,
                "structured_positive_intervention_count": 0,
            },
            "reasons": [],
        },
        public_labels={
            "open_targets_association_status": "not_found",
            "evidence_availability": "moderate",
            "pubmed_gene_disease_count": 1200,
        },
    )

    assert result["decision"] == "tentative_only"
    assert "public_target_disease_support_weak" in result["reasons"]


def test_workflow_enforces_abstention_on_hypothesis_and_report() -> None:
    workflow = LangGraphScientificWorkflow()
    state = ResearchRunState(
        run_id="run_test",
        objective_id="obj_test",
        objective="Evaluate whether EGFR is a credible therapeutic target for rheumatoid arthritis.",
    )
    state.context["biomedical_context"] = {
        "primary_genes": ["EGFR"],
        "diseases": ["rheumatoid arthritis"],
    }
    state.context["abstention_policy"] = {
        "decision": "abstain",
        "abstention_required": True,
        "claim_boundary": "insufficient-evidence response; abstain from target-disease support claim",
        "reasons": ["public_target_disease_support_absent", "open_targets_target_disease_not_matched"],
    }
    state.hypothesis_card = {
        "title": "EGFR candidate target",
        "hypothesis": "EGFR is a candidate therapeutic target for rheumatoid arthritis.",
        "confidence": 0.72,
        "status": "candidate",
    }
    state.report = {
        "title": "EGFR / rheumatoid arthritis Candidate Hypothesis Report",
        "summary": "EGFR is a candidate target.",
        "confidence": 0.72,
        "guardrails": ["Candidate hypothesis only."],
    }

    workflow._enforce_abstention_on_report(state)

    assert state.hypothesis_card["status"] == "abstained"
    assert state.hypothesis_card["confidence"] <= 0.2
    assert "abstains from supporting EGFR" in state.hypothesis_card["hypothesis"]
    assert state.report["decision"] == "abstain"
    assert state.report["confidence"] <= 0.2
    assert "Abstention policy decision `abstain` is enforced." in state.report["guardrails"]


def test_workflow_evidence_batch_scoring_falls_back_after_llm_failure() -> None:
    workflow = LangGraphScientificWorkflow()
    state = ResearchRunState(
        run_id="run_test",
        objective_id="obj_test",
        objective="Evaluate EGFR in non-small cell lung carcinoma.",
    )
    state.context["biomedical_context"] = {
        "primary_genes": ["EGFR"],
        "diseases": ["non-small cell lung carcinoma"],
    }
    state.evidence = [
        {
            "source": "PubMed: EGFR non-small cell lung carcinoma mechanism",
            "text": "EGFR non-small cell lung carcinoma mechanism and treatment response literature.",
        }
    ]

    def fail_llm_json(*args, **kwargs):
        raise RuntimeError("transient SSL failure")

    workflow._llm_json = fail_llm_json  # type: ignore[method-assign]

    scored = workflow._score_evidence_with_llm_batch(
        state,
        {"llm_provider": "anthropic", "llm_model": "claude-sonnet-4-6"},
        "EGFR is relevant to non-small cell lung carcinoma.",
    )

    assert scored[0]["score"]["label"] != ""
    assert "deterministic fallback used" in state.context["warnings"][0]
