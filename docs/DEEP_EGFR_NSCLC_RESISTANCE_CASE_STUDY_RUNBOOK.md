# Deep EGFR-Mutant NSCLC Osimertinib Resistance Case Study Runbook

This runbook defines the cancer-resistance showcase run for AutoScientist: a single hard biomedical case run deeply enough to show mechanistic reasoning, public evidence retrieval, memory, replay, policy guidance, and ablation-based evaluation.

## Research Question

Can AutoScientist produce an audit-ready mechanistic explanation and validation strategy for why EGFR-mutant non-small cell lung carcinoma tumors acquire resistance to osimertinib?

The case is anchored on EGFR because EGFR is a high-evidence NSCLC target and osimertinib is clinically established. The actual question is harder: acquired resistance is heterogeneous, so the system must compare EGFR-dependent mutations, bypass signaling, cell-state transition, histologic transformation, and safety-limited combination strategies.

## What This Is Meant To Demonstrate

1. Multi-scale biomedical reasoning across target biology, variants, pathways, drugs, clinical evidence, safety, biomarkers, and experiments.
2. Public-tool execution rather than pure LLM synthesis.
3. A biological mechanism graph linking genes, variants, drugs, pathways, resistance phenotypes, evidence, and uncertainty.
4. Scientific memory that preserves evolving hypotheses, contradictions, weak branches, and confidence updates.
5. SciFlow policy guidance that changes tool selection and reasoning sequence.
6. Ablation evidence showing what is lost without public tools, memory, or policy control.
7. Calibrated uncertainty: the system should propose research hypotheses and validation plans, not patient-treatment recommendations.

## What This Must Not Claim

1. It does not prove a new cancer therapy.
2. It does not replace expert oncology, pathology, pharmacology, or translational review.
3. It does not give clinical advice.
4. It does not prove biological truth from a single automated run.
5. It is a research-triage and evidence-orchestration demonstration.

## Manifest

Use:

```bash
benchmarks/autoscientist_deep_egfr_nsclc_resistance_case.json
```

The manifest contains one deep case:

```text
egfr_osimertinib_nsclc_resistance_deep
```

It expands into four complementary tasks:

1. `resistance_mechanism_dossier`
2. `bypass_pathway_graph`
3. `biomarker_and_cohort_validation`
4. `combination_strategy_and_experiment_plan`

Each task requires public biomedical tools, ToolUniverse, SciFlow policy, and SciState graph/replay artifacts.

## Recommended Pod Run

Run this only after local tests pass and the pod preflight passes.

```bash
cd /workspace/AutoScientist
set -a && . ./.env && set +a
python -u tools/run_cancer_resistance_case_study.py \
  --mode full \
  --manifest benchmarks/autoscientist_deep_egfr_nsclc_resistance_case.json \
  --output-dir outputs/deep_egfr_nsclc_resistance_case \
  --case-study-output-dir outputs/deep_egfr_nsclc_resistance_case_studies \
  --review-output-dir outputs/review_packages \
  --review-package-name autoscientist_deep_egfr_nsclc_resistance_review \
  --llm-provider anthropic \
  --llm-model claude-sonnet-4-6 \
  --llm-api-key-env-var ANTHROPIC_KEY \
  --agent-count 12 \
  --max-runtime-minutes 90 \
  --tool-budget-usd 25 \
  --strategy-repair-max-queries 6 \
  --llm-max-tokens 1200 \
  --ablations full plain_llm no_public_tools no_memory no_sciflow \
  --neural-epochs 60 \
  --strict-real-run
```

This is intentionally not a cheap run. It is designed to produce roughly 20 benchmark artifacts: 4 tasks x 5 ablations.

## Cheaper Smoke Run

If API or RunPod budget is tight, first run:

