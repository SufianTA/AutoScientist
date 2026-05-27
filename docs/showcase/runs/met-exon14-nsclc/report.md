# MET Exon 14 Skipping in NSCLC
### MET pathway inhibition, exon 14 vs amplification, and resistance

---

**Run ID:** `run_decd8cd59704`  
**Status:** `completed`  
**Confidence:** `0.81`  
**Agent steps:** 151  
**Tool calls:** 63  
**Evidence items:** 35  
**Experiments proposed:** 5  

---


Run: `run_decd8cd59704`
Status: `completed`
Confidence: `0.81`
Confidence interpretation: `moderate`

## Candidate Hypothesis

MET has established or clinically precedented target-disease grounding for non-small cell lung cancer. The output should not present this as a new target discovery. Relevant clinical literature titles include: Vebreltinib plus EGFR-TKI for EGFR-mutated NSCLC with MET-driven resistance: A real-world study of Chinese patients.; A Phase II, Open Label, Single-Arm Study on the Efficacy of Cabozantinib in Patients With Advanced/Metastatic Nonsmall Cell Lung Cancer Harboring MET Exon 14 Alterations who Developed Acquired Resistance to Tepotinib or Capmatinib (CAPTURE Trial).; Ensartinib for advanced or metastatic non-small-cell lung cancer with MET exon 14 skipping mutations (EMBRACE): amulti-center, single-arm, phase 2 trial.. The remaining scientific work is to resolve mechanism details, response or resistance biology, safety liabilities, and patient-selection strategy; this is not a claim that a new target has been discovered.

## Scientific Assessment

- Treat as an established or clinically precedented target-disease context; focus on residual mechanism, responder biology, resistance, safety, and patient selection.
- The disease-target rationale is biologically plausible when live/public evidence links MET to non-small cell lung cancer through disease association, pathway, or mechanism records.
- The current claim should remain pathway-level: evidence supports target and mechanism grounding, not clinical efficacy for any intervention unless direct clinical evidence is cited.
- Relevant clinical literature titles include: Vebreltinib plus EGFR-TKI for EGFR-mutated NSCLC with MET-driven resistance: A real-world study of Chinese patients.; A Phase II, Open Label, Single-Arm Study on the Efficacy of Cabozantinib in Patients With Advanced/Metastatic Nonsmall Cell Lung Cancer Harboring MET Exon 14 Alterations who Developed Acquired Resistance to Tepotinib or Capmatinib (CAPTURE Trial).; Ensartinib for advanced or metastatic non-small-cell lung cancer with MET exon 14 skipping mutations (EMBRACE): amulti-center, single-arm, phase 2 trial..
- Candidate molecules or interventions are prioritization leads only; potency, selectivity, exposure, safety, and disease-model response must be tested.

## Key Scientific Claims

- Capmatinib and tepotinib have received regulatory approval for MET exon 14 skipping-altered NSCLC, establishing MET as a clinically validated therapeutic target in this disease.
- Secondary MET kinase-domain mutations, including D1228N and Y1230C, have been identified as acquired resistance mechanisms following treatment with selective MET inhibitors tepotinib and capmatinib, motivating evaluation of cabozantinib in the CAPTURE trial.
- MET amplification is a documented mechanism of acquired resistance to EGFR-TKIs in EGFR-mutated NSCLC, and combination of MET inhibitors with EGFR-TKIs is under real-world clinical investigation in Chinese patient cohorts.
- Ensartinib, a multi-kinase inhibitor, is under evaluation in the EMBRACE phase 2 trial for advanced or metastatic NSCLC harboring MET exon 14 skipping mutations, representing an alternative mechanistic approach to selective MET inhibition.

## Objective Classification

- Primary task: `therapeutic_reasoning`
- Domain: `therapeutics`
- Risk level: `high`
- Capabilities: public_biomedical, tooluniverse, clawinstitute_board, txagent, safety_reviewer, abstention_policy

## Case Capability Plan

**Mechanism branches to resolve:**
- `copy_number`: Copy-number driven resistance
- `rtk_bypass`: RTK or fusion bypass signaling
- `mapk_pi3k_reactivation`: MAPK or PI3K pathway reactivation
- `lineage_transformation`: Lineage or histologic transformation
- `safety_translation`: Safety and translational feasibility

**Validation assays requested by the case:**
- fusion and copy-number profiling

**Capabilities exercised:** case_compilation, public_evidence_retrieval, claim_graph, evidence_coverage_matrix, experiment_gate_scoring, replayable_provenance

## Evaluation Criteria

Score: `0.826` (19/23 points)
- [met] Identifies the primary biomedical entities and objective scope.
- [met] Separates direct evidence from indirect or planning-only evidence.
- [met] States uncertainty and avoids unsupported clinical efficacy or safety claims.
- [met] Includes limitations and concrete validation experiments.
- [met] Reviews intervention-specific safety, contraindication, and translation gaps.
- [met] Explains target-disease relevance without overstating causality.
- [gap] Answers the specific user objective rather than a generic biomedical prompt.

## Abstention Assessment

- Required: `False`
- Allowed output: candidate hypothesis with explicit limitations

## Biomedical Validation Controls

- BioTruth critic: `weak_support` (score: `81.2`)
- Evidence hierarchy: `35` evidence items; `21` high-tier items; score `72.86`
- Contradiction search attempted: `True`; findings `11`
- Abstention policy decision: `support_allowed` with required flag `False`
- Actionability profile: `high` with recommended decision `support_allowed`

