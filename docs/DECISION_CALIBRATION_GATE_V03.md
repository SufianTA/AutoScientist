# Decision Calibration Gate v0.3

This document describes the abstention/calibration repair added after the 2026-05-25 RunPod four-case value benchmark.

## Problem Found

The strict real RunPod benchmark showed that AutoScientist could execute real biomedical workflows with public tools, ToolUniverse, memory replay, and SciFlow policy, but it still failed an important scientific behavior: abstention.

The clearest failure was:

- Case: `egfr_rheumatoid_arthritis_insufficient`
- Expected behavior: `abstain`
- Previous behavior: `support_allowed`
- Failure reason: the actionability layer treated target-level EGFR clinical/drug/safety context as if it were disease-specific support for rheumatoid arthritis.

That is a serious failure mode because a scientific assistant must know when not to make a target-disease support claim.

## Change Made

The abstention policy now includes public target-disease calibration.

The gate considers:

- OpenTargets target-disease association status.
- OpenTargets association score and rank when available.
- Public evidence availability.
- PubMed target-disease count.
- Evidence hierarchy strength.
- Actionability profile counts.
- Query-only clinical/counterevidence context.

The key principle is:

> Target-level drug, clinical, or safety context is not enough to support a disease-specific target claim when public target-disease grounding is weak or absent.

## New Behavior

The gate now emits:

- `support_allowed` only when disease-specific support is sufficiently grounded.
- `tentative_only` when there is partial target-disease evidence but public support is weak.
- `conflicting` when negative or translational counterevidence is substantive.
- `abstain` when public target-disease support is absent or evidence is not enough for a useful support claim.

The implementation is general and does not hardcode any disease, target, or benchmark case.

## Files Changed

- `apps/api/app/services/abstention_policy.py`
  - Added `public_labels` input.
  - Added `calibrate_public_target_disease_support`.
  - Upgraded schema to `autosci.abstention_policy.v0.3`.

- `agents/app/langgraph_workflow.py`
  - Passes benchmark/public labels into the abstention policy during normal runtime.

- `tools/replay_decision_gate.py`
  - Replays saved artifacts through the new public calibration layer.

- `tools/tests/test_contradiction_and_abstention.py`
  - Adds explicit tests for absent public support and weak public support.

- `apps/api/tests/test_api.py`
  - Updates schema expectation to v0.3.

## Verification

Focused tests:

```bash
pytest tools/tests/test_contradiction_and_abstention.py tools/tests/test_replay_decision_gate.py -q
```

Result:

```text
12 passed
```

Full test suite:

```bash
pytest -q
```

Result:

```text
121 passed
```

Replay against exported real RunPod artifacts:

```bash
python tools/replay_decision_gate.py \
  --artifact-dir outputs/runpod_exports/outputs/autoscientist_bench_v02_fourcase_value/20260525_175307 \
  --output-dir outputs/local_quality_gates_after_calibration \
  --min-accuracy 1.0
```

Result:

```text
status: passed
accuracy: 1.0
```

The replay gate included real artifact rows plus synthetic coverage for all four decision classes:

- `support_allowed`
- `tentative_only`
- `conflicting`
- `abstain`

## Expected Impact On Next RunPod Benchmark

The next RunPod validation should rerun the same four-case canary first. The expected improvement is not merely a better score; it should specifically remove the full-system critical abstention failure.

Acceptance target:

- Full completion rate: `1.0`
- Strict realness gates: passed
- Full critical failure rate: `0`
- Abstention accuracy on insufficient-evidence cases: `1.0`
- Full BioTruth score still higher than `plain_llm` and `no_public_tools`
- Public-tool grounding still active in every full run

Only after this canary passes should the larger 20+ task benchmark be run.

## Remaining Risk

This gate improves calibration, but it does not replace expert biological review. The current BioTruth heuristic scorer is still a triage evaluator, not a definitive biomedical truth judge.

The next deeper improvement should combine this deterministic calibration with judge-mode review and expert spot checks.
