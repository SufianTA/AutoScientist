from tools.custom_tools.base import ScientificTool, ToolResult


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
    for item in evidence:
        score += weights.get(item.get("score", {}).get("label"), 0.0)
    return round(max(0.05, min(score, 0.78)), 2)


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


class HypothesisCardGeneratorTool(ScientificTool):
    name = "hypothesis_card_generator_tool"
    description = "Creates a structured candidate hypothesis card from disease, target, molecule, and evidence records."
    example_input = {"target": "ACVR1", "disease": "FOP", "evidence": []}

    def _run(self, payload: dict) -> ToolResult:
        target = payload.get("target", "ACVR1")
        disease = payload.get("disease", "FOP")
        evidence = payload.get("evidence", [])
        confidence = confidence_from_evidence(evidence)
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
                if any(term in title.lower() for term in ["treatment", "therapeutic", "inhibitor", "drug", "modality"]):
                    literature_candidate_titles.append(title)
        contradictions = []
        if safety_items:
            contradictions.append(
                "Safety/intervention literature was retrieved, so translational risk remains an active uncertainty."
            )
        return ToolResult(
            status="success",
            input=payload,
            output={
                "title": f"{target} pathway modulation as a candidate strategy for {disease}",
                "hypothesis": (
                    f"Modulating {target}-linked BMP signaling is a candidate, evidence-supported but "
                    f"not validated therapeutic hypothesis for {disease}."
                ),
                "evidence": evidence,
                "evidence_label_counts": counts,
                "scientific_assessment": [
                    (
                        f"The disease-target rationale is biologically plausible when live/public evidence links "
                        f"{target} to {disease} through disease association, pathway, or mechanism records."
                    ),
                    (
                        "The current claim should remain pathway-level: evidence supports target and mechanism "
                        "grounding, not clinical efficacy for any intervention."
                    ),
                    (
                        "Candidate molecules or interventions are prioritization leads only; potency, selectivity, "
                        "exposure, safety, and disease-model response must be tested."
                    ),
                ],
                "candidate_intervention_summary": (
                    "PubChem/literature candidate records were found, but none are asserted as clinically effective."
                    if candidate_items
                    else (
                        "Live literature retrieved candidate intervention or treatment records, but they are not "
                        f"asserted as clinically effective: {'; '.join(literature_candidate_titles[:4])}."
                        if literature_candidate_titles
                        else "No candidate intervention records were retrieved in this run."
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
