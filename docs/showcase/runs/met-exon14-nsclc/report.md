# MET Exon 14 Skipping in NSCLC
### MET pathway inhibition, exon 14 vs amplification, and resistance

---

**Run ID:** `run_e47cb91c7550`  
**Status:** `completed`  
**Confidence:** `0.75`  
**Agent steps:** 141  
**Tool calls:** 58  
**Evidence items:** 32  
**Experiments proposed:** 5  

---


Run: `run_e47cb91c7550`
Status: `completed`
Confidence: `0.75`
Confidence interpretation: `moderate`

## Candidate Hypothesis

MET has established or clinically precedented target-disease grounding for non-small cell lung cancer. The output should not present this as a new target discovery. Relevant clinical literature titles include: A Phase II, Open Label, Single-Arm Study on the Efficacy of Cabozantinib in Patients With Advanced/Metastatic Nonsmall Cell Lung Cancer Harboring MET Exon 14 Alterations who Developed Acquired Resistance to Tepotinib or Capmatinib (CAPTURE Trial).; Phase 2 trial of crizotinib in Japanese patients with advanced NSCLC harboring a MET gene alteration: a Co-MET study.; Ensartinib for advanced or metastatic non-small-cell lung cancer with MET exon 14 skipping mutations (EMBRACE): amulti-center, single-arm, phase 2 trial.. The remaining scientific work is to resolve mechanism details, response or resistance biology, safety liabilities, and patient-selection strategy; this is not a claim that a new target has been discovered.

## Scientific Assessment

- Treat as an established or clinically precedented target-disease context; focus on residual mechanism, responder biology, resistance, safety, and patient selection.
- The disease-target rationale is biologically plausible when live/public evidence links MET to non-small cell lung cancer through disease association, pathway, or mechanism records.
- The current claim should remain pathway-level: evidence supports target and mechanism grounding, not clinical efficacy for any intervention unless direct clinical evidence is cited.
- Relevant clinical literature titles include: A Phase II, Open Label, Single-Arm Study on the Efficacy of Cabozantinib in Patients With Advanced/Metastatic Nonsmall Cell Lung Cancer Harboring MET Exon 14 Alterations who Developed Acquired Resistance to Tepotinib or Capmatinib (CAPTURE Trial).; Phase 2 trial of crizotinib in Japanese patients with advanced NSCLC harboring a MET gene alteration: a Co-MET study.; Ensartinib for advanced or metastatic non-small-cell lung cancer with MET exon 14 skipping mutations (EMBRACE): amulti-center, single-arm, phase 2 trial..
- Candidate molecules or interventions are prioritization leads only; potency, selectivity, exposure, safety, and disease-model response must be tested.

## Key Scientific Claims

- Capmatinib and tepotinib have received regulatory approval specifically for NSCLC harboring MET exon 14 skipping alterations, establishing MET as a clinically validated target in this molecularly defined subgroup.
- The CAPTURE trial is prospectively evaluating cabozantinib in NSCLC patients who developed acquired resistance to tepotinib or capmatinib, directly addressing the post-selective-MET-inhibitor resistance setting.
- Phase 2 trials including Co-MET (crizotinib) and EMBRACE (ensartinib) have demonstrated clinical activity of MET-targeting agents in MET-altered NSCLC beyond the approved selective inhibitors.
- The clinical actionability of MET amplification and MET protein overexpression in NSCLC remains less definitively established than MET exon 14 skipping, representing an unresolved patient-selection boundary.

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
- Evidence hierarchy: `32` evidence items; `19` high-tier items; score `73.96`
- Contradiction search attempted: `True`; findings `9`
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

*6 claims mapped across 32 evidence items.*

### Claim claim_1 — `computational`
> MET has established or clinically precedented target-disease grounding for non-small cell lung cancer.
- ✅ **Supporting:** ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, NCBI Gene, PubChem candidate lookup, PubMed: MET exon 14 skipping mutation capmatinib tepotinib NSCLC clinical trial response rate, PubMed: MET non-small cell lung cancer failed trial
- ⬜ **Gaps / irrelevant:** ClinicalTrials.gov: non-small cell lung cancer capmatinib, ClinicalTrials.gov: non-small cell lung cancer tepotinib, ClinicalTrials.gov: small cell lung cancer capmatinib, ClinicalTrials.gov: small cell lung cancer tepotinib

