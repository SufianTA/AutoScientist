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
        text = f"{payload.get('hypothesis', '')} {payload.get('evidence_text', '')}".lower()
        if any(term in text for term in ["toxicity", "unsafe", "adverse"]):
            label, score, evidence_type = "safety_concern", 0.72, "safety"
        elif "acvr1" in text and ("fop" in text or "fibrodysplasia" in text) and ("bmp" in text or "osteogenic" in text):
            label, score, evidence_type = "strong_support", 0.84, "mechanistic"
        elif "acvr1" in text or "bmp" in text:
            label, score, evidence_type = "weak_support", 0.58, "mechanistic"
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
                "rationale": "Rule-based prototype scorer. Replace with PubMedBERT/SciBERT classifier for Milestone 5.",
                "warnings": ["Prototype score is not a validation claim."],
            },
            sources=[{"name": "Rule-based evidence scorer", "id": "mock-evidence-scorer-v0.1"}],
            confidence=score,
        )

