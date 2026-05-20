from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ScientificTaskType(str, Enum):
    TARGET_DISCOVERY = "target_discovery"
    MECHANISM_ANALYSIS = "mechanism_analysis"
    THERAPEUTIC_REASONING = "therapeutic_reasoning"
    DRUG_SAFETY = "drug_safety"
    OMICS_ANALYSIS = "omics_analysis"
    EXPERIMENT_DESIGN = "experiment_design"
    LITERATURE_SYNTHESIS = "literature_synthesis"
    REPORT_EVALUATION = "report_evaluation"


class EvidenceType(str, Enum):
    LITERATURE = "literature"
    TOOL_RESULT = "tool_result"
    MODEL_OUTPUT = "model_output"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    OMICS_ANALYSIS = "omics_analysis"
    DRUG_LABEL_OR_SAFETY = "drug_label_or_safety"
    MECHANISTIC = "mechanistic"
    CONTRADICTORY = "contradictory"
    ABSENCE_OF_EVIDENCE = "absence_of_evidence"
    LOCAL_CONTEXT = "local_context"


class ClaimBoundary(str, Enum):
    MECHANISTIC = "mechanistic"
    COMPUTATIONAL_PRIORITIZATION = "computational_prioritization"
    PRECLINICAL_HYPOTHESIS = "preclinical_hypothesis"
    CLINICAL_EFFICACY_FORBIDDEN = "clinical_efficacy_forbidden"
    SAFETY_CLAIM_FORBIDDEN = "safety_claim_forbidden"
    ABSTAIN = "abstain"


@dataclass
class ObjectiveClassification:
    task_types: list[str]
    primary_task: str
    domain: str
    entities: dict[str, list[str]]
    risk_level: str
    required_capabilities: list[str]
    rationale: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return {
            "task_types": self.task_types,
            "primary_task": self.primary_task,
            "domain": self.domain,
            "entities": self.entities,
            "risk_level": self.risk_level,
            "required_capabilities": self.required_capabilities,
            "rationale": self.rationale,
        }


def classify_objective(objective: str, biomedical_context: dict[str, Any] | None = None) -> ObjectiveClassification:
    text = objective.lower()
    context = biomedical_context or {}
    task_types: list[ScientificTaskType] = []
    rationale: list[str] = []

    def add(task: ScientificTaskType, reason: str) -> None:
        if task not in task_types:
            task_types.append(task)
            rationale.append(reason)

    if any(term in text for term in ["drug", "compound", "therapy", "therapeutic", "treatment", "repurpos"]):
        add(ScientificTaskType.THERAPEUTIC_REASONING, "The objective asks about drugs, therapies, or interventions.")
    if any(term in text for term in ["contraindication", "interaction", "dose", "dosage", "safety", "toxicity", "adverse"]):
        add(ScientificTaskType.DRUG_SAFETY, "The objective includes safety, dosing, toxicity, or interaction language.")
    if any(term in text for term in ["omics", "single-cell", "single cell", "transcript", "proteomic", "expression", "rna-seq", "scrna"]):
        add(ScientificTaskType.OMICS_ANALYSIS, "The objective requires omics or cell-context analysis.")
    if any(term in text for term in ["target", "gene", "biomarker"]):
        add(ScientificTaskType.TARGET_DISCOVERY, "The objective refers to targets, genes, or biomarkers.")
    if any(term in text for term in ["mechanism", "pathway", "causal", "signaling"]):
        add(ScientificTaskType.MECHANISM_ANALYSIS, "The objective asks for mechanism or pathway reasoning.")
    if any(term in text for term in ["experiment", "validate", "assay", "study design", "validation"]):
        add(ScientificTaskType.EXPERIMENT_DESIGN, "The objective asks for experiments or validation.")
    if any(term in text for term in ["literature", "citation", "paper", "pubmed", "review"]):
        add(ScientificTaskType.LITERATURE_SYNTHESIS, "The objective asks for literature or citations.")
    if any(term in text for term in ["evaluate", "score", "rubric", "criteria", "quality"]):
        add(ScientificTaskType.REPORT_EVALUATION, "The objective asks for evaluation or scoring.")
    if not task_types:
        add(ScientificTaskType.MECHANISM_ANALYSIS, "Defaulted to mechanism analysis for a biomedical research objective.")

    primary_task = task_types[0].value
    domain = "biomedicine"
    if ScientificTaskType.OMICS_ANALYSIS in task_types:
        domain = "biomedical_omics"
    elif ScientificTaskType.DRUG_SAFETY in task_types or ScientificTaskType.THERAPEUTIC_REASONING in task_types:
        domain = "therapeutics"

    genes = list(dict.fromkeys(context.get("primary_genes", []) or _extract_gene_like_tokens(objective)))
    diseases = list(dict.fromkeys(context.get("diseases", []) or _extract_disease_like_phrases(objective)))
    interventions = list(dict.fromkeys(context.get("candidate_interventions", []) or _extract_intervention_terms(objective)))
    risk_level = "high" if ScientificTaskType.DRUG_SAFETY in task_types else "medium"
    if "clinical" in text or "patient" in text or "dosage" in text:
        risk_level = "high"

    capabilities = route_capabilities([task.value for task in task_types], risk_level)
    return ObjectiveClassification(
        task_types=[task.value for task in task_types],
        primary_task=primary_task,
        domain=domain,
        entities={"genes": genes[:6], "diseases": diseases[:4], "interventions": interventions[:8]},
        risk_level=risk_level,
        required_capabilities=capabilities,
        rationale=rationale,
    )


