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


def test_actionability_treats_target_level_tractability_as_tentative_without_disease_efficacy() -> None:
    result = assess_actionability(
        task={"gene_symbol": "TARGETX", "disease_name": "intestinal disease"},
        evidence=[
            {
                "source": "Open Targets target tractability",
                "text": (
                    "Open Targets target metadata for TARGETX reports clinical or tractability precedence: "
                    "Approved Drug (SM). This is target-level precedence and must be separated from "
                    "disease-specific efficacy claims for intestinal disease."
                ),
                "evidence_type": "target_metadata",
            },
            {
                "source": "PubMed",
                "text": "Human genetic variant evidence links TARGETX to intestinal disease susceptibility.",
                "evidence_type": "literature",
            },
        ],
        evidence_hierarchy={"high_tier_evidence_count": 2, "hierarchy_score": 60},
        contradiction_analysis={"finding_count": 0},
    )

    assert result["level"] == "moderate"
    assert result["recommended_decision"] == "tentative_only"
    assert result["profile"]["disease_specific_positive_intervention_count"] == 0


def test_actionability_distinguishes_safety_limitations_from_direct_negative_efficacy() -> None:
    result = assess_actionability(
        task={"gene_symbol": "TARGETY", "disease_name": "cancer"},
        evidence=[
            {
                "source": "PubMed",
                "text": "TARGETY inhibitor therapy improved response in cancer clinical trial cohorts.",
                "evidence_type": "clinical_precedence",
            },
            {
                "source": "ClinicalTrials.gov",
                "text": "A completed phase 3 interventional study reported effective TARGETY antibody treatment in cancer.",
                "evidence_type": "clinical_precedence",
            },
            {
                "source": "openFDA adverse events",
                "text": "openFDA returned adverse-event reports for TARGETY inhibitor; these are safety signals, not causal proof.",
                "evidence_type": "safety_context",
            },
        ],
        evidence_hierarchy={"high_tier_evidence_count": 2, "hierarchy_score": 75},
        contradiction_analysis={"finding_count": 1, "findings": [{"category": "safety"}]},
    )

    assert result["level"] == "high"
    assert result["recommended_decision"] == "support_allowed"
    assert result["profile"]["safety_signal_count"] == 1


def test_actionability_marks_direct_negative_translation_as_conflicting() -> None:
    result = assess_actionability(
        task={"gene_symbol": "TARGETZ", "disease_name": "neuro disease"},
        evidence=[
            {
                "source": "PubMed",
                "text": "TARGETZ therapy showed no benefit in neuro disease and did not improve clinical endpoints.",
                "evidence_type": "clinical_precedence",
            },
            {
                "source": "PubMed",
                "text": "A controversial TARGETZ program in neuro disease reported misclassification concerns.",
                "evidence_type": "literature",
            },
        ],
        evidence_hierarchy={"high_tier_evidence_count": 1, "hierarchy_score": 55},
        contradiction_analysis={
            "finding_count": 1,
            "findings": [{"category": "negative_evidence"}],
        },
    )

    assert result["level"] == "conflicting"
    assert result["recommended_decision"] == "conflicting"
    assert "clinical_failure_or_translation_limitation_present" in result["reasons"]


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


def test_actionability_ignores_counterevidence_terms_from_search_placeholders() -> None:
    features = classify_actionability_item(
        {
            "source": "PubMed: TARGET5 disease failed trial not associated",
            "text": "PubMed returned live literature search results for TARGET5 disease failed trial not associated.",
            "evidence_type": "literature",
        },
        gene="target5",
        disease="disease",
    )

    assert features["negative_signal_count"] == 0
    assert features["query_only_counterevidence_context_count"] == 1


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
