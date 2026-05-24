from __future__ import annotations

from app.services.biotruth_critic import evaluate_hypothesis


def test_biotruth_critic_supports_strong_target_disease_evidence() -> None:
    result = evaluate_hypothesis(
        task={
            "gene_symbol": "BRAF",
            "disease_name": "melanoma",
            "public_labels": {
                "open_targets_association_status": "matched",
                "open_targets_association_score": 0.82,
                "pubmed_gene_disease_count": 9000,
                "evidence_availability": "high",
            },
        },
        hypothesis={
            "title": "BRAF melanoma target hypothesis",
            "hypothesis": (
                "BRAF inhibition is a candidate therapeutic mechanism in melanoma based on mutation, "
                "MAPK pathway signaling, clinical evidence, approved drugs, and requires validation."
            ),
            "confidence": 0.78,
            "limitations": ["Resistance and safety require review."],
        },
        evidence=[
            {
                "source": "OpenTargets",
                "text": "BRAF has matched target-disease association for melanoma and approved drug tractability.",
                "evidence_type": "target_disease_association",
                "score": {"label": "supports", "evidence_type": "clinical_precedence"},
            },
            {
                "source": "PubMed",
                "text": "Human patient melanoma studies report BRAF mutation and pathway mechanism evidence.",
                "evidence_type": "literature",
                "score": {"label": "supports", "evidence_type": "mechanistic_literature"},
            },
        ],
        tool_calls=[{"tool_name": "opentargets", "status": "success"}],
    )

    assert result["schema"] == "autosci.biotruth_critic.v0.1"
    assert result["verdict"] == "support"
    assert result["weighted_score"] >= 75
    assert result["dimension_scores"]["disease_relevance"] >= 4
    assert not result["abstention_reasons"]


def test_biotruth_critic_abstains_on_empty_evidence() -> None:
    result = evaluate_hypothesis(
        task={"gene_symbol": "XYZ", "disease_name": "rare disease"},
        hypothesis={"title": "Unsupported", "hypothesis": "XYZ may treat rare disease.", "confidence": 0.9},
        evidence=[],
        tool_calls=[],
    )

    assert result["verdict"] == "abstain"
    assert "no_evidence" in result["abstention_reasons"]
    assert result["weighted_score"] < 50


def test_biotruth_critic_downgrades_weak_pubmed_only_evidence() -> None:
    result = evaluate_hypothesis(
        task={"gene_symbol": "ABC", "disease_name": "asthma", "public_labels": {"pubmed_gene_disease_count": 3}},
        hypothesis={
            "title": "ABC asthma candidate",
            "hypothesis": "ABC is mentioned with asthma and is a candidate hypothesis requiring validation.",
            "confidence": 0.6,
        },
        evidence=[
            {
                "source": "PubMed",
                "text": "A literature search found a few ABC asthma records but no causal or clinical evidence.",
                "evidence_type": "literature",
                "score": {"label": "weak", "evidence_type": "literature_search"},
            }
        ],
        tool_calls=[],
    )

    assert result["verdict"] in {"weak_support", "abstain"}
    assert "high_tier_evidence" in result["missing_evidence"]
    assert result["dimension_scores"]["causal_support"] < 3


def test_biotruth_critic_flags_conflicting_evidence() -> None:
    result = evaluate_hypothesis(
        task={
            "gene_symbol": "TNF",
            "disease_name": "inflammatory bowel disease",
            "public_labels": {
                "open_targets_association_status": "matched",
                "open_targets_association_score": 0.7,
                "pubmed_gene_disease_count": 1000,
            },
        },
        hypothesis={
            "title": "TNF IBD candidate",
            "hypothesis": "TNF is relevant to inflammatory bowel disease, but uncertainty remains.",
            "confidence": 0.5,
        },
        evidence=[
            {
                "source": "PubMed",
                "text": "TNF is associated with inflammatory bowel disease.",
                "evidence_type": "literature",
                "score": {"label": "supports", "evidence_type": "literature_search"},
            },
            {
                "source": "Clinical trial",
                "text": "A failed trial and adverse toxicity created conflicting evidence for this intervention.",
                "evidence_type": "contradictory",
                "score": {"label": "contradiction", "evidence_type": "clinical_precedence"},
            },
        ],
        tool_calls=[{"tool_name": "pubmed", "status": "success"}],
    )

    assert result["contradictions"]
    assert result["verdict"] in {"conflicting", "weak_support", "support"}
    assert result["dimension_scores"]["contradiction_handling"] >= 2


def test_biotruth_critic_schema_is_stable() -> None:
    result = evaluate_hypothesis(
        task={"gene_symbol": "EGFR", "disease_name": "lung adenocarcinoma"},
        hypothesis={"title": "EGFR lung", "hypothesis": "EGFR is a candidate target.", "confidence": 0.4},
        evidence=[],
        tool_calls=[],
    )

    assert set(result) == {
        "schema",
        "verdict",
        "weighted_score",
        "confidence",
        "dimension_scores",
        "dimension_weights",
        "evidence_tier_counts",
        "contradictions",
        "missing_evidence",
        "abstention_reasons",
        "rationale",
    }
    assert set(result["dimension_scores"]) == set(result["dimension_weights"])
