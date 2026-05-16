from tools.custom_tools.base import ScientificTool, ToolResult


class ExperimentRecommendationTool(ScientificTool):
    name = "experiment_recommendation_tool"
    description = "Ranks computational and wet-lab validation steps for a hypothesis card."
    example_input = {"hypothesis_card": {"title": "ACVR1 modulation in FOP"}}

    def _run(self, payload: dict) -> ToolResult:
        hypothesis_card = payload.get("hypothesis_card", {})
        has_safety = bool(hypothesis_card.get("contradictions"))
        return ToolResult(
            status="success",
            input=payload,
            output={
                "experiments": [
                    {
                        "name": "Validate ACVR1/FOP evidence with live target-disease and literature tools",
                        "type": "computational",
                        "cost": "low",
                        "feasibility": "high",
                        "expected_information_gain": "high",
                    },
                    {
                        "name": "Rank candidate interventions by ACVR1/ALK2 potency, selectivity, exposure, and ADMET liabilities",
                        "type": "computational",
                        "cost": "low-medium",
                        "feasibility": "medium",
                        "expected_information_gain": "high",
                    },
                    {
                        "name": (
                            "Run safety-first triage before efficacy assays: exposure margins, off-target kinome/retinoid pathway risk, and disease-context tolerability"
                            if has_safety
                            else "Test BMP pathway readouts in ACVR1-mutant disease-relevant cellular models"
                        ),
                        "type": "computational_plus_wet_lab" if has_safety else "wet_lab",
                        "cost": "medium",
                        "feasibility": "medium",
                        "expected_information_gain": "high",
                    },
                ]
            },
            confidence=0.7,
        )
