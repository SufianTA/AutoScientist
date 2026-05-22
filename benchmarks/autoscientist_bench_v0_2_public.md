# AutoScientist-Bench Public v0.2

Manifest: `benchmarks\autoscientist_bench_v0_2_public.json`
Dataset JSONL: `benchmarks\autoscientist_bench_v0_2_public.jsonl`
Cases: `21`
Templates: `4`
Expanded tasks: `84`

## Public Sources

- Open Targets Platform GraphQL API: https://api.platform.opentargets.org/api/v4/graphql - Target-disease association and target metadata.
- NCBI E-utilities: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi - PubMed/Gene public literature and gene-count grounding.

## Cases

| Case | Target | Disease | Open Targets | PubMed | Priority |
| --- | --- | --- | ---: | ---: | --- |
| `pcsk9_familial_hypercholesterolemia` | PCSK9 | familial hypercholesterolemia | 0.860403 | 1622 | high |
| `pcsk9_hypercholesterolemia` | PCSK9 | Hypercholesterolemia | 0.826654 | 2753 | high |
| `pcsk9_hypercholesterolemia_autosomal_dominant_3` | PCSK9 | hypercholesterolemia, autosomal dominant, 3 | 0.815822 | 1 | exploratory |
| `cftr_cystic_fibrosis` | CFTR | cystic fibrosis | 0.913354 | 14298 | high |
| `cftr_congenital_bilateral_aplasia_of_vas_deferens_from_cftr_mutation` | CFTR | congenital bilateral aplasia of vas deferens from CFTR mutation | 0.828121 | 72 | high |
| `cftr_hereditary_chronic_pancreatitis` | CFTR | hereditary chronic pancreatitis | 0.711576 | 77 | medium |
| `acvr1_fibrodysplasia_ossificans_progressiva` | ACVR1 | fibrodysplasia ossificans progressiva | 0.816447 | 389 | high |
| `acvr1_myelofibrosis` | ACVR1 | myelofibrosis | 0.554446 | 33 | medium |
| `acvr1_neoplasm` | ACVR1 | neoplasm | 0.519645 | 152 | medium |
| `il6_asthma` | IL6 | asthma | 0.584373 | 2798 | medium |
| `il6_aortic_stenosis` | IL6 | aortic stenosis | 0.529181 | 156 | medium |
| `tnf_psoriatic_arthritis` | TNF | psoriatic arthritis | 0.70855 | 2160 | medium |
| `tnf_rheumatoid_arthritis` | TNF | rheumatoid arthritis | 0.642464 | 13621 | medium |
| `braf_cardiofaciocutaneous_syndrome` | BRAF | cardiofaciocutaneous syndrome | 0.876454 | 115 | high |
| `braf_melanoma` | BRAF | melanoma | 0.818553 | 9084 | high |
| `egfr_non_small_cell_lung_carcinoma` | EGFR | non-small cell lung carcinoma | 0.852433 | 15313 | high |
| `egfr_lung_cancer` | EGFR | lung cancer | 0.766258 | 30692 | high |
| `egfr_lung_adenocarcinoma` | EGFR | lung adenocarcinoma | 0.763945 | 9027 | high |
| `app_alzheimer_disease` | APP | Alzheimer disease | 0.804254 | 16316 | high |
| `app_alzheimer_disease_type_1` | APP | Alzheimer disease type 1 | 0.785681 | 3 | exploratory |
| `app_cerebral_amyloid_angiopathy_app_related` | APP | cerebral amyloid angiopathy, APP-related | 0.751857 | 17 | medium |

## Caveats

- Open Targets association scores rank evidence strength and should not be interpreted as clinical confidence.
- PubMed counts are weak grounding signals; final scoring must inspect evidence quality and provenance.
- This manifest evaluates reproducible tool use, memory, and workflow control, not de novo biological truth.