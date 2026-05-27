from __future__ import annotations

from typing import Any


TARGET_ALIASES: dict[str, set[str]] = {
    "tnf": {
        "tnf",
        "tnf-alpha",
        "tnf alpha",
        "anti-tnf",
        "anti-tnfalpha",
        "anti-tnf-alpha",
        "tumor necrosis factor",
        "tumour necrosis factor",
        "infliximab",
        "adalimumab",
        "certolizumab",
        "golimumab",
    },
    "il6": {"il6", "il-6", "interleukin-6", "interleukin 6", "tocilizumab", "sarilumab"},
    "il6r": {"il6r", "il-6 receptor", "interleukin-6 receptor", "tocilizumab", "sarilumab"},
    "tyk2": {"tyk2", "deucravacitinib"},
    "braf": {"braf", "b-raf", "vemurafenib", "dabrafenib", "encorafenib"},
    "egfr": {"egfr", "erbb1", "gefitinib", "erlotinib", "osimertinib", "afatinib"},
    "erbb2": {"erbb2", "her2", "trastuzumab", "pertuzumab", "lapatinib"},
    "alk": {"alk", "crizotinib", "alectinib", "brigatinib", "lorlatinib"},
    "parp1": {"parp1", "parp", "olaparib", "niraparib", "rucaparib", "talazoparib"},
    "kras": {"kras", "sotorasib", "adagrasib"},
    "cftr": {"cftr", "ivacaftor", "lumacaftor", "tezacaftor", "elexacaftor"},
    "smn1": {"smn1", "smn", "nusinersen", "onasemnogene", "risdiplam"},
    "gaa": {"gaa", "alglucosidase", "avalglucosidase"},
    "dmd": {"dmd", "dystrophin", "eteplirsen", "golodirsen", "viltolarsen"},
    "pcsk9": {"pcsk9", "evolocumab", "alirocumab", "inclisiran"},
    "lrrk2": {"lrrk2", "dardarin"},
    "sod1": {"sod1", "tofersen"},
}


DISEASE_ALIASES: dict[str, set[str]] = {
    "inflammatory bowel disease": {"inflammatory bowel disease", "inflammatorybowel", "ibd", "crohn", "ulcerative colitis"},
    "rheumatoid arthritis": {"rheumatoid arthritis", "synovitis"},
    "psoriasis": {"psoriasis", "psoriatic"},
    "melanoma": {"melanoma"},
    "lung adenocarcinoma": {"lung adenocarcinoma", "non-small cell lung", "nsclc", "lung cancer"},
    "lung cancer": {"lung cancer", "non-small cell lung", "nsclc", "lung adenocarcinoma"},
    "breast cancer": {"breast cancer", "breast neoplasm"},
    "ovarian cancer": {"ovarian cancer", "ovarian neoplasm"},
    "pancreatic cancer": {"pancreatic cancer", "pancreatic ductal adenocarcinoma", "pdac"},
    "cystic fibrosis": {"cystic fibrosis"},
    "spinal muscular atrophy": {"spinal muscular atrophy", "sma"},
    "fibrodysplasia ossificans progressiva": {"fibrodysplasia ossificans progressiva", "fop"},
    "pompe disease": {"pompe disease", "glycogen storage disease type ii"},
    "duchenne muscular dystrophy": {"duchenne muscular dystrophy", "dmd"},
    "alzheimer disease": {"alzheimer disease", "alzheimer's disease", "alzheimers"},
    "parkinson disease": {"parkinson disease", "parkinson's disease", "parkinsons"},
    "amyotrophic lateral sclerosis": {"amyotrophic lateral sclerosis", "als"},
    "huntington disease": {"huntington disease", "huntington's disease"},
    "familial hypercholesterolemia": {"familial hypercholesterolemia", "hypercholesterolaemia"},
}


def target_aliases(target: str) -> set[str]:
    value = str(target or "").lower().strip()
    aliases = {value} if value else set()
    aliases.update(TARGET_ALIASES.get(value, set()))
    return {alias for alias in aliases if alias}


def disease_aliases(disease: str) -> set[str]:
    value = str(disease or "").lower().strip()
    aliases = {value} if value else set()
    for canonical, values in DISEASE_ALIASES.items():
        if value == canonical or value in values or canonical in value:
            aliases.update(values)
    if " cancer" in value:
        aliases.add(value.replace(" cancer", " carcinoma"))
        aliases.add(value.replace(" cancer", " neoplasm"))
    if " carcinoma" in value:
        aliases.add(value.replace(" carcinoma", " cancer"))
    if " tumour" in value:
        aliases.add(value.replace(" tumour", " tumor"))
    if " tumor" in value:
        aliases.add(value.replace(" tumor", " tumour"))
    return {alias for alias in aliases if alias}


def title_matches_context(title: str, target: str, disease: str) -> bool:
    text = str(title or "").lower()
    return any(alias in text for alias in target_aliases(target)) and any(alias in text for alias in disease_aliases(disease))