## Scientific Strategy

**Readiness tier:** **Experiment ready (with gaps)** (67/100)
> experiment_ready_with_gaps: blocked mainly by claim_graph_evidence_gap (medium).

**Recommended next action:** `run_falsification_and_depth_pass`
> Readiness is experiment_ready_with_gaps; remaining gaps should be challenged before confidence increases.

**Evidence gaps identified:**

- 🟡 **claim_graph_evidence_gap** (medium): The claim graph still has unsupported evidence links: ClinicalTrials.gov: non-small cell lung cancer capmatinib, ClinicalTrials.gov: non-small cell lung cancer tepotinib, ClinicalTrials.gov: small cell lung cancer capmatinib.
  - Recommended tool: `tooluniverse_query_tool`
- 🟡 **evidence_relevance_noise** (medium): A material fraction of retrieved evidence was judged irrelevant to the claim boundary.
  - Recommended tool: `pubmed_literature_search_tool`

## Claim Graph

*6 claims mapped across 35 evidence items.*

### Claim claim_1 — `computational`
> MET has established or clinically precedented target-disease grounding for non-small cell lung cancer.
- ✅ **Supporting:** ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, NCBI Gene, PubChem candidate lookup, PubMed: MET non-small cell lung cancer association clinical biomarker evidence, PubMed: MET non-small cell lung cancer failed trial
- ⬜ **Gaps / irrelevant:** ClinicalTrials.gov: non-small cell lung cancer capmatinib, ClinicalTrials.gov: non-small cell lung cancer tepotinib, ClinicalTrials.gov: small cell lung cancer capmatinib, ClinicalTrials.gov: small cell lung cancer tepotinib

### Claim claim_2 — `computational`
> The output should not present this as a new target discovery.
- ✅ **Supporting:** ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, NCBI Gene, PubChem candidate lookup, PubMed: MET non-small cell lung cancer association clinical biomarker evidence, PubMed: MET non-small cell lung cancer failed trial
- ⬜ **Gaps / irrelevant:** ClinicalTrials.gov: non-small cell lung cancer capmatinib, ClinicalTrials.gov: non-small cell lung cancer tepotinib, ClinicalTrials.gov: small cell lung cancer capmatinib, ClinicalTrials.gov: small cell lung cancer tepotinib

### Claim claim_3 — `computational`
> Relevant clinical literature titles include: Vebreltinib plus EGFR-TKI for EGFR-mutated NSCLC with MET-driven resistance: A real-world study of Chinese patients.
- ✅ **Supporting:** ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, NCBI Gene, PubChem candidate lookup, PubMed: MET non-small cell lung cancer association clinical biomarker evidence, PubMed: MET non-small cell lung cancer failed trial
- ⬜ **Gaps / irrelevant:** ClinicalTrials.gov: non-small cell lung cancer capmatinib, ClinicalTrials.gov: non-small cell lung cancer tepotinib, ClinicalTrials.gov: small cell lung cancer capmatinib, ClinicalTrials.gov: small cell lung cancer tepotinib

### Claim claim_4 — `⚠ no efficacy claim`
> A Phase II, Open Label, Single-Arm Study on the Efficacy of Cabozantinib in Patients With Advanced/Metastatic Nonsmall Cell Lung Cancer Harboring MET Exon 14 Alterations who Developed Acquired Resistance to Tepotinib or Capmatinib (CAPTURE Trial).
- ✅ **Supporting:** ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, NCBI Gene, PubChem candidate lookup, PubMed: MET non-small cell lung cancer association clinical biomarker evidence, PubMed: MET non-small cell lung cancer failed trial
- ⬜ **Gaps / irrelevant:** ClinicalTrials.gov: non-small cell lung cancer capmatinib, ClinicalTrials.gov: non-small cell lung cancer tepotinib, ClinicalTrials.gov: small cell lung cancer capmatinib, ClinicalTrials.gov: small cell lung cancer tepotinib

### Claim claim_5 — `computational`
> Ensartinib for advanced or metastatic non-small-cell lung cancer with MET exon 14 skipping mutations (EMBRACE): amulti-center, single-arm, phase 2 trial..
- ✅ **Supporting:** ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, NCBI Gene, PubChem candidate lookup, PubMed: MET non-small cell lung cancer association clinical biomarker evidence, PubMed: MET non-small cell lung cancer failed trial
- ⬜ **Gaps / irrelevant:** ClinicalTrials.gov: non-small cell lung cancer capmatinib, ClinicalTrials.gov: non-small cell lung cancer tepotinib, ClinicalTrials.gov: small cell lung cancer capmatinib, ClinicalTrials.gov: small cell lung cancer tepotinib

### Claim claim_6 — `⚠ no efficacy claim`
> The remaining scientific work is to resolve mechanism details, response or resistance biology, safety liabilities, and patient-selection strategy
- ✅ **Supporting:** ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, NCBI Gene, PubChem candidate lookup, PubMed: MET non-small cell lung cancer association clinical biomarker evidence, PubMed: MET non-small cell lung cancer failed trial
- ⬜ **Gaps / irrelevant:** ClinicalTrials.gov: non-small cell lung cancer capmatinib, ClinicalTrials.gov: non-small cell lung cancer tepotinib, ClinicalTrials.gov: small cell lung cancer capmatinib, ClinicalTrials.gov: small cell lung cancer tepotinib


