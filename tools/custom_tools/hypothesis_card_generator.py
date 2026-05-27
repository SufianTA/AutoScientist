from tools.custom_tools.base import ScientificTool, ToolResult
from tools.custom_tools.clinical_status import (
    classify_clinical_status,
    clinical_literature_titles,
)


def label_counts(evidence: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in evidence:
        label = item.get("score", {}).get("label", "unscored")
        counts[label] = counts.get(label, 0) + 1
    return counts


def confidence_from_evidence(evidence: list[dict]) -> float:
    score = 0.42
    weights = {
        "strong_support": 0.08,
        "weak_support": 0.04,
        "mechanistic_relevance": 0.02,
        "safety_concern": -0.08,
        "contradicts": -0.12,
        "irrelevant": -0.04,
    }
    clinical_or_public_floor = 0.0
    for item in evidence:
        score += weights.get(item.get("score", {}).get("label"), 0.0)
        structured = item.get("structured", {}) if isinstance(item.get("structured"), dict) else {}
        labels = structured.get("public_labels", {}) if isinstance(structured.get("public_labels"), dict) else {}
        evidence_type = str(item.get("score", {}).get("evidence_type") or structured.get("evidence_type") or "")
        if labels.get("open_targets_association_status") == "matched":
            try:
                association_score = float(labels.get("open_targets_association_score") or 0.0)
            except (TypeError, ValueError):
                association_score = 0.0
            if association_score >= 0.5:
                clinical_or_public_floor = max(clinical_or_public_floor, 0.68)
            elif association_score >= 0.25:
                clinical_or_public_floor = max(clinical_or_public_floor, 0.6)
        if evidence_type in {"clinical_precedence", "clinical_precedence_literature"}:
            clinical_or_public_floor = max(clinical_or_public_floor, 0.72)
    return round(max(0.05, clinical_or_public_floor, min(score, 0.86)), 2)


# ── Biological-class inference ────────────────────────────────────────────────
# Each tuple: (list of indicator terms, label).  Ordered most-specific first.

_BIO_CLASS_RULES: list[tuple[list[str], str]] = [
    (["receptor tyrosine kinase", "rtk activity"], "receptor tyrosine kinase"),
    (["tyrosine kinase", "protein tyrosine kinase", "jak kinase", "src kinase"], "tyrosine kinase"),
    (["serine/threonine kinase", "serine-threonine kinase", "ser/thr kinase"], "serine/threonine kinase"),
    (["protein kinase", "kinase activity", "kinase domain"], "kinase"),
    (["small gtpase", "gtpase", "gtp binding", "g-protein", "ras superfamily", "ras-related"], "GTPase"),
    (["transcription factor", "dna-binding protein", "transcriptional activator",
      "transcriptional repressor", "zinc finger protein"], "transcription factor"),
    (["tumor suppressor", "growth suppressor"], "tumor suppressor"),
    (["dna repair", "homologous recombination", "mismatch repair",
      "nucleotide excision", "double-strand break"], "DNA repair factor"),
    (["cyclin-dependent kinase", "cdk inhibitor", "cell cycle regulator"], "cell cycle regulator"),
    (["dehydrogenase", "isomerase", "oxidoreductase", "transferase",
      "hydroxylase", "metabolic enzyme"], "metabolic enzyme"),
    (["ion channel", "membrane transporter", "chloride channel", "potassium channel",
      "sodium channel", "abc transporter"], "ion channel/transporter"),
    (["cytokine receptor", "growth factor receptor", "hormone receptor"], "receptor"),
    (["interleukin", "interferon", "chemokine", "tumor necrosis factor",
      "cytokine"], "cytokine/immune mediator"),
    (["phosphatase activity", "tyrosine phosphatase", "phosphatase"], "phosphatase"),
    (["e3 ubiquitin ligase", "deubiquitinase", "ubiquitin", "proteasomal"], "ubiquitin pathway factor"),
    (["histone methyltransferase", "histone demethylase", "acetyltransferase",
      "deacetylase", "chromatin remodeling", "epigenetic"], "epigenetic regulator"),
    (["proto-oncogene", "oncogene", "transforming protein"], "oncogene"),
    (["apoptosis regulator", "pro-apoptotic", "anti-apoptotic", "bcl-2 family"], "apoptosis regulator"),
    (["cell adhesion molecule", "integrin", "cadherin", "extracellular matrix"], "cell adhesion factor"),
    (["g protein-coupled receptor", "gpcr", "seven-transmembrane"], "GPCR"),
]

# ── Alteration / variant context ──────────────────────────────────────────────

_ALTERATION_RULES: list[tuple[list[str], str]] = [
    (["fusion protein", " fused to", "gene fusion", "chromosomal translocation",
      "rearrangement"], "fusion"),
    (["gene amplification", "high-level amplification", "copy number gain"], "amplification"),
    (["exon 14 skipping", "exon skipping", "splice site mutation"], "exon-skip mutation"),
    (["homozygous deletion", "biallelic loss", "haploinsufficiency",
      "loss of heterozygosity"], "loss"),
    (["gain-of-function", "activating mutation", "constitutive activation",
      "oncogenic mutation"], "activating mutation"),
    (["loss-of-function", "inactivating mutation", "truncating mutation",
      "frameshift mutation"], "inactivating mutation"),
    (["overexpression", "protein overexpression"], "overexpression"),
]

# ── Therapeutic/mechanism context ─────────────────────────────────────────────

_MECHANISM_CONTEXT_RULES: list[tuple[list[str], str]] = [
    (["acquired resistance", "resistance mechanism", "bypass resistance",
      "secondary mutation", "resistance bypass"], "oncogenic signaling, resistance mechanisms, and bypass vulnerabilities"),
    (["covalent inhibitor", "switch ii pocket", "irreversible inhibitor",
      "covalent bond"], "oncogenic signaling and covalent inhibitor resistance"),
    (["synthetic lethality", "parp inhibitor", "homologous recombination deficiency",
      "hrd"], "DNA damage response and synthetic lethality"),
    (["differentiation block", "differentiation arrest",
      "myeloid differentiation"], "oncometabolite production and differentiation block"),
    (["immune checkpoint", "tumor microenvironment", "pd-l1", "pd-1",
      "immune evasion"], "oncogenic signaling and immune microenvironment dysregulation"),
    (["combination therapy", "combination strategy",
      "combination rationale", "synergistic"], "disease-relevant pathway inhibition and combination strategy"),
    (["fda-approved", "approved drug", "clinically validated",
      "clinical precedence", "phase 2", "phase 3",
      "phase iii", "randomized trial"], "clinically validated pathway inhibition and residual resistance questions"),
    (["kinase inhibitor", "targeted therapy",
      "tyrosine kinase inhibitor"], "oncogenic kinase activation and targeted inhibition"),
    (["tumor suppressor loss", "loss of function", "haploinsufficiency",
      "biallelic"], "tumor suppressor pathway deregulation"),
    (["cell cycle arrest", "g1 arrest", "rb phosphorylation",
      "cell cycle checkpoint"], "cell cycle dysregulation and targeted inhibition"),
    (["pathway activation", "signal transduction",
      "downstream signaling", "constitutive signaling"], "oncogenic pathway activation and therapeutic targeting"),
]


def _classify_from_rules(search: str, rules: list[tuple[list[str], str]], default: str) -> str:
    for terms, label in rules:
        if any(t in search for t in terms):
            return label
    return default


def mechanism_phrase(target: str, evidence: list[dict]) -> str:
    """
    Derive a mechanism phrase from gene annotation and evidence context.

    Works for any biological target.  Detects:
      1. Biological class  — from gene annotation and evidence text
      2. Alteration type   — fusion, amplification, mutation, etc.
      3. Therapeutic context — resistance, combination, clinical precedence, etc.

    No per-gene name hardcoding; all classification is done on evidence content.
    """
    # Build text corpus for classification
    ev_texts = [str(item.get("text", "")).lower() for item in evidence[:12]]
    combined = " ".join([target.lower(), *ev_texts])

    # Prefer gene annotation (NCBI Gene carries the richest biological description)
    gene_ann = ""
    for item in evidence[:12]:
        if "ncbi" in str(item.get("source", "")).lower():
            text = str(item.get("text", "")).lower()
            if target.lower() in text:
                gene_ann = text
                break
    search = f"{combined} {gene_ann}"

    bio_class = _classify_from_rules(search, _BIO_CLASS_RULES, "regulatory factor")
    alteration = _classify_from_rules(search, _ALTERATION_RULES, "")
    mech_context = _classify_from_rules(
        search, _MECHANISM_CONTEXT_RULES,
        "disease-relevant pathway dysregulation and therapeutic hypothesis",
    )

    target_part = f"{target} {alteration}".strip() if alteration else target
    return f"{target_part} {bio_class}-mediated {mech_context}"


def extract_citations(evidence: list[dict], target: str) -> list[dict]:
    citations = []
    for item in evidence:
        structured = item.get("structured", {})
        for article in structured.get("articles", []):
            citations.append(
                {
                    "source": "PubMed",
                    "title": article.get("title"),
                    "url": article.get("url"),
                    "pmid": article.get("pmid"),
                    "journal": article.get("journal"),
                    "pubdate": article.get("pubdate"),
                }
            )
        for compound in structured.get("compounds", []):
            citations.append(
                {
                    "source": "PubChem",
                    "title": compound.get("name"),
                    "url": compound.get("url"),
                    "cid": compound.get("cid"),
                }
            )
        if structured.get("gene_id"):
            citations.append(
                {
                    "source": "NCBI Gene",
                    "title": structured.get("gene_symbol", target),
                    "url": f"https://www.ncbi.nlm.nih.gov/gene/{structured['gene_id']}",
                    "gene_id": structured.get("gene_id"),
                }
            )
    return citations[:12]


def clinical_precedence_summary(target: str, disease: str, evidence: list[dict]) -> str:
    public_lines = []
    literature_titles = clinical_literature_titles(evidence, target, disease)
    has_target_level_precedence = False
    for item in evidence:
        structured = item.get("structured", {}) if isinstance(item.get("structured"), dict) else {}
        labels = structured.get("public_labels", {}) if isinstance(structured.get("public_labels"), dict) else {}
        evidence_type = str(item.get("score", {}).get("evidence_type") or structured.get("evidence_type") or "")
        if labels.get("open_targets_association_status") == "matched":
            public_lines.append(
                f"Open Targets reports a matched {target}/{disease} association "
                f"(score {labels.get('open_targets_association_score')}, rank {labels.get('open_targets_association_rank')})."
            )
        if evidence_type == "clinical_precedence":
            has_target_level_precedence = True
            public_lines.append(f"Open Targets target metadata indicates target-level clinical or tractability precedence for {target}.")
    if public_lines or literature_titles:
        pieces = [*public_lines[:2]]
        if has_target_level_precedence:
            pieces.append(
                "This should be framed as clinical or translational precedence with unresolved response, "
                "resistance, safety, mechanism, and patient-stratification questions."
            )
        if literature_titles:
            pieces.append("Relevant clinical literature titles include: " + "; ".join(literature_titles[:3]) + ".")
        return " ".join(pieces)
    return (
        f"No explicit clinical-precedence evidence for {target} in {disease} was surfaced; the output should focus "
        "on target-disease grounding and unresolved validation."
    )


class HypothesisCardGeneratorTool(ScientificTool):
    name = "hypothesis_card_generator_tool"
    description = "Creates a structured candidate hypothesis card from disease, target, molecule, and evidence records."
    example_input = {"target": "PCSK9", "disease": "familial hypercholesterolemia", "evidence": []}

    def _run(self, payload: dict) -> ToolResult:
        target = payload.get("target", "disease-relevant target")
        disease = payload.get("disease", "the specified disease context")
        evidence = payload.get("evidence", [])
        confidence = confidence_from_evidence(evidence)
        mechanism = mechanism_phrase(target, evidence)
        clinical_status = classify_clinical_status(target, disease, evidence)
        confidence = max(confidence, float(clinical_status.get("confidence_floor") or 0.0))
        local_only = bool(evidence) and all(str(item.get("source", "")).startswith("local_") for item in evidence)
        counts = label_counts(evidence)
        safety_items = [
            item for item in evidence if item.get("score", {}).get("label") == "safety_concern"
        ]
        candidate_items = [
            item for item in evidence if "pubchem" in item.get("source", "").lower()
        ]
        literature_candidate_titles = []
        for item in evidence:
            if "pubmed" not in item.get("source", "").lower():
                continue
            for article in item.get("structured", {}).get("articles", []):
                title = article.get("title", "")
                if any(
                    term in title.lower()
                    for term in [
                        "treatment",
                        "therapeutic",
                        "therapy",
                        "clinical",
                        "trial",
                        "inhibitor",
                        "antibody",
                        "drug",
                        "modality",
                    ]
                ):
                    literature_candidate_titles.append(title)
        precedence = clinical_precedence_summary(target, disease, evidence)
        contradictions = []
        if safety_items:
            contradictions.append(
                "Safety/intervention literature was retrieved, so translational risk remains an active uncertainty."
            )
        status = str(clinical_status.get("status", "speculative_or_insufficient"))
        has_precedence = status == "established_or_clinically_precedented" or (
            "No explicit clinical-precedence evidence" not in precedence
            and status != "speculative_or_insufficient"
        )
        if status == "established_or_clinically_precedented":
            status_framing = (
                f"{target} has established or clinically precedented target-disease grounding for {disease}. "
                "The output should not present this as a new target discovery."
            )
        elif status == "genetically_or_publicly_grounded":
            status_framing = (
                f"{target} is publicly grounded for {disease}, but association evidence must be separated from "
                "clinical efficacy, safety, druggability, and intervention directionality."
            )
        else:
            status_framing = (
                f"{target} remains an early or insufficiently established hypothesis for {disease}; claims require "
                "explicit validation and stronger public evidence."
            )
        return ToolResult(
            status="success",
            input=payload,
            output={
                "title": (
                    f"{target} clinical-precedence and mechanism review for {disease}"
                    if has_precedence
                    else f"{target} pathway modulation as a candidate strategy for {disease}"
                ),
                "hypothesis": (
                    f"Modulating {mechanism} is a planning-level candidate hypothesis for {disease} "
                    "that requires live external evidence before scientific interpretation."
                    if local_only
                    else (
                        f"{status_framing} "
                        f"{precedence} The remaining scientific work is to resolve mechanism details, "
                        "response or resistance biology, safety liabilities, and patient-selection strategy; "
                        "this is not a claim that a new target has been discovered."
                    )
                ),
                "evidence": evidence,
                "evidence_label_counts": counts,
                "clinical_status": clinical_status,
                "scientific_assessment": [
                    clinical_status["interpretation"],
                    (
                        f"The disease-target rationale is biologically plausible when live/public evidence links "
                        f"{target} to {disease} through disease association, pathway, or mechanism records."
                    ),
                    (
                        "The current claim should remain pathway-level: evidence supports target and mechanism "
                        "grounding, not clinical efficacy for any intervention unless direct clinical evidence is cited."
                    ),
                    precedence,
                    (
                        "Candidate molecules or interventions are prioritization leads only; potency, selectivity, "
                        "exposure, safety, and disease-model response must be tested."
                    ),
                ],
                "candidate_intervention_summary": (
                    "No live candidate intervention records were retrieved in this local planning run."
                    if local_only
                    else (
                    "PubChem/literature candidate records were found, but none are asserted as clinically effective."
                    if candidate_items
                    else (
                        "Live literature retrieved treatment, clinical, or intervention-precedence signals; "
                        "the downstream synthesis should distinguish established clinical use from unresolved "
                        f"mechanism, resistance, safety, or stratification questions: {'; '.join(literature_candidate_titles[:4])}."
                        if literature_candidate_titles
                        else "No candidate intervention records were retrieved in this run."
                    )
                    )
                ),
                "contradictions": contradictions,
                "citations": extract_citations(evidence, target),
                "confidence": confidence,
                "confidence_interpretation": "moderate" if confidence >= 0.55 else "low",
                "limitations": [
                    "Live public database records support hypothesis generation but do not validate efficacy.",
                    "No clinical efficacy or safety claim is made.",
                    "Compound specificity and translational risk remain unresolved.",
                    "Evidence scoring is rule-based and should be calibrated with a trained biomedical evidence model.",
                ],
            },
            confidence=confidence,
        )
