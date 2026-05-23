from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_result_files(bench_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in bench_dir.glob("*__*.json")
        if path.name not in {"benchmark_summary.json", "benchmark_tasks.json", "scistate_graph.json"}
    )


def load_results(bench_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for path in iter_result_files(bench_dir):
        try:
            payload = load_json(path)
        except json.JSONDecodeError:
            continue
        if payload.get("schema") == "autosci.benchmark_task_result.v0.1":
            payload["_path"] = str(path)
            rows.append(payload)
    return rows


def load_scores(bench_dir: Path) -> list[dict[str, Any]]:
    path = bench_dir / "biotruth_scores.json"
    if not path.exists():
        return []
    payload = load_json(path)
    if isinstance(payload, dict):
        if isinstance(payload.get("scores"), list):
            return payload["scores"]
        if isinstance(payload.get("results"), list):
            return payload["results"]
    if isinstance(payload, list):
        return payload
    return []


def result_key(row: dict[str, Any]) -> str:
    task = row.get("task") or {}
    return f"{task.get('id')}::{row.get('ablation')}"


def score_key(row: dict[str, Any]) -> str:
    if isinstance(row.get("packet"), dict):
        packet = row["packet"]
        task = packet.get("task") or {}
        return f"{task.get('id')}::{packet.get('ablation')}"
    task = row.get("task") or {}
    return f"{task.get('id')}::{row.get('ablation')}"


def weighted_score(score: dict[str, Any]) -> float | None:
    if isinstance(score.get("score"), dict):
        nested = score["score"]
        value = nested.get("weighted_score")
        if isinstance(value, (int, float)):
            return float(value)
    for key in ("weighted_score", "mean_weighted_score", "score"):
        value = score.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    value = (score.get("final_score") or {}).get("weighted_score") if isinstance(score.get("final_score"), dict) else None
    return float(value) if isinstance(value, (int, float)) else None


def short(value: Any, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def build_report(bench_dir: Path, case_study_dir: Path | None = None) -> dict[str, Any]:
    summary_path = bench_dir / "benchmark_summary.json"
    summary = load_json(summary_path) if summary_path.exists() else {}
    results = load_results(bench_dir)
    scores = {score_key(score): score for score in load_scores(bench_dir)}
    full_results = [row for row in results if row.get("ablation") == "full"]
    domains: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cases: dict[str, list[dict[str, Any]]] = defaultdict(list)
    tool_names = Counter()
    tool_sources = Counter()
    experiment_terms = Counter()
    weak_branches = []
    for row in full_results:
        task = row.get("task") or {}
        domains[str(task.get("domain") or "unknown")].append(row)
        cases[str(task.get("case_id") or "unknown")].append(row)
        for call in row.get("tool_calls") or []:
            tool_names[str(call.get("tool_name") or "unknown")] += 1
            tool_sources[str(call.get("tool_source") or "unknown")] += 1
        for exp in row.get("experiments") or []:
            name = str(exp.get("name") or "")
            for token in re.findall(r"[A-Za-z][A-Za-z0-9/-]{3,}", name.lower()):
                if token not in {"with", "using", "this", "that", "only", "next"}:
                    experiment_terms[token] += 1
        for evidence in (row.get("report") or {}).get("evidence") or []:
            label = str(evidence.get("support_label") or "").lower()
            if any(marker in label for marker in ("irrelevant", "contrad", "failed")):
                weak_branches.append(
                    {
                        "case_id": task.get("case_id"),
                        "task_id": task.get("id"),
                        "source": evidence.get("source"),
                        "label": evidence.get("support_label"),
                        "text": short(evidence.get("text"), 360),
                    }
                )
    case_summaries = []
    for case_id, rows in sorted(cases.items()):
        score_values = []
        for row in rows:
            score = scores.get(result_key(row))
            value = weighted_score(score) if score else None
            if value is not None:
                score_values.append(value)
        metrics = {
            "case_id": case_id,
            "domain": (rows[0].get("task") or {}).get("domain"),
            "gene_symbol": (rows[0].get("task") or {}).get("gene_symbol"),
            "disease_name": (rows[0].get("task") or {}).get("disease_name"),
            "runs": len(rows),
            "mean_confidence": round(sum(row.get("final_confidence") or 0 for row in rows) / len(rows), 3),
            "total_evidence": sum(row.get("evidence_count") or 0 for row in rows),
            "total_tool_calls": sum(len(row.get("tool_calls") or []) for row in rows),
            "mean_judge_score": round(sum(score_values) / len(score_values), 2) if score_values else None,
            "case_study": str(case_study_dir / f"{case_id}_discovery_case_study.md") if case_study_dir else None,
        }
        case_summaries.append(metrics)
    ranked_by_score = sorted(
        [item for item in case_summaries if item["mean_judge_score"] is not None],
        key=lambda item: item["mean_judge_score"],
        reverse=True,
    )
    ranked_by_evidence = sorted(case_summaries, key=lambda item: item["total_evidence"], reverse=True)
    ranked_by_confidence = sorted(case_summaries, key=lambda item: item["mean_confidence"], reverse=True)
    return {
        "schema": "autosci.discovery_insight_report.v0.1",
        "created_at_unix": int(time.time()),
        "source_benchmark_dir": str(bench_dir),
        "benchmark": {
            "status": summary.get("status"),
            "task_count": summary.get("task_count"),
            "result_count": summary.get("result_count"),
            "elapsed_seconds": summary.get("elapsed_seconds"),
            "realness_gates": summary.get("realness_gates"),
            "summary_by_ablation": summary.get("summary_by_ablation"),
            "neural_policy": (summary.get("neural_policy") or {}).get("metrics"),
            "state_graph": summary.get("state_graph"),
        },
        "domain_summary": {
            domain: {
                "runs": len(rows),
                "cases": len({(row.get("task") or {}).get("case_id") for row in rows}),
                "mean_confidence": round(sum(row.get("final_confidence") or 0 for row in rows) / len(rows), 3),
                "evidence": sum(row.get("evidence_count") or 0 for row in rows),
                "tool_calls": sum(len(row.get("tool_calls") or []) for row in rows),
            }
            for domain, rows in sorted(domains.items())
        },
        "case_summaries": case_summaries,
        "top_cases_by_judge_score": ranked_by_score[:15],
        "lowest_cases_by_judge_score": list(reversed(ranked_by_score[-15:])) if ranked_by_score else [],
        "top_cases_by_evidence": ranked_by_evidence[:15],
        "top_cases_by_confidence": ranked_by_confidence[:15],
        "tool_usage": {
            "sources": tool_sources.most_common(20),
            "tools": tool_names.most_common(30),
        },
        "experiment_themes": experiment_terms.most_common(30),
        "weak_or_failed_branches": weak_branches[:80],
        "shareable_claim": (
            "AutoScientist ran end-to-end target-disease workflows that gathered public evidence, "
            "generated bounded scientific positions, proposed next experiments, and preserved auditable traces."
        ),
        "caveats": [
            "This report summarizes machine-generated research triage artifacts, not validated discoveries.",
            "Expert review is required before presenting any target-disease conclusion as biologically correct.",
            "High scores on known target-disease pairs measure workflow usefulness and grounding, not prospective novelty.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    benchmark = report.get("benchmark") or {}
    lines = [
        "# AutoScientist Deep Discovery Insight Report",
        "",
        "## Claim Being Tested",
        "",
        report["shareable_claim"],
        "",
        "## Run Summary",
        "",
        f"- Status: `{benchmark.get('status')}`",
        f"- Tasks: `{benchmark.get('task_count')}`",
        f"- Results: `{benchmark.get('result_count')}`",
        f"- Elapsed seconds: `{benchmark.get('elapsed_seconds')}`",
        "",
        "## Domain Coverage",
        "",
        "| Domain | Cases | Runs | Mean confidence | Evidence | Tool calls |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for domain, stats in report["domain_summary"].items():
        lines.append(
            f"| {domain} | {stats['cases']} | {stats['runs']} | {stats['mean_confidence']} | "
            f"{stats['evidence']} | {stats['tool_calls']} |"
        )
    lines.extend(["", "## Strongest Case Studies", ""])
    strongest = report["top_cases_by_judge_score"] or report["top_cases_by_evidence"][:10]
    for item in strongest[:10]:
        score = item.get("mean_judge_score")
        score_text = f", judge {score}" if score is not None else ""
        lines.append(
            f"- `{item['case_id']}` ({item['gene_symbol']} / {item['disease_name']}{score_text}): "
            f"{item['total_evidence']} evidence items, {item['total_tool_calls']} tool calls."
        )
    lines.extend(["", "## Weakest Or Highest-Risk Case Studies", ""])
    weakest = report["lowest_cases_by_judge_score"] or []
    if weakest:
        for item in weakest[:10]:
            lines.append(
                f"- `{item['case_id']}` ({item['gene_symbol']} / {item['disease_name']}): "
                f"judge {item.get('mean_judge_score')}, {item['total_evidence']} evidence items."
            )
    else:
        lines.append("- No judge-score ranking was available; inspect weak/failed branches below.")
    lines.extend(["", "## Tool Usage", ""])
    lines.append("Top tool sources:")
    for source, count in report["tool_usage"]["sources"][:10]:
        lines.append(f"- `{source}`: {count}")
    lines.append("")
    lines.append("Top tools:")
    for tool, count in report["tool_usage"]["tools"][:15]:
        lines.append(f"- `{tool}`: {count}")
    lines.extend(["", "## Experiment Themes", ""])
    for term, count in report["experiment_themes"][:20]:
        lines.append(f"- `{term}`: {count}")
    lines.extend(["", "## Preserved Weak Or Failed Branches", ""])
    for branch in report["weak_or_failed_branches"][:20]:
        lines.append(
            f"- `{branch['case_id']}` / `{branch['task_id']}`: {branch['source']} "
            f"({branch['label']}) - {branch['text']}"
        )
    lines.extend(["", "## Caveats", ""])
    for caveat in report["caveats"]:
        lines.append(f"- {caveat}")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a cross-case insight report from AutoScientist discovery outputs.")
    parser.add_argument("--bench-dir", required=True)
    parser.add_argument("--case-study-dir", default="")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    bench_dir = Path(args.bench_dir)
    case_study_dir = Path(args.case_study_dir) if args.case_study_dir else None
    report = build_report(bench_dir, case_study_dir)
    output_json = Path(args.output_json) if args.output_json else bench_dir / "discovery_insight_report.json"
    output_md = Path(args.output_md) if args.output_md else bench_dir / "discovery_insight_report.md"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    output_md.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"json": str(output_json), "markdown": str(output_md)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
