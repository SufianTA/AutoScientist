from tools.custom_tools.base import ScientificTool, ToolResult


class Acvr1TargetProfileTool(ScientificTool):
    name = "acvr1_target_profile_tool"
    description = "Returns a curated local ACVR1 example profile with disease links and pathway notes."
    example_input = {"gene_symbol": "ACVR1"}

    @property
    def input_schema(self) -> dict:
        return {"type": "object", "required": ["gene_symbol"], "properties": {"gene_symbol": {"type": "string"}}}

    def _run(self, payload: dict) -> ToolResult:
        raw_gene = payload.get("gene_symbol")
        if not raw_gene:
            return ToolResult(
                status="failure",
                input=payload,
                output={"message": "gene_symbol is required for this local ACVR1 example tool."},
                confidence=0.0,
                warnings=["No gene_symbol was supplied."],
            )
        gene = str(raw_gene).upper()
        if gene != "ACVR1":
            return ToolResult(
                status="partial",
                input=payload,
                output={"message": "Local example data only covers ACVR1; use live generic tools for other targets."},
                confidence=0.2,
            )
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
                {"name": "Curated local example profile", "id": "local-acvr1-v0.1"},
                {"name": "Placeholder for ToolUniverse/OpenTargets/ClinVar integration"},
            ],
            confidence=0.78,
        )
