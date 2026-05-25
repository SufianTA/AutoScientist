from tools.custom_tools.base import ScientificTool, ToolResult


class ExperimentRecommendationTool(ScientificTool):
    name = "experiment_recommendation_tool"
    description = "Ranks computational and wet-lab validation steps for a hypothesis card."
    example_input = {"hypothesis_card": {"title": "Target modulation in a disease context"}}

    def _run(self, payload: dict) -> ToolResult:
        hypothesis_card = payload.get("hypothesis_card", {})
        title = str(hypothesis_card.get("title", "candidate hypothesis"))
        hypothesis = str(hypothesis_card.get("hypothesis", ""))
        if " pathway modulation" in title:
            target = title.split(" pathway modulation", 1)[0].strip() or "the target"
        elif " clinical-precedence" in title:
            target = title.split(" clinical-precedence", 1)[0].strip() or "the target"
        else:
            target = title.split(" ", 1)[0].strip() or "the target"
        disease = title.rsplit(" for ", 1)[-1].strip() if " for " in title else "the disease context"
        lowered = f"{title} {hypothesis} {disease}".lower()
        has_safety = bool(hypothesis_card.get("contradictions"))
        if "acvr1" in lowered or "bmp" in lowered or "ossification" in lowered:
            wet_lab_readout = "Test disease-relevant BMP/activin pathway readouts in appropriate cellular or animal models"
            intervention_ranking = "Rank candidate interventions by target potency, pathway selectivity, exposure, and ADMET liabilities"
        elif "pcsk9" in lowered or "ldlr" in lowered or "cholesterol" in lowered:
            wet_lab_readout = "Test LDL receptor abundance, LDL uptake, and cholesterol-clearance readouts in hepatocyte models"
            intervention_ranking = "Rank candidate interventions by PCSK9/LDLR mechanism, durability, exposure, and safety liabilities"
        elif "cftr" in lowered or "cystic fibrosis" in lowered:
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
                        "name": (
                            f"Resolve the highest-uncertainty {target} / {disease} evidence gap with targeted "
                            "Open Targets, literature, clinical-precedence, and safety review"
                        ),
                        "type": "computational",
                        "cost": "low",
                        "feasibility": "high",
                        "expected_information_gain": "high",
                        "decision_gate": "Proceed only if the result changes target validity, clinical-precedence interpretation, safety risk, or patient-stratification strategy.",
                        "failure_modes": [
                            "Evidence is indirect or about a related receptor/pathway rather than the target itself.",
                            "Clinical-precedence evidence is retrieved but not separated from new-discovery questions.",
                        ],
                    },
                    {
                        "name": intervention_ranking,
                        "type": "computational",
                        "cost": "low-medium",
                        "feasibility": "medium",
                        "expected_information_gain": "high",
                        "decision_gate": "Advance only if the ranking distinguishes established intervention precedent from unresolved translational gaps.",
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
                        "success_criteria": [
                            "Uses disease-relevant samples or models.",
                            "Includes positive/negative controls and a failure criterion.",
                            "Directly tests the gap identified by evidence synthesis rather than only confirming pathway activity.",
                        ],
                    },
                ]
            },
            confidence=0.7,
        )
