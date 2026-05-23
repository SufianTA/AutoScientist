from tools.custom_tools.base import ScientificTool, ToolResult
from tools.custom_tools.clinical_status import (
    classify_clinical_status,
    clinical_literature_titles,
)


def label_counts(evidence: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in evidence:
        label = item.get("score", {}).get("label", "unscored")
        counts[label] = counts.get(label, 0) + 1
    return counts


def confidence_from_evidence(evidence: list[dict]) -> float:
    score = 0.42
    weights = {
        "strong_support": 0.08,
        "weak_support": 0.04,
        "mechanistic_relevance": 0.02,
        "safety_concern": -0.08,
        "contradicts": -0.12,
        "irrelevant": -0.04,
    }
    clinical_or_public_floor = 0.0
    for item in evidence:
        score += weights.get(item.get("score", {}).get("label"), 0.0)
        structured = item.get("structured", {}) if isinstance(item.get("structured"), dict) else {}
        labels = structured.get("public_labels", {}) if isinstance(structured.get("public_labels"), dict) else {}
        evidence_type = str(item.get("score", {}).get("evidence_type") or structured.get("evidence_type") or "")
        if labels.get("open_targets_association_status") == "matched":
            try:
                association_score = float(labels.get("open_targets_association_score") or 0.0)
            except (TypeError, ValueError):
                association_score = 0.0
            if association_score >= 0.5:
                clinical_or_public_floor = max(clinical_or_public_floor, 0.68)
            elif association_score >= 0.25:
                clinical_or_public_floor = max(clinical_or_public_floor, 0.6)
        if evidence_type in {"clinical_precedence", "clinical_precedence_literature"}:
            clinical_or_public_floor = max(clinical_or_public_floor, 0.72)
    return round(max(0.05, clinical_or_public_floor, min(score, 0.86)), 2)


def mechanism_phrase(target: str, evidence: list[dict]) -> str:
    combined = " ".join(
        [
            target,
            *[
                str(item.get("text", ""))
                for item in evidence[:8]
            ],
        ]
    ).lower()
    if "acvr1" in target.lower() or "bmp" in combined or "ossification" in combined:
        return f"{target}-linked BMP/activin pathway signaling"
    if "pcsk9" in target.lower() or "ldlr" in combined or "cholesterol" in combined:
        return f"{target}-linked LDL receptor and cholesterol-clearance biology"
    if "cftr" in target.lower() or "cystic fibrosis" in combined:
        return f"{target}-linked epithelial ion-transport biology"
    if "tnf" in target.lower() or "anti-tnf" in combined or "inflammatory bowel" in combined:
        return f"{target}-linked inflammatory cytokine signaling and immune-cell activation"
    if "il6" in target.lower() or "il-6" in combined or "rheumatoid arthritis" in combined:
        return f"{target}-linked IL-6 inflammatory signaling, including receptor-mediated pathway context"
    return f"{target}-linked disease mechanism"


def extract_citations(evidence: list[dict], target: str) -> list[dict]:
    citations = []
    for item in evidence:
        structured = item.get("structured", {})
        for article in structured.get("articles", []):
            citations.append(
                {
                    "source": "PubMed",
                    "title": article.get("title"),
                    "url": article.get("url"),
                    "pmid": article.get("pmid"),
                    "journal": article.get("journal"),
                    "pubdate": article.get("pubdate"),
                }
            )
        for compound in structured.get("compounds", []):
            citations.append(
                {
                    "source": "PubChem",
                    "title": compound.get("name"),
                    "url": compound.get("url"),
                    "cid": compound.get("cid"),
                }
            )
        if structured.get("gene_id"):
            citations.append(
                {
                    "source": "NCBI Gene",
                    "title": structured.get("gene_symbol", target),
                    "url": f"https://www.ncbi.nlm.nih.gov/gene/{structured['gene_id']}",
                    "gene_id": structured.get("gene_id"),
                }
            )
    return citations[:12]


def clinical_precedence_summary(target: str, disease: str, evidence: list[dict]) -> str:
    public_lines = []
    literature_titles = clinical_literature_titles(evidence, target, disease)
    has_target_level_precedence = False
    for item in evidence:
        structured = item.get("structured", {}) if isinstance(item.get("structured"), dict) else {}
        labels = structured.get("public_labels", {}) if isinstance(structured.get("public_labels"), dict) else {}
        evidence_type = str(item.get("score", {}).get("evidence_type") or structured.get("evidence_type") or "")
        if labels.get("open_targets_association_status") == "matched":
            public_lines.append(
                f"Open Targets reports a matched {target}/{disease} association "
                f"(score {labels.get('open_targets_association_score')}, rank {labels.get('open_targets_association_rank')})."
            )
        if evidence_type == "clinical_precedence":
            has_target_level_precedence = True
            public_lines.append(f"Open Targets target metadata indicates target-level clinical or tractability precedence for {target}.")
    if public_lines or literature_titles:
        pieces = [*public_lines[:2]]
        if has_target_level_precedence:
            pieces.append(
                "This should be framed as clinical or translational precedence with unresolved response, "
                "resistance, safety, mechanism, and patient-stratification questions."
            )
        if literature_titles:
            pieces.append("Relevant clinical literature titles include: " + "; ".join(literature_titles[:3]) + ".")
        return " ".join(pieces)
    return (
        f"No explicit clinical-precedence evidence for {target} in {disease} was surfaced; the output should focus "
        "on target-disease grounding and unresolved validation."
    )


class HypothesisCardGeneratorTool(ScientificTool):
    name = "hypothesis_card_generator_tool"
    description = "Creates a structured candidate hypothesis card from disease, target, molecule, and evidence records."
    example_input = {"target": "PCSK9", "disease": "familial hypercholesterolemia", "evidence": []}

    def _run(self, payload: dict) -> ToolResult:
        target = payload.get("target", "disease-relevant target")
        disease = payload.get("disease", "the specified disease context")
        evidence = payload.get("evidence", [])
        confidence = confidence_from_evidence(evidence)
        mechanism = mechanism_phrase(target, evidence)
        clinical_status = classify_clinical_status(target, disease, evidence)
        confidence = max(confidence, float(clinical_status.get("confidence_floor") or 0.0))
        local_only = bool(evidence) and all(str(item.get("source", "")).startswith("local_") for item in evidence)
        counts = label_counts(evidence)
        safety_items = [
            item for item in evidence if item.get("score", {}).get("label") == "safety_concern"
        ]
        candidate_items = [
            item for item in evidence if "pubchem" in item.get("source", "").lower()
        ]
        literature_candidate_titles = []
        for item in evidence:
            if "pubmed" not in item.get("source", "").lower():
                continue
            for article in item.get("structured", {}).get("articles", []):
                title = article.get("title", "")
                if any(
                    term in title.lower()
                    for term in [
                        "treatment",
                        "therapeutic",
                        "therapy",
                        "clinical",
                        "trial",
                        "inhibitor",
                        "antibody",
                        "anti-tnf",
                        "anti-il",
                        "drug",
                        "modality",
                    ]
                ):
                    literature_candidate_titles.append(title)
        precedence = clinical_precedence_summary(target, disease, evidence)
        contradictions = []
        if safety_items:
            contradictions.append(
                "Safety/intervention literature was retrieved, so translational risk remains an active uncertainty."
            )
        has_precedence = "No explicit clinical-precedence evidence" not in precedence
        status = str(clinical_status.get("status", "speculative_or_insufficient"))
        if status == "established_or_clinically_precedented":
            status_framing = (
                f"{target} has established or clinically precedented target-disease grounding for {disease}. "
                "The output should not present this as a new target discovery."
            )
        elif status == "genetically_or_publicly_grounded":
            status_framing = (
                f"{target} is publicly grounded for {disease}, but association evidence must be separated from "
                "clinical efficacy, safety, druggability, and intervention directionality."
            )
        else:
            status_framing = (
                f"{target} remains an early or insufficiently established hypothesis for {disease}; claims require "
                "explicit validation and stronger public evidence."
            )
        return ToolResult(
            status="success",
            input=payload,
            output={
                "title": (
                    f"{target} clinical-precedence and mechanism review for {disease}"
                    if has_precedence
                    else f"{target} pathway modulation as a candidate strategy for {disease}"
                ),
                "hypothesis": (
                    f"Modulating {mechanism} is a planning-level candidate hypothesis for {disease} "
                    "that requires live external evidence before scientific interpretation."
                    if local_only
                    else (
                        f"{status_framing} "
                        f"{precedence} The remaining scientific work is to resolve mechanism details, "
                        "response or resistance biology, safety liabilities, and patient-selection strategy; "
                        "this is not a claim that a new target has been discovered."
                    )
                ),
                "evidence": evidence,
                "evidence_label_counts": counts,
                "clinical_status": clinical_status,
                "scientific_assessment": [
                    clinical_status["interpretation"],
                    (
                        f"The disease-target rationale is biologically plausible when live/public evidence links "
                        f"{target} to {disease} through disease association, pathway, or mechanism records."
                    ),
                    (
                        "The current claim should remain pathway-level: evidence supports target and mechanism "
                        "grounding, not clinical efficacy for any intervention unless direct clinical evidence is cited."
                    ),
                    precedence,
                    (
                        "Candidate molecules or interventions are prioritization leads only; potency, selectivity, "
                        "exposure, safety, and disease-model response must be tested."
                    ),
                ],
                "candidate_intervention_summary": (
                    "No live candidate intervention records were retrieved in this local planning run."
                    if local_only
                    else (
                    "PubChem/literature candidate records were found, but none are asserted as clinically effective."
                    if candidate_items
                    else (
                        "Live literature retrieved treatment, clinical, or intervention-precedence signals; "
                        "the downstream synthesis should distinguish established clinical use from unresolved "
                        f"mechanism, resistance, safety, or stratification questions: {'; '.join(literature_candidate_titles[:4])}."
                        if literature_candidate_titles
                        else "No candidate intervention records were retrieved in this run."
                    )
                    )
                ),
                "contradictions": contradictions,
                "citations": extract_citations(evidence, target),
                "confidence": confidence,
                "confidence_interpretation": "moderate" if confidence >= 0.55 else "low",
                "limitations": [
                    "Live public database records support hypothesis generation but do not validate efficacy.",
                    "No clinical efficacy or safety claim is made.",
                    "Compound specificity and translational risk remain unresolved.",
                    "Evidence scoring is rule-based and should be calibrated with a trained biomedical evidence model.",
                ],
            },
            confidence=confidence,
        )
