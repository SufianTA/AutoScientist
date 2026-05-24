from __future__ import annotations

import re
from collections import Counter
from typing import Any

from app.services.evidence_hierarchy import classify_evidence_item


DIMENSION_WEIGHTS = {
    "disease_relevance": 14,
    "causal_support": 18,
    "mechanistic_plausibility": 13,
    "human_evidence": 14,
    "translational_support": 13,
    "contradiction_handling": 11,
    "safety_awareness": 7,
    "uncertainty_calibration": 10,
}

CONTRADICTION_TERMS = {
    "contradict",
    "conflict",
    "failed",
    "failure",
    "negative trial",
    "no association",
    "not associated",
    "lack of association",
    "toxicity",
    "toxic",
    "adverse",
    "resistance",
    "contraindication",
}

CAUSAL_TERMS = {
    "causal",
    "causality",
    "genetic",
    "gwas",
    "variant",
    "mutation",
    "knockout",
    "knockdown",
    "perturbation",
    "inhibition",
    "activation",
    "mechanism",
}

MECHANISM_TERMS = {
    "pathway",
    "signaling",
    "mechanism",
    "receptor",
    "kinase",
    "cytokine",
    "immune",
    "cell",
    "transcription",
    "inflammation",
}

TRANSLATION_TERMS = {
    "approved",
    "clinical",
    "trial",
    "drug",
    "compound",
    "tractability",
    "therapeutic",
    "inhibitor",
    "antibody",
}

HUMAN_TERMS = {
    "human",
    "patient",
    "clinical",
    "gwas",
    "genetic",
    "variant",
    "cohort",
}


