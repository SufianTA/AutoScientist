# AutoScientist Deep Analysis and Next Step Decision

Date: 2026-05-25

## Executive Decision

Do not run another broad, unlabeled benchmark. The next paid run should be a strict real run on the labeled BioTruth v0.2 benchmark after the local replay gate passes.

The reason is simple: the old run proved that the infrastructure can execute tools, store memory, train SciFlow Policy, and generate replay artifacts, but it did not have enough scientific decision labels to prove calibrated biomedical usefulness. BioTruth v0.2 is the first benchmark in this repo that directly tests the behavior we care about: support, tentative, conflicting, safety-limited, and abstain.

## What Passed Locally

The local decision replay gate passed:

- Command: `python tools/replay_decision_gate.py --output-dir outputs/local_quality_gates`
- Latest output: `outputs/local_quality_gates/decision_replay_gate_1779728242.json`
- Status: `passed`
- Accuracy: `1.0`
- Cases: `10`
- Coverage:
  - `support_allowed`: 4
  - `tentative_only`: 3
  - `conflicting`: 2
  - `abstain`: 1
- Edge cases covered:
  - real APP Alzheimer conflicting case
  - real NOD2 Crohn moderate case
  - real BRAF melanoma strong case
  - real TNF rheumatoid arthritis strong case
  - target-level-only tractability
  - direct negative translation
  - insufficient grounding
  - safety-limited but supportable evidence
  - PubMed query-placeholder false positives

This matters because the prior paid canary exposed exactly these calibration bugs. The fixed system now catches them without another paid run.

## What The Previous Pod Run Actually Proved

The 4-case RunPod canary proved infrastructure value, not full scientific-discovery validity.

Strong evidence from the run:

- Strict real execution completed.
- Public biomedical tools executed in every full run.
- ToolUniverse executed in every full run.
- Local memory/replay executed in every full run.
- SciFlow Policy executed and changed retrieval depth.
- The system generated a large SciState Graph:
  - 4,492 nodes
  - 32,992 edges
  - 620 hypotheses
  - 1,000 entities
  - 1,000 experiments
  - 12 tools
- Neural SciFlow Policy trained on 45,524 examples:
  - holdout top-1: 0.8471
  - holdout top-3: 0.9853
  - MRR: 0.9106
  - majority baseline top-1: 0.2205

But the run also exposed a serious scientific calibration problem:

- Old full decision accuracy was 2/4.
- APP Alzheimer was incorrectly marked `support_allowed`.
- NOD2 Crohn was incorrectly marked `support_allowed`.

That is why the current local replay gate is important: it specifically verifies that the fixed decision layer now produces:

- APP Alzheimer: `conflicting`
- NOD2 Crohn: `tentative_only`
- BRAF melanoma: `support_allowed`
- TNF rheumatoid arthritis: `support_allowed`

## What Changed Conceptually

The system is no longer just asking whether evidence exists. It now asks what kind of evidence exists.

The important distinctions are:

- Disease-specific clinical efficacy is different from generic target tractability.
- Safety or resistance caveats should not automatically invalidate a strong target.
- Direct negative efficacy or failed translation should change the final decision.
- PubMed query text should not be counted as evidence.
- Strong association or literature volume is not the same as actionability.

This is exactly the kind of calibration a biomedical reviewer will care about.

## Benchmark Readiness

The correct benchmark for the next run is:

- Manifest: `benchmarks/autoscientist_biotruth_v0_2.json`
- Rubric: `benchmarks/biotruth_rubric_v0_2.json`
- Prepared task output:
  - `outputs/local_preflight/prepare_v02_next/20260525_170311/benchmark_tasks.json`
- Prepared task count: 48
- Prepared acceptance: passed

BioTruth v0.2 is better than the older manifests because it has explicit labels:

- `strong_support`: 3
- `moderate_support`: 2
- `weak_support`: 1
- `conflicting`: 2
- `safety_limited`: 2
- `insufficient_evidence`: 2

Expected decision coverage:

- `support_allowed`: 3 cases
- `tentative_only`: 5 cases
- `conflicting`: 2 cases
- `abstain`: 2 cases

This makes it a much better test of scientific behavior than just running many target-disease pairs with no clear expected outcome.

## What Not To Do Next

Do not run the old 100-task v0.1 benchmark as the primary result.

Why:

