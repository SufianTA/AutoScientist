from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.run_biotruth_pipeline import parse_args as parse_pipeline_args
from tools.run_biotruth_pipeline import run_pipeline
from tools.run_deep_case_study import build_pipeline_argv, postprocess_outputs


DEFAULT_MANIFEST = "benchmarks/autoscientist_deep_egfr_nsclc_resistance_case.json"
DEFAULT_CASE_ID = "egfr_osimertinib_nsclc_resistance_deep"
DEFAULT_TEMPLATES = [
    "resistance_mechanism_dossier",
    "bypass_pathway_graph",
    "biomarker_and_cohort_validation",
    "combination_strategy_and_experiment_plan",
]
DEFAULT_ABLATIONS = ["full", "plain_llm", "no_public_tools", "no_memory", "no_sciflow"]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the deep EGFR-mutant NSCLC osimertinib-resistance AutoScientist case study."
    )
    parser.add_argument("--mode", choices=["prepare", "smoke", "full"], default="full")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--rubric", default="benchmarks/biotruth_rubric_v0_2.json")
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--template-ids", nargs="*", default=DEFAULT_TEMPLATES)
    parser.add_argument("--ablations", nargs="*", default=DEFAULT_ABLATIONS)
    parser.add_argument("--output-dir", default="outputs/deep_egfr_nsclc_resistance_case")
    parser.add_argument("--case-study-output-dir", default="outputs/deep_egfr_nsclc_resistance_case_studies")
    parser.add_argument("--review-output-dir", default="outputs/review_packages")
    parser.add_argument("--review-package-name", default="autoscientist_deep_egfr_nsclc_resistance_review")
    parser.add_argument("--runbook-path", default="docs/DEEP_EGFR_NSCLC_RESISTANCE_CASE_STUDY_RUNBOOK.md")
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