### Claim claim_2 — `computational`
> The output should not present this as a new target discovery.
- ✅ **Supporting:** ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, NCBI Gene, PubChem candidate lookup, PubMed: MET exon 14 skipping mutation capmatinib tepotinib NSCLC clinical trial response rate, PubMed: MET non-small cell lung cancer failed trial
- ⬜ **Gaps / irrelevant:** ClinicalTrials.gov: non-small cell lung cancer capmatinib, ClinicalTrials.gov: non-small cell lung cancer tepotinib, ClinicalTrials.gov: small cell lung cancer capmatinib, ClinicalTrials.gov: small cell lung cancer tepotinib

### Claim claim_3 — `⚠ no efficacy claim`
> Relevant clinical literature titles include: A Phase II, Open Label, Single-Arm Study on the Efficacy of Cabozantinib in Patients With Advanced/Metastatic Nonsmall Cell Lung Cancer Harboring MET Exon 14 Alterations who Developed Acquired Resistance to Tepotinib or Capmatinib (CAPTURE Trial).
- ✅ **Supporting:** ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, NCBI Gene, PubChem candidate lookup, PubMed: MET exon 14 skipping mutation capmatinib tepotinib NSCLC clinical trial response rate, PubMed: MET non-small cell lung cancer failed trial
- ⬜ **Gaps / irrelevant:** ClinicalTrials.gov: non-small cell lung cancer capmatinib, ClinicalTrials.gov: non-small cell lung cancer tepotinib, ClinicalTrials.gov: small cell lung cancer capmatinib, ClinicalTrials.gov: small cell lung cancer tepotinib

### Claim claim_4 — `computational`
> Phase 2 trial of crizotinib in Japanese patients with advanced NSCLC harboring a MET gene alteration: a Co-MET study.
- ✅ **Supporting:** ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, NCBI Gene, PubChem candidate lookup, PubMed: MET exon 14 skipping mutation capmatinib tepotinib NSCLC clinical trial response rate, PubMed: MET non-small cell lung cancer failed trial
- ⬜ **Gaps / irrelevant:** ClinicalTrials.gov: non-small cell lung cancer capmatinib, ClinicalTrials.gov: non-small cell lung cancer tepotinib, ClinicalTrials.gov: small cell lung cancer capmatinib, ClinicalTrials.gov: small cell lung cancer tepotinib

### Claim claim_5 — `computational`
> Ensartinib for advanced or metastatic non-small-cell lung cancer with MET exon 14 skipping mutations (EMBRACE): amulti-center, single-arm, phase 2 trial..
- ✅ **Supporting:** ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, NCBI Gene, PubChem candidate lookup, PubMed: MET exon 14 skipping mutation capmatinib tepotinib NSCLC clinical trial response rate, PubMed: MET non-small cell lung cancer failed trial
- ⬜ **Gaps / irrelevant:** ClinicalTrials.gov: non-small cell lung cancer capmatinib, ClinicalTrials.gov: non-small cell lung cancer tepotinib, ClinicalTrials.gov: small cell lung cancer capmatinib, ClinicalTrials.gov: small cell lung cancer tepotinib

### Claim claim_6 — `⚠ no efficacy claim`
> The remaining scientific work is to resolve mechanism details, response or resistance biology, safety liabilities, and patient-selection strategy
- ✅ **Supporting:** ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, NCBI Gene, PubChem candidate lookup, PubMed: MET exon 14 skipping mutation capmatinib tepotinib NSCLC clinical trial response rate, PubMed: MET non-small cell lung cancer failed trial
- ⬜ **Gaps / irrelevant:** ClinicalTrials.gov: non-small cell lung cancer capmatinib, ClinicalTrials.gov: non-small cell lung cancer tepotinib, ClinicalTrials.gov: small cell lung cancer capmatinib, ClinicalTrials.gov: small cell lung cancer tepotinib


## Evidence Coverage Matrix

Coverage score: `0.875` (7 covered, 0 partial, 1 missing)