def route_capabilities(task_types: list[str], risk_level: str) -> list[str]:
    capabilities = ["tooluniverse", "qworld", "clawinstitute_board"]
    tasks = set(task_types)
    if ScientificTaskType.OMICS_ANALYSIS.value in tasks:
        capabilities.append("medea")
    if ScientificTaskType.THERAPEUTIC_REASONING.value in tasks or ScientificTaskType.DRUG_SAFETY.value in tasks:
        capabilities.append("txagent")
    if ScientificTaskType.REPORT_EVALUATION.value in tasks:
        capabilities.append("qworld")
    if risk_level == "high":
        capabilities.extend(["safety_reviewer", "abstention_policy"])
    return list(dict.fromkeys(capabilities))


def build_capability_plan(classification: dict[str, Any]) -> dict[str, Any]:
    tasks = set(classification.get("task_types", []))
    steps = [
        {"capability": "qworld", "purpose": "Generate question-specific success criteria before the run."},
        {"capability": "tooluniverse", "purpose": "Collect biomedical tool evidence with provenance."},
    ]
    if "omics_analysis" in tasks:
        steps.append({"capability": "medea", "purpose": "Run omics planning, analysis, verification, and reconciliation when configured."})
    if "therapeutic_reasoning" in tasks or "drug_safety" in tasks:
        steps.append({"capability": "txagent", "purpose": "Run therapeutic reasoning over drug, contraindication, interaction, and safety context when configured."})
    steps.extend(
        [
            {"capability": "claim_graph", "purpose": "Attach every claim to supporting, contradictory, or missing evidence."},
            {"capability": "clawinstitute_board", "purpose": "Publish hypotheses, critiques, revisions, and provenance to the research board."},
        ]
    )
    return {"routing_policy": "task_type_and_risk", "steps": steps}


