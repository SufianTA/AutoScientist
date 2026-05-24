# BioTruth 26 Successful Output Analysis

Analyzed `26` completed artifacts from the interrupted 20-case gate salvage package.

## Core Finding

The successful subset shows that AutoScientist can produce real, auditable biomedical target-disease review artifacts with live public evidence and ToolUniverse/OpenTargets traces, but the subset is too small and provider-interrupted to claim full benchmark performance.

## Ablation Summary

| Ablation | N | Mean score | Mean strict quality | Mean evidence | Mean tool calls | Mean public calls | Mean ToolUniverse calls | Replay runs | Controller applied |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full | 7 | 100 | 100 | 23.14 | 33.29 | 11.43 | 9.86 | 7 | 7 |
| no_memory | 7 | 100 | 95 | 19.71 | 28.71 | 9.14 | 8.71 | 0 | 0 |
| no_public_tools | 6 | 65 | 54 | 2 | 0 | 0 | 0 | 6 | 0 |
| no_sciflow | 6 | 100 | 95 | 19.83 | 29 | 9.5 | 8.67 | 6 | 0 |

## Case Coverage

| Case | Completed variants | Scores | Evidence counts |
| --- | --- | --- | --- |
| braf_melanoma | full, no_memory, no_public_tools, no_sciflow | [100, 100, 65, 100] | [24, 19, 2, 20] |
| egfr_lung_adenocarcinoma | full, no_memory, no_public_tools, no_sciflow | [100, 100, 65, 100] | [23, 20, 2, 19] |
| erbb2_breast_cancer | full, no_memory | [100, 100] | [23, 20] |
| il6_rheumatoid_arthritis | full, no_memory, no_public_tools, no_sciflow | [100, 100, 65, 100] | [24, 21, 2, 21] |
| nod2_crohn_disease | full, no_memory, no_public_tools, no_sciflow | [100, 100, 65, 100] | [23, 19, 2, 19] |
| tnf_inflammatory_bowel_disease | full, no_memory, no_public_tools, no_sciflow | [100, 100, 65, 100] | [24, 21, 2, 21] |
| tyk2_psoriasis | full, no_memory, no_public_tools, no_sciflow | [100, 100, 65, 100] | [21, 18, 2, 19] |

## What This Tells Us

- Public biomedical tools are the clearest value driver: no-public-tools outputs have much lower evidence and capped scores where complete.
- Full runs generally have the richest evidence/tool traces among completed cases.
- Memory/SciFlow effects are visible operationally through replay/controller metadata, but this subset is not enough for a strong quality claim.
- The system needs provider-budget preflight plus a canary run before any expensive benchmark.

## Best Successful Full Outputs

- `braf_melanoma` (BRAF / melanoma): score 100, strict 100, evidence 24, tool calls 35, confidence 0.88.
- `il6_rheumatoid_arthritis` (IL6 / rheumatoid arthritis): score 100, strict 100, evidence 24, tool calls 35, confidence 0.78.
- `tnf_inflammatory_bowel_disease` (TNF / inflammatory bowel disease): score 100, strict 100, evidence 24, tool calls 35, confidence 0.72.
- `egfr_lung_adenocarcinoma` (EGFR / lung adenocarcinoma): score 100, strict 100, evidence 23, tool calls 33, confidence 0.88.
- `erbb2_breast_cancer` (ERBB2 / breast cancer): score 100, strict 100, evidence 23, tool calls 33, confidence 0.82.
- `nod2_crohn_disease` (NOD2 / Crohn disease): score 100, strict 100, evidence 23, tool calls 33, confidence 0.72.
- `tyk2_psoriasis` (TYK2 / psoriasis): score 100, strict 100, evidence 21, tool calls 29, confidence 0.72.

## Honest Limitation

This is a successful-subset analysis, not a full benchmark result. The full 20-case gate failed because both live LLM providers became unavailable due billing/spending limits.