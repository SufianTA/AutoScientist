from __future__ import annotations

from app.services.evidence_hierarchy import (
    annotate_evidence_item,
    classify_evidence_item,
    summarize_evidence_hierarchy,
)
from app.services.scientific_planning import type_evidence_items


def test_evidence_hierarchy_classifies_clinical_precedence_as_tier_1() -> None:
    item = {
        "source": "Open Targets",
        "text": "Approved drug and clinical trial evidence support target tractability.",
        "evidence_type": "clinical_precedence",
    }

    classification = classify_evidence_item(item)

    assert classification["evidence_tier"] == "tier_1_clinical_translational"
    assert classification["evidence_tier_rank"] == 1


def test_evidence_hierarchy_classifies_clinicaltrials_records_as_tier_1() -> None:
    classification = classify_evidence_item(
        {
            "source": "ClinicalTrials.gov: rheumatoid arthritis TNF",
            "text": "ClinicalTrials.gov returned translational study records: TNF blockade in RA (COMPLETED, PHASE3).",
            "structured": {"studies": [{"nct_id": "NCT000001", "study_type": "INTERVENTIONAL"}]},
        }
    )

    assert classification["evidence_tier"] == "tier_1_clinical_translational"
    assert classification["evidence_kind"] == "clinical"


def test_evidence_hierarchy_does_not_treat_pubmed_query_words_as_clinical_precedence() -> None:
    classification = classify_evidence_item(
        {
            "source": "PubMed: TARGET disease clinical precedence response",
            "text": "PubMed literature search found records about TARGET disease mechanism but no trial result.",
            "evidence_type": "literature",
        }
    )

    assert classification["evidence_tier"] != "tier_1_clinical_translational"


def test_evidence_hierarchy_classifies_human_genetics_as_tier_2() -> None:
    classification = classify_evidence_item(
        {
            "source": "Open Targets genetics",
            "text": "Human GWAS and patient variant evidence links the target to disease.",
        }
    )

    assert classification["evidence_tier"] == "tier_2_human_biology"


def test_evidence_hierarchy_classifies_pubmed_count_only_as_weak_context() -> None:
    classification = classify_evidence_item(
        {
            "source": "PubMed",
            "text": "PubMed literature search found 12 records for the gene disease query.",
        }
    )

    assert classification["evidence_tier"] == "tier_5_literature_context"


def test_evidence_hierarchy_classifies_reactome_as_mechanistic() -> None:
    classification = classify_evidence_item(
        {
            "source": "Reactome: TNF",
            "text": "Reactome returned pathway/mechanism records for TNF signaling.",
        }
    )

    assert classification["evidence_tier"] == "tier_3_functional_mechanistic"
    assert classification["evidence_kind"] == "mechanism"


def test_evidence_hierarchy_classifies_openfda_as_safety() -> None:
    classification = classify_evidence_item(
        {
            "source": "openFDA adverse events: adalimumab",
            "text": "openFDA returned FAERS adverse-event reports and safety signals.",
        }
    )

    assert classification["evidence_kind"] == "safety"


def test_annotate_evidence_item_embeds_hierarchy_in_structured_payload() -> None:
    annotated = annotate_evidence_item({"source": "PubMed", "text": "PubMed records exist."})

    assert annotated["evidence_tier"] == "tier_5_literature_context"
    assert annotated["structured"]["evidence_hierarchy"]["evidence_tier"] == "tier_5_literature_context"


def test_summarize_evidence_hierarchy_rewards_mixed_high_tier_evidence() -> None:
    strong = summarize_evidence_hierarchy(
        [
            {"source": "Open Targets", "text": "Approved drug clinical trial evidence."},
            {"source": "Open Targets", "text": "Human patient genetic variant evidence."},
            {"source": "Reactome", "text": "Pathway signaling mechanism evidence."},
        ]
    )
    weak = summarize_evidence_hierarchy(
        [{"source": "PubMed", "text": "PubMed literature records mention the gene and disease."}]
    )

    assert strong["high_tier_evidence_count"] == 2
    assert strong["hierarchy_score"] > weak["hierarchy_score"]
    assert weak["weak_only"] is True


def test_type_evidence_items_adds_hierarchy_fields() -> None:
    typed = type_evidence_items([{"source": "PubMed", "text": "PubMed literature records."}])

    assert typed[0]["evidence_type"] == "literature"
    assert typed[0]["evidence_tier"] == "tier_5_literature_context"
    assert typed[0]["structured"]["evidence_hierarchy"]["evidence_tier_rank"] == 5
