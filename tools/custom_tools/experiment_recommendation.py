from tools.custom_tools.base import ScientificTool, ToolResult


class ExperimentRecommendationTool(ScientificTool):
    name = "experiment_recommendation_tool"
    description = "Ranks computational and wet-lab validation steps for a hypothesis card."
    example_input = {"hypothesis_card": {"title": "ACVR1 modulation in FOP"}}

    def _run(self, payload: dict) -> ToolResult:
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
                        "name": "Prioritize candidate inhibitors by potency, selectivity, and ADMET evidence",
                        "type": "computational",
                        "cost": "low-medium",
                        "feasibility": "medium",
                        "expected_information_gain": "high",
                    },
                    {
                        "name": "Test BMP pathway readouts in disease-relevant cellular model",
                        "type": "wet_lab",
                        "cost": "medium",
                        "feasibility": "medium",
                        "expected_information_gain": "high",
                    },
                ]
            },
            confidence=0.7,
        )

