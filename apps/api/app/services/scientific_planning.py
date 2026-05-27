from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.services.evidence_hierarchy import annotate_evidence_item


class ScientificTaskType(str, Enum):
    TARGET_DISCOVERY = "target_discovery"
    MECHANISM_ANALYSIS = "mechanism_analysis"
    THERAPEUTIC_REASONING = "therapeutic_reasoning"
    DRUG_SAFETY = "drug_safety"
    OMICS_ANALYSIS = "omics_analysis"
    EXPERIMENT_DESIGN = "experiment_design"
    LITERATURE_SYNTHESIS = "literature_synthesis"
    REPORT_EVALUATION = "report_evaluation"


class EvidenceType(str, Enum):
    LITERATURE = "literature"
    TOOL_RESULT = "tool_result"
    MODEL_OUTPUT = "model_output"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    OMICS_ANALYSIS = "omics_analysis"
    DRUG_LABEL_OR_SAFETY = "drug_label_or_safety"
    MECHANISTIC = "mechanistic"
    CONTRADICTORY = "contradictory"
    ABSENCE_OF_EVIDENCE = "absence_of_evidence"
    LOCAL_CONTEXT = "local_context"


class ClaimBoundary(str, Enum):
    MECHANISTIC = "mechanistic"
    COMPUTATIONAL_PRIORITIZATION = "computational_prioritization"
    PRECLINICAL_HYPOTHESIS = "preclinical_hypothesis"
    CLINICAL_EFFICACY_FORBIDDEN = "clinical_efficacy_forbidden"
    SAFETY_CLAIM_FORBIDDEN = "safety_claim_forbidden"
    ABSTAIN = "abstain"


@dataclass
class ObjectiveClassification:
    task_types: list[str]
    primary_task: str
    domain: str
    entities: dict[str, list[str]]
    risk_level: str
    required_capabilities: list[str]
    rationale: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return {
            "task_types": self.task_types,
            "primary_task": self.primary_task,
            "domain": self.domain,
            "entities": self.entities,
            "risk_level": self.risk_level,
            "required_capabilities": self.required_capabilities,
            "rationale": self.rationale,
        }


def classify_objective(objective: str, biomedical_context: dict[str, Any] | None = None) -> ObjectiveClassification:
    text = objective.lower()
    context = biomedical_context or {}
    task_types: list[ScientificTaskType] = []
    rationale: list[str] = []

    def add(task: ScientificTaskType, reason: str) -> None:
        if task not in task_types:
            task_types.append(task)
            rationale.append(reason)

    if any(term in text for term in ["drug", "compound", "therapy", "therapeutic", "treatment", "repurpos"]):
        add(ScientificTaskType.THERAPEUTIC_REASONING, "The objective asks about drugs, therapies, or interventions.")
    if any(term in text for term in ["contraindication", "interaction", "dose", "dosage", "safety", "toxicity", "adverse"]):
        add(ScientificTaskType.DRUG_SAFETY, "The objective includes safety, dosing, toxicity, or interaction language.")
    if any(term in text for term in ["omics", "single-cell", "single cell", "transcript", "proteomic", "expression", "rna-seq", "scrna"]):
        add(ScientificTaskType.OMICS_ANALYSIS, "The objective requires omics or cell-context analysis.")
    if any(term in text for term in ["target", "gene", "biomarker"]):
        add(ScientificTaskType.TARGET_DISCOVERY, "The objective refers to targets, genes, or biomarkers.")
    if any(term in text for term in ["mechanism", "pathway", "causal", "signaling"]):
        add(ScientificTaskType.MECHANISM_ANALYSIS, "The objective asks for mechanism or pathway reasoning.")
    if any(term in text for term in ["experiment", "validate", "assay", "study design", "validation"]):
        add(ScientificTaskType.EXPERIMENT_DESIGN, "The objective asks for experiments or validation.")
    if any(term in text for term in ["literature", "citation", "paper", "pubmed", "review"]):
        add(ScientificTaskType.LITERATURE_SYNTHESIS, "The objective asks for literature or citations.")
    if any(term in text for term in ["evaluate", "score", "rubric", "criteria", "quality"]):
        add(ScientificTaskType.REPORT_EVALUATION, "The objective asks for evaluation or scoring.")
    if not task_types:
        add(ScientificTaskType.MECHANISM_ANALYSIS, "Defaulted to mechanism analysis for a biomedical research objective.")

    primary_task = task_types[0].value
    domain = "biomedicine"
    if ScientificTaskType.OMICS_ANALYSIS in task_types:
        domain = "biomedical_omics"
    elif ScientificTaskType.DRUG_SAFETY in task_types or ScientificTaskType.THERAPEUTIC_REASONING in task_types:
        domain = "therapeutics"

    variants = list(dict.fromkeys(context.get("variants", []) or _extract_variant_tokens(objective)))
    variant_set = {str(item).upper() for item in variants}
    genes = [
        gene
        for gene in list(dict.fromkeys(context.get("primary_genes", []) or _extract_gene_like_tokens(objective)))
        if str(gene).upper() not in variant_set and not _looks_like_variant_token(str(gene))
    ]
    diseases = list(dict.fromkeys(context.get("diseases", []) or _extract_disease_like_phrases(objective)))
    interventions = list(dict.fromkeys(context.get("candidate_interventions", []) or _extract_intervention_terms(objective)))
    risk_level = "high" if ScientificTaskType.DRUG_SAFETY in task_types else "medium"
    if "clinical" in text or "patient" in text or "dosage" in text:
        risk_level = "high"

    capabilities = route_capabilities([task.value for task in task_types], risk_level)
    return ObjectiveClassification(
        task_types=[task.value for task in task_types],
        primary_task=primary_task,
        domain=domain,
        entities={
            "genes": genes[:6],
            "variants": variants[:8],
            "diseases": diseases[:4],
            "interventions": interventions[:8],
        },
        risk_level=risk_level,
        required_capabilities=capabilities,
        rationale=rationale,
    )


