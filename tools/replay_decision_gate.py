from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from app.services.abstention_policy import evaluate_abstention_policy
from app.services.actionability_assessor import assess_actionability
from app.services.biotruth_critic import evaluate_hypothesis
from app.services.contradiction_detector import detect_contradictions
from app.services.evidence_hierarchy import summarize_evidence_hierarchy


DEFAULT_CANARY_DIR = Path(
    "outputs/runpod_exports/canary_extracted/"
    "autoscientist_biotruth_4_case_real_canary_20260525/benchmark_run"
)


def run_gate(
    *,
    artifact_dirs: list[Path],
    include_synthetic: bool,
    min_accuracy: float,
) -> dict[str, Any]:
    rows = []
    warnings = []
    for artifact_dir in artifact_dirs:
        if not artifact_dir.exists():
            warnings.append(f"Artifact directory not found: {artifact_dir}")
            continue
        rows.extend(evaluate_artifact_dir(artifact_dir))
    if include_synthetic:
        rows.extend(evaluate_synthetic_cases())

    total = len(rows)
    matches = sum(1 for row in rows if row["matched"])
    accuracy = round(matches / total, 4) if total else 0.0
    failures = [row for row in rows if not row["matched"]]
    coverage = coverage_summary(rows)
    acceptance_failures = []
    if not rows:
        acceptance_failures.append("No replay rows were evaluated.")
    if accuracy < min_accuracy:
        acceptance_failures.append(f"Decision accuracy {accuracy} is below threshold {min_accuracy}.")
    missing_expected = sorted(
        {
            "support_allowed",
            "tentative_only",
            "conflicting",
            "abstain",
        }
        - set(coverage["by_expected_decision"])
    )
    if include_synthetic and missing_expected:
        acceptance_failures.append(f"Synthetic gate is missing expected decisions: {missing_expected}.")

    return {
        "schema": "autosci.decision_replay_gate.v0.1",
        "created_at_unix": int(time.time()),
        "artifact_dirs": [str(path) for path in artifact_dirs],
        "include_synthetic": include_synthetic,
        "min_accuracy": min_accuracy,
        "case_count": total,
        "matches": matches,
        "accuracy": accuracy,
        "status": "passed" if not acceptance_failures else "failed",
        "acceptance_failures": acceptance_failures,
        "warnings": warnings,
        "coverage": coverage,
        "failures": failures,
        "rows": rows,
    }