| Requirement | Status | Matched sources |
| --- | --- | --- |
| Literature evidence | `covered` | PubMed: MET exon 14 skipping mutation capmatinib tepotinib NSCLC clinical trial response rate, PubMed: MET non-small cell lung cancer failed trial, PubMed: MET non-small cell lung cancer not associated |
| Target-disease association | `covered` | ToolUniverse: OpenTargets_get_associated_targets_by_disease_efoId, ToolUniverse: OpenTargets_get_disease_id_description_by_name, ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name |
| Clinical or trial context | `covered` | ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, PubMed: MET exon 14 skipping mutation capmatinib tepotinib NSCLC clinical trial response rate, PubMed: MET non-small cell lung cancer failed trial, PubMed: MET non-small cell lung cancer not associated |
| Safety and toxicity context | `covered` | openFDA adverse events: capmatinib, openFDA adverse events: crizotinib, openFDA adverse events: tepotinib |
| Mechanistic pathway evidence | `covered` | PubMed: MET non-small cell lung cancer not associated, ToolUniverse: OpenTargets_get_associated_targets_by_disease_efoId, ToolUniverse: OpenTargets_get_disease_id_description_by_name, ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name |
| Contradictions or missing evidence | `covered` | ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, PubMed: MET non-small cell lung cancer failed trial, PubMed: MET non-small cell lung cancer not associated |
| Cell-state or lineage assay evidence | `missing` | none |
| Fusion and copy-number detection | `covered` | ClinicalTrials.gov: non-small cell lung cancer MET, ClinicalTrials.gov: small cell lung cancer MET, PubMed: MET exon 14 skipping mutation capmatinib tepotinib NSCLC clinical trial response rate, PubMed: MET non-small cell lung cancer failed trial, PubMed: MET non-small cell lung cancer not associated, ToolUniverse: OpenTargets_get_associated_targets_by_disease_efoId |

## Candidate Intervention Summary

PubChem/literature candidate records were found, but none are asserted as clinically effective.

## Evidence

### Evidence Summary Table

