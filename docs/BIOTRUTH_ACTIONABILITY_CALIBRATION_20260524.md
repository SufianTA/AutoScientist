# BioTruth Actionability Calibration Repair

Date: 2026-05-24

## Why This Repair Exists

The strict RunPod canary proved that AutoScientist can execute real biomedical workflows with live public evidence, ToolUniverse/OpenTargets, memory, traces, and judge scoring.

The same run also exposed a scientific calibration problem: the runtime was too willing to mark moderate or weak target-disease cases as `support_allowed` when the correct posture was `tentative_only`.

This is not a tooling failure. It is a scientific decision failure.

The key distinction is:

- target-disease association asks whether a target is biologically connected to a disease;
- therapeutic actionability asks whether the evidence is strong enough to support a disease-specific intervention or translational next step;
- clinical safety and translation asks whether support must be downgraded because of patient subtype, delivery, safety, resistance, or failed-trial concerns.

The prior runtime mixed those signals too aggressively.

## Evidence From The RunPod Canary

The 6-case strict-real canary completed and produced real artifacts:

- 6/6 full tasks completed.
- Public biomedical tools executed on every case.
- ToolUniverse/OpenTargets executed on every case.
- Memory and replay artifacts were generated.
- Anthropic judge scoring completed for all 6 packets.

Judge summary:

- Mean weighted score: `79.33`.
- Median weighted score: `81.5`.
- Pass rate: `0.6667`.
- Critical failure rate: `0.0`.

By expected decision:

- `support_allowed`: 3 cases, mean `85.33`, pass rate `1.0`.
- `tentative_only`: 3 cases, mean `73.33`, pass rate `0.3333`.

Interpretation:

- The system performed well on strong positive controls.
- The system did not yet perform well enough on moderate, weak, and safety-limited cases.
- The biggest improvement opportunity is better decision calibration, not more raw tool calls.

## Root Cause

Before this repair, `support_allowed` could be unlocked by broad high-tier evidence such as human genetics, target-disease association, PubMed volume, ToolUniverse/OpenTargets context, or generic clinical/translation terms.

That is not strict enough.

Examples of evidence that should not automatically allow support:

- a risk-gene association without intervention directionality;
- high PubMed count without disease-specific clinical precedence;
- OpenTargets target-disease association without a disease-specific intervention;
- clinical terms that appear only because the query included `clinical precedence`;
- a drug that is approved across other indications but not clearly tied to the current disease context;
- safety-limited biology where the target is plausible but translation risk dominates.

## What Changed

### 1. Added ActionabilityProfile

New runtime service:

```text
apps/api/app/services/actionability_assessor.py
```

It computes an auditable `autosci.actionability_profile.v0.1` object from evidence and traces.

The profile separates:

- target-disease grounded evidence;
- disease-specific clinical evidence;
- disease-specific intervention evidence;
- human or genetic evidence;
- mechanistic evidence;
- literature context;
- safety signals;
- negative or conflicting signals;
- tool grounding;
- clinical terms that appear only in PubMed query context.

The profile recommends one of:

- `support_allowed`;
- `tentative_only`;
- `conflicting`;
- `abstain`.

It does not read benchmark gold labels.

### 2. Tightened Abstention Policy

`evaluate_abstention_policy` now accepts the actionability profile.

The rule is conservative:

- if actionability recommends `abstain`, the final decision is `abstain`;
- if actionability recommends `conflicting`, the final decision is `conflicting` unless already abstaining;
- if actionability recommends `tentative_only`, the final decision cannot remain `support_allowed`;
- support requires both critic support and high actionability.

### 3. Reduced False Clinical Evidence From Query Terms

Evidence hierarchy no longer treats PubMed query wording such as `clinical precedence response` as clinical/translational evidence by itself.

Clinical tiering now requires stronger content signals such as:

- ClinicalTrials.gov;
- interventional trial evidence;
- phase evidence;
- approved-drug or approved-therapy text;
- explicit clinical trial evidence;
- approved indications.

### 4. Propagated Actionability Into Reports And Artifacts

The profile now appears in:

- runtime context;
- hypothesis card;
- critique packet;
- final report;
- API report markdown;
- benchmark score packets;
- run executor outputs.

This makes decision calibration reviewable instead of hidden inside a score.

### 5. Fixed Contradiction Count Compatibility

The contradiction detector emits `finding_count`.

Some scoring and memory code still looked for `contradiction_count`.

The scorer and memory layer now read both fields.

### 6. Strengthened Machine Preflight

`tools/machine_preflight.py` now supports:

```bash
--execute-public-tools
--require-public-tools
```

This directly executes:

- NCBI Gene;
- PubMed;
- ClinicalTrials.gov;
- Reactome;
- openFDA.

The RunPod benchmark script now requires this public-tool execution gate before paid benchmark runs.

## Local Verification

Targeted tests:

```text
27 passed
```

Full test suite:

```text
109 passed, 2 warnings
```

Compile check:

```text
python -m compileall tools apps/api/app agents/app -q
```

Public-tool preflight:

```text
overall_status: warn
public_biomedical_tools: pass
```

The warning was local-only:

- low laptop disk space;
- no local NVIDIA GPU.

The public biomedical tools all executed successfully:

- NCBI Gene: success;
- PubMed: success;
- ClinicalTrials.gov: success;
- Reactome: success;
- openFDA: success.

## What This Should Improve

This repair should improve the cases that previously hurt credibility:

- `moderate_support` cases should more often become `tentative_only`;
- `weak_support` cases should not be over-presented as supported;
- safety-limited cases should retain translation caution;
- insufficient-evidence cases should be more likely to abstain;
- PubMed query wording should stop inflating clinical evidence.

It should not simply inflate scores.

The desired effect is better calibration:

- strong cases stay supported;
- moderate cases stay useful but cautious;
- weak cases are downgraded;
- conflicting cases are flagged;
- insufficient cases abstain.

## What Still Needs Pod Validation

This repair is locally tested and ready for strict-real validation, but not yet proven by a new paid run.

The next RunPod canary should check:

- full completion;
- public-tool preflight;
- ToolUniverse execution preflight;
- live LLM preflight;
- judge scoring;
- per-case actionability decisions;
- whether tentative cases improve without damaging strong controls.

The main success metric is not just higher mean score.

The main success metric is better scientific posture:

- high pass rate on strong positives;
- improved `tentative_only` accuracy on moderate/weak/safety-limited cases;
- zero critical failures;
- no unsupported causal claims;
- complete traces and review package.

## Stop Rule

Do not run a larger benchmark until a small strict-real canary shows:

- all preflight gates pass;
- all selected cases complete;
- no provider quota failures;
- all score packets are generated;
- actionability appears in every report;
- strong cases remain supported;
- tentative/conflicting/abstain cases are no longer over-supported.
