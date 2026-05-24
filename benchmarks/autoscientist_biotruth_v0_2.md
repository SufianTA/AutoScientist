# AutoScientist-BioTruth v0.2

Manifest: `benchmarks\autoscientist_biotruth_v0_2.json`
Expanded task JSONL: `benchmarks\autoscientist_biotruth_v0_2_tasks.jsonl`
Cases: `12`
Templates: `4`
Expanded tasks: `48`
Open Targets matched cases: `10/12`

## Domains

- `autoimmune_inflammation`: 4
- `neurodegeneration`: 4
- `oncology`: 3
- `rare_mendelian`: 1

## Gold Labels

- `conflicting`: 2
- `insufficient_evidence`: 2
- `moderate_support`: 2
- `safety_limited`: 2
- `strong_support`: 3
- `weak_support`: 1

## Cases

| Case | Domain | Label | Expected decision | Target | Disease | Open Targets | PubMed | Evidence availability |
| --- | --- | --- | --- | --- | --- | ---: | ---: | --- |
| `tnf_rheumatoid_arthritis_strong` | autoimmune_inflammation | strong_support | support_allowed | TNF | rheumatoid arthritis | 0.642464 | 13624 | moderate |
| `braf_melanoma_strong` | oncology | strong_support | support_allowed | BRAF | melanoma | 0.818553 | 9091 | high |
| `cftr_cystic_fibrosis_strong` | rare_mendelian | strong_support | support_allowed | CFTR | cystic fibrosis | 0.913354 | 14304 | high |
| `nod2_crohn_moderate` | autoimmune_inflammation | moderate_support | tentative_only | NOD2 | Crohn disease | 0.790001 | 1598 | high |
| `apoe_alzheimer_moderate` | neurodegeneration | moderate_support | tentative_only | APOE | Alzheimer disease | 0.683406 | 14747 | high |
| `ptpn22_rheumatoid_arthritis_weak` | autoimmune_inflammation | weak_support | tentative_only | PTPN22 | rheumatoid arthritis | 0.674569 | 405 | high |
| `app_alzheimer_conflicting` | neurodegeneration | conflicting | conflicting | APP | Alzheimer disease | 0.804254 | 16321 | high |
| `kras_pancreatic_cancer_conflicting` | oncology | conflicting | conflicting | KRAS | pancreatic cancer | 0.614574 | 5638 | moderate |
| `lrrk2_parkinson_safety_limited` | neurodegeneration | safety_limited | tentative_only | LRRK2 | Parkinson disease | 0.769702 | 3631 | high |
| `htt_huntington_safety_limited` | neurodegeneration | safety_limited | tentative_only | HTT | Huntington disease | 0.689266 | 4179 | high |
| `egfr_rheumatoid_arthritis_insufficient` | autoimmune_inflammation | insufficient_evidence | abstain | EGFR | rheumatoid arthritis | None | 235 | low |
| `cftr_melanoma_insufficient` | oncology | insufficient_evidence | abstain | CFTR | melanoma | None | 5 | low |

## Caveats

- This benchmark scores target-disease reasoning quality; it does not prove new biological discovery.
- Open Targets association scores are public ranking heuristics and must not be treated as clinical confidence.
- PubMed counts are evidence-availability signals, not evidence-quality labels.
- Final credibility requires expert or rubric-judge scoring over the exported answer packets.