from __future__ import annotations

from collections import Counter
from typing import Any


TIER_ORDER = {
    "tier_1_clinical_translational": 1,
    "tier_2_human_biology": 2,
    "tier_3_functional_mechanistic": 3,
    "tier_4_tractability_context": 4,
    "tier_5_literature_context": 5,
    "tier_unknown": 6,
}

TIER_LABELS = {
    "tier_1_clinical_translational": "clinical or translational evidence",
    "tier_2_human_biology": "human biological evidence",
    "tier_3_functional_mechanistic": "functional or mechanistic evidence",
    "tier_4_tractability_context": "tractability or target context",
    "tier_5_literature_context": "literature context or co-mention evidence",
    "tier_unknown": "unclassified evidence",
}


def classify_evidence_item(item: dict[str, Any]) -> dict[str, Any]:
    """Classify one evidence item into a conservative biomedical evidence tier."""

    text = evidence_text(item)
    body = evidence_body_text(item)
    tier = infer_tier(text, body)
    evidence_kind = infer_evidence_kind(text, tier)
    return {
        "evidence_tier": tier,
        "evidence_tier_rank": TIER_ORDER[tier],
        "evidence_tier_label": TIER_LABELS[tier],
        "evidence_kind": evidence_kind,
        "hierarchy_confidence": hierarchy_confidence(text, tier),
    }


def annotate_evidence_item(item: dict[str, Any]) -> dict[str, Any]:
    classification = classify_evidence_item(item)
    structured = dict(item.get("structured", {})) if isinstance(item.get("structured"), dict) else {}
    structured["evidence_hierarchy"] = classification
    return {**item, **classification, "structured": structured}


def annotate_evidence_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [annotate_evidence_item(item) for item in items]