def title_claim_type(title: str) -> str:
    text = str(title or "").lower()
    if any(term in text for term in ["safety", "adverse", "toxicity", "infection", "contraindication"]):
        return "safety"
    if any(term in text for term in ["clinical", "trial", "therapy", "treatment", "response", "resistance", "approved"]):
        return "clinical_precedence"
    if any(term in text for term in ["mutation", "variant", "genetic", "gwas", "association"]):
        return "genetic"
    if any(term in text for term in ["mechanism", "pathway", "signaling", "cell", "model"]):
        return "mechanistic"
    if any(term in text for term in ["failed", "failure", "not associated", "negative", "null"]):
        return "counterevidence"
    return "literature"


def relevant_pubmed_titles(item: dict[str, Any], target: str, disease: str) -> list[dict[str, Any]]:
    structured = item.get("structured", {}) if isinstance(item.get("structured"), dict) else {}
    matches = []
    for article in structured.get("articles", []) or []:
        title = str(article.get("title") or "")
        if title_matches_context(title, target, disease):
            matches.append(article)
    return matches


def public_labels_from_evidence(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    for item in evidence:
        structured = item.get("structured", {}) if isinstance(item.get("structured"), dict) else {}
        labels = structured.get("public_labels", {}) if isinstance(structured.get("public_labels"), dict) else {}
        if labels:
            return labels
    return {}


def has_target_tractability_precedence(evidence: list[dict[str, Any]]) -> bool:
    for item in evidence:
        structured = item.get("structured", {}) if isinstance(item.get("structured"), dict) else {}
        evidence_type = str(item.get("score", {}).get("evidence_type") or structured.get("evidence_type") or "")
        if evidence_type == "clinical_precedence":
            return True
        positive = structured.get("positive_tractability", [])
        if any(isinstance(entry, dict) and entry.get("value") is True for entry in positive):
            return True
    return False


def has_approved_intervention_context(evidence: list[dict[str, Any]], target: str, disease: str) -> bool:
    target_terms = target_aliases(target)
    disease_terms = disease_aliases(disease)
    for item in evidence:
        text = " ".join(
            [
                str(item.get("source") or ""),
                str(item.get("text") or ""),
                str(item.get("structured") or ""),
            ]
        ).lower()
        if not any(term in text for term in ["approved", "approval", "maximum clinical stage"]):
            continue
        if not (any(alias in text for alias in target_terms) or "drug" in text or "chembl" in text):
            continue
        if disease_terms and not any(alias in text for alias in disease_terms):
            continue
        return True
    return False


def clinical_literature_titles(evidence: list[dict[str, Any]], target: str, disease: str) -> list[str]:
    titles = []
    for item in evidence:
        for article in relevant_pubmed_titles(item, target, disease):
            title = str(article.get("title") or "")
            if title_claim_type(title) in {"clinical_precedence", "safety"}:
                titles.append(title)
    return list(dict.fromkeys(titles))


def classify_clinical_status(target: str, disease: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    labels = public_labels_from_evidence(evidence)
    try:
        association_score = float(labels.get("open_targets_association_score") or 0.0)
    except (TypeError, ValueError):
        association_score = 0.0
    pubmed_count = int(labels.get("pubmed_gene_disease_count") or 0)
    matched = labels.get("open_targets_association_status") == "matched"
    tractability_precedence = has_target_tractability_precedence(evidence) or has_approved_intervention_context(
        evidence, target, disease
    )
    clinical_titles = clinical_literature_titles(evidence, target, disease)
    has_genetic_or_strong_association = matched and (association_score >= 0.35 or pubmed_count >= 100)

    if tractability_precedence and (matched or clinical_titles):
        status = "established_or_clinically_precedented"
        confidence_floor = 0.72
        interpretation = (
            "Treat as an established or clinically precedented target-disease context; focus on residual "
            "mechanism, responder biology, resistance, safety, and patient selection."
        )
    elif has_genetic_or_strong_association:
        status = "genetically_or_publicly_grounded"
        confidence_floor = 0.62
        interpretation = (
            "Treat as target-disease grounded but not clinically established; separate association from "
            "druggability, directionality, safety, and intervention evidence."
        )
    elif pubmed_count > 0 or association_score > 0:
        status = "early_or_indirect"
        confidence_floor = 0.0
        interpretation = "Treat as early or indirect; require claim softening and targeted validation."
    else:
        status = "speculative_or_insufficient"
        confidence_floor = 0.0
        interpretation = "Treat as speculative until public target-disease evidence is retrieved."

    return {
        "status": status,
        "confidence_floor": confidence_floor,
        "open_targets_association_score": association_score,
        "pubmed_gene_disease_count": pubmed_count,
        "has_target_tractability_precedence": tractability_precedence,
        "clinical_literature_titles": clinical_titles[:5],
        "interpretation": interpretation,
    }
