from tools.custom_tools.base import ScientificTool, ToolResult


class FopDiseaseProfileTool(ScientificTool):
    name = "fop_disease_profile_tool"
    description = "Returns a curated local Fibrodysplasia Ossificans Progressiva example profile."
    example_input = {"disease_name": "Fibrodysplasia Ossificans Progressiva"}

    @property
    def input_schema(self) -> dict:
        return {"type": "object", "required": ["disease_name"], "properties": {"disease_name": {"type": "string"}}}

    def _run(self, payload: dict) -> ToolResult:
        disease_name = str(payload.get("disease_name", "")).strip()
        normalized = disease_name.lower()
        if not disease_name:
            return ToolResult(
                status="failure",
                input=payload,
                output={"message": "disease_name is required for this local FOP example tool."},
                confidence=0.0,
                warnings=["No disease_name was supplied."],
            )
        if "fibrodysplasia ossificans progressiva" not in normalized and normalized != "fop":
            return ToolResult(
                status="partial",
                input=payload,
                output={"message": "Local example data only covers FOP; use live generic tools for other diseases."},
                confidence=0.2,
            )
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
                {"name": "Curated local disease example profile", "id": "local-fop-v0.1"},
                {"name": "Placeholder for disease ontology and literature tools"},
            ],
            confidence=0.8,
        )
