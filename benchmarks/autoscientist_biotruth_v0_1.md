# AutoScientist-BioTruth v0.1

Manifest: `benchmarks\autoscientist_biotruth_v0_1.json`
Expanded task JSONL: `benchmarks\autoscientist_biotruth_v0_1_tasks.jsonl`
Cases: `25`
Templates: `4`
Expanded tasks: `100`
Open Targets matched cases: `25/25`

## Domains

- `autoimmune_inflammation`: 5
- `cardiometabolic`: 2
- `hematology`: 1
- `neurodegeneration`: 5
- `oncology`: 6
- `ophthalmology`: 1
- `rare_mendelian`: 5

## Cases

| Case | Domain | Target | Disease | Open Targets | PubMed | Evidence availability |
| --- | --- | --- | --- | ---: | ---: | --- |
| `il6_rheumatoid_arthritis` | autoimmune_inflammation | IL6 | rheumatoid arthritis | 0.51481 | 6773 | moderate |
| `tnf_inflammatory_bowel_disease` | autoimmune_inflammation | TNF | inflammatory bowel disease | 0.409018 | 11401 | moderate |
| `nod2_crohn_disease` | autoimmune_inflammation | NOD2 | Crohn disease | 0.790001 | 1598 | high |
| `tyk2_psoriasis` | autoimmune_inflammation | TYK2 | psoriasis | 0.731621 | 260 | high |
| `ptpn22_rheumatoid_arthritis` | autoimmune_inflammation | PTPN22 | rheumatoid arthritis | 0.674569 | 405 | high |
| `braf_melanoma` | oncology | BRAF | melanoma | 0.818553 | 9090 | high |
| `egfr_lung_adenocarcinoma` | oncology | EGFR | lung adenocarcinoma | 0.763945 | 9030 | high |
| `erbb2_breast_cancer` | oncology | ERBB2 | breast cancer | 0.695923 | 16166 | high |
| `alk_lung_cancer` | oncology | ALK | lung cancer | 0.609289 | 8086 | moderate |
| `parp1_ovarian_cancer` | oncology | PARP1 | ovarian cancer | 0.617298 | 502 | moderate |
| `kras_pancreatic_cancer` | oncology | KRAS | pancreatic cancer | 0.614574 | 5636 | moderate |
| `cftr_cystic_fibrosis` | rare_mendelian | CFTR | cystic fibrosis | 0.913354 | 14303 | high |
| `smn1_spinal_muscular_atrophy` | rare_mendelian | SMN1 | spinal muscular atrophy | 0.728825 | 1868 | high |
| `acvr1_fibrodysplasia_ossificans_progressiva` | rare_mendelian | ACVR1 | fibrodysplasia ossificans progressiva | 0.816447 | 389 | high |
| `gaa_pompe_disease` | rare_mendelian | GAA | Pompe disease | 0.875887 | 1012 | high |
| `dmd_duchenne_muscular_dystrophy` | rare_mendelian | DMD | Duchenne muscular dystrophy | 0.865885 | 16507 | high |
| `app_alzheimer_disease` | neurodegeneration | APP | Alzheimer disease | 0.804254 | 16321 | high |
| `apoe_alzheimer_disease` | neurodegeneration | APOE | Alzheimer disease | 0.683406 | 14746 | high |
| `lrrk2_parkinson_disease` | neurodegeneration | LRRK2 | Parkinson disease | 0.769702 | 3630 | high |
| `sod1_amyotrophic_lateral_sclerosis` | neurodegeneration | SOD1 | amyotrophic lateral sclerosis | 0.870148 | 5634 | high |
| `htt_huntington_disease` | neurodegeneration | HTT | Huntington disease | 0.689266 | 4179 | high |
| `pcsk9_familial_hypercholesterolemia` | cardiometabolic | PCSK9 | familial hypercholesterolemia | 0.860403 | 1622 | high |
| `slc5a2_type_2_diabetes` | cardiometabolic | SLC5A2 | type 2 diabetes mellitus | 0.635194 | 738 | moderate |
| `f9_hemophilia_b` | hematology | F9 | hemophilia B | 0.888019 | 242 | high |
| `vegfa_age_related_macular_degeneration` | ophthalmology | VEGFA | age-related macular degeneration | 0.460005 | 2675 | moderate |

## Caveats

- This benchmark scores target-disease reasoning quality; it does not prove new biological discovery.
- Open Targets association scores are public ranking heuristics and must not be treated as clinical confidence.
- PubMed counts are evidence-availability signals, not evidence-quality labels.
- Final credibility requires expert or rubric-judge scoring over the exported answer packets.