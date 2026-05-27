from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tools.analyze_autoscientist_benchmark import analyze_benchmark_dir, write_analysis
from tools.build_biotruth_benchmark import (
    DEFAULT_OUTPUT as DEFAULT_BIOTRUTH_MANIFEST,
    DEFAULT_RUBRIC,
    DEFAULT_SEED_CASES,
    build_manifest,
    write_outputs as write_biotruth_outputs,
)
from tools.collect_review_package import collect_review_package
from tools.run_autoscientist_bench import run_benchmark
from tools.score_biomedical_correctness import (
    build_score_packets,
    load_benchmark_results,
    load_json,
    score_packets,
    summarize_scores,
    write_outputs as write_score_outputs,
)


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    manifest_result = None
    if args.existing_bench_dir:
        bench_dir = Path(args.existing_bench_dir)
        benchmark_summary = load_json(bench_dir / "benchmark_summary.json")
        manifest_path = Path(args.manifest)
    elif not args.skip_build:
        manifest_result = build_biotruth_manifest(args)
        manifest_path = Path(manifest_result["manifest_path"])
        benchmark_summary = run_biotruth_benchmark(args, manifest_path)
        bench_dir = Path(benchmark_summary.get("output_dir") or Path(benchmark_summary["tasks_path"]).parent)
    else:
        manifest_path = Path(args.manifest)
        if not manifest_path.exists():
            raise SystemExit(f"BioTruth manifest not found: {manifest_path}")
        benchmark_summary = run_biotruth_benchmark(args, manifest_path)
        bench_dir = Path(benchmark_summary.get("output_dir") or Path(benchmark_summary["tasks_path"]).parent)

    analysis_result = None
    score_result = None
    review_package = None
    if benchmark_summary.get("status") != "prepared":
        analysis = analyze_benchmark_dir(bench_dir)
        analysis_result = write_analysis(analysis, bench_dir / "analysis")
        score_result = score_biotruth_outputs(args, bench_dir)
        if not args.skip_review_package:
            review_package = package_review_outputs(args, bench_dir, analysis_result, score_result, manifest_path)

    pipeline_summary = {
        "schema": "autosci.biotruth_pipeline.v0.1",
        "created_at_unix": int(started),
        "elapsed_seconds": round(time.time() - started, 2),
        "mode": args.mode,
        "manifest": manifest_result or {"manifest_path": str(manifest_path)},
        "benchmark_summary": summarize_benchmark_for_pipeline(benchmark_summary),
        "analysis": analysis_result,
        "biotruth_scores": score_result,
        "review_package": review_package,
        "acceptance": pipeline_acceptance(benchmark_summary, score_result, args),
        "next_steps": recommended_next_steps(args),
    }
    summary_path = write_pipeline_summary(pipeline_summary, args, bench_dir)
    pipeline_summary["summary_path"] = str(summary_path)
    summary_path.write_text(json.dumps(pipeline_summary, indent=2, default=str), encoding="utf-8")
    return pipeline_summary


def build_biotruth_manifest(args: argparse.Namespace) -> dict[str, Any]:
    build_args = SimpleNamespace(
        seed_cases=args.seed_cases,
        rubric=args.rubric,
        output_manifest=args.manifest,
        max_cases=args.max_cases,
        templates_per_case=args.templates_per_case,
        association_scan_size=args.association_scan_size,
        public_timeout_seconds=args.public_timeout_seconds,
        offline_public_context=args.offline_public_context,
    )
    manifest = build_manifest(build_args)
    return write_biotruth_outputs(manifest, Path(args.manifest))