def fallback_evaluation_criteria(objective: str, classification: dict[str, Any]) -> list[dict[str, Any]]:
    criteria = [
        {"criterion": "Identifies the primary biomedical entities and objective scope.", "points": 2},
        {"criterion": "Separates direct evidence from indirect or planning-only evidence.", "points": 3},
        {"criterion": "States uncertainty and avoids unsupported clinical efficacy or safety claims.", "points": 4},
        {"criterion": "Includes limitations and concrete validation experiments.", "points": 3},
    ]
    tasks = set(classification.get("task_types", []))
    if "therapeutic_reasoning" in tasks or "drug_safety" in tasks:
        criteria.append({"criterion": "Reviews intervention-specific safety, contraindication, and translation gaps.", "points": 4})
    if "omics_analysis" in tasks:
        criteria.append({"criterion": "Checks omics context, cell type, dataset compatibility, and analysis validity.", "points": 4})
    if "target_discovery" in tasks:
        criteria.append({"criterion": "Explains target-disease relevance without overstating causality.", "points": 3})
    if objective:
        criteria.append({"criterion": "Answers the specific user objective rather than a generic biomedical prompt.", "points": 4})
    return criteria


def infer_evidence_type(item: dict[str, Any]) -> str:
    source = str(item.get("source", "")).lower()
    text = str(item.get("text", "")).lower()
    if source.startswith("local_"):
        return EvidenceType.LOCAL_CONTEXT.value
    if "pubmed" in source or "pmid" in text:
        return EvidenceType.LITERATURE.value
    if "txagent" in source or any(term in text for term in ["contraindication", "adverse", "dosage"]):
        return EvidenceType.DRUG_LABEL_OR_SAFETY.value
    if "medea" in source or any(term in text for term in ["omics", "single-cell", "transcriptomic"]):
        return EvidenceType.OMICS_ANALYSIS.value
    if "opentargets" in source or "tooluniverse" in source:
        return EvidenceType.TOOL_RESULT.value
    if "model" in source:
        return EvidenceType.MODEL_OUTPUT.value
    if any(term in text for term in ["no evidence", "not retrieved", "insufficient"]):
        return EvidenceType.ABSENCE_OF_EVIDENCE.value
    if any(term in text for term in ["contradict", "conflict", "opposes"]):
        return EvidenceType.CONTRADICTORY.value
    return EvidenceType.MECHANISTIC.value


def type_evidence_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    typed = []
    for item in items:
        evidence_type = item.get("evidence_type") or infer_evidence_type(item)
        structured = dict(item.get("structured", {}))
        structured.setdefault("evidence_type", evidence_type)
        typed.append({**item, "evidence_type": evidence_type, "structured": structured})
    return typed


