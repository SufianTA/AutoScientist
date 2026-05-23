from tools.custom_tools.registry import build_custom_tools
from tools.custom_tools.clinical_status import classify_clinical_status, title_matches_context


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


def test_hypothesis_card_does_not_downgrade_clinically_established_targets() -> None:
    tool = build_custom_tools()["hypothesis_card_generator_tool"]

    result = tool.run(
        {
            "target": "TNF",
            "disease": "inflammatory bowel disease",
            "evidence": [
                {
                    "source": "PubMed: TNF inflammatory bowel disease therapy",
                    "text": "Anti-TNF clinical therapy and response stratification literature.",
                    "structured": {
                        "articles": [
                            {
                                "title": "Anti-TNF therapy in inflammatory bowel disease clinical response",
                                "url": "https://pubmed.ncbi.nlm.nih.gov/example",
                            }
                        ]
                    },
                    "score": {"label": "strong_support"},
                }
            ],
        }
    )

    assert "not validated therapeutic hypothesis" not in result.output["hypothesis"]
    assert "clinical" in result.output["candidate_intervention_summary"].lower()


def test_experiment_recommendation_is_target_disease_specific() -> None:
    tool = build_custom_tools()["experiment_recommendation_tool"]

    result = tool.run(
        {
            "hypothesis_card": {
                "title": "TNF pathway modulation as a candidate strategy for inflammatory bowel disease",
                "hypothesis": "TNF inflammatory cytokine signaling is implicated in IBD.",
            }
        }
    )

    names = " ".join(item["name"] for item in result.output["experiments"]).lower()
    assert "anti-tnf" in names
    assert "response/non-response" in names


def test_clinical_status_classifies_established_public_precedence() -> None:
    status = classify_clinical_status(
        "ERBB2",
        "breast cancer",
        [
            {
                "source": "Benchmark public context: Open Targets target-disease association",
                "text": "ERBB2 breast cancer association.",
                "structured": {
                    "public_labels": {
                        "open_targets_association_status": "matched",
                        "open_targets_association_score": 0.7,
                        "pubmed_gene_disease_count": 10000,
                    }
                },
                "score": {"label": "strong_support", "evidence_type": "target_disease_association"},
            },
            {
                "source": "Benchmark public context: Open Targets target tractability",
                "text": "Approved drug antibody precedence.",
                "structured": {
                    "evidence_type": "clinical_precedence",
                    "positive_tractability": [{"label": "Approved Drug", "modality": "AB", "value": True}],
                },
                "score": {"label": "mechanistic_relevance", "evidence_type": "clinical_precedence"},
            },
        ],
    )

    assert status["status"] == "established_or_clinically_precedented"
    assert status["confidence_floor"] >= 0.72


def test_clinical_status_classifies_grounded_but_not_established() -> None:
    status = classify_clinical_status(
        "APOE",
        "Alzheimer disease",
        [
            {
                "source": "Benchmark public context: Open Targets target-disease association",
                "text": "APOE Alzheimer disease association.",
                "structured": {
                    "public_labels": {
                        "open_targets_association_status": "matched",
                        "open_targets_association_score": 0.5,
                        "pubmed_gene_disease_count": 5000,
                    }
                },
                "score": {"label": "strong_support", "evidence_type": "target_disease_association"},
            }
        ],
    )

    assert status["status"] == "genetically_or_publicly_grounded"
    assert "separate association" in status["interpretation"]


def test_title_matching_rejects_off_target_pubmed_titles() -> None:
    assert title_matches_context(
        "Long-term safety of anti-TNF therapy in inflammatory bowel disease",
        "TNF",
        "inflammatory bowel disease",
    )
    assert not title_matches_context(
        "Real-world effectiveness and safety of upadacitinib in Crohn disease",
        "TNF",
        "inflammatory bowel disease",
    )
