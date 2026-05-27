#!/usr/bin/env python3
"""
AutoScientist Showcase Case Study Runner
=========================================

Runs one full-capability cancer case study. No benchmarks, no ablations, no scoring
comparisons. One run. Maximum capability. A clean scientific output you can show.

Usage examples
--------------
  # Run the default case (EGFR-mutant NSCLC resistance) with auto-detected LLM:
  python -m tools.run_showcase

  # Pick a specific case:
  python -m tools.run_showcase --case egfr_osimertinib_resistance

  # Use a custom objective:
  python -m tools.run_showcase --objective "Evaluate PIK3CA H1047R as a target in HR+/HER2- breast cancer."

  # Explicit LLM:
  python -m tools.run_showcase --llm-provider anthropic --llm-api-key-env-var ANTHROPIC_API_KEY

Available cases
---------------
  kras_g12c_nsclc              KRAS G12C in NSCLC — covalent inhibitors, resistance mechanisms
  egfr_osimertinib_resistance  EGFR osimertinib resistance in NSCLC
  braf_v600e_melanoma          BRAF V600E in melanoma — targeted therapy and adaptive resistance
  ret_fusion_thyroid           RET fusions in thyroid cancer
  met_exon14_nsclc             MET exon 14 skipping in NSCLC
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from app.env import load_environment
from app.services.local_runner import (
    configure_console_io,
    paint,
    render_progress_event,
    run_question,
)
from app.routes.reports import render_markdown_report


# ── Curated showcase cases ─────────────────────────────────────────────────────

SHOWCASE_CASES: dict[str, dict[str, Any]] = {
    "kras_g12c_nsclc": {
        "title": "KRAS G12C Inhibition in NSCLC",
        "subtitle": "Covalent inhibitor clinical precedence, resistance mechanisms, and combination strategy",
        "objective": (
            "Generate a comprehensive mechanistic and translational hypothesis dossier for KRAS G12C "
            "pathway inhibition in NSCLC (non-small cell lung cancer). Synthesize: "
            "(1) the established clinical precedence for covalent KRAS G12C inhibitors including sotorasib "
            "and adagrasib, distinguishing approved indications from unresolved questions about response "
            "durability, resistance, and patient selection; "
            "(2) primary resistance mechanisms driven by co-mutations in STK11, KEAP1, and SMAD4, and "
            "acquired resistance via secondary KRAS mutations, RTK bypass signaling through EGFR and MET "
            "upregulation, and RAS pathway reactivation through SOS1 or RAF alterations; "
            "(3) rational combination strategies targeting the bypass vulnerabilities — SOS1 inhibition, "
            "MEK inhibition, immunotherapy co-administration — and the evidence basis for each; "
            "(4) patient stratification biomarkers that predict benefit versus resistance; "
            "and (5) ranked next validation experiments that would most change the clinical development "
            "strategy, distinguishing experiments that address target validity from those addressing "
            "resistance, safety, and patient-selection gaps."
        ),
        "config": {
            "evidence_strictness": "strict",
            "strategy_repair_max_queries": 4,
            "agent_count": 8,
            "llm_max_tokens": 1400,
        },
    },
    "egfr_osimertinib_resistance": {
        "title": "EGFR Osimertinib Resistance in NSCLC",
        "subtitle": "Third-generation EGFR inhibitor acquired resistance mechanisms",
        "objective": (
            "Analyze a complex acquired-resistance scenario after first-line osimertinib in EGFR-mutant "
            "NSCLC and produce a ranked, audit-ready research strategy rather than a treatment "
            "recommendation. Synthesize evidence on: "
            "(1) on-target resistance through EGFR C797S, EGFR amplification, secondary EGFR alterations, "
            "and T790M/C797S cis-versus-trans clone phasing; "
            "(2) bypass resistance via MET amplification, HER2/ERBB2 amplification, RET or ALK fusion "
            "emergence, BRAF V600E, KRAS/NRAS alterations, and PI3K pathway activation; "
            "(3) cell-state and lineage changes including AXL-high EMT-like transition, small-cell "
            "transformation, and squamous transformation; "
            "(4) anatomical or pharmacologic resistance contexts, including CNS sanctuary progression "
            "and exposure-limited resistance hypotheses; "
            "(5) fourth-generation EGFR inhibitors and rational combination strategies under clinical "
            "evaluation, with explicit safety and trial-design caveats; "
            "(6) biomarker and cohort validation using ctDNA, paired pre/post-treatment biopsy, "
            "copy-number profiling, fusion detection, single-cell or spatial assays where relevant; "
            "and (7) ranked next experiments distinguishing driver resistance mechanisms from bystander "
            "alterations, with controls, failure gates, and confidence-update criteria."
        ),
        "config": {
            "evidence_strictness": "strict",
            "strategy_repair_max_queries": 4,
            "agent_count": 8,
            "llm_max_tokens": 1400,
        },
    },
    "braf_v600e_melanoma": {
        "title": "BRAF V600E Targeted Therapy in Melanoma",
        "subtitle": "Combination strategies, adaptive resistance, and immunotherapy sequencing",
        "objective": (
            "Synthesize the scientific rationale and clinical evidence for BRAF V600E targeting in "
            "melanoma. Cover: "
            "(1) established clinical precedence for BRAF/MEK inhibitor combinations — dabrafenib plus "
            "trametinib, vemurafenib plus cobimetinib — distinguishing approved settings from ongoing "
            "questions about sequencing and durability; "
            "(2) adaptive and acquired resistance mechanisms including MAPK pathway reactivation via "
            "BRAF amplification, NRAS mutation, MEK1/2 mutation, and paradoxical ERK activation; "
            "(3) tumor microenvironment contributions to resistance and the rationale for immunotherapy "
            "combination — anti-PD-1, anti-LAG-3, and triplet strategies; "
            "(4) biomarkers predicting benefit versus intrinsic resistance including tumor mutational "
            "burden and immune infiltration signatures; "
            "and (5) validation experiments distinguishing MAPK-driven adaptive resistance from "
            "immune-mediated resistance that would inform combination trial design."
        ),
        "config": {
            "evidence_strictness": "strict",
            "strategy_repair_max_queries": 3,
            "agent_count": 8,
            "llm_max_tokens": 1400,
        },
    },
    "ret_fusion_thyroid": {
        "title": "RET Fusions and Mutations in Thyroid Cancer",
        "subtitle": "Selective RET inhibition, resistance mutations, and patient selection",
        "objective": (
            "Generate a hypothesis dossier for RET kinase inhibition in RET-fusion-driven papillary "
            "thyroid cancer and RET-mutant medullary thyroid cancer. Synthesize: "
            "(1) clinical precedence for selective RET inhibitors selpercatinib and pralsetinib, "
            "distinguishing their activity in fusion-positive versus point-mutation disease; "
            "(2) acquired resistance mechanisms including solvent-front kinase domain mutations "
            "G810R, G810S, G810C and the structural basis for each; "
            "(3) comparison with non-selective multikinase inhibitors cabozantinib and vandetanib — "
            "activity, toxicity, and resistance overlap; "
            "(4) patient stratification by fusion partner identity and mutation hotspot as predictors "
            "of depth and duration of response; "
            "and (5) next experiments to validate combination strategies targeting the bypass and "
            "resistance mutation vulnerabilities, prioritizing those that distinguish primary from "
            "acquired resistance."
        ),
        "config": {
            "evidence_strictness": "strict",
            "strategy_repair_max_queries": 3,
            "agent_count": 8,
            "llm_max_tokens": 1400,
        },
    },
    "met_exon14_nsclc": {
        "title": "MET Exon 14 Skipping in NSCLC",
        "subtitle": "MET pathway inhibition, exon 14 vs amplification, and resistance",
        "objective": (
            "Generate a mechanistic hypothesis for MET exon 14 skipping mutation as a therapeutic "
            "target in NSCLC. Synthesize: "
            "(1) the clinical precedence for MET inhibitors capmatinib and tepotinib in MET exon 14-"
            "positive NSCLC, including response rates and durability from pivotal trials; "
            "(2) the biological distinction between MET exon 14 skipping and MET amplification as "
            "predictive biomarkers — mechanism, predictive value, and cross-response; "
            "(3) acquired resistance mechanisms including secondary MET kinase domain mutations "
            "D1228N, D1228H, and Y1230C, and bypass resistance via KRAS mutation and EGFR "
            "upregulation; "
            "(4) patient stratification strategies differentiating exon 14 skipping driver tumors "
            "from MET amplification secondary to EGFR resistance; "
            "and (5) ranked validation experiments for combination strategies addressing the most "
            "common resistance mechanisms."
        ),
        "config": {
            "evidence_strictness": "strict",
            "strategy_repair_max_queries": 3,
            "agent_count": 8,
            "llm_max_tokens": 1400,
        },
    },
}

DEFAULT_CASE = "egfr_osimertinib_resistance"


# ── LLM auto-detection ─────────────────────────────────────────────────────────

def detect_llm() -> tuple[str, str, str]:
    """Auto-detect available LLM from environment variables. Returns (provider, model, key_env_var)."""
    if os.getenv("ANTHROPIC_KEY"):
        return "anthropic", "claude-sonnet-4-6", "ANTHROPIC_KEY"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic", "claude-sonnet-4-6", "ANTHROPIC_API_KEY"
    if os.getenv("OPENAI_API_KEY"):
        return "openai", "gpt-4.1", "OPENAI_API_KEY"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini", "gemini-3-flash-preview", "GEMINI_API_KEY"
    return "mock", "mock-scientist", ""


# ── Progress renderer ─────────────────────────────────────────────────────────

_SECTION_HEADERS = {
    "INITIALIZE_FRAMEWORK": "  ▶  System initializing",
    "PLAN_RESEARCH": "  ▶  Planning research strategy",
    "FIND_TOOLS": "  ▶  Selecting evidence tools",
    "EXECUTE_EVIDENCE_COLLECTION": "  ▶  Collecting evidence",
    "SCORE_EVIDENCE": "  ▶  Scoring evidence quality",
    "GENERATE_HYPOTHESES": "  ▶  Generating hypothesis",
    "DEBATE_AND_REVISE": "  ▶  Scientist panel debate",
    "CRITIQUE_AND_REFINE": "  ▶  Critiquing and refining",
    "PROPOSE_EXPERIMENTS": "  ▶  Proposing experiments",
    "GENERATE_REPORT": "  ▶  Generating report",
}

_SEEN_SECTIONS: set[str] = set()


def showcase_progress(event: dict[str, Any], color: bool = True) -> None:
    state = event.get("state_name", "")
    if state in _SECTION_HEADERS and state not in _SEEN_SECTIONS:
        _SEEN_SECTIONS.add(state)
        print(paint(_SECTION_HEADERS[state], "bold", color), flush=True)
    rendered = render_progress_event(event, color=color)
    # Indent the rendered output
    for line in rendered.splitlines():
        if line.strip():
            print("    " + line, flush=True)


# ── Showcase report writer ─────────────────────────────────────────────────────

def write_showcase_report(result: dict[str, Any], path: Path, case_title: str, case_subtitle: str) -> None:
    """Write the full showcase markdown report with a rich header."""
    report = result["report"]
    hypothesis = report["hypothesis"]
    evidence = report.get("evidence", [])
    experiments = report.get("experiments") or report.get("next_experiments") or []

    header_lines = [
        f"# {case_title}",
        f"### {case_subtitle}",
        "",
        "---",
        "",
        f"**Run ID:** `{result['run_id']}`  ",
        f"**Status:** `{result['status']}`  ",
        f"**Confidence:** `{result['final_confidence']}`  ",
        f"**Agent steps:** {result['trace_summary']['agent_steps']}  ",
        f"**Tool calls:** {result['trace_summary']['tool_calls']}  ",
        f"**Evidence items:** {len(evidence)}  ",
        f"**Experiments proposed:** {len(experiments)}  ",
        "",
        "---",
        "",
    ]
    body = render_markdown_report(report)
    # Replace the generic title line (first line) with our rich header
    body_lines = body.splitlines()
    # Skip the first line of the default report (it's the hypothesis title we already have)
    if body_lines and body_lines[0].startswith("# "):
        body_lines = body_lines[1:]
    final = "\n".join(header_lines) + "\n" + "\n".join(body_lines) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(final, encoding="utf-8")


def write_provenance(result: dict[str, Any], path: Path) -> None:
    """Write the full JSON provenance for audit and deep inspection."""
    provenance = {
        "run_id": result["run_id"],
        "status": result["status"],
        "final_confidence": result["final_confidence"],
        "trace_summary": result["trace_summary"],
        "provenance": result["provenance"],
        "report": result["report"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(provenance, indent=2, default=str), encoding="utf-8")


# ── Showcase summary printer ───────────────────────────────────────────────────

def print_showcase_summary(result: dict[str, Any], report_path: Path, provenance_path: Path, color: bool = True) -> None:
    report = result["report"]
    hypothesis = report.get("hypothesis", {})
    evidence = report.get("evidence", [])
    experiments = report.get("experiments") or report.get("next_experiments") or []
    strategy = report.get("scientific_strategy", {})
    readiness = strategy.get("readiness", {})
    gaps = strategy.get("gaps", [])
    board_posts = report.get("board_posts", [])
    hyp_post = next((p["content"] for p in board_posts if p.get("post_type") == "hypothesis"), {})
    debate = hyp_post.get("agent_debate", {})
    positions = debate.get("scientist_positions", [])
    votes = [p.get("vote", "review") for p in positions]
    support_votes = sum(1 for v in votes if v in {"support", "support_with_limits"})
    revise_votes = sum(1 for v in votes if v in {"revise", "abstain"})
    claim_graph = report.get("claim_graph", {})
    claims = claim_graph.get("claims", [])

    print("", flush=True)
    print(paint("━" * 60, "cyan", color), flush=True)
    print(paint("  SHOWCASE RUN COMPLETE", "bold", color), flush=True)
    print(paint("━" * 60, "cyan", color), flush=True)
    print(f"  {paint('Hypothesis:', 'bold', color)} {hypothesis.get('title', '—')}", flush=True)
    print(f"  {paint('Confidence:', 'bold', color)} {result['final_confidence']}", flush=True)
    print(f"  {paint('Evidence collected:', 'bold', color)} {len(evidence)} items", flush=True)
    if evidence:
        label_counts: dict[str, int] = {}
        for item in evidence:
            lbl = item.get("support_label") or "unscored"
            label_counts[lbl] = label_counts.get(lbl, 0) + 1
        label_str = ", ".join(f"{k}: {v}" for k, v in sorted(label_counts.items()))
        print(f"    ({label_str})", flush=True)
    print(f"  {paint('Experiments proposed:', 'bold', color)} {len(experiments)}", flush=True)
    if claims:
        print(f"  {paint('Claim graph:', 'bold', color)} {len(claims)} claims mapped", flush=True)
    if positions:
        print(f"  {paint('Scientist debate:', 'bold', color)} {len(positions)} positions — "
              f"{paint(str(support_votes) + ' support', 'green', color)}, "
              f"{paint(str(revise_votes) + ' revise', 'yellow', color)}", flush=True)
    if readiness:
        print(f"  {paint('Readiness tier:', 'bold', color)} {readiness.get('tier', '—')} "
              f"({readiness.get('score', '?')}/100)", flush=True)
    if gaps:
        critical = [g for g in gaps if g.get("severity") == "critical"]
        if critical:
            print(f"  {paint('Critical gaps:', 'bold', color)} {len(critical)}: "
                  f"{', '.join(g.get('id', '') for g in critical[:3])}", flush=True)
    print("", flush=True)
    print(f"  {paint('Markdown report →', 'green', color)} {report_path}", flush=True)
    print(f"  {paint('JSON provenance →', 'dim', color)} {provenance_path}", flush=True)
    print(paint("━" * 60, "cyan", color), flush=True)
    print("", flush=True)


# ── Argument parsing ───────────────────────────────────────────────────────────

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AutoScientist Showcase Case Study Runner — single full-capability cancer case.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join([
            "Available cases:",
            *[f"  {k:40s} {v['title']}" for k, v in SHOWCASE_CASES.items()],
        ]),
    )
    parser.add_argument(
        "--case", default=DEFAULT_CASE, choices=list(SHOWCASE_CASES),
        help=f"Showcase case to run (default: {DEFAULT_CASE})",
    )
    parser.add_argument("--objective", default="", help="Override with a custom objective text")
    parser.add_argument("--output-dir", default="outputs/showcase", help="Output directory")
    parser.add_argument("--llm-provider", default="auto",
                        choices=["auto", "anthropic", "openai", "gemini", "openai_compatible", "local_http", "mock"])
    parser.add_argument("--llm-model", default="")
    parser.add_argument("--llm-api-key-env-var", default="")
    parser.add_argument("--llm-base-url", default="")
    parser.add_argument("--llm-max-tokens", type=int, default=0, help="Override token limit (0 = use case default)")
    parser.add_argument("--agents", type=int, default=0, help="Override agent count (0 = use case default)")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--no-stream", action="store_true", help="Suppress live progress streaming")
    parser.add_argument("--dry-run", action="store_true", help="Print config and exit without running")
    return parser.parse_args(argv)


# ── Main ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    load_environment()
    configure_console_io()
    args = parse_args(argv or sys.argv[1:])
    color = not args.no_color

    # ── Resolve case ──
    case = SHOWCASE_CASES[args.case]
    objective = args.objective.strip() or case["objective"]
    case_config = dict(case["config"])

    # ── Resolve LLM ──
    if args.llm_provider == "auto":
        provider, model, key_env = detect_llm()
    else:
        provider = args.llm_provider
        model = args.llm_model
        key_env = args.llm_api_key_env_var

    if args.llm_model:
        model = args.llm_model
    if args.llm_api_key_env_var:
        key_env = args.llm_api_key_env_var

    if not model:
        model = {
            "anthropic": "claude-sonnet-4-6",
            "openai": "gpt-4.1",
            "gemini": "gemini-3-flash-preview",
            "openai_compatible": "local-model",
            "local_http": "local-http-model",
            "mock": "mock-scientist",
        }.get(provider, "mock-scientist")

    # ── Build run config ──
    run_config: dict[str, Any] = {
        "execution_mode": "inline",
        "real_data_enabled": True,
        "llm_provider": provider,
        "llm_model": model,
        "llm_api_key_env_var": key_env,
        "llm_base_url": args.llm_base_url,
        "require_real_llm": provider != "mock",
        "persist_memory_enabled": True,
        "strategy_repair_enabled": True,
        "txagent_enabled": False,
        **case_config,
    }
    if args.agents > 0:
        run_config["agent_count"] = args.agents
    if args.llm_max_tokens > 0:
        run_config["llm_max_tokens"] = args.llm_max_tokens

    # ── Output paths ──
    ts = int(time.time())
    run_slug = args.case.replace("_", "-") if not args.objective else "custom"
    out_dir = Path(args.output_dir) / f"{run_slug}_{ts}"
    report_path = out_dir / "report.md"
    provenance_path = out_dir / "provenance.json"

    # ── Dry run ──
    if args.dry_run:
        print(json.dumps({
            "case": args.case,
            "title": case["title"],
            "llm": f"{provider}/{model}",
            "config": run_config,
            "output_dir": str(out_dir),
        }, indent=2))
        return 0

    # ── Print header ──
    print("", flush=True)
    print(paint("━" * 60, "cyan", color), flush=True)
    print(paint("  AutoScientist Showcase Case Study", "bold", color), flush=True)
    print(f"  {paint(case['title'], 'bold', color)}", flush=True)
    print(f"  {case['subtitle']}", flush=True)
    print(paint("━" * 60, "cyan", color), flush=True)
    print(f"  LLM:      {paint(f'{provider}/{model}', 'green' if provider != 'mock' else 'yellow', color)}", flush=True)
    if provider == "mock":
        print(f"  {paint('⚠  Mock mode — set ANTHROPIC_API_KEY for full LLM synthesis', 'yellow', color)}", flush=True)
    print(f"  Agents:   {run_config.get('agent_count', 8)}", flush=True)
    print(f"  Evidence: {run_config.get('evidence_strictness', 'strict')} strictness", flush=True)
    print(f"  Output:   {out_dir}", flush=True)
    print(paint("━" * 60, "cyan", color), flush=True)
    print("", flush=True)

    # ── Run ──
    _SEEN_SECTIONS.clear()

    def progress(event: dict[str, Any]) -> None:
        if not args.no_stream:
            showcase_progress(event, color=color)

    started = time.time()
    result = run_question(objective, run_config, progress_callback=progress)
    elapsed = time.time() - started

    print("", flush=True)
    print(f"  Completed in {elapsed:.1f}s", flush=True)

    # ── Write outputs ──
    write_showcase_report(result, report_path, case["title"], case["subtitle"])
    write_provenance(result, provenance_path)

    # ── Print summary ──
    print_showcase_summary(result, report_path, provenance_path, color=color)

    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