def summarize_evidence_hierarchy(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    annotated = [item if item.get("evidence_tier") else annotate_evidence_item(item) for item in evidence]
    counts = Counter(str(item.get("evidence_tier") or "tier_unknown") for item in annotated)
    high_tier_count = counts["tier_1_clinical_translational"] + counts["tier_2_human_biology"]
    weak_count = counts["tier_5_literature_context"] + counts["tier_unknown"]
    total = len(annotated)
    best_rank = min((int(item.get("evidence_tier_rank") or 6) for item in annotated), default=6)
    diversity = len({item.get("evidence_kind") for item in annotated if item.get("evidence_kind")})
    weighted = 0
    for item in annotated:
        rank = int(item.get("evidence_tier_rank") or 6)
        weighted += max(0, 7 - rank)
    hierarchy_score = round((weighted / max(1, total * 6)) * 100, 2)
    return {
        "schema": "autosci.evidence_hierarchy_summary.v0.1",
        "evidence_count": total,
        "tier_counts": dict(sorted(counts.items())),
        "high_tier_evidence_count": high_tier_count,
        "weak_or_unknown_evidence_count": weak_count,
        "best_tier_rank": best_rank if total else None,
        "evidence_kind_diversity": diversity,
        "hierarchy_score": hierarchy_score,
        "weak_only": total > 0 and high_tier_count == 0 and counts["tier_3_functional_mechanistic"] == 0,
        "interpretation": interpret_hierarchy(total, high_tier_count, weak_count, best_rank, hierarchy_score),
    }


def evidence_text(item: dict[str, Any]) -> str:
    score = item.get("score", {}) if isinstance(item.get("score"), dict) else {}
    structured = item.get("structured", {}) if isinstance(item.get("structured"), dict) else {}
    parts = [
        item.get("source"),
        item.get("text"),
        item.get("evidence_type"),
        score.get("label"),
        score.get("evidence_type"),
        score.get("rationale"),
        structured.get("evidence_type"),
        structured.get("source_policy"),
    ]
    return " ".join(str(part).lower() for part in parts if part)


def infer_tier(text: str, body: str | None = None) -> str:
    body_text = body if body is not None else text
    if has_clinical_translational_signal(text, body_text):
        return "tier_1_clinical_translational"
    if any(term in text for term in ["human", "patient", "gwas", "genetic", "variant", "cohort", "patient-derived"]):
        return "tier_2_human_biology"
    if any(
        term in text
        for term in ["perturbation", "knockout", "knockdown", "functional", "pathway", "mechanism", "signaling", "reactome"]
    ):
        return "tier_3_functional_mechanistic"
    if any(term in text for term in ["tractability", "compound", "ligand", "structure", "druggable", "target metadata"]):
        return "tier_4_tractability_context"
    if any(term in text for term in ["pubmed", "literature", "co-mention", "records", "review"]):
        return "tier_5_literature_context"
    return "tier_unknown"


def has_clinical_translational_signal(text: str, body: str | None = None) -> bool:
    body_text = body if body is not None else text
    if is_pubmed_query_context_only(text, body_text):
        return False
    strong_terms = [
        "approved drug",
        "approved therapy",
        "maximum clinical stage of approval",
        "approved indication",
        "approved indications",
        "clinicaltrials.gov",
        "interventional",
        "phase 1",
        "phase 2",
        "phase 3",
        "phase 4",
        "randomized",
        "trial results",
        "clinical trial evidence",
        "translational study",
    ]
    if any(term in body_text for term in strong_terms):
        return True
    if "clinical_precedence" in body_text and any(term in body_text for term in ["approved", "phase", "trial", "interventional"]):
        return True
    return False


def evidence_body_text(item: dict[str, Any]) -> str:
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
    return " ".join(str(part).lower() for part in parts if part)


def is_pubmed_query_context_only(text: str, body: str) -> bool:
    if "pubmed:" not in text:
        return False
    if not any(term in text for term in ["clinical precedence", "clinical trial", "phase", "failed trial", "not associated"]):
        return False
    placeholder = any(
        term in body
        for term in [
            "returned live literature search results",
            "literature search returned records",
            "search returned records",
            "returned records",
        ]
    )
    if placeholder:
        return True
    return not any(
        term in body
        for term in [
            "clinical trial",
            "randomized",
            "phase 1",
            "phase 2",
            "phase 3",
            "phase 4",
            "approved",
            "approval",
            "interventional",
            "trial results",
            "therapeutic efficacy",
        ]
    )


def infer_evidence_kind(text: str, tier: str) -> str:
    if "open targets" in text or "opentargets" in text:
        return "open_targets"
    if "tooluniverse" in text:
        return "tooluniverse"
    if "pubmed" in text or "pmid" in text:
        return "pubmed"
    if "clinical" in text or "trial" in text or "clinicaltrials.gov" in text:
        return "clinical"
    if "safety" in text or "adverse" in text or "toxicity" in text or "openfda" in text or "faers" in text:
        return "safety"
    if "reactome" in text or "pathway" in text or "mechanism" in text or "signaling" in text:
        return "mechanism"
    return tier


def hierarchy_confidence(text: str, tier: str) -> str:
    if tier == "tier_unknown":
        return "low"
    if any(term in text for term in ["status success", "matched", "approved", "clinical", "human", "patient"]):
        return "high"
    if any(term in text for term in ["pubmed", "literature", "pathway", "mechanism", "tractability"]):
        return "moderate"
    return "low"


def interpret_hierarchy(
    total: int,
    high_tier_count: int,
    weak_count: int,
    best_rank: int,
    hierarchy_score: float,
) -> str:
    if total == 0:
        return "no evidence available"
    if high_tier_count and hierarchy_score >= 55:
        return "stronger evidence mix with clinical/human support"
    if best_rank <= 3 and weak_count < total:
        return "moderate evidence mix with mechanistic support"
    if weak_count == total:
        return "weak evidence mix dominated by literature context or unknown evidence"
    return "partial evidence mix; higher-tier evidence should be sought"
