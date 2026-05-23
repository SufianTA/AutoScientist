from __future__ import annotations

import argparse
import json
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TEMPLATE_LABELS = {
    "target_validity_review": "Target Validity",
    "mechanism_safety_review": "Mechanism And Safety",
    "experiment_decision_plan": "Experiment Decision Plan",
    "evidence_grade_and_replay": "Evidence Grade And Replay",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def task_result_files(bench_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in bench_dir.glob("*.json")
        if "__" in path.stem and not path.name.startswith("benchmark_")
    )


def load_results(bench_dir: Path) -> list[dict[str, Any]]:
    results = []
    for path in task_result_files(bench_dir):
        try:
            result = load_json(path)
        except json.JSONDecodeError:
            continue
        if result.get("schema") == "autosci.benchmark_task_result.v0.1":
            result["_artifact_path"] = str(path)
            results.append(result)
    return results


def index_by_case(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        task = result.get("task") or {}
        case_id = task.get("case_id")
        if case_id:
            grouped[case_id].append(result)
    return dict(grouped)


def short_text(value: Any, limit: int = 420) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def extract_articles(tool_call: dict[str, Any]) -> list[dict[str, str]]:
    output = tool_call.get("output") or {}
    nested = output.get("output") if isinstance(output.get("output"), dict) else output
    articles = nested.get("articles") if isinstance(nested, dict) else None
    if not isinstance(articles, list):
        return []
    extracted = []
    for article in articles[:5]:
        if not isinstance(article, dict):
            continue
        extracted.append(
            {
                "pmid": str(article.get("pmid") or ""),
                "title": str(article.get("title") or ""),
                "journal": str(article.get("journal") or ""),
                "pubdate": str(article.get("pubdate") or ""),
                "url": str(article.get("url") or ""),
            }
        )
    return extracted


def summarize_tool_call(tool_call: dict[str, Any]) -> dict[str, Any]:
    output = tool_call.get("output") or {}
    nested = output.get("output") if isinstance(output.get("output"), dict) else output
    summary: dict[str, Any] = {
        "tool_name": tool_call.get("tool_name"),
        "tool_source": tool_call.get("tool_source"),
        "input": tool_call.get("input"),
        "status": output.get("status"),
        "confidence": output.get("confidence"),
    }
    if isinstance(nested, dict):
        for key in ("count", "gene_id", "gene_symbol", "description", "id", "name"):
            if key in nested:
                summary[key] = nested[key]
        if "raw" in nested:
            summary["raw_available"] = True
    articles = extract_articles(tool_call)
    if articles:
        summary["articles"] = articles
    return summary


def evidence_rank(item: dict[str, Any]) -> tuple[int, float]:
    label = str(item.get("support_label") or "").lower()
    score = item.get("support_score")
    numeric = float(score) if isinstance(score, (int, float)) else 0.0
    if "strong" in label:
        tier = 0
    elif "mechanistic" in label:
        tier = 1
    elif "weak" in label:
        tier = 2
    elif "irrelevant" in label or "contrad" in label or "failed" in label:
        tier = 4
    else:
        tier = 3
    return (tier, -numeric)


def collect_evidence(full_results: list[dict[str, Any]], max_items: int = 12) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    seen = set()
    for result in full_results:
        report = result.get("report") or {}
        for item in report.get("evidence") or []:
            key = (item.get("source"), short_text(item.get("text"), 180))
            if key in seen:
                continue
            seen.add(key)
            evidence.append(
                {
                    "source": item.get("source"),
                    "support_label": item.get("support_label"),
                    "support_score": item.get("support_score"),
                    "text": short_text(item.get("text"), 700),
                }
            )
            if len(evidence) >= max_items:
                break
    evidence = sorted(evidence, key=evidence_rank)
    supportive = [item for item in evidence if evidence_rank(item)[0] <= 2][:max_items]
    weak_or_failed = [item for item in evidence if evidence_rank(item)[0] > 2][:max_items]
    return supportive, weak_or_failed


def collect_experiments(full_results: list[dict[str, Any]], max_items: int = 10) -> list[dict[str, Any]]:
    experiments = []
    seen = set()
    for result in full_results:
        for experiment in result.get("experiments") or (result.get("report") or {}).get("experiments") or []:
            if not isinstance(experiment, dict):
                continue
            key = experiment.get("name") or json.dumps(experiment, sort_keys=True)[:120]
            if key in seen:
                continue
            seen.add(key)
            experiments.append(
                {
                    "name": experiment.get("name"),
                    "type": experiment.get("type"),
                    "feasibility": experiment.get("feasibility"),
                    "expected_information_gain": experiment.get("expected_information_gain"),
                    "priority_score": experiment.get("priority_score"),
                    "decision_gate": experiment.get("decision_gate"),
                    "success_criteria": experiment.get("success_criteria") or [],
                    "failure_modes": experiment.get("failure_modes") or [],
                }
            )
            if len(experiments) >= max_items:
                return experiments
    return experiments


def case_ablation_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    by_ablation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in case_results:
        by_ablation[result.get("ablation") or "unknown"].append(result)
    summary = {}
    for ablation, rows in sorted(by_ablation.items()):
        scores = [
            (row.get("value_assessment") or {}).get("score")
            for row in rows
            if isinstance((row.get("value_assessment") or {}).get("score"), (int, float))
        ]
        quality = [
            ((row.get("value_assessment") or {}).get("scientific_quality") or {}).get("score")
            for row in rows
            if isinstance(((row.get("value_assessment") or {}).get("scientific_quality") or {}).get("score"), (int, float))
        ]
        summary[ablation] = {
            "runs": len(rows),
            "completed": sum(1 for row in rows if row.get("status") == "completed"),
            "mean_score": round(sum(scores) / len(scores), 2) if scores else None,
            "mean_scientific_quality": round(sum(quality) / len(quality), 2) if quality else None,
            "mean_evidence_count": round(sum(row.get("evidence_count") or 0 for row in rows) / len(rows), 2) if rows else 0,
            "mean_tool_calls": round(sum(len(row.get("tool_calls") or []) for row in rows) / len(rows), 2) if rows else 0,
        }
    return summary


def build_case_study(case_id: str, case_results: list[dict[str, Any]], bench_dir: Path) -> dict[str, Any]:
    full_results = sorted(
        [row for row in case_results if row.get("ablation") == "full"],
        key=lambda row: (row.get("task") or {}).get("template_id", ""),
    )
    if not full_results:
        raise ValueError(f"No full results found for case {case_id}")
    task = full_results[0].get("task") or {}
    hypotheses = [
        {
            "template_id": (row.get("task") or {}).get("template_id"),
            "title": (row.get("hypothesis") or {}).get("title"),
            "text": (row.get("hypothesis") or {}).get("text"),
            "confidence": (row.get("hypothesis") or {}).get("confidence"),
            "artifact": row.get("_artifact_path"),
        }
        for row in full_results
    ]
    all_tool_calls = [call for row in full_results for call in row.get("tool_calls") or []]
    tool_sources = Counter(call.get("tool_source") or "unknown" for call in all_tool_calls)
    tool_names = Counter(call.get("tool_name") or "unknown" for call in all_tool_calls)
    articles = []
    seen_article = set()
    for call in all_tool_calls:
        for article in extract_articles(call):
            key = article.get("pmid") or article.get("url") or article.get("title")
            if key and key not in seen_article:
                seen_article.add(key)
                articles.append(article)
    public_context = task.get("public_context") or {}
    supportive_evidence, weak_or_failed = collect_evidence(full_results)
    return {
        "schema": "autosci.discovery_case_study.v0.1",
        "created_at_unix": int(time.time()),
        "case_id": case_id,
        "gene_symbol": task.get("gene_symbol"),
        "disease_name": task.get("disease_name"),
        "domain": task.get("domain"),
        "priority": task.get("priority"),
        "objective": task.get("objective"),
        "source_benchmark_dir": str(bench_dir),
        "headline": build_headline(task, full_results),
        "decision_position": build_decision_position(task, hypotheses),
        "full_run_metrics": {
            "templates_completed": len(full_results),
            "mean_confidence": round(sum(row.get("final_confidence") or 0 for row in full_results) / len(full_results), 3),
            "total_evidence_items": sum(row.get("evidence_count") or 0 for row in full_results),
            "total_tool_calls": len(all_tool_calls),
            "public_biomedical_calls": tool_sources.get("live_public_biomedical", 0),
            "tooluniverse_calls": tool_sources.get("tooluniverse", 0),
            "memory_replay_runs": sum(1 for row in full_results if (row.get("replay") or {}).get("available")),
            "sciflow_applied_runs": sum(1 for row in full_results if (row.get("sciflow_application") or {}).get("applied")),
        },
        "ablation_summary": case_ablation_summary(case_results),
        "hypotheses": hypotheses,
        "evidence_highlights": supportive_evidence,
        "weak_or_failed_branches": weak_or_failed,
        "tool_trace_summary": {
            "tool_sources": dict(tool_sources),
            "top_tools": tool_names.most_common(12),
            "sample_tool_calls": [summarize_tool_call(call) for call in all_tool_calls[:18]],
        },
        "literature_highlights": articles[:16],
        "public_context_summary": summarize_public_context(public_context),
        "recommended_experiments": collect_experiments(full_results),
        "audit_paths": {
            "benchmark_summary": str(bench_dir / "benchmark_summary.md"),
            "state_graph": str(bench_dir / "scistate_graph.json"),
            "case_artifacts": [row.get("_artifact_path") for row in full_results],
        },
        "limits": [
            "This is a machine-generated research decision package, not a clinical recommendation.",
            "The output accelerates evidence gathering and hypothesis triage; it does not prove therapeutic efficacy.",
            "External expert review is still required before treating conclusions as validated biology.",
        ],
    }


def build_headline(task: dict[str, Any], full_results: list[dict[str, Any]]) -> str:
    gene = task.get("gene_symbol")
    disease = task.get("disease_name")
    conf = round(sum(row.get("final_confidence") or 0 for row in full_results) / len(full_results), 2)
    return (
        f"AutoScientist produced an audit-ready {gene}/{disease} research dossier "
        f"with mean confidence {conf}, live public evidence, replayable traces, "
        "and prioritized next experiments."
    )


def build_decision_position(task: dict[str, Any], hypotheses: list[dict[str, Any]]) -> str:
    gene = task.get("gene_symbol")
    disease = task.get("disease_name")
    text = " ".join(item.get("text") or "" for item in hypotheses)
    if "not present this as a new target discovery" in text or "clinical" in text.lower():
        return (
            f"{gene} in {disease} should be treated as a clinically precedented or evidence-backed "
            "target context where the system's value is fast synthesis, uncertainty mapping, "
            "and experiment prioritization rather than claiming a brand-new discovery."
        )
    return (
        f"{gene} in {disease} should be treated as a candidate scientific hypothesis with "
        "traceable public evidence and explicit next validation experiments."
    )


def summarize_public_context(public_context: dict[str, Any]) -> dict[str, Any]:
    summary = {}
    for key, value in public_context.items():
        if isinstance(value, dict):
            compact = {}
            for inner_key in ("status", "confidence", "count", "score", "id", "name"):
                if inner_key in value:
                    compact[inner_key] = value[inner_key]
            output = value.get("output")
            if isinstance(output, dict):
                for inner_key in ("count", "gene_symbol", "gene_id", "description"):
                    if inner_key in output:
                        compact[inner_key] = output[inner_key]
            summary[key] = compact or short_text(value, 240)
        else:
            summary[key] = short_text(value, 240)
    return summary


def render_case_markdown(case: dict[str, Any]) -> str:
    lines = [
        f"# Discovery Case Study: {case['gene_symbol']} / {case['disease_name']}",
        "",
        "## Bottom Line",
        "",
        case["headline"],
        "",
        case["decision_position"],
        "",
        "## What The System Did End To End",
        "",
        f"- Started from the objective: {case['objective']}",
        f"- Completed {case['full_run_metrics']['templates_completed']} complementary scientific workflows.",
        f"- Ran {case['full_run_metrics']['total_tool_calls']} tool calls, including "
        f"{case['full_run_metrics']['public_biomedical_calls']} public biomedical calls and "
        f"{case['full_run_metrics']['tooluniverse_calls']} ToolUniverse calls.",
        f"- Wrote replayable memory/provenance for {case['full_run_metrics']['memory_replay_runs']} full runs.",
        f"- Applied SciFlow workflow guidance in {case['full_run_metrics']['sciflow_applied_runs']} full runs.",
        f"- Collected {case['full_run_metrics']['total_evidence_items']} evidence items.",
        "",
        "## Scientific Output",
        "",
    ]
    for item in case["hypotheses"]:
        label = TEMPLATE_LABELS.get(item["template_id"], item["template_id"])
        lines.extend(
            [
                f"### {label}",
                "",
                f"Confidence: `{item.get('confidence')}`",
                "",
                short_text(item.get("text"), 1200),
                "",
            ]
        )
    lines.extend(["## Supporting Evidence Highlights", ""])
    for idx, item in enumerate(case["evidence_highlights"], 1):
        score = item.get("support_score")
        score_text = f", score {score}" if score is not None else ""
        lines.append(f"{idx}. **{item.get('source')}** ({item.get('support_label')}{score_text}): {item.get('text')}")
    lines.extend(["", "## Weak Or Failed Branches The System Preserved", ""])
    if case["weak_or_failed_branches"]:
        for idx, item in enumerate(case["weak_or_failed_branches"], 1):
            score = item.get("support_score")
            score_text = f", score {score}" if score is not None else ""
            lines.append(f"{idx}. **{item.get('source')}** ({item.get('support_label')}{score_text}): {item.get('text')}")
    else:
        lines.append("- No weak or failed branches were selected for the compact dossier.")
    lines.extend(["", "## Literature Highlights", ""])
    if case["literature_highlights"]:
        for article in case["literature_highlights"][:12]:
            label = f"PMID {article['pmid']}" if article.get("pmid") else "Literature"
            url = article.get("url")
            citation = f"{article.get('title')} ({article.get('journal')}, {article.get('pubdate')})"
            lines.append(f"- {label}: {citation}" + (f" - {url}" if url else ""))
    else:
        lines.append("- No PubMed article summaries were present in the trace.")
    lines.extend(["", "## Recommended Next Experiments", ""])
    for idx, exp in enumerate(case["recommended_experiments"], 1):
        lines.extend(
            [
                f"{idx}. **{exp.get('name')}**",
                f"   - Type: `{exp.get('type')}`; feasibility: `{exp.get('feasibility')}`; information gain: `{exp.get('expected_information_gain')}`.",
                f"   - Decision gate: {short_text(exp.get('decision_gate'), 300)}",
            ]
        )
        criteria = exp.get("success_criteria") or []
        if criteria:
            lines.append(f"   - Success criteria: {short_text('; '.join(map(str, criteria)), 300)}")
    lines.extend(["", "## Ablation Evidence", ""])
    lines.append("| Mode | Runs | Mean score | Strict quality | Mean evidence | Mean tool calls |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for mode, stats in case["ablation_summary"].items():
        lines.append(
            f"| {mode} | {stats['runs']} | {stats['mean_score']} | {stats['mean_scientific_quality']} | "
            f"{stats['mean_evidence_count']} | {stats['mean_tool_calls']} |"
        )
    lines.extend(["", "## Audit Trail", ""])
    lines.append(f"- Benchmark summary: `{case['audit_paths']['benchmark_summary']}`")
    lines.append(f"- State graph: `{case['audit_paths']['state_graph']}`")
    for path in case["audit_paths"]["case_artifacts"]:
        lines.append(f"- Full-run artifact: `{path}`")
    lines.extend(["", "## Limits", ""])
    for limit in case["limits"]:
        lines.append(f"- {limit}")
    lines.append("")
    return "\n".join(lines)


def write_case_studies(bench_dir: Path, output_dir: Path, requested_cases: list[str]) -> dict[str, Any]:
    results = load_results(bench_dir)
    cases = index_by_case(results)
    selected = requested_cases or sorted(cases)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for case_id in selected:
        if case_id not in cases:
            raise SystemExit(f"Case not found in benchmark output: {case_id}")
        case = build_case_study(case_id, cases[case_id], bench_dir)
        json_path = output_dir / f"{case_id}_discovery_case_study.json"
        md_path = output_dir / f"{case_id}_discovery_case_study.md"
        json_path.write_text(json.dumps(case, indent=2, default=str), encoding="utf-8")
        md_path.write_text(render_case_markdown(case), encoding="utf-8")
        written.append({"case_id": case_id, "json": str(json_path), "markdown": str(md_path)})
    index = {
        "schema": "autosci.discovery_case_study_index.v0.1",
        "created_at_unix": int(time.time()),
        "source_benchmark_dir": str(bench_dir),
        "case_count": len(written),
        "cases": written,
    }
    (output_dir / "case_study_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    (output_dir / "README.md").write_text(render_index_markdown(index), encoding="utf-8")
    zip_path = output_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in output_dir.rglob("*"):
            archive.write(path, path.relative_to(output_dir.parent))
    index["zip_path"] = str(zip_path)
    return index


def render_index_markdown(index: dict[str, Any]) -> str:
    lines = [
        "# AutoScientist Discovery Case Studies",
        "",
        "These dossiers translate benchmark traces into scientist-facing target-disease decision packages.",
        "",
        "Each case study emphasizes the main claim: end-to-end scientific acceleration through evidence gathering, synthesis, experiment planning, memory/provenance, and replayable artifacts.",
        "",
        "## Cases",
        "",
    ]
    for item in index["cases"]:
        lines.append(f"- `{item['case_id']}`: `{Path(item['markdown']).name}`")
    lines.extend(
        [
            "",
            "## Caveat",
            "",
            "These are research triage artifacts. They are intended for expert review and follow-up experiment design, not clinical decision-making.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build scientist-facing discovery case studies from AutoScientist benchmark traces.")
    parser.add_argument("--bench-dir", required=True)
    parser.add_argument("--output-dir", default="outputs/discovery_case_studies")
    parser.add_argument("--case-id", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    result = write_case_studies(Path(args.bench_dir), Path(args.output_dir), args.case_id)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
