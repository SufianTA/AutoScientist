from tools.custom_tools.base import ScientificTool, ToolResult


class FopDiseaseProfileTool(ScientificTool):
    name = "fop_disease_profile_tool"
    description = "Returns a curated mock Fibrodysplasia Ossificans Progressiva disease profile."
    example_input = {"disease_name": "Fibrodysplasia Ossificans Progressiva"}

    def _run(self, payload: dict) -> ToolResult:
        return ToolResult(
            status="success",
            input=payload,
            output={
                "disease": "Fibrodysplasia Ossificans Progressiva",
                "abbreviation": "FOP",
                "summary": "Rare genetic disorder characterized by progressive heterotopic ossification.",
                "causal_links": [{"gene": "ACVR1", "relationship": "strong genetic association"}],
                "phenotypes": ["heterotopic ossification", "flare-ups", "progressive mobility restriction"],
                "guardrail": "Candidate interventions require experimental and clinical validation.",
            },
            sources=[
                {"name": "Curated mock disease profile", "id": "mock-fop-v0.1"},
                {"name": "Placeholder for disease ontology and literature tools"},
            ],
            confidence=0.8,
        )

