from __future__ import annotations

from typing import Any


def evaluate_abstention_policy(
    *,
    critic: dict[str, Any],
    evidence_hierarchy: dict[str, Any],
    contradiction_analysis: dict[str, Any],
    actionability_profile: dict[str, Any] | None = None,
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
    contradiction_categories = set(contradiction_analysis.get("categories", []) or [])
    if (
        contradiction_analysis.get("finding_count", 0)
        and critic_score < 75
        and (not contradiction_categories or contradiction_categories & {"negative_evidence", "context_mismatch"})
    ):
        reasons.add("unresolved_counterevidence")
    if not contradiction_analysis.get("contradiction_search_attempted"):
        reasons.add("contradiction_search_incomplete")
    actionability = actionability_profile or {}
    actionability_decision = str(actionability.get("recommended_decision") or "")
    actionability_level = str(actionability.get("level") or "")
    for reason in actionability.get("reasons", []) if isinstance(actionability.get("reasons"), list) else []:
        if reason in {
            "no_target_disease_grounded_evidence",
            "no_disease_specific_clinical_precedence",
            "no_disease_specific_intervention_evidence",
            "negative_or_conflicting_signals_present",
            "clinical_failure_or_translation_limitation_present",
            "safety_signals_require_translation_caution",
            "clinical_terms_appear_in_query_context",
            "counterevidence_terms_appear_in_query_context",
        }:
            reasons.add(reason)

    decision = "support_allowed"
    if "no_evidence" in reasons:
        decision = "abstain"
    elif {"critic_found_conflict", "unresolved_counterevidence"} & reasons:
        decision = "conflicting"
    elif "critic_abstained" in reasons and actionability_decision not in {"tentative_only", "support_allowed"}:
        decision = "abstain"
    elif "critic_score_below_support_threshold" in reasons and actionability_decision not in {
        "tentative_only",
        "support_allowed",
    }:
        decision = "abstain"
    elif "clinical_failure_or_translation_limitation_present" in reasons:
        decision = "tentative_only"
    elif {"weak_only_evidence", "no_high_tier_evidence", "contradiction_search_incomplete"} & reasons:
        decision = "tentative_only"
    if actionability_decision == "abstain":
        decision = "abstain"
    elif actionability_decision == "conflicting" and decision != "abstain":
        decision = "conflicting"
    elif actionability_decision == "tentative_only" and decision == "support_allowed":
        decision = "tentative_only"

    return {
        "schema": "autosci.abstention_policy.v0.2",
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
            "actionability_level": actionability_level,
            "actionability_recommended_decision": actionability_decision,
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
