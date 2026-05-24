from __future__ import annotations

from app.services.actionability_assessor import assess_actionability, classify_actionability_item


def test_actionability_allows_support_only_with_disease_specific_intervention_evidence() -> None:
    result = assess_actionability(
        task={"gene_symbol": "TARGET1", "disease_name": "immune disease"},
        evidence=[
            {
                "source": "ClinicalTrials.gov: TARGET1 immune disease",
                "text": "A phase 3 interventional clinical trial tested TARGET1 antibody therapy in immune disease.",
                "evidence_type": "clinical_precedence",
            },
            {
                "source": "Open Targets",
                "text": "TARGET1 immune disease association with approved drug tractability.",
                "evidence_type": "target_disease_association",
            },
        ],
        evidence_hierarchy={"high_tier_evidence_count": 2, "hierarchy_score": 75},
        contradiction_analysis={"finding_count": 0},
    )

    assert result["level"] == "high"
    assert result["recommended_decision"] == "support_allowed"
    assert result["profile"]["disease_specific_intervention_count"] >= 1


def test_actionability_downgrades_association_without_intervention_evidence() -> None:
    result = assess_actionability(
        task={"gene_symbol": "TARGET2", "disease_name": "neuro disease"},
        evidence=[
            {
                "source": "Open Targets genetics",
                "text": "Human GWAS variant evidence links TARGET2 to neuro disease risk.",
                "evidence_type": "target_disease_association",
            },
            {
                "source": "Reactome",
                "text": "TARGET2 neuro disease pathway signaling mechanism evidence.",
            },
        ],
        evidence_hierarchy={"high_tier_evidence_count": 1, "hierarchy_score": 55},
        contradiction_analysis={"finding_count": 0},
    )

    assert result["level"] == "moderate"
    assert result["recommended_decision"] == "tentative_only"
    assert "no_disease_specific_intervention_evidence" in result["reasons"]


def test_actionability_ignores_clinical_terms_that_only_come_from_pubmed_query_context() -> None:
    features = classify_actionability_item(
        {
            "source": "PubMed: TARGET3 rare disease clinical precedence response",
            "text": "PubMed literature search returned records about TARGET3 rare disease mechanism.",
            "evidence_type": "literature",
        },
        gene="target3",
        disease="rare disease",
    )

    assert features["query_only_clinical_context_count"] == 1
    assert features["disease_specific_clinical_count"] == 0


def test_actionability_abstains_without_target_disease_grounding() -> None:
    result = assess_actionability(
        task={"gene_symbol": "TARGET4", "disease_name": "metabolic disease"},
        evidence=[{"source": "PubMed", "text": "Unrelated oncology pathway review."}],
        evidence_hierarchy={"high_tier_evidence_count": 0, "hierarchy_score": 10},
        contradiction_analysis={"finding_count": 0},
    )

    assert result["level"] == "insufficient"
    assert result["recommended_decision"] == "abstain"
    assert "no_target_disease_grounded_evidence" in result["reasons"]
