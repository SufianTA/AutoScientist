# AutoScientist-BioTruth v0.1

Manifest: `benchmarks\autoscientist_biotruth_20_case_gate.json`
Expanded task JSONL: `benchmarks\autoscientist_biotruth_20_case_gate_tasks.jsonl`
Cases: `20`
Templates: `1`
Expanded tasks: `20`
Open Targets matched cases: `20/20`

## Domains

- `autoimmune_inflammation`: 4
- `cardiometabolic`: 2
- `hematology`: 1
- `neurodegeneration`: 3
- `oncology`: 5
- `ophthalmology`: 1
- `rare_mendelian`: 4

## Cases

| Case | Domain | Target | Disease | Open Targets | PubMed | Evidence availability |
| --- | --- | --- | --- | ---: | ---: | --- |
| `il6_rheumatoid_arthritis` | autoimmune_inflammation | IL6 | rheumatoid arthritis | 0.51481 | 6773 | moderate |
| `tnf_inflammatory_bowel_disease` | autoimmune_inflammation | TNF | inflammatory bowel disease | 0.409018 | 11401 | moderate |
| `nod2_crohn_disease` | autoimmune_inflammation | NOD2 | Crohn disease | 0.790001 | 1598 | high |
| `tyk2_psoriasis` | autoimmune_inflammation | TYK2 | psoriasis | 0.731621 | 260 | high |
| `braf_melanoma` | oncology | BRAF | melanoma | 0.818553 | 9090 | high |
| `egfr_lung_adenocarcinoma` | oncology | EGFR | lung adenocarcinoma | 0.763945 | 9030 | high |
| `erbb2_breast_cancer` | oncology | ERBB2 | breast cancer | 0.695923 | 16166 | high |
| `alk_lung_cancer` | oncology | ALK | lung cancer | 0.609289 | 8086 | moderate |
| `parp1_ovarian_cancer` | oncology | PARP1 | ovarian cancer | 0.617298 | 502 | moderate |
| `cftr_cystic_fibrosis` | rare_mendelian | CFTR | cystic fibrosis | 0.913354 | 14303 | high |
| `smn1_spinal_muscular_atrophy` | rare_mendelian | SMN1 | spinal muscular atrophy | 0.728825 | 1868 | high |
| `acvr1_fibrodysplasia_ossificans_progressiva` | rare_mendelian | ACVR1 | fibrodysplasia ossificans progressiva | 0.816447 | 389 | high |
| `dmd_duchenne_muscular_dystrophy` | rare_mendelian | DMD | Duchenne muscular dystrophy | 0.865885 | 16507 | high |
| `app_alzheimer_disease` | neurodegeneration | APP | Alzheimer disease | 0.804254 | 16321 | high |
| `apoe_alzheimer_disease` | neurodegeneration | APOE | Alzheimer disease | 0.683406 | 14746 | high |
| `lrrk2_parkinson_disease` | neurodegeneration | LRRK2 | Parkinson disease | 0.769702 | 3630 | high |
| `pcsk9_familial_hypercholesterolemia` | cardiometabolic | PCSK9 | familial hypercholesterolemia | 0.860403 | 1622 | high |
| `slc5a2_type_2_diabetes` | cardiometabolic | SLC5A2 | type 2 diabetes mellitus | 0.635194 | 738 | moderate |
| `f9_hemophilia_b` | hematology | F9 | hemophilia B | 0.888019 | 242 | high |
| `vegfa_age_related_macular_degeneration` | ophthalmology | VEGFA | age-related macular degeneration | 0.460005 | 2675 | moderate |

## Caveats

- This benchmark scores target-disease reasoning quality; it does not prove new biological discovery.
- Open Targets association scores are public ranking heuristics and must not be treated as clinical confidence.
- PubMed counts are evidence-availability signals, not evidence-quality labels.
- Final credibility requires expert or rubric-judge scoring over the exported answer packets.