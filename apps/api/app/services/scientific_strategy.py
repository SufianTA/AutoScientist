from __future__ import annotations

import copy
import re
from collections import Counter
from typing import Any

SEVERITY_PENALTY = {"high": 18, "medium": 11, "low": 6}
SEVERITY_PRIORITY = {"high": 35, "medium": 22, "low": 12}
COST_FACTOR = {"low": 1.0, "low-medium": 1.2, "medium": 1.45, "medium-high": 1.75, "high": 2.2}
FEASIBILITY_FACTOR = {"high": 1.15, "medium": 1.0, "low": 0.75}
GAIN_FACTOR = {"very_high": 1.55, "high": 1.35, "medium": 1.0, "low": 0.7}


def build_scientific_strategy(
    *,
    objective: str,
    biomedical_context: dict[str, Any],
    evidence: list[dict[str, Any]],
    claim_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an evidence-gap and next-action strategy for the scientific runtime.

    This is intentionally deterministic: it should make the run auditable and should
    not depend on another generative model call to decide whether evidence is weak.
    """

    profile = _evidence_profile(evidence)
    gaps = _evidence_gaps(objective, biomedical_context, evidence, profile, claim_graph or {})
    readiness_score = max(0, min(100, 100 - sum(SEVERITY_PENALTY[gap["severity"]] for gap in gaps)))
    readiness_tier = _readiness_tier(readiness_score, gaps)
    followups = _recommended_followups(gaps)
    return {
        "schema": "autosci.scientific_strategy.v0.1",
        "readiness": {
            "score": readiness_score,
            "tier": readiness_tier,
            "rationale": _readiness_rationale(readiness_tier, gaps),
        },
        "evidence_profile": profile,
        "gaps": gaps,
        "recommended_followups": followups,
        "next_action": _next_action(readiness_tier, gaps),
    }


def rank_experiments_by_strategy(
    experiments: list[dict[str, Any]],
    strategy: dict[str, Any],
) -> list[dict[str, Any]]:
    gaps = strategy.get("gaps", [])
    gap_ids = [gap["id"] for gap in gaps]
    ranked: list[dict[str, Any]] = []
    for experiment in experiments:
        addresses = _experiment_gap_matches(experiment, gap_ids)
        ranked.append(_annotate_experiment(experiment, addresses, gaps))
    ranked.extend(_gap_driven_experiments(gaps, existing_gap_ids={gap_id for item in ranked for gap_id in item["addresses_gaps"]}))
    ranked = sorted(ranked, key=lambda item: item["priority_score"], reverse=True)
    return ranked[:6]


def calibrate_scientific_strategy_with_review(
    strategy: dict[str, Any],
    *,
    evidence: list[dict[str, Any]],
    critique: dict[str, Any] | None = None,
    abstention_policy: dict[str, Any] | None = None,
    biotruth_critic: dict[str, Any] | None = None,
    actionability_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply post-review calibration so readiness cannot outrun reviewer findings."""

    calibrated = copy.deepcopy(strategy or {})
    readiness = dict(calibrated.get("readiness") or {})
    base_score = int(readiness.get("score") or 0)
    gaps = list(calibrated.get("gaps") or [])
    notes: list[str] = []
    penalty = 0

    critique = critique or {}
    severity = str(critique.get("severity") or "").lower()
    if severity in SEVERITY_PENALTY:
        severity_penalty = {"high": 18, "medium": 10, "low": 4}[severity]
        penalty += severity_penalty
        notes.append(f"Reviewer critique severity `{severity}` reduced readiness by {severity_penalty} points.")
        if severity == "high":
            gaps.append(
                _gap(
                    "reviewer_high_severity_concern",
                    "medium",
                    str(critique.get("critique") or "Reviewer identified high-severity scientific concerns.")[:500],
                    ["repair overclaims with direct supporting evidence", "soften unsupported claim boundaries"],
                    "Do not label the dossier validation-ready until the reviewer concern is resolved.",
                )
            )

    label_counts = Counter()
    for item in evidence:
        score = item.get("score", {}) if isinstance(item.get("score"), dict) else {}
        label_counts[str(item.get("support_label") or score.get("label") or "unlabeled").lower()] += 1
    total_labeled = sum(label_counts.values())
    irrelevant_count = label_counts.get("irrelevant", 0)
    if total_labeled and irrelevant_count / total_labeled >= 0.25:
        irrelevance_penalty = min(16, round((irrelevant_count / total_labeled) * 30))
        penalty += irrelevance_penalty
        notes.append(
            f"{irrelevant_count}/{total_labeled} evidence items were labeled irrelevant; readiness reduced by {irrelevance_penalty} points."
        )
        gaps.append(
            _gap(
                "evidence_relevance_noise",
                "medium",
                "A material fraction of retrieved evidence was judged irrelevant to the claim boundary.",
                ["tighten entity-specific retrieval and rerank evidence relevance"],
                "Filter or replace irrelevant evidence before treating the dossier as validation-ready.",
            )
        )

    abstention_policy = abstention_policy or {}
    if abstention_policy.get("abstention_required") or str(abstention_policy.get("decision") or "").lower() in {"abstain", "conflicting"}:
        penalty += 25
        notes.append("Abstention/conflict policy requires conservative readiness calibration.")

    biotruth_critic = biotruth_critic or {}
    verdict = str(biotruth_critic.get("verdict") or "").lower()
    weighted = biotruth_critic.get("weighted_score")
    if verdict in {"abstain", "conflicting"}:
        penalty += 20
        notes.append(f"Biomedical critic verdict `{verdict}` reduced readiness.")
    elif isinstance(weighted, (int, float)) and weighted < 65:
        penalty += 10
        notes.append(f"Biomedical critic weighted score {weighted} reduced readiness.")

    actionability_profile = actionability_profile or {}
    actionability = str(actionability_profile.get("actionability") or actionability_profile.get("decision") or "").lower()
    if actionability in {"not_actionable", "insufficient", "low"}:
        penalty += 10
        notes.append("Actionability review found the dossier insufficiently actionable.")

    new_score = max(0, min(100, base_score - penalty))
    supportive_count = (
        label_counts.get("strong_support", 0)
        + label_counts.get("mechanistic_relevance", 0)
        + label_counts.get("supports", 0)
    )
    if not abstention_policy.get("abstention_required") and supportive_count >= 5 and new_score < 65:
        new_score = 65
        notes.append("Multiple supportive evidence records kept the calibrated dossier at experiment-ready floor.")

    if abstention_policy.get("abstention_required") or new_score < 65:
        new_tier = "hypothesis_only"
    elif severity == "high" or any(gap.get("severity") == "medium" for gap in gaps) or new_score < 82:
        new_tier = "experiment_ready_with_gaps"
    else:
        new_tier = "validation_ready"

    readiness.update(
        {
            "score": new_score,
            "tier": new_tier,
            "uncalibrated_score": base_score,
            "calibration_notes": notes,
            "rationale": _readiness_rationale(new_tier, gaps),
        }
    )
    calibrated["readiness"] = readiness
    calibrated["gaps"] = gaps
    calibrated["next_action"] = _next_action(new_tier, gaps)
    return calibrated


def _evidence_profile(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    sources = Counter()
    labels = Counter()
    evidence_types = Counter()
    pubmed_article_count = 0
    scored = 0
    external_evidence: list[dict[str, Any]] = []
    external_labels = Counter()
    for item in evidence:
        sources[str(item.get("source") or "unknown")] += 1
        score = item.get("score", {})
        label = "unlabeled"
        if isinstance(score, dict):
            label = str(score.get("label") or "unlabeled")
            labels[label] += 1
            if score.get("score") is not None:
                scored += 1
        evidence_type = str(
            (score.get("evidence_type") if isinstance(score, dict) else None)
            or item.get("evidence_type")
            or item.get("structured", {}).get("evidence_type")
            or "unknown"
        )
        evidence_types[evidence_type] += 1
        if evidence_type not in {"local_context", "absence_of_evidence"} and label != "irrelevant":
            external_evidence.append(item)
            external_labels[label] += 1
        structured = item.get("structured", {})
        if isinstance(structured, dict) and "articles" in structured:
            pubmed_article_count += len(structured.get("articles") or [])
        elif str(item.get("source", "")).startswith("PubMed") and isinstance(structured, dict):
            pubmed_article_count += int(structured.get("count") or 0)
    return {
        "evidence_count": len(evidence),
        "scored_count": scored,
        "source_counts": dict(sources),
        "label_counts": dict(labels),
        "evidence_type_counts": dict(evidence_types),
        "pubmed_article_count": pubmed_article_count,
        "has_live_literature": pubmed_article_count > 0,
        "has_tooluniverse": any("opentargets" in source.lower() or "tooluniverse" in source.lower() for source in sources),
        "has_safety": external_labels.get("safety_concern", 0) > 0
        or _any_evidence_text(external_evidence, ["safety", "toxicity", "adverse", "off-target", "admet"]),
        "has_counterevidence": external_labels.get("contradicts", 0) > 0
        or external_labels.get("contradiction", 0) > 0
        or _any_evidence_text(external_evidence, ["contradict", "failed", "null result", "not associated"]),
        "has_cell_context": _any_evidence_text(
            external_evidence,
            ["single-cell", "single cell", "transcriptomic", "cell type", "perturbation", "scrna", "organoid"],
        ),
        "has_intervention_context": _any_evidence_text(
            external_evidence,
            ["compound", "drug", "inhibitor", "antibody", "therapy", "potency", "selectivity", "chembl", "pubchem"],
        ),
    }


def _evidence_gaps(
    objective: str,
    context: dict[str, Any],
    evidence: list[dict[str, Any]],
    profile: dict[str, Any],
    claim_graph: dict[str, Any],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    genes = [str(item) for item in context.get("primary_genes", [])]
    diseases = [str(item) for item in context.get("diseases", [])]
    candidates = [str(item) for item in context.get("candidate_interventions", [])]
    objective_lower = objective.lower()
    entity_phrase = " ".join([*(genes[:1] or ["target"]), *(diseases[:1] or ["disease"])])

    if not profile["has_live_literature"] or profile["pubmed_article_count"] < 3:
        gaps.append(
            _gap(
                "insufficient_literature_depth",
                "medium",
                "The literature grounding is shallow, so the hypothesis may be supported by too few retrieved records.",
                [
                    f"{entity_phrase} mechanism",
                    f"{entity_phrase} therapeutic target validation",
                ],
                "Run targeted PubMed retrieval and inspect article-level relevance before strengthening the claim.",
            )
        )
    if not profile["has_tooluniverse"]:
        gaps.append(
            _gap(
                "missing_target_disease_association",
                "high",
                "No ToolUniverse/OpenTargets-style target-disease association evidence is visible.",
                [f"{entity_phrase} OpenTargets association"],
                "Triangulate disease association before ranking the target.",
            )
        )
    if candidates and not profile["has_intervention_context"]:
        gaps.append(
            _gap(
                "missing_intervention_specific_evidence",
                "high",
                "Candidate interventions are mentioned, but potency, selectivity, exposure, or compound identity evidence is missing.",
                [f"{candidates[0]} {entity_phrase} potency selectivity safety"],
                "Do not rank interventions until compound-level evidence is collected.",
            )
        )
    if any(term in objective_lower for term in ["therapeutic", "drug", "safety", "clinical", "patient", "treatment"]) and not profile["has_safety"]:
        gaps.append(
            _gap(
                "missing_safety_evidence",
                "high",
                "The objective has therapeutic or clinical implications, but safety/off-target evidence is missing.",
                [f"{entity_phrase} safety toxicity adverse effect", f"{entity_phrase} off-target risk"],
                "Treat the result as hypothesis-only until safety evidence is reviewed.",
            )
        )
    if any(term in objective_lower for term in ["single-cell", "single cell", "transcript", "omics", "cell"]) and not profile["has_cell_context"]:
        gaps.append(
            _gap(
                "missing_cell_context_evidence",
                "high",
                "The objective asks for cell-context or omics reasoning, but no matching cell-context evidence is present.",
                [f"{entity_phrase} single-cell transcriptomic", f"{entity_phrase} perturbation expression"],
                "Validate that the mechanism is active in the relevant cell state before proposing wet-lab assays.",
            )
        )
    if not profile["has_counterevidence"]:
        gaps.append(
            _gap(
                "missing_falsification_search",
                "medium",
                "The run has not explicitly searched for contradictory, null, or failed evidence.",
                [f"{entity_phrase} failed trial", f"{entity_phrase} not associated"],
                "Run a falsification pass before increasing confidence.",
            )
        )
    claim_gaps = [
        gap
        for claim in claim_graph.get("claims", [])
        for gap in claim.get("evidence_gaps", [])
        if isinstance(gap, str)
    ]
    if claim_gaps:
        gaps.append(
            _gap(
                "claim_graph_evidence_gap",
                "medium",
                f"The claim graph still has unsupported evidence links: {', '.join(sorted(set(claim_gaps))[:3])}.",
                [f"{entity_phrase} causal evidence"],
                "Repair unsupported claim links or soften the hypothesis boundary.",
            )
        )
    return gaps


_GAP_RECOMMENDED_TOOL: dict[str, str] = {
    "insufficient_literature_depth": "pubmed_literature_search_tool",
    "missing_target_disease_association": "tooluniverse_query_tool",
    "missing_intervention_specific_evidence": "pubchem_compound_lookup_tool",
    "missing_safety_evidence": "pubmed_literature_search_tool",
    "missing_cell_context_evidence": "pubmed_literature_search_tool",
    "missing_falsification_search": "pubmed_literature_search_tool",
    "claim_graph_evidence_gap": "tooluniverse_query_tool",
    "reviewer_high_severity_concern": "pubmed_literature_search_tool",
    "evidence_relevance_noise": "pubmed_literature_search_tool",
}


def _gap(
    gap_id: str,
    severity: str,
    rationale: str,
    follow_up_queries: list[str],
    experiment_implication: str,
) -> dict[str, Any]:
    return {
        "id": gap_id,
        "severity": severity,
        "rationale": rationale,
        "needed_evidence": _needed_evidence(gap_id),
        "follow_up_queries": follow_up_queries,
        "experiment_implication": experiment_implication,
        "recommended_tool": _GAP_RECOMMENDED_TOOL.get(gap_id),
    }


def _needed_evidence(gap_id: str) -> str:
    labels = {
        "insufficient_literature_depth": "article-level literature support with citations",
        "missing_target_disease_association": "target-disease association from OpenTargets or equivalent public knowledge graph",
        "missing_intervention_specific_evidence": "compound/intervention identity, potency, selectivity, exposure, and mechanism",
        "missing_safety_evidence": "safety, off-target, toxicity, and contraindication evidence",
        "missing_cell_context_evidence": "cell-type, transcriptomic, perturbation, or disease-state evidence",
        "missing_falsification_search": "contradictory, null, failed, or negative evidence",
        "claim_graph_evidence_gap": "claim-specific supporting evidence or explicit claim softening",
        "reviewer_high_severity_concern": "direct evidence resolving reviewer-identified overclaim or contradiction",
        "evidence_relevance_noise": "higher-precision retrieval with irrelevant records filtered from the claim boundary",
    }
    return labels.get(gap_id, "additional evidence")


def _recommended_followups(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    followups = []
    for gap in gaps[:5]:
        for query in gap.get("follow_up_queries", [])[:2]:
            followups.append({"gap_id": gap["id"], "query": query, "priority": gap["severity"]})
    return followups[:8]


def _next_action(readiness_tier: str, gaps: list[dict[str, Any]]) -> dict[str, Any]:
    if not gaps:
        return {"action": "prepare_validation_plan", "rationale": "No major deterministic evidence gaps were detected."}
    high_gaps = [gap for gap in gaps if gap["severity"] == "high"]
    if high_gaps:
        return {
            "action": "repair_high_severity_evidence_gaps",
            "rationale": high_gaps[0]["rationale"],
            "first_gap": high_gaps[0]["id"],
        }
    return {
        "action": "run_falsification_and_depth_pass",
        "rationale": f"Readiness is {readiness_tier}; remaining gaps should be challenged before confidence increases.",
        "first_gap": gaps[0]["id"],
    }


def _readiness_tier(score: int, gaps: list[dict[str, Any]]) -> str:
    if any(gap["severity"] == "high" for gap in gaps):
        return "hypothesis_only"
    if score >= 82:
        return "validation_ready"
    if score >= 65:
        return "experiment_ready_with_gaps"
    return "hypothesis_only"


def _readiness_rationale(tier: str, gaps: list[dict[str, Any]]) -> str:
    if not gaps:
        return "No major deterministic evidence gaps were detected."
    leading = gaps[0]
    return f"{tier}: blocked mainly by {leading['id']} ({leading['severity']})."


def _experiment_gap_matches(experiment: dict[str, Any], gap_ids: list[str]) -> list[str]:
    text = " ".join(str(value) for value in experiment.values()).lower()
    matches = []
    gap_terms = {
        "insufficient_literature_depth": ["literature", "pubmed", "citation", "evidence"],
        "missing_target_disease_association": ["target-disease", "opentargets", "association"],
        "missing_intervention_specific_evidence": [
            "intervention",
            "compound",
            "potency",
            "selectivity",
            "admet",
            "clinical-precedence",
            "response",
            "patient-selection",
        ],
        "missing_safety_evidence": ["safety", "toxicity", "off-target", "admet", "adverse", "infection"],
        "missing_cell_context_evidence": ["cell", "single-cell", "transcriptomic", "phenotype", "assay"],
        "missing_falsification_search": ["falsification", "contradict", "failed", "null"],
        "claim_graph_evidence_gap": ["claim", "causal", "mechanism"],
    }
    for gap_id in gap_ids:
        if any(term in text for term in gap_terms.get(gap_id, [])):
            matches.append(gap_id)
    return matches


def _annotate_experiment(
    experiment: dict[str, Any],
    addresses: list[str],
    gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    severity_bonus = sum(SEVERITY_PRIORITY[gap["severity"]] for gap in gaps if gap["id"] in addresses)
    gain = _normalized_gain(experiment.get("expected_information_gain", "medium"))
    feasibility = FEASIBILITY_FACTOR.get(str(experiment.get("feasibility", "medium")).lower(), 1.0)
    cost = COST_FACTOR.get(str(experiment.get("cost", "medium")).lower(), 1.45)
    priority = min(100, round((35 + severity_bonus) * gain * feasibility / cost))
    return {
        **experiment,
        "addresses_gaps": addresses,
        "priority_score": priority,
        "decision_gate": _decision_gate(addresses),
        "success_criteria": _success_criteria(addresses),
        "failure_modes": _failure_modes(addresses),
        "why_next": _why_next(addresses),
    }


def _gap_driven_experiments(gaps: list[dict[str, Any]], existing_gap_ids: set[str]) -> list[dict[str, Any]]:
    generated = []
    for gap in gaps:
        if gap["id"] in existing_gap_ids:
            continue
        generated.append(
            _annotate_experiment(
                {
                    "name": _gap_experiment_name(gap),
                    "type": "computational",
                    "cost": "low-medium",
                    "feasibility": "high" if gap["id"] != "missing_cell_context_evidence" else "medium",
                    "expected_information_gain": "high",
                },
                [gap["id"]],
                gaps,
            )
        )
    return generated


def _gap_experiment_name(gap: dict[str, Any]) -> str:
    names = {
        "insufficient_literature_depth": "Run article-level literature grounding and citation relevance audit",
        "missing_target_disease_association": "Triangulate target-disease association across public knowledge graph and literature evidence",
        "missing_intervention_specific_evidence": "Collect intervention-specific potency, selectivity, exposure, and mechanism evidence",
        "missing_safety_evidence": "Run safety and off-target evidence triage before any efficacy claim",
        "missing_cell_context_evidence": "Validate disease-cell-context relevance with transcriptomic or perturbation evidence",
        "missing_falsification_search": "Run falsification search for contradictory, null, or failed evidence",
        "claim_graph_evidence_gap": "Repair unsupported claim links or soften claim boundaries",
    }
    return names.get(gap["id"], f"Resolve evidence gap: {gap['id']}")


def _decision_gate(addresses: list[str]) -> str:
    if not addresses:
        return "Proceed only if the result adds evidence not already represented in the run."
    return "Advance the hypothesis only if this resolves: " + ", ".join(addresses[:3])


def _success_criteria(addresses: list[str]) -> list[str]:
    criteria = []
    for gap_id in addresses:
        criteria.append(_needed_evidence(gap_id))
    return criteria or ["New evidence changes the confidence, claim boundary, or next experiment."]


def _failure_modes(addresses: list[str]) -> list[str]:
    modes = []
    if "missing_falsification_search" in addresses:
        modes.append("Negative evidence contradicts the mechanism or disease relevance.")
    if "missing_safety_evidence" in addresses:
        modes.append("Safety or off-target evidence makes the candidate unsuitable for prioritization.")
    if "missing_cell_context_evidence" in addresses:
        modes.append("The mechanism is not active in the relevant disease cell state.")
    if "missing_target_disease_association" in addresses:
        modes.append("Public association evidence does not support target-disease relevance.")
    return modes or ["The result is indirect, non-specific, or does not change the claim boundary."]


def _why_next(addresses: list[str]) -> str:
    if not addresses:
        return (
            "Decision-grade validation retained for residual uncertainty after deterministic gap triage; "
            "the experiment should still specify controls, failure criteria, and how confidence changes."
        )
    return "Chosen because it directly addresses the current strategy gap(s): " + ", ".join(addresses[:3])


def _normalized_gain(value: Any) -> float:
    key = str(value or "medium").lower().replace(" ", "_").replace("-", "_")
    if key == "very_high":
        return GAIN_FACTOR["very_high"]
    if "high" in key:
        return GAIN_FACTOR["high"]
    if "low" in key:
        return GAIN_FACTOR["low"]
    return GAIN_FACTOR["medium"]


def _any_evidence_text(evidence: list[dict[str, Any]], terms: list[str]) -> bool:
    chunks = []
    for item in evidence:
        chunks.extend(
            [
                str(item.get("source", "")),
                str(item.get("text", "")),
                str(item.get("structured", "")),
            ]
        )
    text = " ".join(chunks).lower()
    return any(re.search(rf"\b{re.escape(term.lower())}\b", text) for term in terms)
