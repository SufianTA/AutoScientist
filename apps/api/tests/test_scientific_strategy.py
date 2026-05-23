from app.services.scientific_strategy import build_scientific_strategy, rank_experiments_by_strategy


def test_scientific_strategy_identifies_high_value_gaps() -> None:
    strategy = build_scientific_strategy(
        objective="Prioritize a therapeutic hypothesis for IL6 in rheumatoid arthritis with safety review.",
        biomedical_context={"primary_genes": ["IL6"], "diseases": ["rheumatoid arthritis"]},
        evidence=[
            {
                "source": "PubMed: IL6 rheumatoid arthritis mechanism",
                "text": "Retrieved article-level mechanism evidence for IL6 in rheumatoid arthritis.",
                "structured": {"articles": [{"pmid": "1", "title": "IL6 and rheumatoid arthritis"}]},
                "score": {"label": "weak_support", "score": 0.5},
                "evidence_type": "literature",
            }
        ],
        claim_graph={"claims": [{"evidence_gaps": ["local_context"]}]},
    )

    gap_ids = {gap["id"] for gap in strategy["gaps"]}

    assert strategy["readiness"]["tier"] == "hypothesis_only"
    assert "missing_target_disease_association" in gap_ids
    assert "missing_safety_evidence" in gap_ids
    assert "claim_graph_evidence_gap" in gap_ids
    assert strategy["next_action"]["action"] == "repair_high_severity_evidence_gaps"


def test_strategy_ranks_gap_closing_experiments_above_generic_steps() -> None:
    strategy = {
        "gaps": [
            {
                "id": "missing_safety_evidence",
                "severity": "high",
                "rationale": "Safety evidence is missing.",
            }
        ]
    }
    experiments = rank_experiments_by_strategy(
        [
            {
                "name": "Generic wet-lab validation assay",
                "type": "wet_lab",
                "cost": "medium",
                "feasibility": "medium",
                "expected_information_gain": "medium",
            },
            {
                "name": "Run safety and off-target triage",
                "type": "computational",
                "cost": "low",
                "feasibility": "high",
                "expected_information_gain": "high",
            },
        ],
        strategy,
    )

    assert experiments[0]["name"] == "Run safety and off-target triage"
    assert experiments[0]["addresses_gaps"] == ["missing_safety_evidence"]
    assert experiments[0]["priority_score"] > experiments[-1]["priority_score"]
    assert experiments[0]["decision_gate"]


def test_local_context_does_not_count_as_safety_evidence() -> None:
    strategy = build_scientific_strategy(
        objective="Assess therapeutic safety for TNF in rheumatoid arthritis.",
        biomedical_context={"primary_genes": ["TNF"], "diseases": ["rheumatoid arthritis"]},
        evidence=[
            {
                "source": "local_objective_context",
                "text": "The objective asks for therapeutic safety for TNF in rheumatoid arthritis.",
                "structured": {"evidence_type": "local_context"},
                "score": {"label": "mechanistic_relevance", "score": 0.2},
                "evidence_type": "local_context",
            }
        ],
    )

    assert "missing_safety_evidence" in {gap["id"] for gap in strategy["gaps"]}
