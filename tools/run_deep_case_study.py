from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.build_discovery_case_study import write_case_studies
from tools.build_discovery_insight_report import build_report, render_markdown
from tools.collect_review_package import collect_review_package
from tools.run_biotruth_pipeline import parse_args as parse_pipeline_args
from tools.run_biotruth_pipeline import run_pipeline


DEFAULT_MANIFEST = "benchmarks/autoscientist_deep_ra_refractory_case.json"
DEFAULT_CASE_ID = "tnf_refractory_rheumatoid_arthritis_deep"
DEFAULT_TEMPLATES = [
    "refractory_ra_strategy_dossier",
    "nonresponder_mechanism_map",
    "repurposing_and_safety_triage",
    "decision_grade_experiment_plan",
]
DEFAULT_ABLATIONS = ["full", "plain_llm", "no_public_tools", "no_memory", "no_sciflow"]


def build_pipeline_argv(args: argparse.Namespace) -> list[str]:
    argv = [
        "--mode",
        args.mode,
        "--skip-build",
        "--manifest",
        args.manifest,
        "--rubric",
        args.rubric,
        "--output-dir",
        args.output_dir,
        "--review-output-dir",
        args.review_output_dir,
        "--review-package-name",
        args.review_package_name,
        "--case-ids",
        args.case_id,
        "--template-ids",
        *args.template_ids,
        "--ablations",
        *args.ablations,
        "--llm-provider",
        args.llm_provider,
        "--llm-model",
        args.llm_model,
        "--llm-api-key-env-var",
        args.llm_api_key_env_var,
        "--llm-max-tokens",
        str(args.llm_max_tokens),
        "--agent-count",
        str(args.agent_count),
        "--max-runtime-minutes",
        str(args.max_runtime_minutes),
        "--tool-budget-usd",
        str(args.tool_budget_usd),
        "--strategy-repair-max-queries",
        str(args.strategy_repair_max_queries),
        "--sciflow-policy-min-score",
        str(args.sciflow_policy_min_score),
        "--train-neural-policy",
        "--neural-epochs",
        str(args.neural_epochs),
        "--neural-hidden-dim",
        str(args.neural_hidden_dim),
        "--neural-batch-size",
        str(args.neural_batch_size),
        "--replay-limit",
        str(args.replay_limit),
        "--graph-limit",
        str(args.graph_limit),
        "--score-mode",
        args.score_mode,
        "--max-critical-failure-rate",
        str(args.max_critical_failure_rate),
        "--min-full-completion-rate",
        "1.0",
        "--min-full-mean-score",
        str(args.min_full_mean_score),
        "--min-neural-holdout-top1",
        str(args.min_neural_holdout_top1),
        "--min-state-graph-nodes",
        str(args.min_state_graph_nodes),
        "--require-expected-integrations",
    ]
    if args.strict_real_run:
        argv.append("--strict-real-run")
    if args.disable_qworld:
        argv.append("--disable-qworld")
    if args.judge_llm_provider:
        argv.extend(["--judge-llm-provider", args.judge_llm_provider])
    if args.judge_llm_model:
        argv.extend(["--judge-llm-model", args.judge_llm_model])
    if args.judge_llm_api_key_env_var:
        argv.extend(["--judge-llm-api-key-env-var", args.judge_llm_api_key_env_var])
    return argv