- It is broader but less scientifically labeled.
- It mostly measures execution and evidence retrieval.
- It does not cleanly test abstention, conflict, safety-limited cases, or overclaiming.
- It could generate impressive-looking artifacts without proving the main claim.

Do not train a larger model yet.

Why:

- The current weak point is not model size.
- The weak point is decision validation and scientific scoring.
- More training without better labels would make the system look better internally without proving it is scientifically better.

Do not claim autonomous discovery yet.

What we can claim now:

- AutoScientist is an auditable biomedical hypothesis-generation and evidence-grading workbench.
- It uses public biomedical tools, ToolUniverse/OpenTargets, persistent memory, replay, policy guidance, and calibrated decision gates.

What we cannot honestly claim yet:

- It discovers novel biology.
- It is expert-validated.
- It reliably accelerates science across broad domains.

## Recommended Next Paid Run

Run a strict real BioTruth v0.2 benchmark with 48 tasks.

Recommended command:

```bash
python tools/run_biotruth_pipeline.py \
  --mode full \
  --skip-build \
  --manifest benchmarks/autoscientist_biotruth_v0_2.json \
  --rubric benchmarks/biotruth_rubric_v0_2.json \
  --limit 48 \
  --ablations full plain_llm no_memory no_public_tools no_sciflow \
  --llm-provider anthropic \
  --llm-model claude-sonnet-4-6 \
  --llm-api-key-env-var ANTHROPIC_KEY \
  --strict-real-run \
  --require-expected-integrations \
  --min-full-completion-rate 1.0 \
  --min-full-mean-score 80 \
  --min-state-graph-nodes 1 \
  --score-mode heuristic \
  --train-neural-policy \
  --neural-epochs 120
```

Use `--score-mode heuristic` for the first full run to avoid judge API cost and quota failures. If the run passes, export packets for expert or later judge scoring.

## Success Criteria For The Next Run

The run is worth sharing only if these pass:

- Full runtime completion: 48/48.
- Required integrations present in full runs:
  - public biomedical tools
  - ToolUniverse/OpenTargets
  - SciFlow Policy
  - SciState Graph
  - replay/provenance
- Decision calibration:
  - full decision accuracy should be at least 0.80.
  - no catastrophic support of `conflicting` or `insufficient_evidence` cases.
- BioTruth heuristic scoring:
  - full should beat `plain_llm`.
  - full should beat `no_public_tools`.
  - full should beat or at least materially improve over `no_sciflow` on evidence depth, tool coverage, or critical failures.
- Critical failure rate:
  - ideally 0.
  - acceptable maximum: 0.05.
- Review package generated:
  - benchmark summary
  - BioTruth score packets
  - analysis
  - replay artifacts
  - state graph
  - policy package

## What To Analyze After The Run

The important question is not just whether scores are higher. The real question is whether the system makes better scientific decisions.

Analyze:

- Does it abstain when evidence is insufficient?
- Does it mark conflicting cases as conflict instead of support?
- Does it keep moderate and safety-limited cases tentative?
- Does it support strong cases without ignoring safety caveats?
- Does ToolUniverse add evidence that changes the decision or just more text?
- Does SciFlow Policy increase useful evidence depth or just tool calls?
- Does memory/replay create auditable continuity?
- Where does the system overclaim?
- Where does it underclaim?
- Which tool families contribute the most useful evidence?

## Best Shareable Story If The Run Passes

The strongest honest story is:

AutoScientist is a persistent biomedical evidence-and-hypothesis runtime that combines live public biomedical tools, ToolUniverse/OpenTargets, calibrated scientific decision gates, replayable provenance, SciState memory, and a learned SciFlow workflow policy. Its value is not replacing frontier models; its value is forcing biomedical agents to operate through auditable evidence, memory, counterevidence, and reproducible scientific decision boundaries.

That is a credible infrastructure story.

## Best Shareable Story If The Run Fails

If the run fails, the project is still valuable, but the claim changes:

AutoScientist is a strong research scaffold and diagnostic environment for building biomedical AI-scientist systems, and the benchmark identifies where frontier-model outputs overclaim or fail to handle evidence correctly.

That is still respectable because it gives us a real failure analysis, not a demo.

## Immediate Next Step

Before starting the pod, run this locally:

```bash
python tools/replay_decision_gate.py --output-dir outputs/local_quality_gates
```

Only proceed to the pod if it passes.

Then run the 48-task BioTruth v0.2 command above.