## Evidence Coverage Matrix

Coverage score: `0.875` (7 covered, 0 partial, 1 missing)

| Requirement | Status | Matched sources |
| --- | --- | --- |
| Literature evidence | `covered` | PubMed: MET non-small cell lung cancer association clinical biomarker evidence, PubMed: MET non-small cell lung cancer failed trial, PubMed: MET non-small cell lung cancer not associated, PubMed: capmatinib non-small cell lung cancer MET clinical trial response resistance |
| Target-disease association | `covered` | ToolUniverse: OpenTargets_get_associated_targets_by_disease_efoId, ToolUniverse: OpenTargets_get_disease_id_description_by_name, ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name |
| Clinical or trial context | `covered` | ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, PubMed: MET non-small cell lung cancer association clinical biomarker evidence, PubMed: MET non-small cell lung cancer failed trial, PubMed: MET non-small cell lung cancer not associated, PubMed: capmatinib non-small cell lung cancer MET clinical trial response resistance |
| Safety and toxicity context | `covered` | openFDA adverse events: capmatinib, openFDA adverse events: savolitinib, openFDA adverse events: tepotinib |
| Mechanistic pathway evidence | `covered` | PubMed: MET non-small cell lung cancer association clinical biomarker evidence, PubMed: MET non-small cell lung cancer not associated, ToolUniverse: OpenTargets_get_associated_targets_by_disease_efoId, ToolUniverse: OpenTargets_get_disease_id_description_by_name, ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name |
| Contradictions or missing evidence | `covered` | ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, PubMed: MET non-small cell lung cancer failed trial, PubMed: MET non-small cell lung cancer not associated |
| Cell-state or lineage assay evidence | `missing` | none |
| Fusion and copy-number detection | `covered` | ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, PubMed: MET non-small cell lung cancer association clinical biomarker evidence, PubMed: MET non-small cell lung cancer failed trial, PubMed: MET non-small cell lung cancer not associated, PubMed: capmatinib non-small cell lung cancer MET clinical trial response resistance |

## Candidate Intervention Summary

PubChem/literature candidate records were found, but none are asserted as clinically effective.

## Evidence

### Evidence Summary Table

