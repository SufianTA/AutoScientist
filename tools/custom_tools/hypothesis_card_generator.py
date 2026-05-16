from tools.custom_tools.base import ScientificTool, ToolResult


class HypothesisCardGeneratorTool(ScientificTool):
    name = "hypothesis_card_generator_tool"
    description = "Creates a structured candidate hypothesis card from disease, target, molecule, and evidence records."
    example_input = {"target": "ACVR1", "disease": "FOP", "evidence": []}

    def _run(self, payload: dict) -> ToolResult:
        target = payload.get("target", "ACVR1")
        disease = payload.get("disease", "FOP")
        evidence = payload.get("evidence", [])
        confidence = min(0.82, 0.45 + 0.08 * len(evidence))
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
                "contradictions": [],
                "confidence": round(confidence, 2),
                "limitations": [
                    "Mock evidence requires replacement with live ToolUniverse and literature calls.",
                    "No clinical efficacy or safety claim is made.",
                    "Compound specificity and translational risk remain unresolved.",
                ],
            },
            confidence=confidence,
        )

