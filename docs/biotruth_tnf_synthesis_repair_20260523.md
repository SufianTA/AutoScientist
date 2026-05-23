# BioTruth TNF/IBD Synthesis Repair Run

Date: 2026-05-23

## Purpose

This run tested whether AutoScientist can produce an auditable, biologically grounded target-disease analysis for TNF in inflammatory bowel disease using live public biomedical tools, ToolUniverse/OpenTargets, SciFlow workflow policy, persistent memory/replay, and a neural workflow policy trained from accumulated traces.

## Code Revisions Tested

- `28fbe3b` surfaced benchmark public context as answer evidence, including Open Targets association labels and target tractability.
- `a9f386b` tightened evidence synthesis by preventing irrelevant PubMed results from becoming claim support, improving clinical-precedence framing, and making experiment plans target residual uncertainty instead of rediscovering established target validity.

## Main Focused Repair Result

Run directory on pod:

`/workspace/AutoScientist/outputs/autoscientist_bench/20260523_071929`

Local review package:

`pod_artifacts/autoscientist_biotruth_tnf_synthesis_repair_with_judge.zip`

Summary:

- Tasks: 2 focused templates, `mechanism_safety_review` and `experiment_decision_plan`.
- Full-runtime completion: 2/2.
- Strict real gates: passed.
- Neural workflow policy holdout top-1: 0.8054.
- State graph after run: 2,832 nodes, 13,205 edges, 304 hypotheses, 608 entities, 999 experiments, 9 tools.
- Gemini judge mean weighted score: 95.5.
- Gemini judge pass rate: 1.0.
- Critical failure rate: 0.0.
- Evidence certainty: high for both judged tasks.

Per-task judge scores:

| Task | Judge Score | Passed | Critical Failures |
| --- | ---: | --- | --- |
| `tnf_inflammatory_bowel_disease__experiment_decision_plan__r1` | 97.0 | yes | none |
| `tnf_inflammatory_bowel_disease__mechanism_safety_review__r1` | 94.0 | yes | none |

## Earlier Diagnostic Run

Run directory on pod:

`/workspace/AutoScientist/outputs/autoscientist_bench/20260523_065613`

Local review package:

`pod_artifacts/autoscientist_biotruth_tnf_public_evidence_repair_with_judge.zip`

Summary:

- Tasks: 4 TNF/IBD templates across full runtime.
- Internal full-runtime score: 100.
- Heuristic BioTruth full score: 88.0.
- Gemini judge mean weighted score: 63.0.
- Gemini judge pass rate: 0.5.
- This run exposed the remaining synthesis bug: public evidence was retrieved, but some outputs still framed TNF/IBD as a new candidate target instead of an established anti-TNF clinical-precedence case.

## Honest Interpretation

The system now demonstrates real value on a focused biomedical target-disease case: live evidence, public labels, ToolUniverse/OpenTargets traces, memory/replay, policy-controller traces, and external judge scoring all produce inspectable artifacts.

This is not yet a broad scientific-discovery claim; the next credible step is the full 100-task BioTruth run across diverse therapeutic areas, with full/no-memory/no-public-tools/no-SciFlow ablations and judge scoring.

## Reproduction Commands

Focused repair run:

```bash
python tools/run_biotruth_pipeline.py \
  --mode smoke \
  --case-ids tnf_inflammatory_bowel_disease \
  --template-ids mechanism_safety_review experiment_decision_plan \
  --limit 2 \
  --ablations full \
  --llm-provider gemini \
  --llm-model gemini-2.5-flash \
  --llm-api-key-env-var GEMINI_API_KEY \
  --strict-real-run \
  --train-neural-policy \
  --neural-epochs 20 \
  --score-mode heuristic \
  --disable-qworld
```

External judge:

```bash
python tools/score_biomedical_correctness.py \
  --bench-dir outputs/autoscientist_bench/20260523_071929 \
  --mode judge \
  --ablations full \
  --max-results 2 \
  --llm-provider gemini \
  --llm-model gemini-2.5-flash \
  --llm-max-tokens 8192 \
  --output-dir outputs/autoscientist_bench/20260523_071929/biotruth_judge_full
```