```bash
python -u tools/run_cancer_resistance_case_study.py \
  --mode full \
  --manifest benchmarks/autoscientist_deep_egfr_nsclc_resistance_case.json \
  --output-dir outputs/deep_egfr_nsclc_resistance_case_smoke \
  --case-study-output-dir outputs/deep_egfr_nsclc_resistance_case_studies_smoke \
  --review-output-dir outputs/review_packages \
  --review-package-name autoscientist_deep_egfr_nsclc_resistance_smoke \
  --llm-provider anthropic \
  --llm-model claude-sonnet-4-6 \
  --llm-api-key-env-var ANTHROPIC_KEY \
  --agent-count 10 \
  --max-runtime-minutes 60 \
  --tool-budget-usd 10 \
  --strategy-repair-max-queries 4 \
  --llm-max-tokens 1000 \
  --template-ids resistance_mechanism_dossier combination_strategy_and_experiment_plan \
  --ablations full plain_llm no_public_tools \
  --neural-epochs 30 \
  --strict-real-run
```

This produces 2 tasks x 3 ablations = 6 benchmark artifacts and should be used if the full run feels too risky.

## Stop Conditions

Stop the run and diagnose before spending more money if any of these happen:

1. Machine preflight fails.
2. API key is missing or provider calls fail before the first artifact.
3. ToolUniverse import or health check fails.
4. Public biomedical tools are unavailable.
5. The first full artifact does not contain public biomedical and ToolUniverse calls.
6. The first full artifact is mostly generic narrative with fewer than 15 evidence items.
7. The first full artifact fails to discuss at least three competing resistance mechanisms.
8. The run produces no files for more than 10 minutes after startup.

## Acceptance Criteria

The run is worth sharing only if all of the following are true:

1. Strict realness gates pass.
2. Full run completion rate is 1.0.
3. Full mean integration score is at least 85.
4. Full BioTruth heuristic score is at least 85.
5. Full critical failure rate is 0.0.
6. Full runs execute public biomedical tools and ToolUniverse.
7. Full runs produce memory/replay artifacts.
8. Full runs produce SciFlow policy traces.
9. The state graph has at least 100 nodes.
10. The final case study includes evidence, weak branches, safety caveats, contradiction tracking, subgroup-specific mechanisms, and experiment gates.

## Expected Outputs

The wrapper creates:

1. Benchmark result JSON files for every task/ablation.
2. `benchmark_summary.md`
3. `biotruth_scores.md`
4. `analysis/*.md`
5. `scistate_graph.json`
6. neural SciFlow policy artifacts
7. discovery case-study Markdown and JSON
8. deep discovery insight report
9. sanitized review package ZIP

## How To Interpret The Result

Strong result:

- Full system outperforms `plain_llm` and `no_public_tools`.
- Full system uses substantially more evidence and tool calls.
- Full system compares EGFR C797S, MET amplification, bypass signaling, EMT/state transition, and histologic transformation rather than naming only one cause.
- Full system preserves uncertainty and safety limitations.
- Full system proposes concrete experiments with controls and failure criteria.
- The case study is understandable to a biomedical reviewer.

Weak result:

- Full system mostly repeats EGFR target validity.
- Resistance mechanisms are shallow or unranked.
- Experiment proposals are generic.
- Safety signals are listed but not used in ranking.
- Ablations are too similar to the full system.

Failure:

- Missing public-tool traces.
- Missing replay/memory.
- Overconfident treatment recommendation.
- No meaningful experiment decision gates.
- Critical BioTruth failures.

## Shareable Framing

Use this language if the run passes:

> AutoScientist was evaluated on a deep EGFR-mutant NSCLC osimertinib-resistance case study requiring public biomedical evidence retrieval, ToolUniverse execution, memory/replay, policy-guided workflow control, mechanism graph construction, safety caveats, and decision-grade experiment planning. The goal was not to claim a new therapy, but to test whether the system can produce an auditable scientific strategy package that accelerates expert review.

## Local Readiness Checklist

Before turning on the pod:

```bash
pytest -q
python tools/run_cancer_resistance_case_study.py --dry-run
python tools/run_biotruth_pipeline.py \
  --mode prepare \
  --skip-build \
  --manifest benchmarks/autoscientist_deep_egfr_nsclc_resistance_case.json \
  --output-dir outputs/local_deep_egfr_nsclc_prepare \
  --allow-mock \
  --skip-review-package
```

Only start the pod after these pass.