def build_claim_graph(hypothesis_card: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    hypothesis = str(hypothesis_card.get("hypothesis") or "")
    claims = _split_claims(hypothesis)
    if not claims and hypothesis:
        claims = [hypothesis]
    nodes = []
    for index, claim in enumerate(claims[:6], start=1):
        support = []
        contradiction = []
        gaps = []
        for item in evidence:
            evidence_type = item.get("evidence_type") or infer_evidence_type(item)
            source = item.get("source", "unknown")
            score = item.get("score", {})
            label = score.get("label") if isinstance(score, dict) else None
            if evidence_type in {EvidenceType.CONTRADICTORY.value} or label == "contradiction":
                contradiction.append(source)
            elif evidence_type in {EvidenceType.ABSENCE_OF_EVIDENCE.value, EvidenceType.LOCAL_CONTEXT.value}:
                gaps.append(source)
            else:
                support.append(source)
        boundary = ClaimBoundary.COMPUTATIONAL_PRIORITIZATION.value
        if not support:
            boundary = ClaimBoundary.ABSTAIN.value
        if any(term in claim.lower() for term in ["safe", "efficacy", "effective", "treats", "cures"]):
            boundary = ClaimBoundary.CLINICAL_EFFICACY_FORBIDDEN.value
        nodes.append(
            {
                "id": f"claim_{index}",
                "text": claim,
                "supporting_evidence_sources": sorted(set(support)),
                "contradictory_evidence_sources": sorted(set(contradiction)),
                "evidence_gaps": sorted(set(gaps)),
                "claim_boundary": boundary,
            }
        )
    return {"claims": nodes, "evidence_count": len(evidence), "policy": "claim_evidence_boundary_v1"}


def build_abstention_assessment(classification: dict[str, Any], evidence: list[dict[str, Any]], claim_graph: dict[str, Any]) -> dict[str, Any]:
    evidence_types = {item.get("evidence_type") or infer_evidence_type(item) for item in evidence}
    reasons = []
    if not evidence or evidence_types <= {EvidenceType.LOCAL_CONTEXT.value, EvidenceType.ABSENCE_OF_EVIDENCE.value}:
        reasons.append("Only local planning context or absence-of-evidence records are available.")
    if classification.get("risk_level") == "high" and EvidenceType.DRUG_LABEL_OR_SAFETY.value not in evidence_types:
        reasons.append("High-risk therapeutic or patient-context objective lacks safety-specific evidence.")
    unsupported_claims = [
        claim for claim in claim_graph.get("claims", []) if claim.get("claim_boundary") == ClaimBoundary.ABSTAIN.value
    ]
    if unsupported_claims:
        reasons.append("At least one generated claim lacks external supporting evidence.")
    return {
        "abstention_required": bool(reasons),
        "reasons": reasons,
        "allowed_output": (
            "candidate hypothesis with explicit limitations"
            if not reasons
            else "planning-only or insufficient-evidence response with no efficacy/safety claim"
        ),
    }


def evaluate_report_against_criteria(report: dict[str, Any], criteria: list[dict[str, Any]]) -> dict[str, Any]:
    text = " ".join(
        [
            str(report.get("title", "")),
            str(report.get("summary", "")),
            " ".join(str(item) for item in report.get("guardrails", [])),
            " ".join(str(item) for item in report.get("next_experiments", [])),
        ]
    ).lower()
    scored = []
    earned = 0
    total = 0
    for criterion in criteria:
        points = int(criterion.get("points", 1) or 1)
        total += points
        label = str(criterion.get("criterion", ""))
        tokens = [token for token in re.findall(r"[a-z]{4,}", label.lower()) if token not in {"criterion", "specific"}]
        matched = sum(1 for token in tokens if token in text)
        satisfied = matched >= max(1, min(3, len(tokens) // 4))
        if satisfied:
            earned += points
        scored.append({**criterion, "satisfied": satisfied, "matched_terms": matched})
    return {
        "score": round(earned / total, 3) if total else 0.0,
        "earned_points": earned,
        "total_points": total,
        "criteria": scored,
        "method": "keyword_coverage_fallback",
    }


def _extract_gene_like_tokens(text: str) -> list[str]:
    stop = {"AND", "THE", "USE", "NOT", "FOR", "WITH", "DNA", "RNA", "LLM"}
    return [match for match in re.findall(r"\b[A-Z][A-Z0-9]{2,9}\b", text) if match not in stop]


def _extract_disease_like_phrases(text: str) -> list[str]:
    phrases = []
    for pattern in [
        r"for ([A-Za-z][A-Za-z0-9 /'-]+?)(?:\.|,|;| and | with | by |$)",
        r"in ([A-Za-z][A-Za-z0-9 /'-]+?)(?:\.|,|;| and | with | by |$)",
    ]:
        match = re.search(pattern, text)
        if match:
            phrases.append(re.sub(r"^[A-Z0-9]+-driven\s+", "", match.group(1), flags=re.I).strip())
    return phrases


def _extract_intervention_terms(text: str) -> list[str]:
    candidates = []
    for pattern in [r"\b(?:drug|compound|therapy|treatment)\s+([A-Za-z0-9 -]{3,40})"]:
        candidates.extend(match.strip() for match in re.findall(pattern, text, flags=re.I))
    return candidates


def _split_claims(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|;\s+", text.strip())
    return [part.strip() for part in parts if len(part.strip()) > 20]
