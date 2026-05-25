from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def analyze_benchmark_dir(bench_dir: Path) -> dict[str, Any]:
    if not bench_dir.exists():
        raise FileNotFoundError(f"Benchmark directory not found: {bench_dir}")
    summary = load_json(bench_dir / "benchmark_summary.json")
    task_results = load_task_results(bench_dir)
    full_results = [item for item in task_results if item.get("ablation") == "full"]
    by_ablation = group_by(task_results, "ablation")
    return {
        "schema": "autosci.benchmark_analysis.v0.1",
        "created_at_unix": int(time.time()),
        "bench_dir": str(bench_dir),
        "summary_status": summary.get("status"),
        "realness_gates": summary.get("realness_gates", {}),
        "task_count": summary.get("task_count"),
        "result_count": summary.get("result_count"),
        "full_runtime": summarize_full_runtime(full_results),
        "ablation_comparison": compare_ablations(by_ablation),
        "decision_calibration": decision_calibration(task_results),
        "integration_coverage": integration_coverage(full_results),
        "evidence_profile": evidence_profile(full_results),
        "state_graph": summary.get("state_graph", {}),
        "policy": policy_profile(summary),
        "claims": publishable_claims(summary, full_results, by_ablation),
        "limitations": limitations(summary, full_results, by_ablation),
    }


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_task_results(bench_dir: Path) -> list[dict[str, Any]]:
    results = []
    for path in sorted(bench_dir.glob("*__*.json")):
        if path.name in {"benchmark_summary.json", "benchmark_tasks.json", "scistate_graph.json"}:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") == "autosci.benchmark_task_result.v0.1":
            data["_path"] = str(path)
            results.append(data)
    return results