def run_biotruth_benchmark(args: argparse.Namespace, manifest_path: Path) -> dict[str, Any]:
    if args.mode == "prepare":
        limit = args.limit or args.max_cases * args.templates_per_case
        prepare_only = True
    elif args.mode == "smoke":
        limit = args.limit or 8
        prepare_only = False
    else:
        limit = args.limit or args.max_cases * args.templates_per_case
        prepare_only = False
    provider = args.llm_provider
    model = args.llm_model
    if args.allow_mock and provider == "auto":
        provider = "mock"
        model = model or "mock-scientist"
    benchmark_args = SimpleNamespace(
        manifest=str(manifest_path),
        output_dir=args.output_dir,
        limit=limit,
        replicates_per_case=args.replicates_per_case,
        case_ids=args.case_ids,
        template_ids=args.template_ids,
        ablations=args.ablations,
        prepare_only=prepare_only,
        offline_public_context=args.offline_public_context,
        public_timeout_seconds=args.public_timeout_seconds,
        llm_provider=provider,
        llm_model=model,
        llm_api_key_env_var=args.llm_api_key_env_var,
        llm_max_tokens=args.llm_max_tokens,
        agent_count=args.agent_count,
        max_runtime_minutes=args.max_runtime_minutes,
        tool_budget_usd=args.tool_budget_usd,
        require_real_llm=not args.allow_mock and not prepare_only,
        enable_sciflow_policy=not args.disable_sciflow_policy,
        sciflow_policy_model_id=args.sciflow_policy_model_id,
        sciflow_policy_model_path=args.sciflow_policy_model_path,
        sciflow_policy_min_score=args.sciflow_policy_min_score,
        disable_strategy_repair=args.disable_strategy_repair,
        strategy_repair_max_queries=args.strategy_repair_max_queries,
        skip_policy_training=args.skip_policy_training,
        policy_model_name=args.policy_model_name,
        train_neural_policy=args.train_neural_policy,
        neural_policy_model_name=args.neural_policy_model_name,
        neural_epochs=args.neural_epochs,
        neural_hidden_dim=args.neural_hidden_dim,
        neural_batch_size=args.neural_batch_size,
        skip_package=args.skip_package,
        replay_limit=args.replay_limit,
        graph_limit=args.graph_limit,
        strict_real_run=(args.strict_real_run and not prepare_only and not args.allow_mock),
        min_full_completion_rate=args.min_full_completion_rate,
        min_full_mean_score=args.min_full_mean_score,
        require_full_integrations=args.require_full_integrations,
        require_expected_integrations=args.require_expected_integrations,
        min_neural_holdout_top1=args.min_neural_holdout_top1,
        min_state_graph_nodes=args.min_state_graph_nodes,
    )
    return run_benchmark(benchmark_args)


def score_biotruth_outputs(args: argparse.Namespace, bench_dir: Path) -> dict[str, Any]:
    rubric = load_json(Path(args.rubric))
    results = load_benchmark_results(bench_dir, ablations=args.ablations)
    packets = build_score_packets(results, rubric)
    scoring_args = SimpleNamespace(
        bench_dir=bench_dir,
        mode=args.score_mode,
        max_results=args.max_score_results,
        llm_provider=args.judge_llm_provider,
        llm_model=args.judge_llm_model,
        llm_api_key_env_var=args.judge_llm_api_key_env_var,
        llm_base_url=args.judge_llm_base_url,
        llm_max_tokens=args.judge_llm_max_tokens,
    )
    scored = score_packets(scoring_args, packets, rubric)
    summary = summarize_scores(scored, scoring_args, rubric)
    output = write_score_outputs(scored, summary, bench_dir)
    output["summary"] = summary
    return output


def package_review_outputs(
    args: argparse.Namespace,
    bench_dir: Path,
    analysis_result: dict[str, Any] | None,
    score_result: dict[str, Any] | None,
    manifest_path: Path,
) -> dict[str, Any]:
    extras = [
        str(Path(args.rubric)),
        str(Path(args.seed_cases)),
        str(manifest_path),
        str(manifest_path.with_suffix(".md")),
        str(Path("docs/BIOTRUTH_BENCHMARK.md")),
        str(Path("docs/CLAIMS_AND_LIMITATIONS.md")),
    ]
    if analysis_result:
        extras.extend([analysis_result["analysis_json"], analysis_result["analysis_markdown"]])
    if score_result:
        extras.extend([score_result["scores_path"], score_result["markdown_path"], score_result["packets_path"]])
    package_args = SimpleNamespace(
        benchmark_root=args.output_dir,
        bench_dir=str(bench_dir),
        output_dir=args.review_output_dir,
        name=args.review_package_name or f"autoscientist_biotruth_review_{int(time.time())}",
        extra=extras,
        allow_secret_matches=False,
    )
    return collect_review_package(package_args)


