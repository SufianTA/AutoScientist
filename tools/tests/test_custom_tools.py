from tools.custom_tools.registry import build_custom_tools


def test_custom_tools_return_standard_result() -> None:
    tools = build_custom_tools()
    result = tools["acvr1_target_profile_tool"].run({"gene_symbol": "ACVR1"}).model_dump()
    assert result["status"] == "success"
    assert "output" in result
    assert "sources" in result
    assert result["tool_version"] == "0.1.0"
    assert "ncbi_gene_profile_tool" in tools
    assert "pubmed_literature_search_tool" in tools
    assert "pubchem_candidate_lookup_tool" in tools


def test_evidence_scorer_labels_acvr1_fop_mechanism() -> None:
    scorer = build_custom_tools()["evidence_quality_scorer_tool"]
    result = scorer.run(
        {
            "hypothesis": "Inhibiting ACVR1 may reduce aberrant osteogenic signaling in FOP.",
            "evidence_text": "ACVR1 variants activate BMP signaling in FOP models.",
        }
    )
    assert result.output["label"] == "strong_support"