def group_by(items: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[str(item.get(key) or "unknown")].append(item)
    return dict(grouped)


def summarize_full_runtime(results: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [int(item.get("value_assessment", {}).get("score") or 0) for item in results]
    completed = [item for item in results if item.get("status") == "completed"]
    return {
        "runs": len(results),
        "completed": len(completed),
        "completion_rate": round(len(completed) / len(results), 4) if results else 0.0,
        "mean_score": round(statistics.mean(scores), 2) if scores else 0.0,
        "min_score": min(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "mean_evidence_count": round(statistics.mean([int(item.get("evidence_count") or 0) for item in results]), 2)
        if results
        else 0.0,
        "mean_tool_calls": round(statistics.mean([len(item.get("tool_calls") or []) for item in results]), 2)
        if results
        else 0.0,
    }


def compare_ablations(by_ablation: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    full = score_mean(by_ablation.get("full", []))
    full_tool_calls = mean_tool_calls(by_ablation.get("full", []))
    full_evidence = mean_evidence_count(by_ablation.get("full", []))
    full_public_calls = mean_public_biomedical_calls(by_ablation.get("full", []))
    full_tooluniverse_calls = mean_tooluniverse_calls(by_ablation.get("full", []))
    comparisons = {}
    for name, results in sorted(by_ablation.items()):
        if name == "full":
            continue
        comparisons[name] = {
            "runs": len(results),
            "mean_score": score_mean(results),
            "decision_accuracy": decision_calibration(results)["overall"]["accuracy"],
            "score_delta_full_minus_ablation": round(full - score_mean(results), 2),
            "mean_tool_calls": mean_tool_calls(results),
            "tool_call_delta_full_minus_ablation": round(full_tool_calls - mean_tool_calls(results), 2),
            "mean_evidence_count": mean_evidence_count(results),
            "evidence_delta_full_minus_ablation": round(full_evidence - mean_evidence_count(results), 2),
            "mean_public_biomedical_calls": mean_public_biomedical_calls(results),
            "public_biomedical_call_delta_full_minus_ablation": round(
                full_public_calls - mean_public_biomedical_calls(results),
                2,
            ),
            "mean_tooluniverse_calls": mean_tooluniverse_calls(results),
            "tooluniverse_call_delta_full_minus_ablation": round(
                full_tooluniverse_calls - mean_tooluniverse_calls(results),
                2,
            ),
            "replay_runs": sum(1 for item in results if item.get("replay", {}).get("available")),
            "controller_runs": sum(1 for item in results if item.get("sciflow_policy", {}).get("status") == "success"),
            "controller_applied_runs": sum(1 for item in results if controller_impact(item).get("applied")),
        }
    return comparisons


def decision_calibration(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_ablation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_expected: dict[str, list[dict[str, Any]]] = defaultdict(list)
    records = []
    mismatches = []
    for item in results:
        expected = str(item.get("task", {}).get("expected_decision") or "").strip()
        if not expected:
            continue
        observed = observed_decision(item)
        actionability = observed_actionability_decision(item)
        record = {
            "task_id": item.get("task", {}).get("id"),
            "run_id": item.get("run_id"),
            "ablation": item.get("ablation"),
            "gold_label": item.get("task", {}).get("gold_label"),
            "expected": expected,
            "observed": observed,
            "actionability": actionability,
            "matched": observed == expected,
            "artifact_path": item.get("_path") or item.get("artifact_path"),
        }
        records.append(record)
        by_ablation[str(item.get("ablation") or "unknown")].append(record)
        by_expected[expected].append(record)
        if not record["matched"]:
            mismatches.append(record)
    return {
        "overall": summarize_decision_records(records),
        "by_ablation": {key: summarize_decision_records(value) for key, value in sorted(by_ablation.items())},
        "by_expected_decision": {key: summarize_decision_records(value) for key, value in sorted(by_expected.items())},
        "mismatches": mismatches[:50],
    }


def summarize_decision_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"count": 0, "matches": 0, "accuracy": None}
    matches = sum(1 for item in records if item.get("matched"))
    return {
        "count": len(records),
        "matches": matches,
        "accuracy": round(matches / len(records), 4),
        "observed_decisions": dict(sorted(Counter(str(item.get("observed") or "unknown") for item in records).items())),
    }


def observed_decision(item: dict[str, Any]) -> str:
    report = item.get("report", {}) if isinstance(item.get("report"), dict) else {}
    abstention = item.get("abstention_policy") or report.get("abstention_policy") or {}
    if isinstance(abstention, dict) and abstention.get("decision"):
        return str(abstention.get("decision"))
    critic = item.get("biotruth_critic") or report.get("biotruth_critic") or {}
    verdict = str(critic.get("verdict") or "") if isinstance(critic, dict) else ""
    return {
        "support": "support_allowed",
        "weak_support": "tentative_only",
        "conflicting": "conflicting",
        "abstain": "abstain",
    }.get(verdict, "")


def observed_actionability_decision(item: dict[str, Any]) -> str:
    report = item.get("report", {}) if isinstance(item.get("report"), dict) else {}
    actionability = report.get("actionability_profile") or {}
    if isinstance(actionability, dict):
        return str(actionability.get("recommended_decision") or "")
    return ""


def score_mean(results: list[dict[str, Any]]) -> float:
    scores = [int(item.get("value_assessment", {}).get("score") or 0) for item in results]
    return round(statistics.mean(scores), 2) if scores else 0.0


def mean_tool_calls(results: list[dict[str, Any]]) -> float:
    return round(statistics.mean([len(item.get("tool_calls") or []) for item in results]), 2) if results else 0.0


def controller_impact(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("value_assessment", {}).get("controller_impact", {}) or item.get("sciflow_application", {}) or {}


def mean_evidence_count(results: list[dict[str, Any]]) -> float:
    return round(statistics.mean([int(item.get("evidence_count") or 0) for item in results]), 2) if results else 0.0


def mean_public_biomedical_calls(results: list[dict[str, Any]]) -> float:
    return round(
        statistics.mean(
            [
                sum(1 for call in item.get("tool_calls") or [] if call.get("tool_source") == "live_public_biomedical")
                for item in results
            ]
        ),
        2,
    ) if results else 0.0


def mean_tooluniverse_calls(results: list[dict[str, Any]]) -> float:
    return round(
        statistics.mean(
            [
                sum(1 for call in item.get("tool_calls") or [] if call.get("tool_source") == "tooluniverse")
                for item in results
            ]
        ),
        2,
    ) if results else 0.0


def integration_coverage(results: list[dict[str, Any]]) -> dict[str, Any]:
    names = ["public_biomedical", "tooluniverse", "qworld", "local_board"]
    coverage = {}
    for name in names:
        coverage[name] = {
            "executed_runs": sum(1 for item in results if item.get("integrations", {}).get(name, {}).get("executed")),
            "total_runs": len(results),
        }
        coverage[name]["coverage_rate"] = (
            round(coverage[name]["executed_runs"] / len(results), 4) if results else 0.0
        )
    coverage["sciflow_policy"] = {
        "executed_runs": sum(1 for item in results if item.get("sciflow_policy", {}).get("status") == "success"),
        "total_runs": len(results),
        "coverage_rate": round(
            sum(1 for item in results if item.get("sciflow_policy", {}).get("status") == "success") / len(results),
            4,
        )
        if results
        else 0.0,
    }
    coverage["memory_replay"] = {
        "executed_runs": sum(1 for item in results if item.get("replay", {}).get("available")),
        "total_runs": len(results),
        "coverage_rate": round(sum(1 for item in results if item.get("replay", {}).get("available")) / len(results), 4)
        if results
        else 0.0,
    }
    return coverage


def evidence_profile(results: list[dict[str, Any]]) -> dict[str, Any]:
    source_counts: Counter[str] = Counter()
    tool_counts: Counter[str] = Counter()
    support_labels: Counter[str] = Counter()
    for item in results:
        for call in item.get("tool_calls") or []:
            tool_counts[str(call.get("tool_name") or "unknown")] += 1
        for evidence in item.get("report", {}).get("evidence", []) if isinstance(item.get("report"), dict) else []:
            source_counts[str(evidence.get("source") or "unknown")] += 1
            support_labels[str(evidence.get("support_label") or evidence.get("score", {}).get("label") or "unknown")] += 1
    return {
        "top_tools": tool_counts.most_common(20),
        "top_evidence_sources": source_counts.most_common(20),
        "support_labels": support_labels.most_common(20),
    }


def policy_profile(summary: dict[str, Any]) -> dict[str, Any]:
    neural = summary.get("neural_policy") or {}
    transparent = summary.get("trained_policy") or {}
    return {
        "transparent_policy": {
            "artifact_path": transparent.get("artifact_path"),
            "num_examples": (transparent.get("training_summary") or {}).get("num_examples"),
            "metrics": transparent.get("metrics"),
        },
        "neural_policy": {
            "artifact_path": neural.get("artifact_path"),
            "num_examples": (neural.get("metrics") or {}).get("num_examples"),
            "holdout_top1": (neural.get("metrics") or {}).get("top1_holdout_accuracy"),
            "holdout_top3": (neural.get("metrics") or {}).get("top3_holdout_accuracy"),
            "holdout_mrr": (neural.get("metrics") or {}).get("mrr_holdout"),
            "majority_baseline_top1": (neural.get("metrics") or {}).get("majority_top1_holdout_accuracy"),
        },
    }


def publishable_claims(
    summary: dict[str, Any],
    full_results: list[dict[str, Any]],
    by_ablation: dict[str, list[dict[str, Any]]],
) -> list[str]:
    claims = []
    gates = summary.get("realness_gates", {})
    if gates.get("passed"):
        claims.append("Strict realness gates passed for the benchmark configuration.")
    full = summarize_full_runtime(full_results)
    if full["completion_rate"] == 1.0:
        claims.append("All full-runtime benchmark tasks completed.")
    coverage = integration_coverage(full_results)
    if coverage.get("public_biomedical", {}).get("coverage_rate") == 1.0:
        claims.append("Every full-runtime task executed public biomedical tools.")
    if coverage.get("memory_replay", {}).get("coverage_rate") == 1.0:
        claims.append("Every full-runtime task produced replayable memory/provenance.")
    for ablation, comparison in compare_ablations(by_ablation).items():
        if comparison["score_delta_full_minus_ablation"] > 0:
            claims.append(f"Full runtime outscored `{ablation}` by {comparison['score_delta_full_minus_ablation']} points on average.")
        if ablation == "no_sciflow" and comparison.get("controller_applied_runs") == 0:
            if comparison.get("evidence_delta_full_minus_ablation", 0) > 0 or comparison.get(
                "tool_call_delta_full_minus_ablation",
                0,
            ) > 0:
                claims.append(
                    "SciFlow Policy changed execution behavior versus `no_sciflow`: "
                    f"+{comparison.get('evidence_delta_full_minus_ablation')} mean evidence items and "
                    f"+{comparison.get('tool_call_delta_full_minus_ablation')} mean tool calls."
                )
    return claims


def limitations(
    summary: dict[str, Any],
    full_results: list[dict[str, Any]],
    by_ablation: dict[str, list[dict[str, Any]]],
) -> list[str]:
    items = []
    gates = summary.get("realness_gates", {})
    if gates and not gates.get("passed"):
        items.append("Realness gates did not pass; inspect gate failures before sharing claims.")
    if "no_memory" not in by_ablation:
        items.append("No-memory ablation was not present, so persistent-memory value is not quantified in this run.")
    if "no_public_tools" not in by_ablation:
        items.append("No-public-tools ablation was not present, so grounding value is not quantified in this run.")
    no_sciflow = compare_ablations(by_ablation).get("no_sciflow")
    if no_sciflow and no_sciflow.get("evidence_delta_full_minus_ablation", 0) <= 0 and no_sciflow.get(
        "tool_call_delta_full_minus_ablation",
        0,
    ) <= 0:
        items.append("SciFlow Policy did not create an operational retrieval-depth delta in this run.")
    items.append("Benchmark scores are integration/provenance scores, not expert biological truth labels.")
    return items


def render_markdown(analysis: dict[str, Any]) -> str:
    full = analysis["full_runtime"]
    lines = [
        "# AutoScientist Benchmark Analysis",
        "",
        f"Benchmark directory: `{analysis['bench_dir']}`",
        f"Summary status: `{analysis['summary_status']}`",
        "",
        "## Full Runtime",
        "",
        f"- Runs: `{full['runs']}`",
        f"- Completed: `{full['completed']}`",
        f"- Completion rate: `{full['completion_rate']}`",
        f"- Mean score: `{full['mean_score']}`",
        f"- Mean evidence count: `{full['mean_evidence_count']}`",
        f"- Mean tool calls: `{full['mean_tool_calls']}`",
        "",
        "## Realness Gates",
        "",
        f"- Passed: `{analysis.get('realness_gates', {}).get('passed')}`",
    ]
    for failure in analysis.get("realness_gates", {}).get("failures", []):
        lines.append(f"- Failure: {failure}")
    lines.extend(["", "## Integration Coverage", "", "| Integration | Runs | Coverage |", "| --- | ---: | ---: |"])
    for name, item in analysis["integration_coverage"].items():
        lines.append(f"| {name} | {item['executed_runs']}/{item['total_runs']} | {item['coverage_rate']} |")
    calibration = analysis.get("decision_calibration", {})
    lines.extend(
        [
            "",
            "## Scientific Decision Calibration",
            "",
            f"- Overall accuracy: `{calibration.get('overall', {}).get('accuracy')}`",
            f"- Evaluable decisions: `{calibration.get('overall', {}).get('count')}`",
            "",
            "| Expected decision | Count | Matches | Accuracy | Observed decisions |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for name, item in calibration.get("by_expected_decision", {}).items():
        lines.append(
            f"| {name} | {item.get('count')} | {item.get('matches')} | {item.get('accuracy')} | "
            f"`{json.dumps(item.get('observed_decisions', {}), default=str)}` |"
        )
    lines.extend(
        [
            "",
            "## Ablation Comparison",
            "",
            "| Ablation | Runs | Mean score | Decision accuracy | Score delta | Evidence delta | Tool-call delta | Replay runs | Controller advice | Controller applied |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name, item in analysis["ablation_comparison"].items():
        lines.append(
            f"| {name} | {item['runs']} | {item['mean_score']} | {item.get('decision_accuracy')} | "
            f"{item['score_delta_full_minus_ablation']} | "
            f"{item['evidence_delta_full_minus_ablation']} | {item['tool_call_delta_full_minus_ablation']} | "
            f"{item['replay_runs']} | {item['controller_runs']} | {item['controller_applied_runs']} |"
        )
    policy = analysis["policy"]["neural_policy"]
    lines.extend(
        [
            "",
            "## SciFlow Policy",
            "",
            f"- Artifact: `{policy.get('artifact_path')}`",
            f"- Examples: `{policy.get('num_examples')}`",
            f"- Holdout top-1: `{policy.get('holdout_top1')}`",
            f"- Holdout top-3: `{policy.get('holdout_top3')}`",
            f"- Holdout MRR: `{policy.get('holdout_mrr')}`",
            f"- Majority baseline top-1: `{policy.get('majority_baseline_top1')}`",
            "",
            "## Claims Supported By This Run",
            "",
        ]
    )
    lines.extend(f"- {claim}" for claim in analysis["claims"])
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in analysis["limitations"])
    return "\n".join(lines)


def write_analysis(analysis: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"benchmark_analysis_{int(analysis['created_at_unix'])}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(analysis, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(analysis), encoding="utf-8")
    return {"analysis_json": str(json_path), "analysis_markdown": str(md_path)}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze AutoScientist benchmark artifacts.")
    parser.add_argument("--bench-dir", required=True)
    parser.add_argument("--output-dir", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    bench_dir = Path(args.bench_dir)
    output_dir = Path(args.output_dir) if args.output_dir else bench_dir / "analysis"
    analysis = analyze_benchmark_dir(bench_dir)
    result = write_analysis(analysis, output_dir)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
