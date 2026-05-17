from tools.custom_tools.base import ScientificTool, ToolResult


class ExperimentRecommendationTool(ScientificTool):
    name = "experiment_recommendation_tool"
    description = "Ranks computational and wet-lab validation steps for a hypothesis card."
    example_input = {"hypothesis_card": {"title": "Target modulation in a disease context"}}

    def _run(self, payload: dict) -> ToolResult:
        hypothesis_card = payload.get("hypothesis_card", {})
        title = str(hypothesis_card.get("title", "candidate hypothesis"))
        hypothesis = str(hypothesis_card.get("hypothesis", ""))
        target = title.split(" pathway modulation", 1)[0].strip() or "the target"
        has_safety = bool(hypothesis_card.get("contradictions"))
        if "acvr1" in title.lower() or "bmp" in hypothesis.lower() or "ossification" in hypothesis.lower():
            wet_lab_readout = "Test disease-relevant BMP/activin pathway readouts in appropriate cellular or animal models"
            intervention_ranking = "Rank candidate interventions by target potency, pathway selectivity, exposure, and ADMET liabilities"
        elif "pcsk9" in title.lower() or "ldlr" in hypothesis.lower() or "cholesterol" in hypothesis.lower():
            wet_lab_readout = "Test LDL receptor abundance, LDL uptake, and cholesterol-clearance readouts in hepatocyte models"
            intervention_ranking = "Rank candidate interventions by PCSK9/LDLR mechanism, durability, exposure, and safety liabilities"
        elif "cftr" in title.lower() or "cystic fibrosis" in hypothesis.lower():
            wet_lab_readout = "Test epithelial ion transport, protein processing, and rescue readouts in disease-relevant airway models"
            intervention_ranking = "Rank candidate interventions by target engagement, rescue magnitude, exposure, and safety liabilities"
        else:
            wet_lab_readout = "Test target-pathway and disease-phenotype readouts in disease-relevant cellular or animal models"
            intervention_ranking = "Rank candidate interventions by target engagement, selectivity, exposure, and ADMET liabilities"
        return ToolResult(
            status="success",
            input=payload,
            output={
                "experiments": [
                    {
                        "name": f"Validate {target} disease-target evidence with live target-disease, literature, and safety tools",
                        "type": "computational",
                        "cost": "low",
                        "feasibility": "high",
                        "expected_information_gain": "high",
                    },
                    {
                        "name": intervention_ranking,
                        "type": "computational",
                        "cost": "low-medium",
                        "feasibility": "medium",
                        "expected_information_gain": "high",
                    },
                    {
                        "name": (
                            "Run safety-first triage before efficacy assays: exposure margins, off-target biology, and disease-context tolerability"
                            if has_safety
                            else wet_lab_readout
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
