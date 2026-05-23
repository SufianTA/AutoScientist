from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.env import load_environment
from app.services.llm_provider import call_llm_json


DEFAULT_RUBRIC = Path("benchmarks/biotruth_rubric_v0_1.json")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_benchmark_results(bench_dir: Path, *, ablations: list[str] | None = None) -> list[dict[str, Any]]:
    selected = set(ablations or [])
    results = []
    for path in sorted(bench_dir.glob("*__*.json")):
        if path.name in {"benchmark_summary.json", "benchmark_tasks.json", "scistate_graph.json"}:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != "autosci.benchmark_task_result.v0.1":
            continue
        if selected and data.get("ablation") not in selected:
            continue
        data["_path"] = str(path)
        results.append(data)
    return results


def build_score_packets(results: list[dict[str, Any]], rubric: dict[str, Any]) -> list[dict[str, Any]]:
    return [build_score_packet(result, rubric) for result in results]


def build_score_packet(result: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    task = result.get("task", {})
    report = result.get("report", {}) if isinstance(result.get("report"), dict) else {}
    evidence = report.get("evidence", []) if isinstance(report.get("evidence"), list) else []
    experiments = result.get("experiments") or report.get("experiments") or report.get("next_experiments") or []
    guardrails = result.get("guardrails") or report.get("guardrails") or []
    tool_calls = result.get("tool_calls") or []
    return {
        "schema": "autosci.biotruth_score_packet.v0.1",
        "created_at_unix": int(time.time()),
        "rubric_schema": rubric.get("schema"),
        "task": {
            "id": task.get("id"),
            "case_id": task.get("case_id"),
            "template_id": task.get("template_id"),
            "domain": task.get("domain"),
            "gene_symbol": task.get("gene_symbol"),
            "disease_name": task.get("disease_name"),
            "objective": task.get("objective"),
            "public_labels": extract_public_labels(task),
            "public_context": compact(task.get("public_context", {}), max_chars=1800),
            "benchmark_tags": task.get("benchmark_tags", []),
        },
        "ablation": result.get("ablation"),
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "trace": {
            "artifact_path": result.get("_path") or result.get("artifact_path"),
            "replay_available": bool(result.get("replay", {}).get("available")),
            "tool_call_count": len(tool_calls),
            "evidence_count": int(result.get("evidence_count") or len(evidence)),
            "integrations": result.get("integrations", {}),
            "value_assessment": result.get("value_assessment", {}),
        },
        "answer": {
            "hypothesis": compact(result.get("hypothesis") or report.get("hypothesis") or {}, max_chars=2600),
            "evidence": compact_list(evidence, limit=12, max_chars=1400),
            "experiments": compact_list(experiments, limit=8, max_chars=1200),
            "guardrails": compact_list(guardrails, limit=8, max_chars=1200),
            "tool_calls": compact_tool_calls(tool_calls, limit=20),
        },
    }


def extract_public_labels(task: dict[str, Any]) -> dict[str, Any]:
    labels = task.get("public_labels")
    if isinstance(labels, dict) and labels:
        return labels
    context = task.get("public_context") if isinstance(task.get("public_context"), dict) else {}
    context_labels = context.get("public_labels") if isinstance(context.get("public_labels"), dict) else {}
    if context_labels:
        return context_labels
    pubmed = context.get("pubmed_gene_disease") if isinstance(context.get("pubmed_gene_disease"), dict) else {}
    target = context.get("open_targets_target") if isinstance(context.get("open_targets_target"), dict) else {}
    return {
        "mode": context.get("mode"),
        "open_targets_target_status": target.get("status"),
        "pubmed_gene_disease_count": int(pubmed.get("count") or 0),
    }


def compact(value: Any, *, max_chars: int) -> Any:
    text = json.dumps(value, default=str, ensure_ascii=True)
    if len(text) <= max_chars:
        return value
    return {"truncated": True, "text": text[:max_chars]}


def compact_list(items: Any, *, limit: int, max_chars: int) -> list[Any]:
    if not isinstance(items, list):
        return []
    return [compact(item, max_chars=max_chars) for item in items[:limit]]


def compact_tool_calls(tool_calls: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    compacted = []
    for call in tool_calls[:limit]:
        compacted.append(
            {
                "tool_name": call.get("tool_name"),
                "tool_source": call.get("tool_source"),
                "status": call.get("status"),
                "input": compact(call.get("input") or call.get("args") or call.get("parameters") or {}, max_chars=700),
                "output": compact(call.get("output") or call.get("result") or {}, max_chars=900),
            }
        )
    return compacted


def heuristic_score(packet: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    text = packet_text(packet)
    task = packet.get("task", {})
    trace = packet.get("trace", {})
    labels = task.get("public_labels") or {}
    evidence_count = int(trace.get("evidence_count") or 0)
    tool_call_count = int(trace.get("tool_call_count") or 0)
    public_call_count = sum_public_calls(trace.get("integrations", {}))
    replay_available = bool(trace.get("replay_available"))
    gene = str(task.get("gene_symbol") or "").lower()
    disease = str(task.get("disease_name") or "").lower()
    target_present = gene and gene in text
    disease_present = disease and disease in text
    score = float(labels.get("open_targets_association_score") or 0.0)
    pubmed_count = int(labels.get("pubmed_gene_disease_count") or 0)
    dimensions = {
        "target_disease_validity": bounded_dimension(
            1 + int(target_present) + int(disease_present) + int(score >= 0.2) + int(pubmed_count >= 5)
        ),
        "evidence_grounding": bounded_dimension(1 + min(3, evidence_count // 3) + int(public_call_count > 0)),
        "mechanism_plausibility": bounded_dimension(
            2 + int(any(term in text for term in ["mechanism", "pathway", "cell", "signaling"])) + int(evidence_count >= 6)
        ),
        "safety_and_translation": bounded_dimension(
            1 + int(any(term in text for term in ["safety", "toxicity", "adverse", "tractability", "clinical"]))
            + int("guardrails" in json.dumps(packet.get("answer", {}), default=str).lower())
            + int(evidence_count >= 8)
        ),
        "experiment_quality": bounded_dimension(
            1 + int("experiments" in packet.get("answer", {})) + int("control" in text) + int("failure" in text)
        ),
        "calibration_and_limitations": bounded_dimension(
            1 + int(any(term in text for term in ["uncertain", "limitation", "counterevidence", "weak", "failed"]))
            + int("confidence" in text)
            + int(evidence_count >= 8)
        ),
        "auditability": bounded_dimension(1 + int(replay_available) + int(tool_call_count >= 4) + int(evidence_count >= 4)),
    }
    critical_failures = []
    if packet.get("status") != "completed":
        critical_failures.append("incomplete_run")
    if not target_present or not disease_present:
        critical_failures.append("wrong_target_or_disease")
    if evidence_count == 0 or public_call_count == 0:
        critical_failures.append("missing_public_grounding")
    return finalize_score(
        dimensions=dimensions,
        critical_failures=critical_failures,
        rubric=rubric,
        evidence_certainty=certainty_from_public_labels(score, pubmed_count),
        mode="heuristic_triage",
        rationale=(
            "Deterministic triage score based on trace structure, public evidence availability, and target/disease "
            "presence. This is not a substitute for expert or rubric-judge biological correctness scoring."
        ),
    )


def packet_text(packet: dict[str, Any]) -> str:
    return json.dumps(packet.get("answer", {}), default=str).lower()


def sum_public_calls(integrations: dict[str, Any]) -> int:
    total = 0
    for name in ("public_biomedical", "tooluniverse"):
        value = integrations.get(name, {}) if isinstance(integrations, dict) else {}
        total += int(value.get("call_count") or 0)
        if value.get("executed"):
            total += 1
    return total


def bounded_dimension(value: int) -> int:
    return max(0, min(5, int(value)))


def certainty_from_public_labels(open_targets_score: float, pubmed_count: int) -> str:
    if open_targets_score >= 0.65 and pubmed_count >= 50:
        return "high"
    if open_targets_score >= 0.35 and pubmed_count >= 10:
        return "moderate"
    if open_targets_score > 0 or pubmed_count > 0:
        return "low"
    return "very_low"


def judge_score(
    packet: dict[str, Any],
    rubric: dict[str, Any],
    *,
    provider: str,
    model: str,
    api_key_env_var: str | None,
    base_url: str | None,
    max_tokens: int,
) -> dict[str, Any]:
    prompt = build_judge_prompt(packet, rubric)
    response = call_llm_json(
        provider=provider,
        model=model,
        api_key_env_var=api_key_env_var,
        base_url=base_url,
        max_tokens=max_tokens,
        temperature=0.0,
        system_prompt=(
            "You are a strict biomedical benchmark judge. Score only the provided trace and public labels. "
            "Do not reward confident unsupported claims. Return only one valid JSON object, with no markdown, "
            "comments, trailing commas, or extra prose."
        ),
        prompt=prompt,
    )
    payload = response.get("json", {})
    dimensions = normalize_dimension_scores(payload.get("dimension_scores", {}), rubric)
    failures = [str(item) for item in payload.get("critical_failures", []) if str(item).strip()]
    return finalize_score(
        dimensions=dimensions,
        critical_failures=failures,
        rubric=rubric,
        evidence_certainty=str(payload.get("evidence_certainty") or "low"),
        mode="llm_judge",
        rationale=str(payload.get("rationale") or "")[:2000],
        raw_provider_response={
            "provider": response.get("provider"),
            "model": response.get("model"),
            "latency_ms": response.get("latency_ms"),
        },
    )


def build_judge_prompt(packet: dict[str, Any], rubric: dict[str, Any]) -> str:
    dimension_template = {item["id"]: 0 for item in rubric.get("dimensions", [])}
    allowed_failure_flags = [item["id"] for item in rubric.get("critical_failure_flags", [])]
    compact_rubric = {
        "dimensions": [
            {
                "id": item["id"],
                "weight": item["weight"],
                "question": item["question"],
                "score_anchors": item["score_anchors"],
            }
            for item in rubric.get("dimensions", [])
        ],
        "critical_failure_flags": rubric.get("critical_failure_flags", []),
        "pass_policy": rubric.get("pass_policy", {}),
    }
    return (
        "Score this AutoScientist biomedical answer packet using the rubric.\n\n"
        "Return exactly one JSON object with these fields and no other text.\n"
        "Use every dimension key exactly once and score each as an integer from 0 to 5.\n"
        "Use only the listed critical failure flag ids; use [] when none apply.\n\n"
        f"Allowed critical_failure ids: {json.dumps(allowed_failure_flags, ensure_ascii=True)}\n\n"
        "Required JSON shape:\n"
        + json.dumps(
            {
                "dimension_scores": dimension_template,
                "critical_failures": [],
                "evidence_certainty": "high|moderate|low|very_low",
                "rationale": "short explanation tied to the trace",
            },
            indent=2,
            ensure_ascii=True,
        )
        + "\n\n"
        f"RUBRIC:\n{json.dumps(compact_rubric, indent=2, ensure_ascii=True)}\n\n"
        f"ANSWER_PACKET:\n{json.dumps(packet, indent=2, ensure_ascii=True, default=str)}"
    )


def judge_failure_score(packet: dict[str, Any], rubric: dict[str, Any], exc: Exception) -> dict[str, Any]:
    dimensions = {dimension["id"]: 0 for dimension in rubric.get("dimensions", [])}
    task = packet.get("task", {}) if isinstance(packet.get("task"), dict) else {}
    return finalize_score(
        dimensions=dimensions,
        critical_failures=["judge_failed"],
        rubric=rubric,
        evidence_certainty="very_low",
        mode="llm_judge_failed",
        rationale=(
            "The judge provider failed to return a parseable rubric score for "
            f"{task.get('id') or 'unknown task'}: {type(exc).__name__}: {str(exc)[:500]}"
        ),
        raw_provider_response={
            "error_type": type(exc).__name__,
            "error": str(exc)[:1000],
        },
    )


def normalize_dimension_scores(value: Any, rubric: dict[str, Any]) -> dict[str, int]:
    scores = {}
    source = value if isinstance(value, dict) else {}
    for dimension in rubric.get("dimensions", []):
        dimension_id = dimension["id"]
        try:
            scores[dimension_id] = bounded_dimension(int(round(float(source.get(dimension_id, 0)))))
        except (TypeError, ValueError):
            scores[dimension_id] = 0
    return scores


def finalize_score(
    *,
    dimensions: dict[str, int],
    critical_failures: list[str],
    rubric: dict[str, Any],
    evidence_certainty: str,
    mode: str,
    rationale: str,
    raw_provider_response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    weighted = weighted_score(dimensions, rubric)
    policy = rubric.get("pass_policy", {})
    minimum_dimension = min(dimensions.values()) if dimensions else 0
    passed = (
        weighted >= float(policy.get("minimum_weighted_score", 75))
        and minimum_dimension >= int(policy.get("minimum_dimension_score", 2))
        and len(critical_failures) <= int(policy.get("critical_failures_allowed", 0))
    )
    return {
        "schema": "autosci.biotruth_score.v0.1",
        "mode": mode,
        "weighted_score": weighted,
        "dimension_scores": dimensions,
        "minimum_dimension_score": minimum_dimension,
        "critical_failures": critical_failures,
        "evidence_certainty": evidence_certainty,
        "passed": passed,
        "rationale": rationale,
        "raw_provider_response": raw_provider_response or {},
    }


def weighted_score(dimensions: dict[str, int], rubric: dict[str, Any]) -> float:
    total = 0.0
    for dimension in rubric.get("dimensions", []):
        dimension_id = dimension["id"]
        total += (float(dimensions.get(dimension_id, 0)) / 5.0) * float(dimension.get("weight", 0))
    return round(total, 2)


def score_packets(args: argparse.Namespace, packets: list[dict[str, Any]], rubric: dict[str, Any]) -> list[dict[str, Any]]:
    scored = []
    for packet in packets[: args.max_results or None]:
        if args.mode == "export":
            score = None
        elif args.mode == "heuristic":
            score = heuristic_score(packet, rubric)
        elif args.mode == "judge":
            try:
                score = judge_score(
                    packet,
                    rubric,
                    provider=args.llm_provider,
                    model=args.llm_model,
                    api_key_env_var=args.llm_api_key_env_var or None,
                    base_url=args.llm_base_url or None,
                    max_tokens=args.llm_max_tokens,
                )
            except Exception as exc:
                score = judge_failure_score(packet, rubric, exc)
        else:
            raise ValueError(f"Unknown scoring mode: {args.mode}")
        scored.append({"packet": packet, "score": score})
    return scored


def summarize_scores(scored: list[dict[str, Any]], args: argparse.Namespace, rubric: dict[str, Any]) -> dict[str, Any]:
    scored_only = [item for item in scored if item.get("score")]
    by_ablation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in scored_only:
        packet = item["packet"]
        by_ablation[str(packet.get("ablation") or "unknown")].append(item["score"])
        by_domain[str(packet.get("task", {}).get("domain") or "unknown")].append(item["score"])
    return {
        "schema": "autosci.biotruth_score_summary.v0.1",
        "created_at_unix": int(time.time()),
        "bench_dir": str(args.bench_dir),
        "mode": args.mode,
        "rubric": {
            "schema": rubric.get("schema"),
            "version": rubric.get("version"),
            "pass_policy": rubric.get("pass_policy", {}),
        },
        "packet_count": len(scored),
        "scored_count": len(scored_only),
        "overall": summarize_score_list([item["score"] for item in scored_only]),
        "by_ablation": {key: summarize_score_list(values) for key, values in sorted(by_ablation.items())},
        "by_domain": {key: summarize_score_list(values) for key, values in sorted(by_domain.items())},
        "limitations": [
            "Heuristic mode is a prefilter and does not establish biological correctness.",
            "Judge mode depends on the chosen model and should be audited with expert spot checks.",
            "A credible claim requires full versus ablation comparison on the same BioTruth tasks.",
        ],
    }


def summarize_score_list(scores: list[dict[str, Any]]) -> dict[str, Any]:
    if not scores:
        return {"count": 0}
    weighted = [float(item.get("weighted_score") or 0.0) for item in scores]
    return {
        "count": len(scores),
        "mean_weighted_score": round(statistics.mean(weighted), 2),
        "median_weighted_score": round(statistics.median(weighted), 2),
        "min_weighted_score": round(min(weighted), 2),
        "max_weighted_score": round(max(weighted), 2),
        "pass_rate": round(sum(1 for item in scores if item.get("passed")) / len(scores), 4),
        "critical_failure_rate": round(
            sum(1 for item in scores if item.get("critical_failures")) / len(scores),
            4,
        ),
        "evidence_certainty": dict(sorted(counts(item.get("evidence_certainty", "unknown") for item in scores).items())),
    }


def counts(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        key = str(value)
        result[key] = result.get(key, 0) + 1
    return result


def write_outputs(scored: list[dict[str, Any]], summary: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    packets_path = output_dir / "biotruth_score_packets.jsonl"
    with packets_path.open("w", encoding="utf-8") as handle:
        for item in scored:
            handle.write(json.dumps(item["packet"], default=str) + "\n")
    scores_path = output_dir / "biotruth_scores.json"
    scores_path.write_text(json.dumps({"summary": summary, "results": scored}, indent=2, default=str), encoding="utf-8")
    markdown_path = output_dir / "biotruth_scores.md"
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    return {
        "packets_path": str(packets_path),
        "scores_path": str(scores_path),
        "markdown_path": str(markdown_path),
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# BioTruth Correctness Scores",
        "",
        f"Mode: `{summary['mode']}`",
        f"Packets: `{summary['packet_count']}`",
        f"Scored: `{summary['scored_count']}`",
        "",
        "## Overall",
        "",
    ]
    lines.extend(render_summary_block(summary.get("overall", {})))
    lines.extend(["", "## By Ablation", ""])
    for name, values in summary.get("by_ablation", {}).items():
        lines.append(f"### {name}")
        lines.extend(render_summary_block(values))
        lines.append("")
    lines.extend(["## By Domain", ""])
    for name, values in summary.get("by_domain", {}).items():
        lines.append(f"### {name}")
        lines.extend(render_summary_block(values))
        lines.append("")
    lines.extend(["## Limitations", ""])
    lines.extend(f"- {item}" for item in summary.get("limitations", []))
    return "\n".join(lines)


def render_summary_block(values: dict[str, Any]) -> list[str]:
    if not values or values.get("count", 0) == 0:
        return ["- No scored packets."]
    return [
        f"- Count: `{values['count']}`",
        f"- Mean weighted score: `{values['mean_weighted_score']}`",
        f"- Median weighted score: `{values['median_weighted_score']}`",
        f"- Pass rate: `{values['pass_rate']}`",
        f"- Critical failure rate: `{values['critical_failure_rate']}`",
        f"- Evidence certainty: `{values['evidence_certainty']}`",
    ]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score AutoScientist benchmark outputs with the BioTruth rubric.")
    parser.add_argument("--bench-dir", required=True)
    parser.add_argument("--rubric", default=str(DEFAULT_RUBRIC))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--mode", choices=["export", "heuristic", "judge"], default="export")
    parser.add_argument("--ablations", nargs="*", default=["full"])
    parser.add_argument("--max-results", type=int, default=0)
    parser.add_argument("--llm-provider", default="gemini")
    parser.add_argument("--llm-model", default="gemini-2.5-flash")
    parser.add_argument("--llm-api-key-env-var", default="")
    parser.add_argument("--llm-base-url", default="")
    parser.add_argument("--llm-max-tokens", type=int, default=1600)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_environment()
    args = parse_args(argv)
    args.bench_dir = Path(args.bench_dir)
    rubric = load_json(Path(args.rubric))
    results = load_benchmark_results(args.bench_dir, ablations=args.ablations)
    if not results:
        raise SystemExit(f"No benchmark task results found in {args.bench_dir}")
    packets = build_score_packets(results, rubric)
    scored = score_packets(args, packets, rubric)
    summary = summarize_scores(scored, args, rubric)
    output_dir = Path(args.output_dir) if args.output_dir else args.bench_dir
    output = write_outputs(scored, summary, output_dir)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
