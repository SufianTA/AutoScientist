from __future__ import annotations

from typing import Any


def evaluate_abstention_policy(
    *,
    critic: dict[str, Any],
    evidence_hierarchy: dict[str, Any],
    contradiction_analysis: dict[str, Any],
    existing_abstention: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Combine scientific quality signals into a final abstention decision."""

    reasons = set(existing_abstention.get("reasons", []) if isinstance(existing_abstention, dict) else [])
    critic_verdict = str(critic.get("verdict") or "")
    critic_score = float(critic.get("weighted_score") or 0.0)
    if critic_verdict == "abstain":
        reasons.add("critic_abstained")
    if critic_verdict == "conflicting":
        reasons.add("critic_found_conflict")
    if critic_score < 55:
        reasons.add("critic_score_below_support_threshold")
    if evidence_hierarchy.get("evidence_count", 0) == 0:
        reasons.add("no_evidence")
    if evidence_hierarchy.get("weak_only"):
        reasons.add("weak_only_evidence")
    if int(evidence_hierarchy.get("high_tier_evidence_count") or 0) == 0:
        reasons.add("no_high_tier_evidence")
    if contradiction_analysis.get("finding_count", 0) and critic_score < 75:
        reasons.add("unresolved_counterevidence")
    if not contradiction_analysis.get("contradiction_search_attempted"):
        reasons.add("contradiction_search_incomplete")

    decision = "support_allowed"
    if {"critic_abstained", "no_evidence", "critic_score_below_support_threshold"} & reasons:
        decision = "abstain"
    elif {"critic_found_conflict", "unresolved_counterevidence"} & reasons:
        decision = "conflicting"
    elif {"weak_only_evidence", "no_high_tier_evidence", "contradiction_search_incomplete"} & reasons:
        decision = "tentative_only"

    return {
        "schema": "autosci.abstention_policy.v0.1",
        "decision": decision,
        "abstention_required": decision == "abstain",
        "claim_boundary": claim_boundary(decision),
        "reasons": sorted(reasons),
        "inputs": {
            "critic_verdict": critic_verdict,
            "critic_weighted_score": critic_score,
            "hierarchy_score": evidence_hierarchy.get("hierarchy_score"),
            "high_tier_evidence_count": evidence_hierarchy.get("high_tier_evidence_count"),
            "contradiction_finding_count": contradiction_analysis.get("finding_count"),
            "contradiction_search_attempted": contradiction_analysis.get("contradiction_search_attempted"),
        },
    }


def claim_boundary(decision: str) -> str:
    if decision == "support_allowed":
        return "candidate hypothesis with explicit limitations; no clinical efficacy or safety claim"
    if decision == "tentative_only":
        return "tentative candidate only; explicitly list missing evidence before any support claim"
    if decision == "conflicting":
        return "conflicting evidence response; do not present as supported until counterevidence is resolved"
    return "insufficient-evidence response; abstain from target-disease support claim"
