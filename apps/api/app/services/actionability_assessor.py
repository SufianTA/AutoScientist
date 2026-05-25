from __future__ import annotations

import json
import re
from typing import Any


CLINICAL_TERMS = {
    "approved",
    "approval",
    "clinical trial",
    "clinicaltrials.gov",
    "phase 1",
    "phase 2",
    "phase 3",
    "phase 4",
    "randomized",
    "interventional",
    "treated",
    "treatment",
    "therapy",
    "therapeutic",
}

POSITIVE_TRANSLATIONAL_TERMS = {
    "approved",
    "approval",
    "approved drug",
    "approved therapy",
    "approved indication",
    "efficacy",
    "effective",
    "benefit",
    "improved",
    "improves",
    "response",
    "responded",
    "standard of care",
    "successful",
}

INTERVENTION_TERMS = {
    "drug",
    "compound",
    "inhibitor",
    "antibody",
    "agonist",
    "antagonist",
    "modulator",
    "blockade",
    "therapy",
    "treatment",
    "biologic",
    "small molecule",
}

BIOLOGY_TERMS = {
    "genetic",
    "gwas",
    "variant",
    "mutation",
    "patient",
    "human",
    "mechanism",
    "pathway",
    "signaling",
    "causal",
    "association",
}

SAFETY_TERMS = {
    "adverse",
    "toxicity",
    "toxic",
    "contraindication",
    "safety signal",
    "black box",
    "intolerable",
}

NEGATIVE_TERMS = {
    "failed trial",
    "negative trial",
    "no benefit",
    "did not improve",
    "did not meet",
    "lack of efficacy",
    "lack efficacy",
    "not associated",
    "no association",
    "lack of association",
    "controversial",
    "misclassification",
    "worse outcome",
    "worsened outcome",
    "mixed results",
    "inconsistent",
}

QUERY_PLACEHOLDER_TERMS = {
    "returned live literature search results",
    "literature search returned records",
    "search returned records",
    "returned records",
}