def evaluate_artifact_dir(artifact_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(artifact_dir.glob("*__full.json")):
        payload = load_json(path)
        if payload.get("schema") != "autosci.benchmark_task_result.v0.1":
            continue
        task = payload.get("task") or {}
        expected = str(task.get("expected_decision") or "").strip()
        if not expected:
            continue
        report = payload.get("report") if isinstance(payload.get("report"), dict) else {}
        row = evaluate_case(
            case_id=str(task.get("case_id") or task.get("id") or path.stem),
            source="artifact",
            expected_decision=expected,
            task=task,
            evidence=list(report.get("evidence") or []),
            tool_calls=list(payload.get("tool_calls") or []),
            hypothesis=payload.get("hypothesis") or report.get("hypothesis") or {},
            previous_decision=previous_decision(payload),
            artifact_path=path,
        )
        rows.append(row)
    return rows


def evaluate_synthetic_cases() -> list[dict[str, Any]]:
    return [
        evaluate_case(**case)
        for case in [
            strong_disease_specific_case(),
            tentative_target_level_case(),
            conflicting_negative_translation_case(),
            insufficient_grounding_case(),
            safety_limited_but_supportable_case(),
            query_placeholder_case(),
        ]
    ]


def evaluate_case(
    *,
    case_id: str,
    source: str,
    expected_decision: str,
    task: dict[str, Any],
    evidence: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
    hypothesis: dict[str, Any],
    previous_decision: str | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    hierarchy = summarize_evidence_hierarchy(evidence)
    contradictions = detect_contradictions(task=task, evidence=evidence, tool_calls=tool_calls)
    actionability = assess_actionability(
        task=task,
        evidence=evidence,
        evidence_hierarchy=hierarchy,
        contradiction_analysis=contradictions,
    )
    critic = evaluate_hypothesis(
        task=task,
        hypothesis=hypothesis,
        evidence=evidence,
        tool_calls=tool_calls,
    )
    abstention = evaluate_abstention_policy(
        critic=critic,
        evidence_hierarchy=hierarchy,
        contradiction_analysis=contradictions,
        actionability_profile=actionability,
    )
    observed = str(abstention.get("decision") or "")
    return {
        "case_id": case_id,
        "source": source,
        "artifact_path": str(artifact_path) if artifact_path else None,
        "gene_symbol": task.get("gene_symbol"),
        "disease_name": task.get("disease_name"),
        "expected_decision": expected_decision,
        "previous_decision": previous_decision,
        "observed_decision": observed,
        "matched": observed == expected_decision,
        "critic_verdict": critic.get("verdict"),
        "critic_weighted_score": critic.get("weighted_score"),
        "actionability_level": actionability.get("level"),
        "actionability_recommended_decision": actionability.get("recommended_decision"),
        "negative_signal_count": actionability.get("profile", {}).get("negative_signal_count"),
        "positive_intervention_count": actionability.get("profile", {}).get(
            "disease_specific_positive_intervention_count"
        ),
        "safety_signal_count": actionability.get("profile", {}).get("safety_signal_count"),
        "query_only_clinical_context_count": actionability.get("profile", {}).get(
            "query_only_clinical_context_count"
        ),
        "query_only_counterevidence_context_count": actionability.get("profile", {}).get(
            "query_only_counterevidence_context_count"
        ),
        "high_tier_evidence_count": hierarchy.get("high_tier_evidence_count"),
        "contradiction_finding_count": contradictions.get("finding_count"),
        "contradiction_categories": contradictions.get("categories", []),
        "abstention_reasons": abstention.get("reasons", []),
    }


def previous_decision(payload: dict[str, Any]) -> str | None:
    report = payload.get("report") if isinstance(payload.get("report"), dict) else {}
    abstention = payload.get("abstention_policy") or report.get("abstention_policy") or {}
    if isinstance(abstention, dict):
        return abstention.get("decision")
    return None


def coverage_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "by_source": count_by(rows, "source"),
        "by_expected_decision": count_by(rows, "expected_decision"),
        "by_observed_decision": count_by(rows, "observed_decision"),
        "by_actionability_level": count_by(rows, "actionability_level"),
        "with_negative_signals": sum(1 for row in rows if int(row.get("negative_signal_count") or 0) > 0),
        "with_safety_signals": sum(1 for row in rows if int(row.get("safety_signal_count") or 0) > 0),
        "with_query_context": sum(
            1
            for row in rows
            if int(row.get("query_only_clinical_context_count") or 0) > 0
            or int(row.get("query_only_counterevidence_context_count") or 0) > 0
        ),
    }


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def strong_disease_specific_case() -> dict[str, Any]:
    return {
        "case_id": "synthetic_strong_disease_specific",
        "source": "synthetic",
        "expected_decision": "support_allowed",
        "task": {"gene_symbol": "TARGETA", "disease_name": "immune arthritis"},
        "hypothesis": {
            "title": "TARGETA immune arthritis",
            "hypothesis": (
                "TARGETA inhibition is supported by disease-specific clinical efficacy, "
                "human biology, mechanism, and explicit safety limits."
            ),
            "confidence": 0.8,
        },
        "evidence": [
            {
                "source": "ClinicalTrials.gov",
                "text": (
                    "A completed phase 3 interventional trial reported effective TARGETA "
                    "antibody treatment with improved response in immune arthritis."
                ),
                "evidence_type": "clinical_precedence",
            },
            {
                "source": "PubMed",
                "text": "Human patient cohorts link TARGETA signaling to immune arthritis mechanism.",
                "evidence_type": "literature",
            },
        ],
        "tool_calls": [
            {
                "tool_name": "clinical_trials_search_tool",
                "input": {"query": "TARGETA immune arthritis failed trial adverse toxicity"},
                "status": "success",
            }
        ],
    }


def tentative_target_level_case() -> dict[str, Any]:
    return {
        "case_id": "synthetic_target_level_only",
        "source": "synthetic",
        "expected_decision": "tentative_only",
        "task": {"gene_symbol": "TARGETB", "disease_name": "intestinal disease"},
        "hypothesis": {
            "title": "TARGETB intestinal disease",
            "hypothesis": "TARGETB has genetic support but target-level tractability is not disease efficacy.",
            "confidence": 0.55,
        },
        "evidence": [
            {
                "source": "Open Targets target tractability",
                "text": (
                    "Open Targets target metadata for TARGETB reports clinical or tractability precedence: "
                    "Approved Drug (SM). This is target-level precedence and must be separated from "
                    "disease-specific efficacy claims for intestinal disease."
                ),
                "evidence_type": "target_metadata",
            },
            {
                "source": "PubMed",
                "text": "Human genetic variant evidence links TARGETB to intestinal disease susceptibility.",
                "evidence_type": "literature",
            },
        ],
        "tool_calls": [{"tool_name": "opentargets_target_tractability", "status": "success"}],
    }


def conflicting_negative_translation_case() -> dict[str, Any]:
    return {
        "case_id": "synthetic_negative_translation",
        "source": "synthetic",
        "expected_decision": "conflicting",
        "task": {"gene_symbol": "TARGETC", "disease_name": "neuro disease"},
        "hypothesis": {
            "title": "TARGETC neuro disease",
            "hypothesis": "TARGETC has mechanistic rationale but clinical translation is unresolved.",
            "confidence": 0.45,
        },
        "evidence": [
            {
                "source": "PubMed",
                "text": "TARGETC therapy showed no benefit in neuro disease and did not improve endpoints.",
                "evidence_type": "clinical_precedence",
            },
            {
                "source": "PubMed",
                "text": "A controversial TARGETC program reported misclassification concerns in neuro disease.",
                "evidence_type": "literature",
            },
        ],
        "tool_calls": [{"tool_name": "pubmed_literature_search_tool", "status": "success"}],
    }


def insufficient_grounding_case() -> dict[str, Any]:
    return {
        "case_id": "synthetic_insufficient_grounding",
        "source": "synthetic",
        "expected_decision": "abstain",
        "task": {"gene_symbol": "TARGETD", "disease_name": "kidney disease"},
        "hypothesis": {"title": "TARGETD kidney disease", "hypothesis": "TARGETD may be relevant."},
        "evidence": [{"source": "PubMed", "text": "Unrelated oncology pathway review."}],
        "tool_calls": [{"tool_name": "pubmed_literature_search_tool", "status": "success"}],
    }


def safety_limited_but_supportable_case() -> dict[str, Any]:
    return {
        "case_id": "synthetic_safety_limited_supportable",
        "source": "synthetic",
        "expected_decision": "support_allowed",
        "task": {"gene_symbol": "TARGETE", "disease_name": "solid tumor"},
        "hypothesis": {
            "title": "TARGETE solid tumor",
            "hypothesis": (
                "TARGETE inhibition has disease-specific clinical activity, with explicit safety caveats."
            ),
            "confidence": 0.72,
        },
        "evidence": [
            {
                "source": "PubMed",
                "text": "TARGETE inhibitor therapy improved response in solid tumor clinical trial cohorts.",
                "evidence_type": "clinical_precedence",
            },
            {
                "source": "ClinicalTrials.gov",
                "text": "A phase 2 interventional study reported effective TARGETE treatment in solid tumor.",
                "evidence_type": "clinical_precedence",
            },
            {
                "source": "openFDA adverse events",
                "text": (
                    "openFDA returned adverse-event reports for TARGETE inhibitor; "
                    "these are safety signals, not incidence rates or causal proof."
                ),
                "evidence_type": "safety_context",
            },
        ],
        "tool_calls": [{"tool_name": "openfda_adverse_event_tool", "status": "success"}],
    }


def query_placeholder_case() -> dict[str, Any]:
    return {
        "case_id": "synthetic_query_placeholder",
        "source": "synthetic",
        "expected_decision": "tentative_only",
        "task": {"gene_symbol": "TARGETF", "disease_name": "rare disease"},
        "hypothesis": {
            "title": "TARGETF rare disease",
            "hypothesis": "TARGETF has early mechanism evidence, but clinical evidence is not established.",
            "confidence": 0.5,
        },
        "evidence": [
            {
                "source": "PubMed: TARGETF rare disease failed trial not associated",
                "text": (
                    "PubMed returned live literature search results for TARGETF rare disease "
                    "failed trial not associated."
                ),
                "evidence_type": "literature",
            },
            {
                "source": "PubMed",
                "text": "TARGETF rare disease pathway mechanism evidence requires validation.",
                "evidence_type": "literature",
            },
        ],
        "tool_calls": [{"tool_name": "pubmed_literature_search_tool", "status": "success"}],
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_outputs(gate: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"decision_replay_gate_{gate['created_at_unix']}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(gate, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(gate), encoding="utf-8")
    return {"gate_json": str(json_path), "gate_markdown": str(md_path)}


def render_markdown(gate: dict[str, Any]) -> str:
    lines = [
        "# AutoScientist Decision Replay Gate",
        "",
        f"- Status: `{gate['status']}`",
        f"- Cases: `{gate['case_count']}`",
        f"- Accuracy: `{gate['accuracy']}`",
        f"- Threshold: `{gate['min_accuracy']}`",
        "",
        "## Acceptance Failures",
        "",
    ]
    lines.extend(f"- {failure}" for failure in gate["acceptance_failures"])
    if not gate["acceptance_failures"]:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Coverage",
            "",
            f"- Expected decisions: `{json.dumps(gate['coverage']['by_expected_decision'])}`",
            f"- Observed decisions: `{json.dumps(gate['coverage']['by_observed_decision'])}`",
            f"- Actionability levels: `{json.dumps(gate['coverage']['by_actionability_level'])}`",
            f"- Cases with negative signals: `{gate['coverage']['with_negative_signals']}`",
            f"- Cases with safety signals: `{gate['coverage']['with_safety_signals']}`",
            f"- Cases with query-context controls: `{gate['coverage']['with_query_context']}`",
            "",
            "## Rows",
            "",
            "| Case | Source | Expected | Observed | Match | Critic | Actionability | Notes |",
            "| --- | --- | --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for row in gate["rows"]:
        notes = []
        if row.get("previous_decision") and row["previous_decision"] != row["observed_decision"]:
            notes.append(f"previous={row['previous_decision']}")
        if row.get("negative_signal_count"):
            notes.append(f"negative={row['negative_signal_count']}")
        if row.get("safety_signal_count"):
            notes.append(f"safety={row['safety_signal_count']}")
        lines.append(
            f"| {row['case_id']} | {row['source']} | {row['expected_decision']} | "
            f"{row['observed_decision']} | {row['matched']} | {row['critic_verdict']} | "
            f"{row['actionability_level']}:{row['actionability_recommended_decision']} | "
            f"{'; '.join(notes)} |"
        )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay saved benchmark decisions through current gates.")
    parser.add_argument(
        "--artifact-dir",
        action="append",
        default=[],
        help="Benchmark artifact directory containing *__full.json files. Can be repeated.",
    )
    parser.add_argument("--skip-default-canary", action="store_true")
    parser.add_argument("--no-synthetic", action="store_true")
    parser.add_argument("--min-accuracy", type=float, default=1.0)
    parser.add_argument("--output-dir", default="outputs/local_quality_gates")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dirs = [Path(item) for item in args.artifact_dir]
    if not args.skip_default_canary:
        artifact_dirs.append(DEFAULT_CANARY_DIR)
    gate = run_gate(
        artifact_dirs=artifact_dirs,
        include_synthetic=not args.no_synthetic,
        min_accuracy=args.min_accuracy,
    )
    outputs = write_outputs(gate, Path(args.output_dir))
    print(json.dumps({**outputs, "status": gate["status"], "accuracy": gate["accuracy"]}, indent=2))
    return 0 if gate["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
