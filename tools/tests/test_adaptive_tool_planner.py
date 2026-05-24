from __future__ import annotations

from app.services.adaptive_tool_planner import evidence_gaps, plan_adaptive_tools


def test_adaptive_tool_planner_recommends_human_and_contradiction_queries() -> None:
    plan = plan_adaptive_tools(
        task={"gene_symbol": "BRAF", "disease_name": "melanoma"},
        evidence_hierarchy={
            "evidence_count": 3,
            "high_tier_evidence_count": 0,
            "weak_only": False,
            "tier_counts": {"tier_3_functional_mechanistic": 1},
        },
        contradiction_analysis={"contradiction_search_attempted": False},
        max_recommendations=4,
    )

    queries = [item.get("query", "") for item in plan["recommendations"]]
    tools = [item.get("tool_name", "") for item in plan["recommendations"]]
    assert plan["schema"] == "autosci.adaptive_tool_plan.v0.1"
    assert "human_or_clinical_evidence" in plan["gaps"]
    assert "contradiction_search" in plan["gaps"]
    assert "clinical_trials_search_tool" in tools
    assert any("human genetics clinical trial" in query for query in queries)
    assert any("failed trial no association" in query for query in queries)


def test_adaptive_tool_planner_identifies_weak_literature_only_gap() -> None:
    gaps = evidence_gaps(
        {
            "evidence_count": 1,
            "high_tier_evidence_count": 0,
            "weak_only": True,
            "tier_counts": {"tier_5_literature_context": 1},
        },
        {"contradiction_search_attempted": True},
    )

    assert "weak_literature_only" in gaps
    assert "mechanistic_evidence" in gaps


def test_adaptive_tool_planner_has_no_recommendations_for_covered_evidence() -> None:
    plan = plan_adaptive_tools(
        task={"gene_symbol": "TNF", "disease_name": "inflammatory bowel disease"},
        evidence_hierarchy={
            "evidence_count": 8,
            "high_tier_evidence_count": 2,
            "weak_only": False,
            "tier_counts": {"tier_3_functional_mechanistic": 2},
        },
        contradiction_analysis={"contradiction_search_attempted": True},
    )

    assert plan["gaps"] == []
    assert plan["recommendations"] == []
    assert plan["should_continue"] is False