def assess_actionability(
    *,
    task: dict[str, Any],
    evidence: list[dict[str, Any]],
    evidence_hierarchy: dict[str, Any] | None = None,
    contradiction_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Estimate whether evidence supports a research action, not just an association.

    This is deliberately evidence-type driven instead of benchmark-label driven.
    The runtime must not read gold labels to decide whether a target is strong,
    moderate, weak, or insufficient.
    """

    profile = {
        "target_disease_grounded_count": 0,
        "disease_specific_clinical_count": 0,
        "disease_specific_intervention_count": 0,
        "human_or_genetic_count": 0,
        "mechanistic_count": 0,
        "literature_context_count": 0,
        "safety_signal_count": 0,
        "negative_signal_count": 0,
        "translation_limitation_count": 0,
        "disease_specific_positive_intervention_count": 0,
        "structured_positive_intervention_count": 0,
        "tool_grounding_count": 0,
        "query_only_clinical_context_count": 0,
        "query_only_counterevidence_context_count": 0,
    }
    gene = normalize_term(task.get("gene_symbol"))
    disease = normalize_term(task.get("disease_name"))
    for item in evidence or []:
        features = classify_actionability_item(item, gene=gene, disease=disease)
        for key in profile:
            profile[key] += int(features.get(key) or 0)

    hierarchy = evidence_hierarchy or {}
    contradictions = contradiction_analysis or {}
    high_tier_count = int(hierarchy.get("high_tier_evidence_count") or 0)
    hierarchy_score = float(hierarchy.get("hierarchy_score") or 0.0)
    contradiction_count = substantive_negative_contradiction_count(contradictions)
    if contradiction_count:
        profile["negative_signal_count"] += contradiction_count
        profile["translation_limitation_count"] += contradiction_count

    reasons: list[str] = []
    if not evidence:
        reasons.append("no_evidence")
    if profile["target_disease_grounded_count"] == 0:
        reasons.append("no_target_disease_grounded_evidence")
    if profile["disease_specific_clinical_count"] == 0:
        reasons.append("no_disease_specific_clinical_precedence")
    if profile["disease_specific_intervention_count"] == 0:
        reasons.append("no_disease_specific_intervention_evidence")
    if high_tier_count == 0:
        reasons.append("no_high_tier_evidence")
    if profile["negative_signal_count"] > 0:
        reasons.append("negative_or_conflicting_signals_present")
    if profile["translation_limitation_count"] > 0:
        reasons.append("clinical_failure_or_translation_limitation_present")
    if profile["safety_signal_count"] > 0:
        reasons.append("safety_signals_require_translation_caution")
    if profile["query_only_clinical_context_count"] > 0:
        reasons.append("clinical_terms_appear_in_query_context")
    if profile["query_only_counterevidence_context_count"] > 0:
        reasons.append("counterevidence_terms_appear_in_query_context")

    level = actionability_level(profile, high_tier_count, hierarchy_score)
    recommended_decision = recommended_decision_from_profile(profile, level, reasons)
    return {
        "schema": "autosci.actionability_profile.v0.1",
        "level": level,
        "recommended_decision": recommended_decision,
        "profile": profile,
        "reasons": sorted(set(reasons)),
        "inputs": {
            "high_tier_evidence_count": high_tier_count,
            "hierarchy_score": hierarchy_score,
            "contradiction_finding_count": contradiction_count,
        },
        "interpretation": interpretation(level, recommended_decision, reasons),
    }


def classify_actionability_item(item: dict[str, Any], *, gene: str, disease: str) -> dict[str, int]:
    source = textify(item.get("source"))
    body = body_text(item)
    combined = f"{source} {body}"
    evidence_type = textify(item.get("evidence_type"))
    score = item.get("score", {}) if isinstance(item.get("score"), dict) else {}
    score_type = textify(score.get("evidence_type"))
    source_name = source.lower()
    target_grounded = has_term(combined, gene) if gene else False
    disease_grounded = has_term(combined, disease) if disease else False
    grounded_pair = target_grounded and disease_grounded
    source_clinical_signal = has_any(source, CLINICAL_TERMS) or "clinical precedence" in source
    body_clinical_signal = has_any(body, CLINICAL_TERMS)
    clinical_signal = body_clinical_signal or evidence_type == "clinical_precedence" or score_type == "clinical_precedence"
    intervention_signal = has_any(body, INTERVENTION_TERMS)
    safety_signal = has_any(combined, SAFETY_TERMS)
    placeholder_body = is_search_placeholder(body)
    body_negative_signal = has_any(body, NEGATIVE_TERMS) and not placeholder_body
    query_only_negative = placeholder_body and (has_any(source, NEGATIVE_TERMS) or has_any(body, NEGATIVE_TERMS))
    negative_signal = body_negative_signal
    translation_limitation = negative_signal
    target_level_only = is_target_level_only_context(body)
    positive_intervention_signal = (
        intervention_signal
        and clinical_signal
        and has_any(body, POSITIVE_TRANSLATIONAL_TERMS)
        and not negative_signal
        and not query_only_negative
        and not target_level_only
    )
    tool_grounding = any(
        name in source_name
        for name in ["opentargets", "open targets", "tooluniverse", "clinicaltrials.gov", "pubmed", "ncbi"]
    )
    query_only_clinical = is_query_context_only(
        source=source,
        body=body,
        clinical_signal=clinical_signal or source_clinical_signal,
    )

    return {
        "target_disease_grounded_count": int(grounded_pair),
        "disease_specific_clinical_count": int(grounded_pair and clinical_signal and not query_only_clinical),
        "disease_specific_intervention_count": int(grounded_pair and intervention_signal and not query_only_clinical),
        "human_or_genetic_count": int(
            grounded_pair and has_any(body, {"human", "patient", "genetic", "gwas", "variant", "mutation", "cohort"})
        ),
        "mechanistic_count": int(
            grounded_pair and has_any(body, {"mechanism", "pathway", "signaling", "knockout", "perturbation"})
        ),
        "literature_context_count": int("pubmed" in source_name or "literature" in combined),
        "safety_signal_count": int(safety_signal),
        "negative_signal_count": int(negative_signal),
        "translation_limitation_count": int(translation_limitation and not query_only_negative),
        "disease_specific_positive_intervention_count": int(grounded_pair and positive_intervention_signal and not query_only_clinical),
        "structured_positive_intervention_count": int(
            grounded_pair
            and positive_intervention_signal
            and not query_only_clinical
            and any(name in source_name for name in ["opentargets", "open targets", "clinicaltrials.gov", "tooluniverse"])
        ),
        "tool_grounding_count": int(tool_grounding),
        "query_only_clinical_context_count": int(query_only_clinical),
        "query_only_counterevidence_context_count": int(query_only_negative),
    }


def actionability_level(profile: dict[str, int], high_tier_count: int, hierarchy_score: float) -> str:
    if profile["target_disease_grounded_count"] == 0:
        return "insufficient"
    if profile["negative_signal_count"] >= 2:
        return "conflicting"
    if profile["negative_signal_count"] > 0 and profile["disease_specific_positive_intervention_count"] == 0:
        return "conflicting"
    if (
        profile["disease_specific_positive_intervention_count"] >= 2
        or profile["structured_positive_intervention_count"] >= 1
    ) and profile["translation_limitation_count"] == 0:
        return "high"
    if profile["human_or_genetic_count"] > 0 or profile["mechanistic_count"] > 0 or high_tier_count > 0 or hierarchy_score >= 45:
        return "moderate"
    return "low"


def recommended_decision_from_profile(profile: dict[str, int], level: str, reasons: list[str]) -> str:
    if level == "insufficient":
        return "abstain"
    if level == "conflicting":
        return "conflicting"
    if "negative_or_conflicting_signals_present" in reasons and profile["disease_specific_positive_intervention_count"] == 0:
        return "conflicting"
    if "clinical_failure_or_translation_limitation_present" in reasons:
        return "tentative_only"
    if level == "high" and profile["translation_limitation_count"] == 0 and profile["negative_signal_count"] == 0:
        return "support_allowed"
    return "tentative_only"


def body_text(item: dict[str, Any]) -> str:
    score = item.get("score", {}) if isinstance(item.get("score"), dict) else {}
    structured = item.get("structured", {}) if isinstance(item.get("structured"), dict) else {}
    parts = [
        item.get("text"),
        item.get("evidence_type"),
        score.get("label"),
        score.get("evidence_type"),
        score.get("rationale"),
        structured.get("evidence_type"),
        structured.get("source_policy"),
    ]
    return " ".join(textify(part) for part in parts if part)


def is_query_context_only(*, source: str, body: str, clinical_signal: bool) -> bool:
    if not clinical_signal:
        return False
    source_lower = source.lower()
    if "pubmed:" not in source_lower:
        return False
    clinical_in_source = has_any(source_lower, CLINICAL_TERMS) or "clinical precedence" in source_lower
    if not clinical_in_source:
        return False
    non_query_clinical_markers = {
        "clinical trial",
        "randomized",
        "phase 1",
        "phase 2",
        "phase 3",
        "phase 4",
        "approved",
        "approval",
        "interventional",
        "treated with",
        "therapy",
        "therapeutic efficacy",
    }
    return not has_any(body, non_query_clinical_markers)


def is_search_placeholder(body: str) -> bool:
    return has_any(body, QUERY_PLACEHOLDER_TERMS)


def is_target_level_only_context(body: str) -> bool:
    return "target-level precedence" in body or "separated from disease-specific efficacy claims" in body


def substantive_negative_contradiction_count(contradictions: dict[str, Any]) -> int:
    findings = contradictions.get("findings")
    if isinstance(findings, list):
        return sum(1 for finding in findings if isinstance(finding, dict) and finding.get("category") == "negative_evidence")
    categories = contradictions.get("categories")
    if isinstance(categories, list):
        return int("negative_evidence" in categories)
    return int(contradictions.get("contradiction_count") or 0)


def interpretation(level: str, decision: str, reasons: list[str]) -> str:
    if decision == "support_allowed":
        return "disease-specific intervention or clinical precedence evidence is present; support is allowed with limits"
    if decision == "tentative_only":
        return "biological evidence exists, but intervention-specific or clinical-precedence evidence is incomplete"
    if decision == "conflicting":
        return "negative, safety, or translation-limiting signals must be resolved before support"
    return "target-disease grounding is insufficient for a useful scientific support claim"


def normalize_term(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def textify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.lower()
    try:
        return json.dumps(value, default=str).lower()
    except TypeError:
        return str(value).lower()


def has_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def has_term(text: str, term: str) -> bool:
    if not term:
        return False
    if len(term) <= 5 and term.isalnum():
        return bool(re.search(rf"\b{re.escape(term)}\b", text))
    return term in text
