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


def test_example_tools_do_not_default_to_acvr1_or_fop() -> None:
    tools = build_custom_tools()

    assert tools["acvr1_target_profile_tool"].run({}).status == "failure"
    assert tools["fop_disease_profile_tool"].run({}).status == "failure"

    acvr1_other = tools["acvr1_target_profile_tool"].run({"gene_symbol": "PCSK9"})
    fop_other = tools["fop_disease_profile_tool"].run({"disease_name": "familial hypercholesterolemia"})
    assert acvr1_other.status == "partial"
    assert fop_other.status == "partial"
    assert "ACVR1" not in str(fop_other.output)


def test_live_biomedical_tools_require_explicit_inputs() -> None:
    tools = build_custom_tools()

    assert tools["ncbi_gene_profile_tool"].run({}).status == "failure"
    assert tools["pubmed_literature_search_tool"].run({}).status == "failure"
    assert tools["pubchem_candidate_lookup_tool"].run({}).status == "failure"