def postprocess_outputs(args: argparse.Namespace, bench_dir: Path, summary: dict) -> dict:
    case_study_dir = Path(args.case_study_output_dir)
    case_index = write_case_studies(bench_dir, case_study_dir, [args.case_id])

    insight = build_report(bench_dir, case_study_dir)
    insight_json = bench_dir / "deep_discovery_insight_report.json"
    insight_md = bench_dir / "deep_discovery_insight_report.md"
    insight_json.write_text(json.dumps(insight, indent=2, default=str), encoding="utf-8")
    insight_md.write_text(render_markdown(insight), encoding="utf-8")

    extras = [
        args.manifest,
        args.rubric,
        str(case_study_dir / "README.md"),
        str(case_study_dir / f"{args.case_id}_discovery_case_study.md"),
        str(case_study_dir / f"{args.case_id}_discovery_case_study.json"),
        str(insight_json),
        str(insight_md),
        args.runbook_path,
        "docs/CLAIMS_AND_LIMITATIONS.md",
    ]
    if summary.get("summary_path"):
        extras.append(str(summary["summary_path"]))
    analysis = summary.get("analysis") or {}
    if analysis.get("analysis_json"):
        extras.extend([analysis["analysis_json"], analysis["analysis_markdown"]])
    scores = summary.get("biotruth_scores") or {}
    if scores.get("scores_path"):
        extras.extend([scores["scores_path"], scores["markdown_path"], scores["packets_path"]])

    package = collect_review_package(
        argparse.Namespace(
            benchmark_root=args.output_dir,
            bench_dir=str(bench_dir),
            output_dir=args.review_output_dir,
            name=args.review_package_name + "_with_case_study",
            extra=extras,
            allow_secret_matches=False,
        )
    )
    return {
        "case_study": case_index,
        "insight_report": {"json": str(insight_json), "markdown": str(insight_md)},
        "review_package": package,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the deep refractory-RA AutoScientist case study.")
    parser.add_argument("--mode", choices=["prepare", "smoke", "full"], default="full")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--rubric", default="benchmarks/biotruth_rubric_v0_2.json")
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--template-ids", nargs="*", default=DEFAULT_TEMPLATES)
    parser.add_argument("--ablations", nargs="*", default=DEFAULT_ABLATIONS)
    parser.add_argument("--output-dir", default="outputs/deep_ra_refractory_case")
    parser.add_argument("--case-study-output-dir", default="outputs/deep_ra_refractory_case_studies")
    parser.add_argument("--review-output-dir", default="outputs/review_packages")
    parser.add_argument("--review-package-name", default="autoscientist_deep_ra_refractory_review")
    parser.add_argument("--runbook-path", default="docs/DEEP_RA_REFRACTORY_CASE_STUDY_RUNBOOK.md")
    parser.add_argument("--llm-provider", default="anthropic")
    parser.add_argument("--llm-model", default="claude-sonnet-4-6")
    parser.add_argument("--llm-api-key-env-var", default="ANTHROPIC_KEY")
    parser.add_argument("--llm-max-tokens", type=int, default=1200)
    parser.add_argument("--judge-llm-provider", default="")
    parser.add_argument("--judge-llm-model", default="")
    parser.add_argument("--judge-llm-api-key-env-var", default="")
    parser.add_argument("--agent-count", type=int, default=12)
    parser.add_argument("--max-runtime-minutes", type=int, default=90)
    parser.add_argument("--tool-budget-usd", type=float, default=25.0)
    parser.add_argument("--strategy-repair-max-queries", type=int, default=6)
    parser.add_argument("--sciflow-policy-min-score", type=float, default=0.12)
    parser.add_argument("--neural-epochs", type=int, default=60)
    parser.add_argument("--neural-hidden-dim", type=int, default=192)
    parser.add_argument("--neural-batch-size", type=int, default=96)
    parser.add_argument("--replay-limit", type=int, default=80)
    parser.add_argument("--graph-limit", type=int, default=8000)
    parser.add_argument("--score-mode", choices=["export", "heuristic", "judge"], default="heuristic")
    parser.add_argument("--max-critical-failure-rate", type=float, default=0.05)
    parser.add_argument("--min-full-mean-score", type=float, default=85.0)
    parser.add_argument("--min-neural-holdout-top1", type=float, default=0.5)
    parser.add_argument("--min-state-graph-nodes", type=int, default=100)
    parser.add_argument("--disable-qworld", action="store_true", default=True)
    parser.add_argument("--strict-real-run", action="store_true", default=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    pipeline_argv = build_pipeline_argv(args)
    if args.dry_run:
        print(json.dumps({"pipeline_argv": pipeline_argv}, indent=2))
        return 0

    summary = run_pipeline(parse_pipeline_args(pipeline_argv))
    bench_dir = Path(summary["benchmark_summary"]["output_dir"])
    postprocess = postprocess_outputs(args, bench_dir, summary) if summary["benchmark_summary"]["status"] == "completed" else {}
    result = {
        "status": summary["benchmark_summary"]["status"],
        "acceptance": summary["acceptance"],
        "bench_dir": str(bench_dir),
        "summary_path": summary.get("summary_path"),
        "postprocess": postprocess,
    }
    print(json.dumps(result, indent=2, default=str))
    return 0 if summary["acceptance"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
