from __future__ import annotations

from typing import Any


def evaluate_abstention_policy(
    *,
    critic: dict[str, Any],
    evidence_hierarchy: dict[str, Any],
    contradiction_analysis: dict[str, Any],
    actionability_profile: dict[str, Any] | None = None,
    existing_abstention: dict[str, Any] | None = None,
    public_labels: dict[str, Any] | None = None,
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
    actionability_counts = actionability.get("profile") if isinstance(actionability.get("profile"), dict) else {}
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

    public_calibration = calibrate_public_target_disease_support(
        public_labels=public_labels or {},
        actionability_profile=actionability,
        evidence_hierarchy=evidence_hierarchy,
    )
    reasons.update(public_calibration["reasons"])

    decision = "support_allowed"
    if "no_evidence" in reasons:
        decision = "abstain"
    elif "public_target_disease_support_absent" in reasons:
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
    if decision == "support_allowed" and "public_target_disease_support_weak" in reasons:
        decision = "tentative_only"
    if (
        decision == "support_allowed"
        and "safety_signals_require_translation_caution" in reasons
        and int(actionability_counts.get("disease_specific_positive_intervention_count") or 0) < 2
    ):
        decision = "tentative_only"

    return {
        "schema": "autosci.abstention_policy.v0.3",
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
            "public_calibration": public_calibration,
        },
    }


def calibrate_public_target_disease_support(
    *,
    public_labels: dict[str, Any],
    actionability_profile: dict[str, Any],
    evidence_hierarchy: dict[str, Any],
) -> dict[str, Any]:
    """Estimate whether public evidence supports target-disease actionability.

    This guard prevents target-level drug, safety, or oncology context from being
    mistaken for disease-specific support in an unrelated benchmark disease.
    """

    reasons: set[str] = set()
    association_status = str(public_labels.get("open_targets_association_status") or "").lower()
    evidence_availability = str(public_labels.get("evidence_availability") or "").lower()
    association_score = coerce_float(public_labels.get("open_targets_association_score"))
    association_rank = coerce_int(public_labels.get("open_targets_association_rank"))
    pubmed_gene_disease_count = coerce_int(public_labels.get("pubmed_gene_disease_count"))
    profile = actionability_profile.get("profile") if isinstance(actionability_profile.get("profile"), dict) else {}
    query_only_clinical = int(profile.get("query_only_clinical_context_count") or 0)
    query_only_counterevidence = int(profile.get("query_only_counterevidence_context_count") or 0)
    positive_interventions = int(profile.get("disease_specific_positive_intervention_count") or 0)
    structured_positive = int(profile.get("structured_positive_intervention_count") or 0)
    high_tier_count = int(evidence_hierarchy.get("high_tier_evidence_count") or 0)
    hierarchy_score = float(evidence_hierarchy.get("hierarchy_score") or 0.0)

    if association_status and association_status != "matched":
        reasons.add("open_targets_target_disease_not_matched")
    if evidence_availability == "low":
        reasons.add("public_evidence_availability_low")
    if association_score is not None and association_score < 0.2:
        reasons.add("open_targets_association_score_low")
    if association_rank is not None and association_rank > 100:
        reasons.add("open_targets_association_rank_weak")
    if query_only_clinical or query_only_counterevidence:
        reasons.add("query_context_cannot_establish_target_disease_support")

    public_support_absent = (
        association_status
        and association_status != "matched"
        and evidence_availability == "low"
        and positive_interventions < 3
    )
    public_support_weak = (
        association_status
        and association_status != "matched"
        and (positive_interventions < 3 or structured_positive == 0)
    ) or (
        evidence_availability == "low"
        and hierarchy_score < 65
        and high_tier_count < 20
    )

    if public_support_absent:
        reasons.add("public_target_disease_support_absent")
    elif public_support_weak:
        reasons.add("public_target_disease_support_weak")

    return {
        "schema": "autosci.public_target_disease_calibration.v0.1",
        "reasons": sorted(reasons),
        "association_status": association_status or None,
        "association_score": association_score,
        "association_rank": association_rank,
        "evidence_availability": evidence_availability or None,
        "pubmed_gene_disease_count": pubmed_gene_disease_count,
        "positive_intervention_count": positive_interventions,
        "structured_positive_intervention_count": structured_positive,
        "high_tier_evidence_count": high_tier_count,
        "hierarchy_score": hierarchy_score,
    }


def coerce_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def coerce_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def claim_boundary(decision: str) -> str:
    if decision == "support_allowed":
        return "candidate hypothesis with explicit limitations; no clinical efficacy or safety claim"
    if decision == "tentative_only":
        return "tentative candidate only; explicitly list missing evidence before any support claim"
    if decision == "conflicting":
        return "conflicting evidence response; do not present as supported until counterevidence is resolved"
    return "insufficient-evidence response; abstain from target-disease support claim"
