# Deep Refractory Rheumatoid Arthritis Case Study Runbook

This runbook defines the next pod-scale AutoScientist demonstration: a single hard biomedical case run deeply enough to show agentic scientific execution, not just benchmark pass/fail behavior.

## Research Question

Can AutoScientist produce an audit-ready research strategy for rheumatoid arthritis patients with inadequate response or secondary loss of response to TNF inhibitors and JAK inhibitors?

The case is anchored on TNF because TNF is a well-established rheumatoid arthritis target, but the actual question is harder: identify what to do when the established pathway is insufficient, compare alternative mechanisms, surface safety and non-response caveats, and design decision-grade experiments.

## What This Is Meant To Demonstrate

1. Long-horizon biomedical reasoning across mechanism, translation, safety, and experiment design.
2. Public-tool execution rather than pure LLM synthesis.
3. Memory, replay, and provenance that make the run auditable.
4. SciFlow policy guidance changing the execution trace.
5. Ablation evidence showing what is lost without public tools, memory, or policy control.
6. Calibrated uncertainty: the system must not make treatment recommendations or overclaim discovery.

## What This Must Not Claim

1. It does not prove a new rheumatoid arthritis treatment.
2. It does not replace expert immunology, rheumatology, or translational review.
3. It does not give clinical advice.
4. It does not prove biological truth from a single automated run.
5. It is a research-triage and evidence-orchestration demonstration.

## Manifest

Use:

```bash
benchmarks/autoscientist_deep_ra_refractory_case.json
```

The manifest contains one deep case:

```text
tnf_refractory_rheumatoid_arthritis_deep
```

It expands into four complementary tasks:

1. `refractory_ra_strategy_dossier`
2. `nonresponder_mechanism_map`
3. `repurposing_and_safety_triage`
4. `decision_grade_experiment_plan`

Each task requires public biomedical tools, ToolUniverse, SciFlow policy, and SciState graph/replay artifacts.

## Recommended Pod Run

Run this only after local tests pass and the pod preflight passes.

```bash
cd /workspace/AutoScientist
set -a && . ./.env && set +a
python -u tools/run_deep_case_study.py \
  --mode full \
  --manifest benchmarks/autoscientist_deep_ra_refractory_case.json \
  --output-dir outputs/deep_ra_refractory_case \
  --case-study-output-dir outputs/deep_ra_refractory_case_studies \
  --review-output-dir outputs/review_packages \
  --review-package-name autoscientist_deep_ra_refractory_review \
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

If Anthropic or RunPod budget is tight, first run:

```bash
python -u tools/run_deep_case_study.py \
  --mode full \
  --manifest benchmarks/autoscientist_deep_ra_refractory_case.json \
  --output-dir outputs/deep_ra_refractory_case_smoke \
  --case-study-output-dir outputs/deep_ra_refractory_case_studies_smoke \
  --review-output-dir outputs/review_packages \
  --review-package-name autoscientist_deep_ra_refractory_smoke \
  --llm-provider anthropic \
  --llm-model claude-sonnet-4-6 \
  --llm-api-key-env-var ANTHROPIC_KEY \
  --agent-count 10 \
  --max-runtime-minutes 60 \
  --tool-budget-usd 10 \
  --strategy-repair-max-queries 4 \
  --llm-max-tokens 1000 \
  --template-ids refractory_ra_strategy_dossier repurposing_and_safety_triage \
  --ablations full plain_llm no_public_tools \
  --neural-epochs 30 \
  --strict-real-run
```

This produces 2 tasks x 3 ablations = 6 benchmark artifacts and should be used if the full run feels too risky.

## Stop Conditions

Stop the run and diagnose before spending more money if any of these happen:

1. Machine preflight fails.
2. Anthropic key is missing or provider calls fail before the first artifact.
3. ToolUniverse import or health check fails.
4. Public biomedical tools are unavailable.
5. The first full artifact does not contain public biomedical and ToolUniverse calls.
6. The first full artifact is mostly generic narrative with fewer than 15 evidence items.
7. The run produces no files for more than 10 minutes after startup.

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
10. The final case study includes evidence, weak branches, safety caveats, and experiment gates.

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
- Full system preserves uncertainty and safety limitations.
- Full system proposes concrete experiments with controls and failure criteria.
- The case study is understandable to a biomedical reviewer.

Weak result:

- Full system mostly repeats known TNF biology.
- Alternative mechanisms are shallow.
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

> AutoScientist was evaluated on a deep refractory rheumatoid arthritis case study requiring public biomedical evidence retrieval, ToolUniverse execution, memory/replay, policy-guided workflow control, safety caveats, and decision-grade experiment planning. The goal was not to claim a new therapy, but to test whether the system can produce an auditable scientific strategy package that accelerates expert review.

## Local Readiness Checklist

Before turning on the pod:

```bash
pytest -q
python tools/run_deep_case_study.py --dry-run
python tools/run_biotruth_pipeline.py \
  --mode prepare \
  --skip-build \
  --manifest benchmarks/autoscientist_deep_ra_refractory_case.json \
  --output-dir outputs/local_deep_ra_prepare \
  --allow-mock \
  --skip-review-package
```

Only start the pod after these pass.
