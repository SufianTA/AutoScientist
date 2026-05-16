from tools.custom_tools.base import ScientificTool, ToolResult


class Acvr1TargetProfileTool(ScientificTool):
    name = "acvr1_target_profile_tool"
    description = "Returns a curated mock ACVR1 target profile with disease links and pathway notes."
    example_input = {"gene_symbol": "ACVR1"}

    @property
    def input_schema(self) -> dict:
        return {"type": "object", "required": ["gene_symbol"], "properties": {"gene_symbol": {"type": "string"}}}

    def _run(self, payload: dict) -> ToolResult:
        gene = payload.get("gene_symbol", "ACVR1").upper()
        if gene != "ACVR1":
            return ToolResult(status="partial", input=payload, output={"message": "Mock data only covers ACVR1"}, confidence=0.2)
        return ToolResult(
            status="success",
            input=payload,
            output={
                "gene_symbol": "ACVR1",
                "name": "Activin A receptor type 1",
                "mechanism_notes": [
                    "ACVR1 encodes a BMP type I receptor involved in osteogenic signaling.",
                    "FOP is commonly associated with activating ACVR1 variants such as R206H.",
                    "Therapeutic modulation should be framed as pathway-level hypothesis, not validated efficacy.",
                ],
                "pathways": ["BMP signaling", "TGF-beta superfamily signaling", "osteogenic differentiation"],
                "known_variants": [{"variant": "R206H", "context": "canonical FOP-associated activating variant"}],
            },
            sources=[
                {"name": "Curated mock profile", "id": "mock-acvr1-v0.1"},
                {"name": "Placeholder for ToolUniverse/OpenTargets/ClinVar integration"},
            ],
            confidence=0.78,
        )