def summarize_benchmark_for_pipeline(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": summary.get("status"),
        "output_dir": summary.get("output_dir"),
        "task_count": summary.get("task_count"),
        "result_count": summary.get("result_count"),
        "summary_path": summary.get("summary_path"),
        "summary_markdown_path": summary.get("summary_markdown_path"),
        "realness_gates": summary.get("realness_gates"),
        "summary_by_ablation": summary.get("summary_by_ablation", {}),
        "full_vs_ablation_deltas": summary.get("full_vs_ablation_deltas", {}),
    }


def pipeline_acceptance(
    benchmark_summary: dict[str, Any],
    score_result: dict[str, Any] | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    failures = []
    if benchmark_summary.get("status") not in {"completed", "prepared"}:
        failures.append(f"Benchmark status was {benchmark_summary.get('status')}.")
    if benchmark_summary.get("status") == "completed":
        full = (benchmark_summary.get("summary_by_ablation") or {}).get("full", {})
        if full.get("completed") != full.get("runs"):
            failures.append("Full ablation did not complete all runs.")
        if args.score_mode != "export" and score_result:
            score_summary = score_result.get("summary", {})
            by_ablation = score_summary.get("by_ablation", {})
            full_score = by_ablation.get("full", {}).get("mean_weighted_score")
            no_public_score = by_ablation.get("no_public_tools", {}).get("mean_weighted_score")
            if full_score is not None and no_public_score is not None and full_score <= no_public_score:
                failures.append("BioTruth score did not improve over no_public_tools.")
            full_failure_rate = by_ablation.get("full", {}).get("critical_failure_rate")
            if full_failure_rate is None:
                full_failure_rate = score_summary.get("overall", {}).get("critical_failure_rate", 1)
            if full_failure_rate > args.max_critical_failure_rate:
                failures.append("Full-system critical failure rate exceeded threshold.")
    return {
        "passed": not failures,
        "failures": failures,
        "score_mode": args.score_mode,
        "max_critical_failure_rate": args.max_critical_failure_rate,
    }


def recommended_next_steps(args: argparse.Namespace) -> list[str]:
    if args.mode == "prepare":
        return [
            "Run smoke mode with a real LLM/API key to validate end-to-end execution.",
            "If smoke passes, run full mode on the H100 pod with full, plain_llm, memory, public-tool, and controller ablations.",
        ]
    if args.mode == "smoke":
        return [
            "Inspect BioTruth score deltas and critical failures before paying for the full run.",
            "Run full mode on the pod only if full beats no_public_tools and outputs are scientifically coherent.",
        ]
    return [
        "Export review package and inspect representative packets with a human biomedical reviewer.",
        "Use failures to retrain SciFlow Policy and adjust strategy repair before another expensive run.",
    ]


def write_pipeline_summary(summary: dict[str, Any], args: argparse.Namespace, bench_dir: Path) -> Path:
    path = bench_dir / f"biotruth_pipeline_{summary['created_at_unix']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full BioTruth AutoScientist pipeline.")
    parser.add_argument("--mode", choices=["prepare", "smoke", "full"], default="smoke")
    parser.add_argument("--seed-cases", default=str(DEFAULT_SEED_CASES))
    parser.add_argument("--rubric", default=str(DEFAULT_RUBRIC))
    parser.add_argument("--manifest", default=str(DEFAULT_BIOTRUTH_MANIFEST))
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--existing-bench-dir", default="")
    parser.add_argument("--max-cases", type=int, default=25)
    parser.add_argument("--templates-per-case", type=int, default=4)
    parser.add_argument("--association-scan-size", type=int, default=150)
    parser.add_argument("--public-timeout-seconds", type=int, default=15)
    parser.add_argument("--offline-public-context", action="store_true")
    parser.add_argument("--output-dir", default="outputs/autoscientist_bench")
    parser.add_argument("--review-output-dir", default="outputs/review_packages")
    parser.add_argument("--review-package-name", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--replicates-per-case", type=int, default=1)
    parser.add_argument("--case-ids", nargs="*", default=[])
    parser.add_argument("--template-ids", nargs="*", default=[])
    parser.add_argument("--ablations", nargs="*", default=["full", "plain_llm", "no_memory", "no_public_tools", "no_sciflow"])
    parser.add_argument("--llm-provider", default="auto")
    parser.add_argument("--llm-model", default="")
    parser.add_argument("--llm-api-key-env-var", default="")
    parser.add_argument("--llm-max-tokens", type=int, default=384)
    parser.add_argument("--allow-mock", action="store_true")
    parser.add_argument("--agent-count", type=int, default=3)
    parser.add_argument("--max-runtime-minutes", type=int, default=8)
    parser.add_argument("--tool-budget-usd", type=float, default=1.0)
    parser.add_argument("--disable-sciflow-policy", action="store_true")
    parser.add_argument("--sciflow-policy-model-id", default="")
    parser.add_argument("--sciflow-policy-model-path", default="")
    parser.add_argument("--sciflow-policy-min-score", type=float, default=0.15)
    parser.add_argument("--disable-strategy-repair", action="store_true")
    parser.add_argument("--strategy-repair-max-queries", type=int, default=2)
    parser.add_argument("--skip-policy-training", action="store_true")
    parser.add_argument("--policy-model-name", default="scientific_workflow_policy")
    parser.add_argument("--train-neural-policy", action="store_true")
    parser.add_argument("--neural-policy-model-name", default="neural_scientific_workflow_policy")
    parser.add_argument("--neural-epochs", type=int, default=80)
    parser.add_argument("--neural-hidden-dim", type=int, default=128)
    parser.add_argument("--neural-batch-size", type=int, default=64)
    parser.add_argument("--skip-package", action="store_true")
    parser.add_argument("--skip-review-package", action="store_true")
    parser.add_argument("--replay-limit", type=int, default=20)
    parser.add_argument("--graph-limit", type=int, default=1000)
    parser.add_argument("--strict-real-run", action="store_true")
    parser.add_argument("--min-full-completion-rate", type=float, default=1.0)
    parser.add_argument("--min-full-mean-score", type=float, default=80.0)
    parser.add_argument("--require-full-integrations", nargs="*", default=["public_biomedical", "tooluniverse", "local_board"])
    parser.add_argument("--require-expected-integrations", action="store_true")
    parser.add_argument("--min-neural-holdout-top1", type=float, default=0.0)
    parser.add_argument("--min-state-graph-nodes", type=int, default=1)
    parser.add_argument("--score-mode", choices=["export", "heuristic", "judge"], default="heuristic")
    parser.add_argument("--max-score-results", type=int, default=0)
    parser.add_argument("--judge-llm-provider", default="gemini")
    parser.add_argument("--judge-llm-model", default="gemini-3-flash-preview")
    parser.add_argument("--judge-llm-api-key-env-var", default="")
    parser.add_argument("--judge-llm-base-url", default="")
    parser.add_argument("--judge-llm-max-tokens", type=int, default=1600)
    parser.add_argument("--max-critical-failure-rate", type=float, default=0.05)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    summary = run_pipeline(parse_args(argv or sys.argv[1:]))
    print(
        json.dumps(
            {
                "status": summary["benchmark_summary"].get("status"),
                "mode": summary["mode"],
                "task_count": summary["benchmark_summary"].get("task_count"),
                "result_count": summary["benchmark_summary"].get("result_count"),
                "acceptance": summary["acceptance"],
                "summary_path": summary["summary_path"],
                "review_package": summary.get("review_package", {}).get("zip_path")
                if summary.get("review_package")
                else None,
            },
            indent=2,
        )
    )
    return 0 if summary["acceptance"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