def route_capabilities(task_types: list[str], risk_level: str) -> list[str]:
    capabilities = ["public_biomedical", "tooluniverse", "clawinstitute_board"]
    tasks = set(task_types)
    if ScientificTaskType.THERAPEUTIC_REASONING.value in tasks or ScientificTaskType.DRUG_SAFETY.value in tasks:
        capabilities.append("txagent")
    if risk_level == "high":
        capabilities.extend(["safety_reviewer", "abstention_policy"])
    return list(dict.fromkeys(capabilities))


def compile_case_profile(
    objective: str,
    classification: dict[str, Any],
    biomedical_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = biomedical_context or {}
    entities = classification.get("entities", {}) if isinstance(classification.get("entities"), dict) else {}
    text = " ".join(
        [
            objective,
            " ".join(entities.get("genes", []) or []),
            " ".join(entities.get("diseases", []) or []),
            " ".join(entities.get("interventions", []) or []),
        ]
    ).lower()

    def present(*terms: str) -> bool:
        return any(term in text for term in terms)

    mechanism_branches: list[dict[str, Any]] = []
    branch_specs = [
        ("on_target_variant", ["c797s", "t790m", "secondary egfr", "exon 20"], "Variant-level on-target resistance"),
        ("copy_number", ["amplification", "copy-number", "copy number", "egfr amp"], "Copy-number driven resistance"),
        ("rtk_bypass", ["met", "erbb2", "her2", "ret", "alk", "fusion"], "RTK or fusion bypass signaling"),
        ("mapk_pi3k_reactivation", ["mapk", "pi3k", "kras", "braf", "nras", "pik3ca"], "MAPK or PI3K pathway reactivation"),
        ("cell_state", ["emt", "axl", "state transition", "plasticity"], "Cell-state plasticity"),
        ("lineage_transformation", ["small-cell", "small cell", "squamous", "histologic"], "Lineage or histologic transformation"),
        ("anatomic_pharmacologic", ["cns", "sanctuary", "exposure", "pharmacologic"], "Anatomic or pharmacologic resistance"),
        ("safety_translation", ["safety", "toxicity", "adverse", "combination"], "Safety and translational feasibility"),
    ]
    for branch_id, terms, label in branch_specs:
        if present(*terms):
            mechanism_branches.append(
                {
                    "id": branch_id,
                    "label": label,
                    "evidence_need": "supporting evidence, counterevidence, assay feasibility, and failure gate",
                }
            )

    evidence_requirements = [
        {"id": "literature", "label": "Literature evidence", "sources": ["PubMed", "NCBI"]},
        {"id": "target_disease", "label": "Target-disease association", "sources": ["OpenTargets", "ToolUniverse"]},
        {"id": "clinical_context", "label": "Clinical or trial context", "sources": ["ClinicalTrials", "PubMed"]},
        {"id": "safety", "label": "Safety and toxicity context", "sources": ["openFDA", "PubMed"]},
        {"id": "mechanism", "label": "Mechanistic pathway evidence", "sources": ["ToolUniverse", "PubMed"]},
        {"id": "counterevidence", "label": "Contradictions or missing evidence", "sources": ["contradiction_search", "abstention_policy"]},
    ]
    if any(branch["id"] in {"cell_state", "lineage_transformation"} for branch in mechanism_branches):
        evidence_requirements.append(
            {"id": "cell_state_assays", "label": "Cell-state or lineage assay evidence", "sources": ["single-cell", "spatial", "pathology"]}
        )
    if any(branch["id"] == "rtk_bypass" for branch in mechanism_branches):
        evidence_requirements.append(
            {"id": "fusion_copy_number", "label": "Fusion and copy-number detection", "sources": ["ctDNA", "NGS", "copy-number profiling"]}
        )

    validation_assays = []
    if present("ctdna", "clone", "phasing", "t790m", "c797s"):
        validation_assays.append("ctDNA clone structure and cis/trans phasing")
    if present("paired", "biopsy", "pre/post", "post-treatment"):
        validation_assays.append("paired pre/post-treatment biopsy profiling")
    if present("single-cell", "single cell", "spatial", "emt", "axl"):
        validation_assays.append("single-cell or spatial cell-state profiling")
    if present("fusion", "amplification", "copy-number"):
        validation_assays.append("fusion and copy-number profiling")
    if present("organoid", "xenograft", "patient-derived", "explant"):
        validation_assays.append("patient-derived functional model validation")
    if not validation_assays:
        validation_assays = ["public evidence audit", "targeted validation experiment with positive and negative controls"]

    return {
        "schema": "autosci.case_profile.v0.1",
        "objective": objective,
        "entities": {
            "genes": entities.get("genes", []),
            "variants": entities.get("variants", []),
            "diseases": entities.get("diseases", []),
            "interventions": entities.get("interventions", []),
            "context_primary_genes": context.get("primary_genes", []),
            "context_variants": context.get("variants", []),
            "context_diseases": context.get("diseases", []),
        },
        "mechanism_branches": mechanism_branches,
        "evidence_requirements": evidence_requirements,
        "validation_assays": validation_assays,
        "capability_demonstrations": [
            "case_compilation",
            "public_evidence_retrieval",
            "claim_graph",
            "evidence_coverage_matrix",
            "experiment_gate_scoring",
            "replayable_provenance",
        ],
    }


def build_capability_plan(classification: dict[str, Any], case_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    tasks = set(classification.get("task_types", []))
    steps = [
        {"capability": "tooluniverse", "purpose": "Collect biomedical tool evidence with provenance."},
    ]
    if "omics_analysis" in tasks:
        steps.append(
            {
                "capability": "public_omics_context",
                "purpose": (
                    "Use public biomedical evidence, Open Targets context, and explicit validation experiments "
                    "for cell-context and omics-aware reasoning."
                ),
            }
        )
    if "therapeutic_reasoning" in tasks or "drug_safety" in tasks:
        steps.append({"capability": "txagent", "purpose": "Run therapeutic reasoning over drug, contraindication, interaction, and safety context when configured."})
    steps.extend(
        [
            {"capability": "claim_graph", "purpose": "Attach every claim to supporting, contradictory, or missing evidence."},
            {"capability": "evidence_coverage_matrix", "purpose": "Show which case-specific evidence requirements are covered, partial, or missing."},
            {"capability": "experiment_gate_scoring", "purpose": "Rank proposed experiments by decision impact, feasibility, controls, and failure criteria."},
            {"capability": "clawinstitute_board", "purpose": "Publish hypotheses, critiques, revisions, and provenance to the research board."},
        ]
    )
    return {
        "routing_policy": "task_type_and_risk",
        "steps": steps,
        "case_capabilities": (case_profile or {}).get("capability_demonstrations", []),
    }


def build_claim_retrieval_plan(
    objective: str,
    classification: dict[str, Any],
    case_profile: dict[str, Any] | None = None,
    biomedical_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create generic evidence-retrieval claims from typed entities and case requirements."""
    context = biomedical_context or {}
    profile = case_profile or {}
    entities = classification.get("entities", {}) if isinstance(classification.get("entities"), dict) else {}
    profile_entities = profile.get("entities", {}) if isinstance(profile.get("entities"), dict) else {}

    genes = _unique_strings(
        [
            *(entities.get("genes") or []),
            *(profile_entities.get("genes") or []),
            *(context.get("primary_genes") or []),
        ]
    )[:3]
    diseases = _unique_strings(
        [
            *(entities.get("diseases") or []),
            *(profile_entities.get("diseases") or []),
            *(context.get("diseases") or []),
        ]
    )[:3]
    variants = _unique_strings(
        [
            *(entities.get("variants") or []),
            *(profile_entities.get("variants") or []),
            *(context.get("variants") or []),
        ]
    )[:6]
    interventions = _unique_strings(
        [
            *(entities.get("interventions") or []),
            *(profile_entities.get("interventions") or []),
            *(context.get("candidate_interventions") or []),
        ]
    )[:5]

    target = genes[0] if genes else ""
    disease = diseases[0] if diseases else ""
    focus = " ".join(item for item in [target, disease] if item).strip() or objective
    specs: list[dict[str, Any]] = []

    def add_claim(claim_type: str, claim: str, query_parts: list[str], intent: str, priority: int) -> None:
        query = " ".join(_unique_strings([part for part in query_parts if part])).strip()
        if not query:
            return
        specs.append(
            {
                "id": f"planned_claim_{len(specs) + 1}",
                "claim_type": claim_type,
                "claim": claim,
                "query": query,
                "source_intent": intent,
                "priority": priority,
            }
        )

    add_claim(
        "target_disease_grounding",
        f"External evidence should establish whether {focus} has target-disease grounding.",
        [target, disease, "association clinical biomarker evidence"],
        "public_literature_and_knowledge_graph",
        100,
    )
    add_claim(
        "mechanism",
        f"Mechanistic evidence should explain the pathway or resistance logic for {focus}.",
        [target, disease, "mechanism pathway resistance signaling"],
        "mechanistic_literature",
        90,
    )
    if variants:
        add_claim(
            "variant_or_biomarker",
            f"Variant-level evidence should evaluate {', '.join(variants[:3])} in the case context.",
            [target, " ".join(variants[:3]), disease, "variant resistance biomarker"],
            "variant_literature",
            85,
        )
    if interventions:
        add_claim(
            "intervention_precedence",
            f"Retrieved evidence should separate intervention precedence from unresolved research questions.",
            [interventions[0], disease, target, "clinical trial response resistance"],
            "clinical_literature_and_trials",
            80,
        )
        add_claim(
            "safety_translation",
            f"Safety and translation evidence should constrain any intervention discussion.",
            [interventions[0], disease, "toxicity adverse safety tolerability"],
            "safety_literature_and_labels",
            75,
        )
    else:
        add_claim(
            "safety_translation",
            "Safety and translation evidence should constrain therapeutic interpretation.",
            [focus, "toxicity adverse safety tolerability"],
            "safety_literature",
            60,
        )

    for branch in profile.get("mechanism_branches", [])[:3]:
        label = str(branch.get("label") or branch.get("id") or "").strip()
        if not label:
            continue
        add_claim(
            "case_mechanism_branch",
            f"Case-specific mechanism branch requires evidence: {label}.",
            [target, disease, label, "evidence validation"],
            "case_specific_literature",
            70,
        )

    add_claim(
        "counterevidence",
        f"Contradictory or negative evidence should be checked before advancing {focus}.",
        [target, disease, "failed trial negative evidence resistance not associated"],
        "counterevidence_search",
        65,
    )

    deduped = []
    seen_queries: set[str] = set()
    for spec in sorted(specs, key=lambda item: item["priority"], reverse=True):
        key = spec["query"].lower()
        if key in seen_queries:
            continue
        spec = dict(spec)
        spec["id"] = f"planned_claim_{len(deduped) + 1}"
        deduped.append(spec)
        seen_queries.add(key)
        if len(deduped) >= 8:
            break

    return {
        "schema": "autosci.claim_retrieval_plan.v0.1",
        "policy": "entity_and_requirement_driven",
        "claims": deduped,
        "entities": {
            "genes": genes,
            "diseases": diseases,
            "variants": variants,
            "interventions": interventions,
        },
    }


def map_evidence_to_claims(
    evidence: list[dict[str, Any]],
    claim_plan: dict[str, Any] | None,
    claim_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    planned_claims = (claim_plan or {}).get("claims", []) or []
    generated_claims = (claim_graph or {}).get("claims", []) or []
    rows = []
    for claim in planned_claims:
        query_tokens = _claim_tokens(" ".join([str(claim.get("query", "")), str(claim.get("claim", ""))]))
        claim_type = str(claim.get("claim_type") or "")
        matches = []
        for index, item in enumerate(evidence):
            score = item.get("score", {}) if isinstance(item.get("score"), dict) else {}
            label = str(item.get("support_label") or score.get("label") or "").lower()
            if label in {"irrelevant"}:
                continue
            haystack = " ".join(
                [
                    str(item.get("source", "")),
                    str(item.get("text", "")),
                    json_like(item.get("structured", {})),
                ]
            ).lower()
            matched = sorted(token for token in query_tokens if token in haystack)
            if _claim_specific_match(claim_type, query_tokens, matched, haystack):
                matches.append(
                    {
                        "evidence_index": index,
                        "source": item.get("source", "unknown"),
                        "label": label or "unscored",
                        "matched_terms": matched[:8],
                    }
                )
        if len(matches) >= 2:
            status = "covered"
        elif matches:
            status = "partial"
        else:
            status = "missing"
        rows.append(
            {
                "id": claim.get("id"),
                "claim_type": claim.get("claim_type"),
                "claim": claim.get("claim"),
                "query": claim.get("query"),
                "support_status": status,
                "matched_evidence": matches[:8],
            }
        )

    covered = sum(1 for row in rows if row["support_status"] == "covered")
    partial = sum(1 for row in rows if row["support_status"] == "partial")
    return {
        "schema": "autosci.claim_evidence_matrix.v0.1",
        "planned_claim_count": len(planned_claims),
        "generated_claim_count": len(generated_claims),
        "coverage_score": round((covered + 0.5 * partial) / len(rows), 3) if rows else 0.0,
        "covered_count": covered,
        "partial_count": partial,
        "missing_count": sum(1 for row in rows if row["support_status"] == "missing"),
        "claims": rows,
    }


def build_quality_dashboard(
    evidence: list[dict[str, Any]],
    tool_outputs: list[dict[str, Any]],
    claim_matrix: dict[str, Any] | None = None,
    evidence_coverage: dict[str, Any] | None = None,
    scientific_strategy: dict[str, Any] | None = None,
    critique: dict[str, Any] | None = None,
    experiments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    labels: dict[str, int] = {}
    for item in evidence:
        score = item.get("score", {}) if isinstance(item.get("score"), dict) else {}
        label = str(item.get("support_label") or score.get("label") or "unscored")
        labels[label] = labels.get(label, 0) + 1
    relevant = sum(count for label, count in labels.items() if label not in {"irrelevant", "unscored"})
    tool_status: dict[str, int] = {}
    for output in tool_outputs:
        result = output.get("result", {}) if isinstance(output.get("result"), dict) else {}
        status = str(output.get("status") or result.get("status") or "unknown")
        tool_status[status] = tool_status.get(status, 0) + 1
    strong_experiments = sum(1 for exp in experiments or [] if exp.get("gate_quality") == "strong")
    usable_experiments = sum(1 for exp in experiments or [] if exp.get("gate_quality") in {"strong", "usable"})
    readiness = (scientific_strategy or {}).get("readiness", {}) if isinstance(scientific_strategy, dict) else {}
    flags = []
    total_evidence = len(evidence)
    if total_evidence and labels.get("irrelevant", 0) / total_evidence > 0.4:
        flags.append("High irrelevant-evidence fraction; retrieval should be tightened.")
    if (claim_matrix or {}).get("missing_count", 0):
        flags.append("One or more planned claims still lack mapped evidence.")
    if (evidence_coverage or {}).get("missing_count", 0):
        flags.append("One or more case evidence requirements remain missing.")
    if str((critique or {}).get("severity") or "").lower() == "high":
        flags.append("High-severity critique affected final calibration.")
    if tool_status.get("failure", 0):
        flags.append("Some tool calls failed and should be inspected in provenance.")

    return {
        "schema": "autosci.quality_dashboard.v0.1",
        "evidence": {
            "total": total_evidence,
            "labels": labels,
            "relevance_rate": round(relevant / total_evidence, 3) if total_evidence else 0.0,
        },
        "tools": {
            "total": len(tool_outputs),
            "statuses": tool_status,
            "success_rate": round(tool_status.get("success", 0) / len(tool_outputs), 3) if tool_outputs else 0.0,
        },
        "claims": {
            "coverage_score": (claim_matrix or {}).get("coverage_score", 0.0),
            "covered": (claim_matrix or {}).get("covered_count", 0),
            "partial": (claim_matrix or {}).get("partial_count", 0),
            "missing": (claim_matrix or {}).get("missing_count", 0),
        },
        "requirements": {
            "coverage_score": (evidence_coverage or {}).get("coverage_score", 0.0),
            "covered": (evidence_coverage or {}).get("covered_count", 0),
            "partial": (evidence_coverage or {}).get("partial_count", 0),
            "missing": (evidence_coverage or {}).get("missing_count", 0),
        },
        "experiments": {
            "total": len(experiments or []),
            "usable_or_strong": usable_experiments,
            "strong": strong_experiments,
        },
        "readiness": {
            "score": readiness.get("score"),
            "tier": readiness.get("tier"),
        },
        "flags": flags,
    }


def build_evidence_coverage_matrix(
    case_profile: dict[str, Any],
    evidence: list[dict[str, Any]],
    claim_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    requirements = case_profile.get("evidence_requirements", []) or []
    claims = (claim_graph or {}).get("claims", []) or []
    rows = []
    for requirement in requirements:
        req_id = str(requirement.get("id", "requirement"))
        label = str(requirement.get("label", req_id))
        expected_sources = [str(src) for src in requirement.get("sources", [])]
        source_tokens, content_tokens = _coverage_tokens(req_id, label, expected_sources)
        matched_sources = []
        for item in evidence:
            score = item.get("score", {}) if isinstance(item.get("score"), dict) else {}
            label_value = str(item.get("support_label") or score.get("label") or "").lower()
            if label_value in {"irrelevant", "contradiction", "contradicts"}:
                continue
            source_text = str(item.get("source", "")).lower()
            body_text = " ".join(
                [
                    str(item.get("text", "")),
                    json_like(item.get("structured", {})),
                    json_like(score),
                ]
            ).lower()
            haystack = " ".join(
                [
                    source_text,
                    body_text,
                ]
            )
            source_match = not source_tokens or any(token in source_text for token in source_tokens)
            content_match = any(token in body_text or token in haystack for token in content_tokens)
            if source_match and content_match:
                matched_sources.append(str(item.get("source", "unknown")))
        supporting_claims = [
            claim.get("id")
            for claim in claims
            if any(src in claim.get("supporting_evidence_sources", []) for src in matched_sources)
        ]
        required_distinct = 1 if req_id in {"counterevidence", "cell_state_assays", "fusion_copy_number"} else 2
        if len(set(matched_sources)) >= required_distinct:
            status = "covered"
        elif matched_sources:
            status = "partial"
        else:
            status = "missing"
        rows.append(
            {
                "id": req_id,
                "label": label,
                "expected_sources": expected_sources,
                "status": status,
                "matched_sources": sorted(set(matched_sources)),
                "supporting_claims": sorted(set(supporting_claims)),
            }
        )
    covered = sum(1 for row in rows if row["status"] == "covered")
    partial = sum(1 for row in rows if row["status"] == "partial")
    score = round((covered + 0.5 * partial) / len(rows), 3) if rows else 0.0
    return {
        "schema": "autosci.evidence_coverage_matrix.v0.1",
        "coverage_score": score,
        "covered_count": covered,
        "partial_count": partial,
        "missing_count": sum(1 for row in rows if row["status"] == "missing"),
        "requirements": rows,
    }


def score_experiment_gates(
    experiments: list[dict[str, Any]],
    case_profile: dict[str, Any],
    evidence_coverage: dict[str, Any],
) -> list[dict[str, Any]]:
    missing = [row for row in evidence_coverage.get("requirements", []) if row.get("status") != "covered"]
    assays = [str(assay).lower() for assay in case_profile.get("validation_assays", [])]
    scored = []
    for experiment in experiments:
        exp = dict(experiment)
        text = " ".join(str(exp.get(key, "")) for key in ("name", "type", "decision_gate", "success_criteria", "failure_modes")).lower()
        info = _ordinal_score(exp.get("expected_information_gain"), {"very_high": 4, "high": 3, "medium": 2, "low": 1})
        feasibility = _ordinal_score(exp.get("feasibility"), {"high": 3, "medium": 2, "low": 1})
        cost = _ordinal_score(exp.get("cost"), {"low": 3, "low-medium": 2.5, "medium": 2, "medium-high": 1.5, "high": 1})
        controls = 1 if ("control" in text or exp.get("success_criteria")) else 0
        failure_gate = 1 if ("failure" in text or exp.get("failure_modes")) else 0
        assay_match = 1 if any(any(token in text for token in assay.split()[:3]) for assay in assays) else 0
        gap_match = 1 if any(str(row.get("id", "")).replace("_", " ") in text for row in missing) else 0
        score = round((info * 0.28 + feasibility * 0.16 + cost * 0.12 + controls * 0.16 + failure_gate * 0.16 + assay_match * 0.07 + gap_match * 0.05) / 2.91, 3)
        exp["decision_impact_score"] = min(1.0, score)
        exp["gate_quality"] = "strong" if score >= 0.75 else "usable" if score >= 0.5 else "weak"
        exp["gate_reasons"] = [
            reason
            for condition, reason in [
                (controls == 0, "Add explicit positive/negative controls."),
                (failure_gate == 0, "Add a falsifying failure criterion."),
                (assay_match == 0, "Tie the experiment to a named case validation assay."),
                (gap_match == 0 and missing, "Tie the experiment to an uncovered evidence requirement."),
            ]
            if condition
        ]
        scored.append(exp)
    return sorted(scored, key=lambda item: item.get("decision_impact_score", 0), reverse=True)


def fallback_evaluation_criteria(objective: str, classification: dict[str, Any]) -> list[dict[str, Any]]:
    criteria = [
        {"criterion": "Identifies the primary biomedical entities and objective scope.", "points": 2},
        {"criterion": "Separates direct evidence from indirect or planning-only evidence.", "points": 3},
        {"criterion": "States uncertainty and avoids unsupported clinical efficacy or safety claims.", "points": 4},
        {"criterion": "Includes limitations and concrete validation experiments.", "points": 3},
    ]
    tasks = set(classification.get("task_types", []))
    if "therapeutic_reasoning" in tasks or "drug_safety" in tasks:
        criteria.append({"criterion": "Reviews intervention-specific safety, contraindication, and translation gaps.", "points": 4})
    if "omics_analysis" in tasks:
        criteria.append({"criterion": "Checks omics context, cell type, dataset compatibility, and analysis validity.", "points": 4})
    if "target_discovery" in tasks:
        criteria.append({"criterion": "Explains target-disease relevance without overstating causality.", "points": 3})
    if objective:
        criteria.append({"criterion": "Answers the specific user objective rather than a generic biomedical prompt.", "points": 4})
    return criteria


def infer_evidence_type(item: dict[str, Any]) -> str:
    source = str(item.get("source", "")).lower()
    text = str(item.get("text", "")).lower()
    if source.startswith("local_"):
        return EvidenceType.LOCAL_CONTEXT.value
    if "pubmed" in source or "pmid" in text:
        return EvidenceType.LITERATURE.value
    if "txagent" in source or any(term in text for term in ["contraindication", "adverse", "dosage"]):
        return EvidenceType.DRUG_LABEL_OR_SAFETY.value
    if any(term in text for term in ["omics", "single-cell", "transcriptomic"]):
        return EvidenceType.OMICS_ANALYSIS.value
    if "opentargets" in source or "tooluniverse" in source:
        return EvidenceType.TOOL_RESULT.value
    if "model" in source:
        return EvidenceType.MODEL_OUTPUT.value
    if any(term in text for term in ["no evidence", "not retrieved", "insufficient"]):
        return EvidenceType.ABSENCE_OF_EVIDENCE.value
    if any(term in text for term in ["contradict", "conflict", "opposes"]):
        return EvidenceType.CONTRADICTORY.value
    return EvidenceType.MECHANISTIC.value


def type_evidence_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    typed = []
    for item in items:
        evidence_type = item.get("evidence_type") or infer_evidence_type(item)
        structured = dict(item.get("structured", {}))
        structured.setdefault("evidence_type", evidence_type)
        typed.append(annotate_evidence_item({**item, "evidence_type": evidence_type, "structured": structured}))
    return typed


def build_claim_graph(hypothesis_card: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    hypothesis = str(hypothesis_card.get("hypothesis") or "")
    claims = _split_claims(hypothesis)
    if not claims and hypothesis:
        claims = [hypothesis]
    nodes = []
    for index, claim in enumerate(claims[:6], start=1):
        support = []
        contradiction = []
        gaps = []
        for item in evidence:
            evidence_type = item.get("evidence_type") or infer_evidence_type(item)
            source = item.get("source", "unknown")
            score = item.get("score", {})
            label = score.get("label") if isinstance(score, dict) else None
            if evidence_type in {EvidenceType.CONTRADICTORY.value} or label in {"contradiction", "contradicts"}:
                contradiction.append(source)
            elif label == "irrelevant" or evidence_type in {EvidenceType.ABSENCE_OF_EVIDENCE.value, EvidenceType.LOCAL_CONTEXT.value}:
                gaps.append(source)
            else:
                support.append(source)
        boundary = ClaimBoundary.COMPUTATIONAL_PRIORITIZATION.value
        if not support:
            boundary = ClaimBoundary.ABSTAIN.value
        if any(term in claim.lower() for term in ["safe", "efficacy", "effective", "treats", "cures"]):
            boundary = ClaimBoundary.CLINICAL_EFFICACY_FORBIDDEN.value
        nodes.append(
            {
                "id": f"claim_{index}",
                "text": claim,
                "supporting_evidence_sources": sorted(set(support)),
                "contradictory_evidence_sources": sorted(set(contradiction)),
                "evidence_gaps": sorted(set(gaps)),
                "claim_boundary": boundary,
            }
        )
    return {"claims": nodes, "evidence_count": len(evidence), "policy": "claim_evidence_boundary_v1"}


def build_abstention_assessment(classification: dict[str, Any], evidence: list[dict[str, Any]], claim_graph: dict[str, Any]) -> dict[str, Any]:
    evidence_types = {item.get("evidence_type") or infer_evidence_type(item) for item in evidence}
    reasons = []
    if not evidence or evidence_types <= {EvidenceType.LOCAL_CONTEXT.value, EvidenceType.ABSENCE_OF_EVIDENCE.value}:
        reasons.append("Only local planning context or absence-of-evidence records are available.")
    if classification.get("risk_level") == "high" and EvidenceType.DRUG_LABEL_OR_SAFETY.value not in evidence_types:
        reasons.append("High-risk therapeutic or patient-context objective lacks safety-specific evidence.")
    unsupported_claims = [
        claim for claim in claim_graph.get("claims", []) if claim.get("claim_boundary") == ClaimBoundary.ABSTAIN.value
    ]
    if unsupported_claims:
        reasons.append("At least one generated claim lacks external supporting evidence.")
    return {
        "abstention_required": bool(reasons),
        "reasons": reasons,
        "allowed_output": (
            "candidate hypothesis with explicit limitations"
            if not reasons
            else "planning-only or insufficient-evidence response with no efficacy/safety claim"
        ),
    }


def evaluate_report_against_criteria(report: dict[str, Any], criteria: list[dict[str, Any]]) -> dict[str, Any]:
    text = " ".join(
        [
            str(report.get("title", "")),
            str(report.get("summary", "")),
            " ".join(str(item) for item in report.get("guardrails", [])),
            " ".join(str(item) for item in report.get("next_experiments", [])),
        ]
    ).lower()
    scored = []
    earned = 0
    total = 0
    for criterion in criteria:
        points = int(criterion.get("points", 1) or 1)
        total += points
        label = str(criterion.get("criterion", ""))
        tokens = [token for token in re.findall(r"[a-z]{4,}", label.lower()) if token not in {"criterion", "specific"}]
        matched = sum(1 for token in tokens if token in text)
        satisfied = matched >= max(1, min(3, len(tokens) // 4))
        if satisfied:
            earned += points
        scored.append({**criterion, "satisfied": satisfied, "matched_terms": matched})
    return {
        "score": round(earned / total, 3) if total else 0.0,
        "earned_points": earned,
        "total_points": total,
        "criteria": scored,
        "method": "keyword_coverage_fallback",
    }


def _extract_gene_like_tokens(text: str) -> list[str]:
    stop = {"AND", "THE", "USE", "NOT", "FOR", "WITH", "DNA", "RNA", "LLM"}
    return [
        match
        for match in re.findall(r"\b[A-Z][A-Z0-9]{2,9}\b", text)
        if match not in stop and not _looks_like_variant_token(match)
    ]


def _looks_like_variant_token(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]\d{2,5}[A-Z](?:fs|del|ins)?", str(value or ""), flags=re.I))


def _extract_variant_tokens(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\b[A-Z]\d{2,5}[A-Z](?:fs|del|ins)?\b", text)))[:8]


def _extract_disease_like_phrases(text: str) -> list[str]:
    phrases = []
    for pattern in [
        r"for ([A-Za-z][A-Za-z0-9 /'-]+?)(?:\.|,|;| and | with | by |$)",
        r"in ([A-Za-z][A-Za-z0-9 /'-]+?)(?:\.|,|;| and | with | by |$)",
    ]:
        match = re.search(pattern, text)
        if match:
            phrases.append(re.sub(r"^[A-Z0-9]+-driven\s+", "", match.group(1), flags=re.I).strip())
    return phrases


def _extract_intervention_terms(text: str) -> list[str]:
    candidates = []
    for pattern in [r"\b(?:drug|compound|therapy|treatment)\s+([A-Za-z0-9 -]{3,40})"]:
        candidates.extend(match.strip() for match in re.findall(pattern, text, flags=re.I))
    return candidates


def _split_claims(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|;\s+", text.strip())
    return [part.strip() for part in parts if len(part.strip()) > 20]


def _unique_strings(values: list[Any]) -> list[str]:
    cleaned = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        if text.lower() not in {item.lower() for item in cleaned}:
            cleaned.append(text)
    return cleaned


def _claim_tokens(text: str) -> list[str]:
    stop = {
        "about",
        "after",
        "association",
        "before",
        "clinical",
        "context",
        "disease",
        "evidence",
        "external",
        "grounding",
        "retrieved",
        "should",
        "study",
        "trial",
        "with",
    }
    tokens = [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9-]{2,}", text.lower())
        if token not in stop and len(token) >= 3
    ]
    return list(dict.fromkeys(tokens))[:16]


def _claim_specific_match(claim_type: str, query_tokens: list[str], matched: list[str], haystack: str) -> bool:
    if len(matched) < 2:
        return False
    anchors_by_type = {
        "target_disease_grounding": {"biomarker", "driver", "association", "target", "clinical"},
        "mechanism": {"mechanism", "pathway", "signaling", "resistance", "activation", "bypass"},
        "variant_or_biomarker": set(),
        "intervention_precedence": {"response", "trial", "phase", "approved", "inhibitor", "therapy"},
        "safety_translation": {"toxicity", "adverse", "safety", "tolerability", "serious"},
        "case_mechanism_branch": set(),
        "counterevidence": {"failed", "negative", "null", "not", "insufficient"},
    }
    matched_set = set(matched)
    variant_tokens = {token for token in query_tokens if re.fullmatch(r"[a-z]\d{2,5}[a-z](?:fs|del|ins)?", token)}
    if claim_type == "variant_or_biomarker":
        return bool(variant_tokens & matched_set) and len(matched) >= 3
    if claim_type == "case_mechanism_branch":
        branch_anchors = {
            token
            for token in query_tokens
            if token
            not in {
                "target",
                "validation",
                "resistance",
                "mechanism",
                "branch",
                "requires",
                "case-specific",
            }
            and token not in {"cancer", "carcinoma", "lung", "thyroid", "melanoma"}
        }
        return bool(branch_anchors & matched_set) and len(matched) >= 3
    anchors = anchors_by_type.get(claim_type, set())
    if anchors and not (anchors & matched_set or any(anchor in haystack for anchor in anchors)):
        return False
    if claim_type == "safety_translation" and not any(term in haystack for term in anchors_by_type["safety_translation"]):
        return False
    if claim_type == "counterevidence" and not any(term in haystack for term in anchors_by_type["counterevidence"]):
        return False
    return len(matched) >= max(3, min(5, len(query_tokens) // 2))


def _coverage_tokens(req_id: str, label: str, expected_sources: list[str]) -> tuple[list[str], list[str]]:
    source_map = {
        "literature": ["pubmed", "pmid"],
        "target_disease": ["opentargets", "open targets", "tooluniverse"],
        "clinical_context": ["clinicaltrials", "clinical trials", "pubmed"],
        "safety": ["openfda", "adverse", "safety", "toxicity", "pubmed"],
        "mechanism": ["reactome", "pubmed", "tooluniverse"],
        "counterevidence": ["pubmed", "clinicaltrials", "contradiction"],
        "cell_state_assays": ["pubmed", "single-cell", "spatial", "pathology"],
        "fusion_copy_number": ["pubmed", "clinicaltrials", "tooluniverse"],
    }
    content_map = {
        "literature": ["pmid", "article", "publication", "study"],
        "target_disease": ["association", "target", "disease", "driver"],
        "clinical_context": ["trial", "phase", "nct", "clinical", "precedence"],
        "safety": ["adverse", "toxicity", "safety", "serious", "tolerability"],
        "mechanism": ["pathway", "signaling", "mechanism", "phosphorylation"],
        "counterevidence": ["contradiction", "failed", "terminated", "null", "insufficient", "not associated"],
        "cell_state_assays": ["emt", "axl", "single-cell", "single cell", "spatial", "lineage", "transformation"],
        "fusion_copy_number": ["fusion", "copy-number", "copy number", "amplification", "alk", "ret", "erbb2", "met"],
    }
    fallback = [token for token in re.findall(r"[a-z0-9-]{4,}", f"{req_id} {label}".lower())]
    source_tokens = source_map.get(req_id, [src.lower() for src in expected_sources if src])
    content_tokens = content_map.get(req_id, fallback)
    return list(dict.fromkeys(source_tokens)), list(dict.fromkeys(content_tokens))


def _ordinal_score(value: object, mapping: dict[str, float]) -> float:
    return float(mapping.get(str(value or "").lower(), 0))


def json_like(value: object) -> str:
    try:
        return str(value) if isinstance(value, str) else repr(value)
    except Exception:
        return ""
