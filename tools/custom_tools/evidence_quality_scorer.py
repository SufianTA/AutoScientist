from tools.custom_tools.base import ScientificTool, ToolResult


class EvidenceQualityScorerTool(ScientificTool):
    name = "evidence_quality_scorer_tool"
    description = "Scores whether evidence supports, contradicts, or is irrelevant to a therapeutic hypothesis."
    example_input = {
        "hypothesis": "Inhibiting ACVR1 may reduce aberrant osteogenic signaling in FOP.",
        "evidence_text": "ACVR1 variants activate BMP signaling in FOP models.",
        "evidence_source": "mock_literature",
    }

    def _run(self, payload: dict) -> ToolResult:
        text = str(payload.get("evidence_text", "")).lower()
        hypothesis = str(payload.get("hypothesis", "")).lower()
        source = str(payload.get("evidence_source", "")).lower()
        hypothesis_terms = {
            term
            for term in hypothesis.replace("/", " ").replace("-", " ").split()
            if len(term) >= 4 and term not in {"candidate", "hypothesis", "mechanisms", "relevant", "modulating"}
        }
        overlap = sum(1 for term in hypothesis_terms if term in text)
        if source.startswith("local_objective_context"):
            label, score, evidence_type = "mechanistic_relevance", 0.35, "planning_context"
        elif source.startswith("local_retrieval_plan"):
            label, score, evidence_type = "irrelevant", 0.1, "retrieval_plan"
        elif any(term in text for term in ["toxicity", "unsafe", "adverse", "safety"]):
            label, score, evidence_type = "safety_concern", 0.72, "safety"
        elif (
            "acvr1" in text
            and ("fop" in text or "fibrodysplasia" in text)
            and ("bmp" in text or "osteogenic" in text or "ossification" in text)
        ):
            label, score, evidence_type = "strong_support", 0.84, "mechanistic"
        elif overlap >= 3:
            label, score, evidence_type = "strong_support", 0.76, "mechanistic"
        elif overlap >= 2:
            label, score, evidence_type = "weak_support", 0.61, "mechanistic"
        elif overlap >= 1 and any(term in text for term in ["mutation", "mutations", "associated", "association", "therapeutic target"]):
            label, score, evidence_type = "weak_support", 0.58, "mechanistic"
        elif "acvr1" in text or "bmp" in text or "fibrodysplasia" in text or "ossification" in text:
            label, score, evidence_type = "weak_support", 0.58, "mechanistic"
        elif "pubchem" in text or "candidate" in text or "compound" in text:
            label, score, evidence_type = "mechanistic_relevance", 0.46, "chemical"
        elif "contradict" in text or "no association" in text:
            label, score, evidence_type = "contradicts", 0.69, "literature"
        else:
            label, score, evidence_type = "irrelevant", 0.31, "unknown"
        return ToolResult(
            status="success",
            input=payload,
            output={
                "label": label,
                "score": score,
                "evidence_type": evidence_type,
                "rationale": (
                    "Deterministic evidence scorer using safety terms, biomedical keyword overlap, and "
                    "domain-specific mechanism cues. Strict runs can replace this with a real LLM or onboarded model scorer."
                ),
                "warnings": ["Score is not a validation claim."],
            },
            sources=[{"name": "Deterministic evidence scorer", "id": "evidence-scorer-v0.2"}],
            confidence=score,
        )