def evaluate_hypothesis(
    *,
    task: dict[str, Any],
    hypothesis: dict[str, Any],
    evidence: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
    public_labels: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a conservative, structured scientific review of a hypothesis.

    This critic is intentionally heuristic and auditable. It does not replace
    external BioTruth judge scoring; it gives the runtime a stricter internal
    gate before publishing a polished report.
    """

    labels = public_labels or task.get("public_labels") or {}
    evidence_items = evidence or []
    tier_counts = evidence_tier_counts(evidence_items)
    contradictions = contradiction_items(evidence_items)
    text = corpus_text(task, hypothesis, evidence_items)
    scores = {
        "disease_relevance": disease_relevance_score(task, text, labels, evidence_items),
        "causal_support": causal_support_score(text, evidence_items, labels),
        "mechanistic_plausibility": keyword_score(text, MECHANISM_TERMS, base=1, scale=1),
        "human_evidence": human_evidence_score(text, labels),
        "translational_support": translational_score(text, labels),
        "contradiction_handling": contradiction_score(text, contradictions),
        "safety_awareness": safety_score(text, evidence_items),
        "uncertainty_calibration": uncertainty_score(text, hypothesis, evidence_items),
    }
    missing = missing_evidence(scores, tier_counts, evidence_items, tool_calls)
    weighted = weighted_score(scores)
    verdict = critic_verdict(weighted, contradictions, missing, evidence_items, scores)
    abstention_reasons = abstention_reasons_for(verdict, scores, tier_counts, evidence_items, contradictions, missing)
    return {
        "schema": "autosci.biotruth_critic.v0.1",
        "verdict": verdict,
        "weighted_score": weighted,
        "confidence": round(min(1.0, max(0.0, weighted / 100.0)), 3),
        "dimension_scores": scores,
        "dimension_weights": DIMENSION_WEIGHTS,
        "evidence_tier_counts": dict(tier_counts),
        "contradictions": contradictions[:8],
        "missing_evidence": missing,
        "abstention_reasons": abstention_reasons,
        "rationale": rationale(verdict, weighted, scores, tier_counts, contradictions, missing),
    }


def corpus_text(task: dict[str, Any], hypothesis: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
    parts = [
        task.get("objective"),
        task.get("gene_symbol"),
        task.get("disease_name"),
        hypothesis.get("title"),
        hypothesis.get("hypothesis"),
        hypothesis.get("candidate_intervention_summary"),
        " ".join(str(item) for item in hypothesis.get("limitations", []) if item),
    ]
    for item in evidence:
        parts.extend(
            [
                item.get("source"),
                item.get("text"),
                item.get("evidence_type"),
                item.get("score", {}).get("evidence_type") if isinstance(item.get("score"), dict) else None,
                item.get("score", {}).get("rationale") if isinstance(item.get("score"), dict) else None,
            ]
        )
    return " ".join(str(part) for part in parts if part).lower()


def evidence_tier_counts(evidence: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in evidence:
        counts[evidence_tier(item)] += 1
    return counts


def evidence_tier(item: dict[str, Any]) -> str:
    return str(item.get("evidence_tier") or classify_evidence_item(item)["evidence_tier"])


def contradiction_items(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found = []
    for item in evidence:
        text = " ".join(str(value).lower() for value in [item.get("source"), item.get("text"), item.get("evidence_type")] if value)
        score = item.get("score", {}) if isinstance(item.get("score"), dict) else {}
        label = str(score.get("label") or "").lower()
        if label in {"contradiction", "contradicts"} or any(term in text for term in CONTRADICTION_TERMS):
            found.append(
                {
                    "source": item.get("source", "unknown"),
                    "evidence_type": item.get("evidence_type") or score.get("evidence_type"),
                    "text": str(item.get("text", ""))[:500],
                }
            )
    return found


def disease_relevance_score(
    task: dict[str, Any],
    text: str,
    labels: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> int:
    gene = str(task.get("gene_symbol") or "").lower()
    disease = str(task.get("disease_name") or "").lower()
    score = int(bool(gene and gene in text)) + int(bool(disease and disease in text))
    if labels.get("open_targets_association_status") == "matched":
        score += 2
    try:
        association = float(labels.get("open_targets_association_score") or 0)
    except (TypeError, ValueError):
        association = 0.0
    if association >= 0.5:
        score += 1
    if any(item.get("evidence_type") == "target_disease_association" for item in evidence):
        score += 1
    return bounded(score)


def causal_support_score(text: str, evidence: list[dict[str, Any]], labels: dict[str, Any]) -> int:
    score = keyword_score(text, CAUSAL_TERMS, base=0, scale=1)
    if labels.get("open_targets_association_status") == "matched":
        score += 1
    if any(evidence_tier(item) in {"tier_1_clinical_translational", "tier_2_human_biology"} for item in evidence):
        score += 1
    return bounded(score)


def human_evidence_score(text: str, labels: dict[str, Any]) -> int:
    score = keyword_score(text, HUMAN_TERMS, base=0, scale=1)
    if int(labels.get("pubmed_gene_disease_count") or 0) >= 25:
        score += 1
    return bounded(score)


def translational_score(text: str, labels: dict[str, Any]) -> int:
    score = keyword_score(text, TRANSLATION_TERMS, base=0, scale=1)
    if "approved" in text or "clinical_precedence" in text:
        score += 1
    if labels.get("evidence_availability") == "high":
        score += 1
    return bounded(score)


def contradiction_score(text: str, contradictions: list[dict[str, Any]]) -> int:
    if contradictions and any(term in text for term in ["limitation", "counter", "contradict", "failed", "uncertain"]):
        return 4
    if contradictions:
        return 2
    if any(
        term in text
        for term in [
            "limitation",
            "counterevidence",
            "uncertain",
            "not prove",
            "resistance",
            "requires validation",
            "validation",
        ]
    ):
        return 3
    return 1


def safety_score(text: str, evidence: list[dict[str, Any]]) -> int:
    score = 0
    if any(term in text for term in ["safety", "toxicity", "adverse", "dose", "contraindication"]):
        score += 2
    if any(evidence_tier(item) == "tier_1_clinical_translational" for item in evidence):
        score += 1
    if "no safety claim" in text or "safety claim" in text:
        score += 1
    return bounded(score)


def uncertainty_score(text: str, hypothesis: dict[str, Any], evidence: list[dict[str, Any]]) -> int:
    score = 0
    if any(term in text for term in ["uncertain", "limitation", "candidate", "requires validation", "not prove"]):
        score += 2
    if hypothesis.get("confidence") is not None:
        score += 1
    if len(evidence) < 3:
        return min(score, 2)
    if any(term in text for term in ["abstain", "insufficient"]):
        score += 1
    return bounded(score)


def keyword_score(text: str, terms: set[str], *, base: int, scale: int) -> int:
    matches = sum(1 for term in terms if term in text)
    return bounded(base + matches // max(1, scale))


def missing_evidence(
    scores: dict[str, int],
    tier_counts: Counter[str],
    evidence: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
) -> list[str]:
    missing = []
    if not evidence:
        missing.append("no_evidence")
    if scores["disease_relevance"] < 3:
        missing.append("disease_relevance")
    if scores["causal_support"] < 3:
        missing.append("causal_support")
    if scores["human_evidence"] < 2:
        missing.append("human_evidence")
    if scores["translational_support"] < 2:
        missing.append("translational_support")
    if scores["contradiction_handling"] < 3:
        missing.append("contradiction_search")
    if not (tier_counts["tier_1_clinical_translational"] or tier_counts["tier_2_human_biology"]):
        missing.append("high_tier_evidence")
    if not tool_calls and len(evidence) <= 2:
        missing.append("tool_execution")
    return sorted(set(missing))


def critic_verdict(
    weighted: float,
    contradictions: list[dict[str, Any]],
    missing: list[str],
    evidence: list[dict[str, Any]],
    scores: dict[str, int],
) -> str:
    if not evidence or "no_evidence" in missing or scores["disease_relevance"] <= 1:
        return "abstain"
    if contradictions and weighted < 70:
        return "conflicting"
    if weighted >= 75 and "disease_relevance" not in missing and "causal_support" not in missing:
        return "support"
    if weighted >= 50:
        return "weak_support"
    return "abstain"


def abstention_reasons_for(
    verdict: str,
    scores: dict[str, int],
    tier_counts: Counter[str],
    evidence: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    missing: list[str],
) -> list[str]:
    reasons = []
    if verdict == "abstain":
        reasons.append("critic_verdict_abstain")
    if not evidence:
        reasons.append("no_evidence")
    if contradictions and verdict in {"conflicting", "abstain"}:
        reasons.append("unresolved_contradictions")
    if scores["disease_relevance"] < 3:
        reasons.append("weak_disease_relevance")
    if scores["causal_support"] < 3:
        reasons.append("weak_causal_support")
    if not (tier_counts["tier_1_clinical_translational"] or tier_counts["tier_2_human_biology"]):
        reasons.append("no_high_tier_evidence")
    reasons.extend(missing)
    return sorted(set(reasons))


def weighted_score(scores: dict[str, int]) -> float:
    total = 0.0
    for dimension, weight in DIMENSION_WEIGHTS.items():
        total += (bounded(scores.get(dimension, 0)) / 5.0) * weight
    return round(total, 2)


def bounded(value: int | float) -> int:
    return max(0, min(5, int(round(float(value)))))


def rationale(
    verdict: str,
    weighted: float,
    scores: dict[str, int],
    tier_counts: Counter[str],
    contradictions: list[dict[str, Any]],
    missing: list[str],
) -> str:
    weakest = sorted(scores.items(), key=lambda item: item[1])[:3]
    tier_text = ", ".join(f"{key}={value}" for key, value in sorted(tier_counts.items())) or "no evidence tiers"
    missing_text = ", ".join(missing) if missing else "none"
    contradiction_text = f"{len(contradictions)} contradiction(s)" if contradictions else "no explicit contradictions"
    return (
        f"Verdict {verdict} with weighted score {weighted}. Evidence tiers: {tier_text}. "
        f"Weakest dimensions: {', '.join(f'{name}:{score}' for name, score in weakest)}. "
        f"Missing evidence: {missing_text}. Counterevidence: {contradiction_text}."
    )


def contains_any(text: str, terms: set[str]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)
