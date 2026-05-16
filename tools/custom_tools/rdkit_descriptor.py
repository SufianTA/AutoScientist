from math import isnan

from tools.custom_tools.base import ScientificTool, ToolResult


def pseudo_descriptors(smiles: str) -> dict:
    if not smiles or any(ch.isspace() for ch in smiles):
        return {"valid": False, "warnings": ["SMILES contains whitespace or is empty"]}
    carbon_count = smiles.count("C") + smiles.count("c")
    hetero_count = sum(smiles.count(ch) for ch in ["N", "O", "S", "P", "n", "o", "s"])
    ring_markers = sum(ch.isdigit() for ch in smiles)
    molecular_weight = round(12.01 * carbon_count + 14.0 * smiles.count("N") + 16.0 * smiles.count("O") + 1.5 * len(smiles), 2)
    logp = round(0.42 * carbon_count - 0.35 * hetero_count, 2)
    tpsa = round(18.0 * hetero_count, 2)
    hbd = smiles.count("O") + smiles.count("N")
    hba = hetero_count
    rotatable_bonds = max(0, smiles.count("-") + smiles.count("C") // 4)
    lipinski_violations = sum([molecular_weight > 500, logp > 5, hbd > 5, hba > 10])
    return {
        "valid": not isnan(molecular_weight),
        "molecular_weight": molecular_weight,
        "logp": logp,
        "hbd": hbd,
        "hba": hba,
        "tpsa": tpsa,
        "rotatable_bonds": rotatable_bonds,
        "ring_marker_count": ring_markers,
        "lipinski_violations": int(lipinski_violations),
    }


class RdkitDescriptorTool(ScientificTool):
    name = "rdkit_descriptor_tool"
    description = "Mock RDKit-compatible descriptor tool. Replace with RDKit implementation when dependency is available."
    example_input = {"smiles": ["CC(=O)O", "C1=CC=CC=C1"]}

    @property
    def input_schema(self) -> dict:
        return {"type": "object", "required": ["smiles"], "properties": {"smiles": {"type": "array", "items": {"type": "string"}}}}

    def _run(self, payload: dict) -> ToolResult:
        smiles = payload.get("smiles", [])
        records = [{"smiles": item, **pseudo_descriptors(item)} for item in smiles]
        return ToolResult(
            status="success",
            input=payload,
            output={"descriptors": records},
            sources=[{"name": "Mock descriptor calculator", "id": "mock-rdkit-v0.1"}],
            confidence=0.45,
            warnings=["Uses heuristic descriptors until RDKit is installed."],
        )