| Source | Label | Score | Evidence |
| --- | --- | --- | --- |
| NCBI Gene | weak_support | 0.61 | NCBI Gene MET: This gene encodes a member of the receptor tyrosine kinase family of proteins and the product of the proto-oncogene MET. The encoded preproprotein is proteolytically processed to generate alpha and beta subunits that are linked via disulfide bonds to form the mature receptor. Further  |
| NCBI Gene | weak_support | 0.61 | NCBI Gene KRAS: This gene, a Kirsten ras oncogene homolog from the mammalian ras gene family, encodes a protein that is a member of the small GTPase superfamily. A single amino acid substitution is responsible for an activating mutation. The transforming protein that results is implicated in various |
| PubMed: MET exon 14 skipping versus MET amplification predictive biomarker mechanism CBL ubiquitin degradation NSCLC | irrelevant | 0.1 | PubMed returned live literature search results for MET exon 14 skipping versus MET amplification predictive biomarker mechanism CBL ubiquitin degradation NSCLC. |
| PubMed: MET exon 14 skipping capmatinib tepotinib NSCLC pivotal trial response rate GEOMETRY VISION | irrelevant | 0.1 | PubMed returned live literature search results for MET exon 14 skipping capmatinib tepotinib NSCLC pivotal trial response rate GEOMETRY VISION. |
| PubMed: acquired resistance MET inhibitor D1228N D1228H Y1230C KRAS EGFR bypass mutation NSCLC | irrelevant | 0.1 | PubMed returned live literature search results for acquired resistance MET inhibitor D1228N D1228H Y1230C KRAS EGFR bypass mutation NSCLC. |
| Reactome: MET | irrelevant | 0.31 | Reactome returned pathway/mechanism records: . |
| Reactome: KRAS | irrelevant | 0.31 | Reactome returned pathway/mechanism records: . |
| Reactome: MET-HGF signaling pathway | irrelevant | 0.31 | Reactome returned pathway/mechanism records: . |
| Reactome: RAS-MAPK signaling pathway | irrelevant | 0.31 | Reactome returned pathway/mechanism records: . |
| PubMed: MET non-small cell lung cancer association clinical biomarker evidence | strong_support | 0.78 | Comprehensive characterization of non-small cell lung cancer of different PD-L1 expression classes: a study of 1,038 Chinese patients.; Complications following small-molecule inhibitors for non-small cell lung cancer.; Targetable driver gene-tumor immune microenvironment axis in non-small cell lung  |
| ClinicalTrials.gov: non-small cell lung cancer MET | strong_support | 0.76 | ClinicalTrials.gov returned translational study records: Study of INC280 in Patients With c-MET Dependent Advanced Solid Tumors (COMPLETED, PHASE1); Activity of Lorlatinib Based on ALK Resistance Mutations Detected on Blood in ALK Positive NSCLC Patients (ACTIVE_NOT_RECRUITING, PHASE2); Proton Based |
| ClinicalTrials.gov: non-small cell lung cancer capmatinib | irrelevant | 0.31 | ClinicalTrials.gov returned translational study records: Study of INC280 in Patients With c-MET Dependent Advanced Solid Tumors (COMPLETED, PHASE1); Managed Access Programs for INC280, Capmatinib (NO_LONGER_AVAILABLE, phase not listed); Special Drug Use-results Surveillance of Tabrecta Tablets (COMP |
| ClinicalTrials.gov: non-small cell lung cancer tepotinib | irrelevant | 0.31 | ClinicalTrials.gov returned translational study records: Lazertinib & Tepotinib for EGFR Mutant NSCLC in MET Overexpressed or Amplified Who Progressed After Lazertinib Treatment (RECRUITING, PHASE2); A Study of Tepotinib Plus Osimertinib in Osimertinib Relapsed MET Amplified NSCLC (INSIGHT 2) (ACTIV |
| PubChem candidate lookup | mechanistic_relevance | 0.46 | PubChem returned candidate/intervention records for: capmatinib, tepotinib, savolitinib, osimertinib, sotorasib, crizotinib. |
| ClinicalTrials.gov: small cell lung cancer MET | strong_support | 0.76 | ClinicalTrials.gov returned translational study records: Study of INC280 in Patients With c-MET Dependent Advanced Solid Tumors (COMPLETED, PHASE1); Activity of Lorlatinib Based on ALK Resistance Mutations Detected on Blood in ALK Positive NSCLC Patients (ACTIVE_NOT_RECRUITING, PHASE2); Proton Based |
| ClinicalTrials.gov: small cell lung cancer capmatinib | irrelevant | 0.31 | ClinicalTrials.gov returned translational study records: Study of INC280 in Patients With c-MET Dependent Advanced Solid Tumors (COMPLETED, PHASE1); Managed Access Programs for INC280, Capmatinib (NO_LONGER_AVAILABLE, phase not listed); Special Drug Use-results Surveillance of Tabrecta Tablets (COMP |
| ClinicalTrials.gov: small cell lung cancer tepotinib | irrelevant | 0.31 | ClinicalTrials.gov returned translational study records: Lazertinib & Tepotinib for EGFR Mutant NSCLC in MET Overexpressed or Amplified Who Progressed After Lazertinib Treatment (RECRUITING, PHASE2); A Study of Tepotinib Plus Osimertinib in Osimertinib Relapsed MET Amplified NSCLC (INSIGHT 2) (ACTIV |
| PubMed: MET D1228N D1228H Y1230C non-small cell lung cancer variant resistance biomarker | irrelevant | 0.1 | PubMed returned live literature search results for MET D1228N D1228H Y1230C non-small cell lung cancer variant resistance biomarker. |
| openFDA adverse events: tepotinib | safety_concern | 0.72 | openFDA returned 219 matching adverse-event reports. Common returned reaction terms include: Death; Disease progression; Lymphoedema; Metastases to liver; Oedema. These are safety signals, not incidence rates or causal proof. |
| openFDA adverse events: capmatinib | safety_concern | 0.72 | openFDA returned 405 matching adverse-event reports. Common returned reaction terms include: Death; Fatigue; Neoplasm progression; Thrombophlebitis; Cellulitis. These are safety signals, not incidence rates or causal proof. |
| openFDA adverse events: savolitinib | safety_concern | 0.72 | openFDA returned 61 matching adverse-event reports. Common returned reaction terms include: Cellulitis; Device related infection; Drug-induced liver injury; Pleural effusion; Subdural haematoma. These are safety signals, not incidence rates or causal proof. |
| PubMed: capmatinib non-small cell lung cancer MET clinical trial response resistance | strong_support | 0.78 | A Phase II, Open Label, Single-Arm Study on the Efficacy of Cabozantinib in Patients With Advanced/Metastatic Nonsmall Cell Lung Cancer Harboring MET Exon 14 Alterations who Developed Acquired Resistance to Tepotinib or Capmatinib (CAPTURE Trial).; Capmatinib plus nazartinib in patients with EGFR-mu |
| ToolUniverse: OpenTargets_get_disease_id_description_by_name | strong_support | 0.76 | OpenTargets_get_disease_id_description_by_name returned OpenTargets search hits: non-small cell lung carcinoma: A group of at least three distinct histological types of lung cancer, including non-small cell squamous cell carcinoma, adenocarcinoma, and large cell carcinoma. Non-small cell lung carcin |
| ToolUniverse: OpenTargets_get_disease_id_description_by_name | strong_support | 0.76 | OpenTargets_get_disease_id_description_by_name returned OpenTargets search hits: small cell lung carcinoma: Small cell lung cancer (SCLC) is a highly aggressive malignant neoplasm, accounting for 10-15% of lung cancer cases, characterized byrapid growth, and early metastasis. SCLC usually manifests  |
| PubMed: MET exon 14 skipping patient stratification EGFR resistance secondary MET amplification combination therapy | irrelevant | 0.1 | PubMed returned live literature search results for MET exon 14 skipping patient stratification EGFR resistance secondary MET amplification combination therapy. |
| ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name | strong_support | 0.76 | OpenTargets_get_drug_chembId_by_generic_name returned OpenTargets search hits: TEPOTINIB: Small molecule drug with a maximum clinical stage of Approval (across all indications), with an approval for neoplasm and non-small cell lung carcinoma and 5 investigational indications.; TEPOTINIB HYDROCHLORID |
| ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name | strong_support | 0.76 | OpenTargets_get_drug_chembId_by_generic_name returned OpenTargets search hits: OSIMERTINIB: Small molecule drug with a maximum clinical stage of Approval (across all indications), with an approval for non-small cell lung carcinoma and neoplasm and 9 investigational indications.; OSIMERTINIB MESYLATE |
| ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name | strong_support | 0.76 | OpenTargets_get_drug_chembId_by_generic_name returned OpenTargets search hits: SOTORASIB: Small molecule drug with a maximum clinical stage of Approval (across all indications), with an approval for neoplasm and non-small cell lung carcinoma and 4 investigational indications. |
| ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name | strong_support | 0.76 | OpenTargets_get_drug_chembId_by_generic_name returned OpenTargets search hits: CRIZOTINIB: Small molecule drug with a maximum clinical stage of Approval (across all indications), with an approval for neoplasm and non-small cell lung carcinoma and 14 investigational indications. |
| ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name | irrelevant | 0.31 | OpenTargets_get_drug_chembId_by_generic_name returned OpenTargets search hits: SAVOLITINIB: Small molecule drug with a maximum clinical stage of Phase 3 (across all indications), with 9 investigational indications. |
| ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name | strong_support | 0.76 | OpenTargets_get_drug_chembId_by_generic_name returned OpenTargets search hits: CAPMATINIB: Small molecule drug with a maximum clinical stage of Approval (across all indications), with an approval for non-small cell lung carcinoma and neoplasm and 5 investigational indications.; CAPMATINIB HYDROCHLOR |
| ToolUniverse: OpenTargets_get_associated_targets_by_disease_efoId | strong_support | 0.76 | OpenTargets_get_associated_targets_by_disease_efoId returned 13431 associated targets for non-small cell lung carcinoma; top retrieved targets: EGFR association score 0.888; KRAS association score 0.842; ALK association score 0.812; ERBB2 association score 0.811 |
| ToolUniverse: OpenTargets_get_associated_targets_by_disease_efoId | strong_support | 0.76 | OpenTargets_get_associated_targets_by_disease_efoId returned 420 associated targets for non-small cell squamous lung carcinoma; top retrieved targets: EGFR association score 0.468; ALK association score 0.375; VEGFA association score 0.373; CRTC1 association score 0.371 |
| PubMed: MET non-small cell lung cancer failed trial | strong_support | 0.78 | Ensartinib for advanced or metastatic non-small-cell lung cancer with MET exon 14 skipping mutations (EMBRACE): amulti-center, single-arm, phase 2 trial.; Capmatinib efficacy for METex14 non-small cell lung cancer patients: Results of the IFCT-2104 CAPMATU study.; MET in Non-Small-Cell Lung Cancer ( |
| PubMed: MET non-small cell lung cancer not associated | strong_support | 0.78 | Crizotinib or vebreltinib response and resistance in advanced non-small cell lung cancer with MET exon 14 skipping.; Antibody-Drug Conjugates Beyond HER2 in Non-Small Cell Lung Cancer (NSCLC): Mechanisms, Emerging Targets, and Future Directions.; The landscape of MET alterations in non-small cell lu |

## Citations and Retrieved Records

- [MET](https://www.ncbi.nlm.nih.gov/gene/4233) (gene_id: 4233)
- [KRAS](https://www.ncbi.nlm.nih.gov/gene/3845) (gene_id: 3845)
- [Comprehensive characterization of non-small cell lung cancer of different PD-L1 expression classes: a study of 1,038 Chinese patients.](https://pubmed.ncbi.nlm.nih.gov/42182702/) (pmid: 42182702; journal: Journal of thoracic disease; pubdate: 2026 Apr 30)
- [Complications following small-molecule inhibitors for non-small cell lung cancer.](https://pubmed.ncbi.nlm.nih.gov/42107523/) (pmid: 42107523; journal: Expert review of anticancer therapy; pubdate: 2026 May 11)
- [Targetable driver gene-tumor immune microenvironment axis in non-small cell lung cancer: from molecular pathological mechanisms to precision immunotherapy stratification strategies.](https://pubmed.ncbi.nlm.nih.gov/42079655/) (pmid: 42079655; journal: Frontiers in immunology; pubdate: 2026)
- [Vebreltinib plus EGFR-TKI for EGFR-mutated NSCLC with MET-driven resistance: A real-world study of Chinese patients.](https://pubmed.ncbi.nlm.nih.gov/42068890/) (pmid: 42068890; journal: Lung cancer (Amsterdam, Netherlands); pubdate: 2026 Apr 29)
- [Immunological effects of amivantamab in EGFR or MET-expressing non-small cell lung cancer.](https://pubmed.ncbi.nlm.nih.gov/41874698/) (pmid: 41874698; journal: Cancer immunology, immunotherapy : CII; pubdate: 2026 Mar 24)
- [capmatinib](https://pubchem.ncbi.nlm.nih.gov/compound/25145656) (cid: 25145656)
- [tepotinib](https://pubchem.ncbi.nlm.nih.gov/compound/25171648) (cid: 25171648)
- [savolitinib](https://pubchem.ncbi.nlm.nih.gov/compound/68289010) (cid: 68289010)
- [osimertinib](https://pubchem.ncbi.nlm.nih.gov/compound/71496458) (cid: 71496458)
- [sotorasib](https://pubchem.ncbi.nlm.nih.gov/compound/137278711) (cid: 137278711)

## Limitations

- Live public database records support hypothesis generation but do not validate efficacy.
- No clinical efficacy or safety claim is made.
- Compound specificity and translational risk remain unresolved.
- Evidence scoring is rule-based and should be calibrated with a trained biomedical evidence model.
- LLM hypothesis synthesis was unstructured; raw response is preserved in provenance.

## Scientist Panel Debate

*Collaboration model: `parallel_llm_scientist_panel`*

### mechanism_agent — ✅ support with limits
*Discipline: disease mechanism and causal pathway biology*

MET exon 14 skipping is a validated oncogenic driver in NSCLC with established mechanistic rationale and regulatory-approved targeted therapies; the scientific frontier lies in resistance biology and rational combination strategies

**Concerns:**
- Response durability is limited (median PFS under 9 months) and resistance mechanisms are heterogeneous, complicating single combination strategy prioritization
- MET amplification as a biomarker is confounded by copy number thresholds and tumor heterogeneity, risking patient misclassification
- D1228 and Y1230 resistance mutations may require type II inhibitors or allosteric agents not yet approved, creating a therapeutic gap
- Cross-resistance between capmatinib and tepotinib limits sequential MET inhibitor strategies

**Requested follow-ups:**
- Prospective ctDNA profiling at progression to quantify relative frequency of on-target vs bypass resistance in exon14-skipping cohorts
- Structural studies comparing type Ib vs type II MET inhibitor binding to D1228N and Y1230C mutant kinase to guide next-generation inhibitor selection
- Preclinical co-treatment experiments with MET inhibitor plus SHP2 inhibitor in KRAS-bypass resistance models

### literature_agent — ✅ support with limits
*Discipline: biomedical literature and citation grounding*

MET exon 14 skipping is a validated, clinically actionable driver in NSCLC with approved targeted therapies; the scientific frontier lies in resistance biology and combination strategies, not target discovery

**Concerns:**
- Pivotal trial ORR data cited from hypothesis card without direct PubMed PMIDs; durability figures need citation-level verification
- Cross-resistance between type Ib inhibitors and cabozantinib for D1228/Y1230 mutations is incompletely characterized in published literature
- MET amplification copy-number thresholds for clinical predictive value remain inconsistently defined across trials
- RNA-based exon 14 skipping detection superiority over DNA NGS is asserted in guidelines but sensitivity/specificity data vary by platform

**Requested follow-ups:**
- PubMed retrieval of GEOMETRY mono-1 and VISION primary publications for ORR, PFS, and OS with PMIDs
- Mechanistic studies comparing degradation kinetics of exon 14-skipped vs wild-type MET receptor in isogenic cell lines
- Ranked combination experiment: MET inhibitor plus SHP2 inhibitor (RAS bypass) vs MET inhibitor plus EGFR antibody, with resistance mutation-stratified endpoints

### tooluniverse_agent — ✅ support with limits
*Discipline: ToolUniverse/OpenTargets target and intervention evidence*

MET exon 14 skipping is a validated, clinically actionable driver in NSCLC with approved selective MET inhibitors, distinct mechanistically and predictively from MET amplification, but limited by acquired resistance and patient-selection complexity

**Concerns:**
- Response durability is limited; median PFS ~12 months in treatment-naive METex14 cohorts, with no OS benefit demonstrated in randomized trials
- D1228 and Y1230 resistance mutations are not addressable by current approved type Ib inhibitors; next-generation options (cabozantinib, type II inhibitors) lack robust phase III data
- MET amplification as a co-occurring alteration may confound METex14 predictive biomarker interpretation in real-world NGS panels
- Cross-resistance between capmatinib and tepotinib is near-complete, limiting sequential single-agent strategies

**Requested follow-ups:**
- Rank combination experiments: MET inhibitor plus SHP2 inhibitor (addresses RAS bypass) > MET inhibitor plus EGFR-TKI (addresses EGFR upregulation bypass) > type II MET inhibitor (addresses D1228/Y1230) > MET inhibitor plus MEK inhibitor
- Validate D1228N/Y1230C structural models to identify type II inhibitor binding compatibility using cryo-EM or co-crystal data
- Prospectively define MET amplification copy number threshold (GCN10 or MET/CEP72) that predicts single-agent MET inhibitor response independent of exon 14 status

### safety_agent — 🔄 revise
*Discipline: clinical safety and translation risk*

As safety_agent I challenge several efficacy and translational overclaims in the hypothesis card while acknowledging the established clinical precedence for MET exon 14 skipping as a therapeutic target.

**Concerns:**
- ORR and PFS figures cited in literature vary by line of therapy and biomarker selection method (RNA vs DNA); pooling these without stratification inflates apparent efficacy
- MET amplification as secondary EGFR resistance mechanism does not predict response to MET inhibitor monotherapy equivalently to exon 14 skipping; this distinction must be explicit in patient stratification
- Combination regimens (e.g., MET inhibitor plus EGFR-TKI) have additive hepatotoxicity and QTc risks not adequately addressed in the hypothesis
- Preclinical resistance models may not recapitulate clonal heterogeneity seen in clinical specimens; ranked validation experiments should include patient-derived organoids or ctDNA monitoring

**Requested follow-ups:**
- Provide line-of-therapy-stratified ORR and PFS data separately for capmatinib and tepotinib pivotal trials
- Clarify biomarker detection method (RNA-based vs DNA-based) used in each cited trial and its impact on prevalence estimates
- Specify safety monitoring plan for hepatotoxicity in proposed MET plus EGFR-TKI combination experiments

### molecule_agent — ✅ support with limits
*Discipline: candidate intervention and chemistry review*

MET exon 14 skipping is a validated oncogenic driver in NSCLC with approved type Ib MET inhibitors capmatinib and tepotinib; the mechanistic and resistance landscape is well-characterized but combination strategies remain unvalidated clinically

**Concerns:**
- ORR and PFS data cited are from pivotal trials; real-world durability may be lower and cross-trial comparison is confounded by line of therapy
- D1228 and Y1230 resistance mutation frequencies are derived from small post-progression cohorts; relative prevalence vs bypass resistance is uncertain
- Combination strategies (e.g., MET inhibitor plus EGFR inhibitor or SHP2 inhibitor) lack randomized efficacy data; preclinical synergy has not translated to approved regimens
- RNA splicing assay sensitivity varies by platform; liquid biopsy ctDNA detection of splice variants has lower sensitivity than tissue, risking patient misclassification

**Requested follow-ups:**
- Provide ranked preclinical evidence for MET inhibitor plus SHP2 inhibitor combinations against D1228N/Y1230C resistance models
- Clarify whether ensartinib (EMBRACE trial) activity profile differs mechanistically from capmatinib/tepotinib given its multi-kinase profile
- Quantify co-mutation frequency of KRAS in METex14-skipping tumors at baseline vs at progression to establish bypass resistance prevalence

### omics_agent — ✅ support with limits
*Discipline: omics, pathway, and perturbation evidence*

Pathway and cellular evidence strongly support MET exon 14 skipping as a bona fide oncogenic driver in NSCLC, with mechanistically distinct biology from MET amplification, and the resistance landscape is well-characterized enough to prioritize combination experiments.

**Concerns:**
- Durability data remain limited; median PFS ~12 months suggests most patients develop resistance within 1 year, weakening long-term efficacy claims
- Cross-response between exon14-skipping and amplification cohorts is inconsistently reported across trials, complicating biomarker boundary claims
- Mechanistic evidence for EGFR upregulation as a resistance route is largely preclinical; clinical validation in post-MET-inhibitor biopsies is sparse
- Distinguishing true exon14-skipping driver tumors from co-occurring low-level MET amplification requires rigorous ctDNA and FISH co-testing not uniformly applied

**Requested follow-ups:**
- Serial ctDNA profiling in capmatinib/tepotinib-treated patients to quantify relative frequency of D1228, Y1230 vs KRAS vs EGFR resistance mechanisms
- Isogenic cell line models expressing D1228N or Y1230C to confirm differential sensitivity to type Ib vs type II vs bivalent MET inhibitors
- Co-immunoprecipitation and ubiquitination assays in exon14-skipping vs wild-type MET cells to directly quantify CBL-mediated degradation difference

### critic_agent — 🔄 revise
*Discipline: skeptical scientific review*

The hypothesis card correctly frames MET exon 14 skipping as an established target in NSCLC, but several mechanistic and evidentiary gaps weaken the synthesis as presented.

**Concerns:**
- Specific ORR and PFS figures cited (40-68%, 5-12 months) are not directly sourced in the scored evidence digest and require primary trial citation (GEOMETRY mono-1, VISION) for verification
- The mechanistic claim that exon 14 skipping specifically impairs CBL-binding domain ubiquitination is biologically sound but not explicitly supported by any evidence source in the digest
- Cross-resistance between capmatinib and tepotinib for on-target mutations is asserted but not evidenced; the CAPTURE trial tests cabozantinib post-resistance, implying incomplete cross-resistance but this is not mechanistically resolved
- Stratification strategy conflating MET copy number gain with true amplification versus polysomy is a known clinical pitfall not addressed in the hypothesis card

**Requested follow-ups:**
- Provide primary trial citations (GEOMETRY mono-1, VISION) with specific ORR and PFS data stratified by treatment line to substantiate response rate claims
- Clarify whether MET FISH-based amplification thresholds used in EGFR-resistance settings are validated to distinguish true gene amplification from polysomy in the stratification strategy
- Specify ranked combination experiments: e.g., MET inhibitor plus EGFR TKI for EGFR bypass resistance, MET inhibitor plus SHP2 inhibitor for on-target resistance, and MET inhibitor plus KRAS G12C inhibitor for KRAS bypass

### PI Adjudication

{"accepted_claims":["MET exon 14 skipping eliminates the CBL ubiquitin-ligase docking site encoded by exon 14, impairing receptor degradation and causing sustained MET signaling","Capmatinib and tepotinib are FDA-approved for METex14-skipping NSCLC with approximately 41-68% ORR in treatment-naive patients and approximately 40% in pretreated cohorts; median PFS approximately 5.4-8.5 months in pivotal trials","MET exon 14 skipping and MET amplification are biologically and predictively distinct; secondary MET amplification after EGFR-TKI is a bypass resistance mechanism with lower single-agent MET inhibitor response rates","Acquired resistance includes on-target kinase domain mutations D1228N/H and Y1230C and off-target bypass via KRAS mutation and EGFR upregulation","Patient stratification distinguishing exon 14 skipping driver tumors from secondary MET amplification is essential to avoid misapplication of MET monotherapy"],"softened_or_rejected_claims":["Median PFS upper bound of 12 months is not uniformly PMID-verified and is softened to approximately 5.4-8.5 months pending citation confirmation","RNA-based NGS superiority over DNA NGS for exon 14 skipping detection is an active m


## Proposed Next Experiments

### Experiment 1: Resolve the highest-uncertainty MET / non-small cell lung cancer evidence gap with targeted Open Targets, literature, clinical-precedence, and safety review
**Type:** `computational` | **Cost:** `low` | **Feasibility:** `high` | **Expected information gain:** `high`

**Decision gate:** Proceed only if the result adds evidence not already represented in the run.

**Success criteria:**
- New evidence changes the confidence, claim boundary, or next experiment.

**Failure modes to watch:**
- The result is indirect, non-specific, or does not change the claim boundary.

**Gate score:** `0.711` (usable)

**Gate improvements:**
- Tie the experiment to an uncovered evidence requirement.

### Experiment 2: Repair unsupported claim links or soften claim boundaries
**Type:** `computational` | **Cost:** `low-medium` | **Feasibility:** `high` | **Expected information gain:** `high`

**Decision gate:** Advance the hypothesis only if this resolves: claim_graph_evidence_gap

**Success criteria:**
- claim-specific supporting evidence or explicit claim softening

**Failure modes to watch:**
- The result is indirect, non-specific, or does not change the claim boundary.

**Gate score:** `0.667` (usable)

**Gate improvements:**
- Tie the experiment to a named case validation assay.
- Tie the experiment to an uncovered evidence requirement.

### Experiment 3: Resolve evidence gap: evidence_relevance_noise
**Type:** `computational` | **Cost:** `low-medium` | **Feasibility:** `high` | **Expected information gain:** `high`

**Decision gate:** Advance the hypothesis only if this resolves: evidence_relevance_noise

**Success criteria:**
- higher-precision retrieval with irrelevant records filtered from the claim boundary

**Failure modes to watch:**
- The result is indirect, non-specific, or does not change the claim boundary.

**Gate score:** `0.667` (usable)

**Gate improvements:**
- Tie the experiment to a named case validation assay.
- Tie the experiment to an uncovered evidence requirement.

### Experiment 4: Rank candidate interventions by EGFR mutant selectivity, wild-type sparing, CNS penetration, acquired-resistance profile, and ADMET liabilities
**Type:** `computational` | **Cost:** `low-medium` | **Feasibility:** `medium` | **Expected information gain:** `high`

**Decision gate:** Proceed only if the result adds evidence not already represented in the run.

**Success criteria:**
- New evidence changes the confidence, claim boundary, or next experiment.

**Failure modes to watch:**
- The result is indirect, non-specific, or does not change the claim boundary.

**Gate score:** `0.636` (usable)

**Gate improvements:**
- Tie the experiment to an uncovered evidence requirement.

### Experiment 5: Run safety-first triage before efficacy assays: exposure margins, off-target biology, and disease-context tolerability
**Type:** `computational_plus_wet_lab` | **Cost:** `medium` | **Feasibility:** `medium` | **Expected information gain:** `high`

**Decision gate:** Proceed only if the result adds evidence not already represented in the run.

**Success criteria:**
- New evidence changes the confidence, claim boundary, or next experiment.

**Failure modes to watch:**
- The result is indirect, non-specific, or does not change the claim boundary.

**Gate score:** `0.615` (usable)

**Gate improvements:**
- Tie the experiment to an uncovered evidence requirement.


## Critique and Refinement

**Severity:** `medium`

The hypothesis correctly frames MET as clinically precedented in NSCLC, but several evidence links remain unsupported: ClinicalTrials.gov entries for capmatinib and tepotinib in NSCLC and SCLC are cited without claim-specific supporting text. KRAS evidence is included but mechanistically tangential to the MET-NSCLC claim. The NCBI Gene summary for MET does not mention NSCLC specifically, only renal, hepatocellular, and head-and-neck cancers, creating a weak anchor for the primary claim. Safety data from openFDA for tepotinib, capmatinib, and savolitinib are acknowledged but not integrated into the safety liability narrative. Resistance mutation variants (D1228N, D1228H, Y1230C) are referenced but their clinical frequency and actionability are not quantified. The readiness score of 89 may be inflated given 14 of 35 evidence items are labeled irrelevant.

**Recommended fix:** Remove or clearly annotate KRAS evidence as contextual background rather than primary support. Replace unsupported ClinicalTrials.gov links with specific trial identifiers and outcome summaries. Explicitly cite NCBI or peer-reviewed sources confirming MET alteration prevalence in NSCLC. Integrate openFDA safety signals into a structured safety liability section. Quantify resistance mutation frequencies from pivotal trials. Recalculate readiness score excluding irrelevant evidence items.

## Guardrails

- Candidate hypothesis only.
- Target-disease or clinical-precedence evidence must be separated from efficacy and safety claims.
- Requires experimental validation before clinical interpretation.

---
*Generated by AutoScientist. Candidate hypothesis only. Requires experimental validation.*