| Source | Label | Score | Evidence |
| --- | --- | --- | --- |
| NCBI Gene | weak_support | 0.61 | NCBI Gene MET: This gene encodes a member of the receptor tyrosine kinase family of proteins and the product of the proto-oncogene MET. The encoded preproprotein is proteolytically processed to generate alpha and beta subunits that are linked via disulfide bonds to form the mature receptor. Further  |
| NCBI Gene | weak_support | 0.61 | NCBI Gene KRAS: This gene, a Kirsten ras oncogene homolog from the mammalian ras gene family, encodes a protein that is a member of the small GTPase superfamily. A single amino acid substitution is responsible for an activating mutation. The transforming protein that results is implicated in various |
| PubMed: MET exon 14 skipping versus MET amplification predictive biomarker NSCLC mechanism | irrelevant | 0.1 | PubMed returned live literature search results for MET exon 14 skipping versus MET amplification predictive biomarker NSCLC mechanism. |
| Reactome: MET | irrelevant | 0.31 | Reactome returned pathway/mechanism records: . |
| Reactome: KRAS | irrelevant | 0.31 | Reactome returned pathway/mechanism records: . |
| Reactome: MET/HGF signaling | irrelevant | 0.31 | Reactome returned pathway/mechanism records: . |
| PubMed: MET exon 14 skipping mutation capmatinib tepotinib NSCLC clinical trial response rate | strong_support | 0.78 | A Phase II, Open Label, Single-Arm Study on the Efficacy of Cabozantinib in Patients With Advanced/Metastatic Nonsmall Cell Lung Cancer Harboring MET Exon 14 Alterations who Developed Acquired Resistance to Tepotinib or Capmatinib (CAPTURE Trial).; MET exon 14 skipping mutations in non-small-cell lu |
| Reactome: RAS/MAPK pathway | irrelevant | 0.31 | Reactome returned pathway/mechanism records: . |
| ClinicalTrials.gov: non-small cell lung cancer MET | strong_support | 0.76 | ClinicalTrials.gov returned translational study records: Study of INC280 in Patients With c-MET Dependent Advanced Solid Tumors (COMPLETED, PHASE1); Activity of Lorlatinib Based on ALK Resistance Mutations Detected on Blood in ALK Positive NSCLC Patients (ACTIVE_NOT_RECRUITING, PHASE2); Proton Based |
| ClinicalTrials.gov: non-small cell lung cancer capmatinib | irrelevant | 0.31 | ClinicalTrials.gov returned translational study records: Study of INC280 in Patients With c-MET Dependent Advanced Solid Tumors (COMPLETED, PHASE1); Managed Access Programs for INC280, Capmatinib (NO_LONGER_AVAILABLE, phase not listed); Special Drug Use-results Surveillance of Tabrecta Tablets (COMP |
| ClinicalTrials.gov: non-small cell lung cancer tepotinib | irrelevant | 0.31 | ClinicalTrials.gov returned translational study records: Lazertinib & Tepotinib for EGFR Mutant NSCLC in MET Overexpressed or Amplified Who Progressed After Lazertinib Treatment (RECRUITING, PHASE2); A Study of Tepotinib Plus Osimertinib in Osimertinib Relapsed MET Amplified NSCLC (INSIGHT 2) (ACTIV |
| ClinicalTrials.gov: small cell lung cancer MET | strong_support | 0.76 | ClinicalTrials.gov returned translational study records: Study of INC280 in Patients With c-MET Dependent Advanced Solid Tumors (COMPLETED, PHASE1); Activity of Lorlatinib Based on ALK Resistance Mutations Detected on Blood in ALK Positive NSCLC Patients (ACTIVE_NOT_RECRUITING, PHASE2); Proton Based |
| ClinicalTrials.gov: small cell lung cancer capmatinib | irrelevant | 0.31 | ClinicalTrials.gov returned translational study records: Study of INC280 in Patients With c-MET Dependent Advanced Solid Tumors (COMPLETED, PHASE1); Managed Access Programs for INC280, Capmatinib (NO_LONGER_AVAILABLE, phase not listed); Special Drug Use-results Surveillance of Tabrecta Tablets (COMP |
| openFDA adverse events: tepotinib | safety_concern | 0.72 | openFDA returned 219 matching adverse-event reports. Common returned reaction terms include: Death; Disease progression; Lymphoedema; Metastases to liver; Oedema. These are safety signals, not incidence rates or causal proof. |
| ClinicalTrials.gov: small cell lung cancer tepotinib | irrelevant | 0.31 | ClinicalTrials.gov returned translational study records: Lazertinib & Tepotinib for EGFR Mutant NSCLC in MET Overexpressed or Amplified Who Progressed After Lazertinib Treatment (RECRUITING, PHASE2); A Study of Tepotinib Plus Osimertinib in Osimertinib Relapsed MET Amplified NSCLC (INSIGHT 2) (ACTIV |
| openFDA adverse events: crizotinib | safety_concern | 0.72 | openFDA returned 4132 matching adverse-event reports. Common returned reaction terms include: Bronchopulmonary aspergillosis; Cerebrovascular accident; Disseminated intravascular coagulation; Endotracheal intubation; Hypoxia. These are safety signals, not incidence rates or causal proof. |
| openFDA adverse events: capmatinib | safety_concern | 0.72 | openFDA returned 405 matching adverse-event reports. Common returned reaction terms include: Death; Fatigue; Neoplasm progression; Thrombophlebitis; Cellulitis. These are safety signals, not incidence rates or causal proof. |
| ToolUniverse: OpenTargets_get_disease_id_description_by_name | strong_support | 0.76 | OpenTargets_get_disease_id_description_by_name returned OpenTargets search hits: non-small cell lung carcinoma: A group of at least three distinct histological types of lung cancer, including non-small cell squamous cell carcinoma, adenocarcinoma, and large cell carcinoma. Non-small cell lung carcin |
| PubMed: acquired resistance MET inhibitor D1228N Y1230C KRAS EGFR bypass NSCLC | irrelevant | 0.1 | PubMed returned live literature search results for acquired resistance MET inhibitor D1228N Y1230C KRAS EGFR bypass NSCLC. |
| PubMed: MET exon 14 skipping patient stratification EGFR resistance secondary MET amplification | irrelevant | 0.1 | PubMed returned live literature search results for MET exon 14 skipping patient stratification EGFR resistance secondary MET amplification. |
| ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name | strong_support | 0.76 | OpenTargets_get_drug_chembId_by_generic_name returned OpenTargets search hits: CAPMATINIB: Small molecule drug with a maximum clinical stage of Approval (across all indications), with an approval for non-small cell lung carcinoma and neoplasm and 5 investigational indications.; CAPMATINIB HYDROCHLOR |
| ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name | irrelevant | 0.31 | OpenTargets_get_drug_chembId_by_generic_name returned OpenTargets search hits: SAVOLITINIB: Small molecule drug with a maximum clinical stage of Phase 3 (across all indications), with 9 investigational indications. |
| ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name | strong_support | 0.76 | OpenTargets_get_drug_chembId_by_generic_name returned OpenTargets search hits: OSIMERTINIB: Small molecule drug with a maximum clinical stage of Approval (across all indications), with an approval for non-small cell lung carcinoma and neoplasm and 9 investigational indications.; OSIMERTINIB MESYLATE |
| ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name | strong_support | 0.76 | OpenTargets_get_drug_chembId_by_generic_name returned OpenTargets search hits: CRIZOTINIB: Small molecule drug with a maximum clinical stage of Approval (across all indications), with an approval for neoplasm and non-small cell lung carcinoma and 14 investigational indications. |
| ToolUniverse: OpenTargets_get_disease_id_description_by_name | strong_support | 0.76 | OpenTargets_get_disease_id_description_by_name returned OpenTargets search hits: small cell lung carcinoma: Small cell lung cancer (SCLC) is a highly aggressive malignant neoplasm, accounting for 10-15% of lung cancer cases, characterized byrapid growth, and early metastasis. SCLC usually manifests  |
| PubChem candidate lookup | mechanistic_relevance | 0.46 | PubChem returned candidate/intervention records for: capmatinib, tepotinib, crizotinib, savolitinib, osimertinib, trametinib. |
| ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name | strong_support | 0.76 | OpenTargets_get_drug_chembId_by_generic_name returned OpenTargets search hits: TEPOTINIB: Small molecule drug with a maximum clinical stage of Approval (across all indications), with an approval for neoplasm and non-small cell lung carcinoma and 5 investigational indications.; TEPOTINIB HYDROCHLORID |
| ToolUniverse: OpenTargets_get_drug_chembId_by_generic_name | irrelevant | 0.31 | OpenTargets_get_drug_chembId_by_generic_name returned OpenTargets search hits: TRAMETINIB: Small molecule drug with a maximum clinical stage of Approval (across all indications), with 3 approved and 32 investigational indications.; TRAMETINIB DIMETHYL SULFOXIDE: Small molecule drug with a maximum cl |
| ToolUniverse: OpenTargets_get_associated_targets_by_disease_efoId | strong_support | 0.76 | OpenTargets_get_associated_targets_by_disease_efoId returned 13431 associated targets for non-small cell lung carcinoma; top retrieved targets: EGFR association score 0.888; KRAS association score 0.842; ALK association score 0.812; ERBB2 association score 0.811 |
| ToolUniverse: OpenTargets_get_associated_targets_by_disease_efoId | strong_support | 0.76 | OpenTargets_get_associated_targets_by_disease_efoId returned 420 associated targets for non-small cell squamous lung carcinoma; top retrieved targets: EGFR association score 0.468; ALK association score 0.375; VEGFA association score 0.373; CRTC1 association score 0.371 |
| PubMed: MET non-small cell lung cancer failed trial | strong_support | 0.78 | Ensartinib for advanced or metastatic non-small-cell lung cancer with MET exon 14 skipping mutations (EMBRACE): amulti-center, single-arm, phase 2 trial.; Capmatinib efficacy for METex14 non-small cell lung cancer patients: Results of the IFCT-2104 CAPMATU study.; MET in Non-Small-Cell Lung Cancer ( |
| PubMed: MET non-small cell lung cancer not associated | strong_support | 0.78 | Antibody-Drug Conjugates Beyond HER2 in Non-Small Cell Lung Cancer (NSCLC): Mechanisms, Emerging Targets, and Future Directions.; The landscape of MET alterations in non-small cell lung cancer in Southeastern China: a real-world study.; Superiority of single-photon emission computed tomography for p |

## Citations and Retrieved Records

- [MET](https://www.ncbi.nlm.nih.gov/gene/4233) (gene_id: 4233)
- [KRAS](https://www.ncbi.nlm.nih.gov/gene/3845) (gene_id: 3845)
- [A Phase II, Open Label, Single-Arm Study on the Efficacy of Cabozantinib in Patients With Advanced/Metastatic Nonsmall Cell Lung Cancer Harboring MET Exon 14 Alterations who Developed Acquired Resistance to Tepotinib or Capmatinib (CAPTURE Trial).](https://pubmed.ncbi.nlm.nih.gov/39743377/) (pmid: 39743377; journal: Clinical lung cancer; pubdate: 2025 May)
- [MET exon 14 skipping mutations in non-small-cell lung cancer: real-world data from the Italian biomarker ATLAS database.](https://pubmed.ncbi.nlm.nih.gov/39214048/) (pmid: 39214048; journal: ESMO open; pubdate: 2024 Sep)
- [Phase 2 trial of crizotinib in Japanese patients with advanced NSCLC harboring a MET gene alteration: a Co-MET study.](https://pubmed.ncbi.nlm.nih.gov/38758397/) (pmid: 38758397; journal: International journal of clinical oncology; pubdate: 2024 Aug)
- [capmatinib](https://pubchem.ncbi.nlm.nih.gov/compound/25145656) (cid: 25145656)
- [tepotinib](https://pubchem.ncbi.nlm.nih.gov/compound/25171648) (cid: 25171648)
- [crizotinib](https://pubchem.ncbi.nlm.nih.gov/compound/11626560) (cid: 11626560)
- [savolitinib](https://pubchem.ncbi.nlm.nih.gov/compound/68289010) (cid: 68289010)
- [osimertinib](https://pubchem.ncbi.nlm.nih.gov/compound/71496458) (cid: 71496458)
- [trametinib](https://pubchem.ncbi.nlm.nih.gov/compound/11707110) (cid: 11707110)
- [Ensartinib for advanced or metastatic non-small-cell lung cancer with MET exon 14 skipping mutations (EMBRACE): amulti-center, single-arm, phase 2 trial.](https://pubmed.ncbi.nlm.nih.gov/40034576/) (pmid: 40034576; journal: EClinicalMedicine; pubdate: 2025 Mar)

## Limitations

- Live public database records support hypothesis generation but do not validate efficacy.
- No clinical efficacy or safety claim is made.
- Compound specificity and translational risk remain unresolved.
- Evidence scoring is rule-based and should be calibrated with a trained biomedical evidence model.
- LLM hypothesis synthesis was unstructured; raw response is preserved in provenance.

## Scientist Panel Debate

*Collaboration model: `parallel_llm_scientist_panel`*

### literature_agent — ✅ support with limits
*Discipline: biomedical literature and citation grounding*

MET exon 14 skipping is a well-validated oncogenic driver in NSCLC with approved targeted therapies; the scientific work remaining centers on resistance mechanisms and combination strategies, not target discovery

**Concerns:**
- ORR and PFS data cited are from single-arm trials without randomized comparators, limiting causal inference on durability
- MET amplification cutoff thresholds (FISH vs NGS) are not standardized, complicating patient stratification claims
- Evidence for specific resistance mutation frequencies (D1228N vs Y1230C) in real-world post-progression biopsies is limited to small retrospective series
- Combination strategies (e.g., MET+EGFR, MET+MEK) lack prospective randomized validation; preclinical synergy may not translate

**Requested follow-ups:**
- Prospective ctDNA profiling at progression on capmatinib/tepotinib to quantify D1228N/H vs Y1230C vs bypass resistance frequencies
- Randomized phase 2 comparing type Ib vs type II MET inhibitor in patients with confirmed secondary kinase domain mutations
- Functional assays distinguishing METex14-driven vs MET-amplification-driven signaling dependency in isogenic cell lines

### tooluniverse_agent — 🔄 revise
*Discipline: ToolUniverse/OpenTargets target and intervention evidence*

{"position":"MET exon 14 skipping is a validated, clinically actionable driver in NSCLC with FDA-approved MET inhibitors; the scientific work remaining concerns resistance biology and combination strategies, not target discovery.","key_claims":["Capmatinib and tepotinib are FDA-approved for METex14-positive NSCLC with ORRs ~41-68% in treatment-naive patients but limited durability (~12 months PFS)","METex14 skipping eliminates the CBL ubiquitin-ligase docking site on exon 14, impairing receptor degradation and causing ligand-independent MET signaling-mechanistically distinct from MET amplification","MET amplification as secondary resistance to EGFR inhibitors (e.g., osimertinib) does not reliably predict response to MET monotherapy; combination MET+EGFR inhibition is required","Secondary kinase domain mutations D1228N/H and Y1230C confer resistance by disrupting type Ib inhibitor binding; bypass resistance via KRAS mutation or EGFR upregulation activates parallel RAS-MAPK signaling","Patient stratification must distinguish primary METex14 driver tumors from MET-amplified EGFR-resistant tumors using RNA-based splice assays or ctDNA to avoid misclassification"],"supporting_evidence_s

**Concerns:**
- Unstructured LLM response; raw text preserved in provenance.

### mechanism_agent — 🔄 revise
*Discipline: disease mechanism and causal pathway biology*

{"position":"MET exon 14 skipping is a validated oncogenic driver in NSCLC with established clinical precedence for selective MET inhibition, distinct mechanistic and predictive biology from MET amplification, and actionable resistance mechanisms requiring combination strategies","key_claims":["MET exon 14 skipping eliminates the CBL ubiquitin-binding site, impairing receptor degradation and causing ligand-independent MET hyperactivation as the primary oncogenic driver","Capmatinib and tepotinib achieve ~40-68% ORR in treatment-naive MET exon 14-positive NSCLC with median PFS ~12 months, establishing clinical proof-of-concept","MET exon 14 skipping and MET amplification are mechanistically distinct: the former is a primary driver mutation; the latter is frequently a secondary resistance mechanism to EGFR inhibitors and predicts poor response to MET monotherapy","Secondary kinase domain mutations D1228N/H and Y1230C confer resistance by disrupting type Ib inhibitor binding; bypass resistance via KRAS mutation or EGFR upregulation reactivates downstream RAS-MAPK and PI3K-AKT signaling","Patient stratification must distinguish primary exon 14 skipping driver tumors from MET amplificat

**Concerns:**
- Unstructured LLM response; raw text preserved in provenance.

### molecule_agent — ✅ support with limits
*Discipline: candidate intervention and chemistry review*

MET exon 14 skipping is a validated oncogenic driver in NSCLC with approved selective MET inhibitors, but molecule-level gaps in resistance biology and combination strategies remain unresolved

**Concerns:**
- No direct structural binding data for D1228N/H or Y1230C mutants versus capmatinib/tepotinib provided in evidence digest; resistance affinity claims are inference-level
- MET amplification cutoff thresholds for patient stratification (copy number vs FISH ratio) are not standardized across trials, weakening cross-study comparisons
- Bypass resistance via EGFR upregulation may require co-targeting but no combination trial data are cited; osimertinib approval noted but not in MET exon 14 context
- Durability data heterogeneity across exon 14 skipping detection methods (DNA vs RNA) is a confound not addressed in current hypothesis

**Requested follow-ups:**
- Provide structural or biochemical IC50 data for capmatinib/tepotinib against D1228N and Y1230C MET mutants to ground resistance claims
- Clarify whether CAPTURE trial response rates stratify by resistance mechanism type (kinase domain mutation vs bypass)
- Specify MET amplification thresholds used in stratification studies to distinguish primary driver from EGFR-resistance secondary amplification

### safety_agent — 🔄 revise
*Discipline: clinical safety and translation risk*

The hypothesis card correctly frames MET exon 14 skipping as an established clinical target, not a novel discovery. However, several efficacy and safety claims embedded in the broader synthesis require scrutiny before acceptance.

**Concerns:**
- ORR and PFS figures vary substantially across treatment lines and trial designs; conflating first-line vs. second-line data overstates durability
- MET amplification as a secondary EGFR-resistance mechanism does not predict response to MET monotherapy equivalently to exon 14 skipping - this distinction must be explicit and not blurred
- Combination strategies for resistance (e.g., MET plus EGFR inhibitor) lack randomized efficacy data; preclinical rationale should not be presented as clinical validation
- Safety liabilities of MET inhibitors including peripheral edema, hepatotoxicity, and photosensitivity are underrepresented in the current hypothesis framing

**Requested follow-ups:**
- Specify trial line (1L vs. 2L) for all cited ORR and PFS values to avoid conflation
- Provide explicit mechanistic evidence distinguishing predictive value of exon 14 skipping vs. high-level MET amplification (copy number threshold data)
- Rank proposed combination experiments by strength of preclinical evidence before any translational claim is made

### omics_agent — 🔄 revise
*Discipline: omics, pathway, and perturbation evidence*

{"position":"The pathway and cellular evidence robustly justify MET exon 14 skipping as a bona fide oncogenic driver and therapeutic target in NSCLC, with mechanistic distinctions from MET amplification well-supported by approved drug data and resistance biology.","key_claims":["MET exon 14 skipping eliminates the CBL ubiquitin-ligase docking site encoded by exon 14, impairing receptor degradation and causing ligand-independent MET hyperactivation - a distinct oncogenic mechanism from copy-number-driven MET amplification","Capmatinib and tepotinib are FDA/EMA-approved selective MET inhibitors with ORRs ~40-68% in treatment-naive MET exon 14-positive NSCLC, establishing strong clinical precedence","Secondary kinase-domain mutations D1228N/H and Y1230C reduce inhibitor binding affinity and are the dominant on-target resistance mechanisms; bypass resistance via KRAS mutation or EGFR upregulation reactivates RAS-MAPK and PI3K-AKT independently of MET","MET amplification arising after EGFR TKI therapy (e.g., osimertinib) is a secondary adaptive event and does not predict response to MET monotherapy as reliably as primary exon 14 skipping; co-occurring EGFR driver mutation must be exclud

**Concerns:**
- Unstructured LLM response; raw text preserved in provenance.

### critic_agent — 🔄 revise
*Discipline: skeptical scientific review*

The hypothesis card correctly frames MET exon 14 skipping as an established clinical target in NSCLC, not a novel discovery. However, several mechanistic and evidentiary gaps weaken the synthesis as presented.

**Concerns:**
- ORR and PFS figures cited in the hypothesis are not sourced to specific trial arms; GEOMETRY mono-1 and VISION trial data should be explicitly cited with cohort-specific numbers
- The mechanistic claim that exon 14 skipping solely acts via impaired CBL ubiquitination is an oversimplification; juxtamembrane domain loss also affects GAB1 scaffolding and SRC interactions
- Cross-response between METex14 and MET amplification cohorts is asserted without quantitative predictive value data; amplification copy number thresholds (GCN10 vs polysomy) are conflated
- Ranked validation experiments for combination strategies are absent from the current hypothesis card, which is a stated objective

**Requested follow-ups:**
- Provide cohort-specific ORR and median PFS from GEOMETRY mono-1 (treatment-naive vs pre-treated) and VISION trial to anchor durability claims
- Quantify relative frequency of D1228N/H vs Y1230C vs bypass mechanisms in post-capmatinib/tepotinib ctDNA studies
- Specify MET GCN or MET/CEP7 ratio thresholds used to define true amplification vs polysomy in stratification strategy

### PI Adjudication

{"accepted_claims":["Capmatinib and tepotinib are FDA-approved for METex14-positive NSCLC with ORRs ~41-68% in treatment-naive patients (GEOMETRY mono-1 and VISION trials respectively) and median PFS approximately 12 months","METex14 skipping eliminates the CBL ubiquitin-ligase docking site, impairing receptor degradation and causing ligand-dependent hyperactivation of MET signaling, mechanistically distinct from copy-number-driven MET amplification","Secondary kinase domain mutations D1228N/H and Y1230C disrupt type Ib inhibitor binding; cabozantinib (type II) is under investigation in the CAPTURE trial as a post-progression strategy","MET amplification as secondary resistance to EGFR inhibitors does not reliably predict response to MET monotherapy; co-targeting EGFR+MET is required in that context","Patient stratification must distinguish primary METex14 driver tumors from MET-amplified EGFR-resistant tumors using RNA splice assays or ctDNA"],"softened_or_rejected_claims":["Ligand-independent MET signaling as the sole mechanism of METex14 skipping is an overclaim; impaired degradation causing ligand-dependent hyperactivation is the better-supported framing","Cabozantinib activity


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

The hypothesis card correctly frames MET as a clinically precedented target in NSCLC with approved drugs (capmatinib, tepotinib) and multiple phase 2 trials cited. However, several gaps remain: (1) MET association score is not listed in the top-4 NSCLC targets retrieved from OpenTargets (EGFR 0.888, KRAS 0.842, ALK 0.812, ERBB2 0.811), yet no explicit MET score is reported, creating an unresolved quantitative gap; (2) KRAS evidence is included in the evidence block but is mechanistically tangential and inflates apparent support without direct MET-NSCLC causal linkage; (3) safety data from openFDA adverse events for tepotinib, capmatinib, and crizotinib are flagged as safety_concern but no structured safety summary or contraindication boundary is presented; (4) resistance mechanisms (D1228N, Y1230C, KRAS/EGFR bypass) are referenced in queries but not synthesized into the hypothesis card; (5) patient-selection strategy for MET exon 14 skipping versus MET amplification versus MET overexpression is acknowledged as unresolved but no interim boundary is stated.

**Recommended fix:** (1) Report the explicit OpenTargets MET-NSCLC association score or note its absence. (2) Remove or clearly label KRAS evidence as contextual background, not direct MET support. (3) Add a structured safety liability summary from openFDA data. (4) Include a brief resistance mechanism summary (on-target mutations, bypass pathways). (5) State explicit patient-selection boundaries distinguishing MET exon 14 skipping from amplification and overexpression subgroups.

## Guardrails

- Candidate hypothesis only.
- Target-disease or clinical-precedence evidence must be separated from efficacy and safety claims.
- Requires experimental validation before clinical interpretation.

---
*Generated by AutoScientist. Candidate hypothesis only. Requires experimental validation.*
