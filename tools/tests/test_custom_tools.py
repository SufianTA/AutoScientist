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
    assert "clinical_trials_search_tool" in tools
    assert "reactome_pathway_search_tool" in tools
    assert "openfda_adverse_event_tool" in tools


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
    assert tools["clinical_trials_search_tool"].run({}).status == "failure"
    assert tools["reactome_pathway_search_tool"].run({}).status == "failure"
    assert tools["openfda_adverse_event_tool"].run({}).status == "failure"


def test_clinical_trials_tool_parses_v2_response(monkeypatch) -> None:
    from tools.custom_tools import live_biomedical

    def fake_fetch_json(url: str, timeout: int = 20) -> dict:
        assert "clinicaltrials.gov/api/v2/studies" in url
        assert "query.cond=rheumatoid+arthritis" in url
        return {
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {"nctId": "NCT000001", "briefTitle": "TNF blockade in RA"},
                        "statusModule": {"overallStatus": "COMPLETED"},
                        "designModule": {"phases": ["PHASE3"], "studyType": "INTERVENTIONAL"},
                        "conditionsModule": {"conditions": ["Rheumatoid Arthritis"]},
                        "armsInterventionsModule": {
                            "interventions": [{"name": "adalimumab"}, {"name": "placebo"}]
                        },
                        "outcomesModule": {"primaryOutcomes": [{"measure": "ACR20 response"}]},
                    }
                }
            ]
        }

    monkeypatch.setattr(live_biomedical, "fetch_json", fake_fetch_json)
    tool = build_custom_tools()["clinical_trials_search_tool"]
    result = tool.run({"condition": "rheumatoid arthritis", "query": "TNF", "page_size": 3})

    assert result.status == "success"
    assert result.output["studies"][0]["nct_id"] == "NCT000001"
    assert result.output["studies"][0]["phase"] == ["PHASE3"]
    assert result.output["studies"][0]["primary_outcomes"] == ["ACR20 response"]


def test_reactome_pathway_tool_parses_response(monkeypatch) -> None:
    from tools.custom_tools import live_biomedical

    def fake_fetch_json(url: str, timeout: int = 20) -> dict:
        assert "reactome.org/ContentService/search/query" in url
        return {
            "rowCount": 1,
            "results": [
                {
                    "stId": "R-HSA-12345",
                    "name": "TNF signaling",
                    "schemaClass": "Pathway",
                    "speciesName": "Homo sapiens",
                }
            ],
        }

    monkeypatch.setattr(live_biomedical, "fetch_json", fake_fetch_json)
    tool = build_custom_tools()["reactome_pathway_search_tool"]
    result = tool.run({"query": "TNF", "page_size": 3})

    assert result.status == "success"
    assert result.output["pathways"][0]["stable_id"] == "R-HSA-12345"
    assert result.output["pathways"][0]["name"] == "TNF signaling"


def test_openfda_adverse_event_tool_parses_response(monkeypatch) -> None:
    from tools.custom_tools import live_biomedical

    def fake_fetch_json(url: str, timeout: int = 20) -> dict:
        assert "api.fda.gov/drug/event.json" in url
        return {
            "meta": {"results": {"total": 7}},
            "results": [
                {
                    "safetyreportid": "100",
                    "serious": "1",
                    "receivedate": "20260101",
                    "primarysourcecountry": "US",
                    "patient": {
                        "reaction": [
                            {"reactionmeddrapt": "Injection site reaction"},
                            {"reactionmeddrapt": "Headache"},
                        ]
                    },
                }
            ],
        }

    monkeypatch.setattr(live_biomedical, "fetch_json", fake_fetch_json)
    tool = build_custom_tools()["openfda_adverse_event_tool"]
    result = tool.run({"drug_name": "adalimumab", "limit": 3})

    assert result.status == "success"
    assert result.output["total_matching_reports"] == 7
    assert result.output["serious_reports_in_returned"] == 1
    assert result.output["common_reactions"][0]["reaction"] == "Headache"


def test_openfda_adverse_event_tool_degrades_to_partial_on_api_failure(monkeypatch) -> None:
    from tools.custom_tools import live_biomedical

    def fake_fetch_json(url: str, timeout: int = 20) -> dict:
        raise RuntimeError("temporary upstream failure")

    monkeypatch.setattr(live_biomedical, "fetch_json", fake_fetch_json)
    tool = build_custom_tools()["openfda_adverse_event_tool"]
    result = tool.run({"drug_name": "osimertinib", "limit": 3})

    assert result.status == "partial"
    assert result.output["safety_gap"].startswith("openFDA adverse-event lookup was unavailable")
    assert result.warnings


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
    assert "tnf / inflammatory bowel disease" in names
    assert "clinical-precedence" in names
    assert "disease-relevant" in names


def test_experiment_recommendation_prefers_primary_case_entities_over_bypass_mentions() -> None:
    tool = build_custom_tools()["experiment_recommendation_tool"]

    result = tool.run(
        {
            "hypothesis_card": {
                "title": "EGFR resistance strategy for non-small cell lung cancer",
                "hypothesis": (
                    "EGFR-mutant NSCLC resistance may involve BRAF, KRAS, MET, and ERBB2 bypass alterations, "
                    "but the primary case anchor remains EGFR."
                ),
                "case_profile": {
                    "entities": {
                        "genes": ["EGFR", "MET", "ERBB2"],
                        "diseases": ["non-small cell lung cancer"],
                    }
                },
            }
        }
    )

    names = " ".join(item["name"] for item in result.output["experiments"]).lower()
    assert "egfr mutant selectivity" in names
    assert "braf mutation selectivity" not in names


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
