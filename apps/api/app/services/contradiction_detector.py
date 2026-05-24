from __future__ import annotations

from typing import Any


NEGATIVE_TERMS = {
    "failed",
    "failure",
    "negative",
    "no association",
    "not associated",
    "lack of association",
    "did not improve",
    "no benefit",
    "worse",
}

SAFETY_TERMS = {
    "toxicity",
    "toxic",
    "adverse",
    "contraindication",
    "intolerable",
    "black box",
    "safety signal",
}

CONTEXT_MISMATCH_TERMS = {
    "wrong tissue",
    "wrong disease",
    "subtype",
    "not disease-specific",
    "biomarker only",
    "correlative",
}

RESISTANCE_TERMS = {
    "resistance",
    "escape",
    "compensation",
    "redundant pathway",
    "feedback activation",
}


def build_contradiction_queries(task: dict[str, Any]) -> list[str]:
    gene = str(task.get("gene_symbol") or "target").strip()
    disease = str(task.get("disease_name") or "disease").strip()
    if not gene or gene == "target" or not disease or disease == "disease":
        return []
    return [
        f"{gene} {disease} failed trial",
        f"{gene} {disease} no association",
        f"{gene} {disease} adverse toxicity",
        f"{gene} {disease} resistance mechanism",
        f"{gene} {disease} subtype mismatch",
    ]


def detect_contradictions(
    *,
    task: dict[str, Any],
    evidence: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    findings = []
    for item in evidence:
        finding = classify_contradiction_item(item)
        if finding:
            findings.append(finding)
    categories = sorted({finding["category"] for finding in findings})
    queries = build_contradiction_queries(task)
    searched = contradiction_search_was_attempted(tool_calls or [], evidence)
    return {
        "schema": "autosci.contradiction_analysis.v0.1",
        "planned_queries": queries,
        "contradiction_search_attempted": searched,
        "finding_count": len(findings),
        "categories": categories,
        "findings": findings[:12],
        "coverage": {
            "negative_evidence": "negative_evidence" in categories,
            "safety": "safety" in categories,
            "context_mismatch": "context_mismatch" in categories,
            "resistance_or_compensation": "resistance_or_compensation" in categories,
        },
        "interpretation": interpret_contradictions(findings, searched),
    }


def classify_contradiction_item(item: dict[str, Any]) -> dict[str, Any] | None:
    text = item_text(item)
    score = item.get("score", {}) if isinstance(item.get("score"), dict) else {}
    label = str(score.get("label") or "").lower()
    category = None
    terms = []
    if label in {"contradiction", "contradicts"} or any(term in text for term in NEGATIVE_TERMS):
        category = "negative_evidence"
        terms.extend([term for term in NEGATIVE_TERMS if term in text])
    if any(term in text for term in SAFETY_TERMS):
        category = category or "safety"
        terms.extend([term for term in SAFETY_TERMS if term in text])
    if any(term in text for term in CONTEXT_MISMATCH_TERMS):
        category = category or "context_mismatch"
        terms.extend([term for term in CONTEXT_MISMATCH_TERMS if term in text])
    if any(term in text for term in RESISTANCE_TERMS):
        category = category or "resistance_or_compensation"
        terms.extend([term for term in RESISTANCE_TERMS if term in text])
    if category is None:
        return None
    return {
        "category": category,
        "matched_terms": sorted(set(terms)),
        "source": item.get("source", "unknown"),
        "evidence_type": item.get("evidence_type") or score.get("evidence_type"),
        "text": str(item.get("text", ""))[:700],
    }


def contradiction_search_was_attempted(tool_calls: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> bool:
    combined = " ".join(
        [
            *[
                " ".join(str(value).lower() for value in [call.get("tool_name"), call.get("input"), call.get("args")] if value)
                for call in tool_calls
            ],
            *[item_text(item) for item in evidence],
        ]
    )
    return any(term in combined for term in ["failed trial", "no association", "toxicity", "adverse", "resistance"])


def item_text(item: dict[str, Any]) -> str:
    score = item.get("score", {}) if isinstance(item.get("score"), dict) else {}
    return " ".join(
        str(value).lower()
        for value in [
            item.get("source"),
            item.get("text"),
            item.get("evidence_type"),
            score.get("label"),
            score.get("evidence_type"),
            score.get("rationale"),
        ]
        if value
    )


def interpret_contradictions(findings: list[dict[str, Any]], searched: bool) -> str:
    if findings:
        return "counterevidence or limitation signals were detected and must be addressed in the final claim"
    if searched:
        return "contradiction-oriented search was attempted, but no explicit contradiction signal was detected"
    return "contradiction search coverage is incomplete"
