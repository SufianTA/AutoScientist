from __future__ import annotations

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

    assert result["schema"] == "autosci.abstention_policy.v0.2"
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
