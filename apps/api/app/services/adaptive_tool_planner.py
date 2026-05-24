from __future__ import annotations

from typing import Any


def plan_adaptive_tools(
    *,
    task: dict[str, Any],
    evidence_hierarchy: dict[str, Any],
    contradiction_analysis: dict[str, Any] | None = None,
    max_recommendations: int = 5,
) -> dict[str, Any]:
    """Plan follow-up tool calls from explicit evidence gaps."""

    gaps = evidence_gaps(evidence_hierarchy, contradiction_analysis or {})
    recommendations = []
    for gap in gaps:
        recommendations.extend(recommendations_for_gap(task, gap))
    deduped = []
    seen = set()
    for item in recommendations:
        signature = (item["tool_family"], item.get("query") or item.get("tool_name"), item.get("reason"))
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(item)
        if len(deduped) >= max(1, max_recommendations):
            break
    return {
        "schema": "autosci.adaptive_tool_plan.v0.1",
        "policy": "evidence_gap_to_tool_family_v1",
        "gaps": gaps,
        "recommendations": deduped,
        "should_continue": bool(deduped),
    }


def evidence_gaps(
    evidence_hierarchy: dict[str, Any],
    contradiction_analysis: dict[str, Any],
) -> list[str]:
    gaps = []
    if int(evidence_hierarchy.get("evidence_count") or 0) == 0:
        gaps.append("no_evidence")
    if int(evidence_hierarchy.get("high_tier_evidence_count") or 0) == 0:
        gaps.append("human_or_clinical_evidence")
    if evidence_hierarchy.get("weak_only"):
        gaps.append("weak_literature_only")
    tier_counts = evidence_hierarchy.get("tier_counts", {}) if isinstance(evidence_hierarchy.get("tier_counts"), dict) else {}
    if int(tier_counts.get("tier_3_functional_mechanistic") or 0) == 0:
        gaps.append("mechanistic_evidence")
    if not contradiction_analysis.get("contradiction_search_attempted"):
        gaps.append("contradiction_search")
    return sorted(set(gaps))


def recommendations_for_gap(task: dict[str, Any], gap: str) -> list[dict[str, Any]]:
    gene = str(task.get("gene_symbol") or "target").strip()
    disease = str(task.get("disease_name") or "disease").strip()
    if gap == "no_evidence":
        return [
            pubmed(gene, disease, "target validation", gap),
            opentargets("OpenTargets_get_associated_targets_by_disease_efoId", gap),
        ]
    if gap == "human_or_clinical_evidence":
        return [
            clinical_trials(gene, disease, gap),
            pubmed(gene, disease, "human genetics clinical trial", gap),
            pubmed(gene, disease, "patient cohort therapeutic response", gap),
        ]
    if gap == "weak_literature_only":
        return [
            pubmed(gene, disease, "mechanism perturbation validation", gap),
            pubmed(gene, disease, "clinical evidence approved drug", gap),
        ]
    if gap == "mechanistic_evidence":
        return [
            pubmed(gene, disease, "pathway mechanism signaling", gap),
            {
                "tool_family": "pathway",
                "tool_name": "reactome_pathway_search_tool",
                "query": gene,
                "reason": gap,
            },
            {
                "tool_family": "pathway",
                "tool_name": "reactome_pathway_search_tool",
                "query": f"{gene} {disease}",
                "reason": gap,
            },
        ]
    if gap == "contradiction_search":
        return [
            pubmed(gene, disease, "failed trial no association", gap),
            pubmed(gene, disease, "toxicity adverse resistance", gap),
        ]
    return []


def pubmed(gene: str, disease: str, suffix: str, reason: str) -> dict[str, Any]:
    return {
        "tool_family": "pubmed",
        "tool_name": "pubmed_literature_search_tool",
        "query": f"{gene} {disease} {suffix}",
        "reason": reason,
    }


def opentargets(tool_name: str, reason: str) -> dict[str, Any]:
    return {
        "tool_family": "tooluniverse_opentargets",
        "tool_name": tool_name,
        "reason": reason,
    }


def clinical_trials(gene: str, disease: str, reason: str) -> dict[str, Any]:
    return {
        "tool_family": "clinical_trials",
        "tool_name": "clinical_trials_search_tool",
        "condition": disease,
        "query": gene,
        "reason": reason,
    }
