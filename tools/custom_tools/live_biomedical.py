from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import urlopen

from tools.custom_tools.base import ScientificTool, ToolResult


def ascii_safe(text: Any) -> Any:
    if not isinstance(text, str):
        return text
    replacements = {
        "α": "alpha",
        "β": "beta",
        "γ": "gamma",
        "δ": "delta",
        "κ": "kappa",
        "μ": "mu",
        "–": "-",
        "—": "-",
        "“": '"',
        "”": '"',
        "’": "'",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("ascii", errors="ignore").decode("ascii")


def fetch_json(url: str, timeout: int = 20) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(url, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - live network defensive branch
            last_error = exc
            delay = 1.2 * (attempt + 1) if "429" in str(exc) else 0.4 * (attempt + 1)
            time.sleep(delay)
    raise RuntimeError(f"Live API request failed after retries: {last_error}")


class NCBIGeneProfileTool(ScientificTool):
    name = "ncbi_gene_profile_tool"
    description = "Retrieves a live NCBI Gene summary for a human gene symbol."
    example_input = {"gene_symbol": "PCSK9", "organism": "Homo sapiens"}

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "gene_symbol": {"type": "string"},
                "organism": {"type": "string", "default": "Homo sapiens"},
            },
            "required": ["gene_symbol"],
        }

    def _run(self, payload: dict[str, Any]) -> ToolResult:
        gene = payload.get("gene_symbol")
        if not gene:
            return ToolResult(
                status="failure",
                input=payload,
                output={"message": "gene_symbol is required."},
                confidence=0.0,
                warnings=["No gene symbol was supplied."],
            )
        organism = payload.get("organism", "Homo sapiens")
        term = f"{gene}[Gene Name] AND {organism}[Organism]"
        search_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
            + urlencode({"db": "gene", "term": term, "retmode": "json", "retmax": 1})
        )
        search = fetch_json(search_url)
        ids = search.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return ToolResult(
                status="partial",
                input=payload,
                output={"gene_symbol": gene, "message": "No NCBI Gene record found."},
                sources=[{"name": "NCBI Gene", "url": search_url}],
                confidence=0.2,
                warnings=["No live NCBI Gene hit."],
            )
        gene_id = ids[0]
        summary_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
            + urlencode({"db": "gene", "id": gene_id, "retmode": "json"})
        )
        summary = fetch_json(summary_url)
        record = summary.get("result", {}).get(gene_id, {})
        output = {
            "gene_id": gene_id,
            "gene_symbol": record.get("name", gene),
            "description": record.get("description"),
            "summary": record.get("summary"),
            "organism": record.get("organism", {}).get("scientificname", organism),
            "map_location": record.get("maplocation"),
            "other_designations": record.get("otherdesignations"),
        }
        return ToolResult(
            status="success",
            input=payload,
            output=output,
            sources=[{"name": "NCBI Gene", "id": gene_id, "url": summary_url}],
            confidence=0.86,
        )


class PubMedLiteratureSearchTool(ScientificTool):
    name = "pubmed_literature_search_tool"
    description = "Searches PubMed live and returns PMID, title, journal, and publication date summaries."
    example_input = {"query": "PCSK9 familial hypercholesterolemia LDLR", "retmax": 5}

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "retmax": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        }

    def _run(self, payload: dict[str, Any]) -> ToolResult:
        query = payload.get("query")
        if not query:
            return ToolResult(
                status="failure",
                input=payload,
                output={"message": "query is required."},
                confidence=0.0,
                warnings=["No PubMed query was supplied."],
            )
        retmax = int(payload.get("retmax", 5))
        search_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
            + urlencode({"db": "pubmed", "term": query, "retmode": "json", "retmax": retmax})
        )
        search = fetch_json(search_url)
        ids = search.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return ToolResult(
                status="partial",
                input=payload,
                output={"query": query, "articles": [], "count": 0},
                sources=[{"name": "PubMed", "url": search_url}],
                confidence=0.25,
                warnings=["No PubMed records returned."],
            )
        summary_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
            + urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
        )
        summary = fetch_json(summary_url)
        result = summary.get("result", {})
        articles = []
        for pmid in result.get("uids", []):
            item = result.get(pmid, {})
            articles.append(
                {
                    "pmid": pmid,
                    "title": ascii_safe(item.get("title")),
                    "journal": ascii_safe(item.get("fulljournalname") or item.get("source")),
                    "pubdate": ascii_safe(item.get("pubdate")),
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                }
            )
        return ToolResult(
            status="success",
            input=payload,
            output={
                "query": query,
                "count": int(search.get("esearchresult", {}).get("count", 0)),
                "articles": articles,
            },
            sources=[{"name": "PubMed", "url": summary_url}],
            confidence=0.82,
        )


class PubChemCandidateTool(ScientificTool):
    name = "pubchem_candidate_lookup_tool"
    description = "Looks up candidate intervention names in PubChem and returns identifiers and properties."
    example_input = {"names": ["evolocumab", "inclisiran"]}

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"names": {"type": "array", "items": {"type": "string"}}},
            "required": ["names"],
        }

    def _run(self, payload: dict[str, Any]) -> ToolResult:
        names = payload.get("names") or []
        if not names:
            return ToolResult(
                status="failure",
                input=payload,
                output={"message": "names is required."},
                confidence=0.0,
                warnings=["No candidate names were supplied."],
            )
        compounds = []
        warnings = []
        for name in names:
            url = (
                "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
                + quote(str(name))
                + "/property/CanonicalSMILES,MolecularFormula,MolecularWeight/JSON"
            )
            try:
                data = fetch_json(url)
                properties = data.get("PropertyTable", {}).get("Properties", [])
                if not properties:
                    warnings.append(f"No PubChem property record for {name}.")
                    continue
                prop = properties[0]
                compounds.append(
                    {
                        "name": name,
                        "cid": prop.get("CID"),
                        "canonical_smiles": prop.get("CanonicalSMILES"),
                        "molecular_formula": prop.get("MolecularFormula"),
                        "molecular_weight": prop.get("MolecularWeight"),
                        "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{prop.get('CID')}",
                        "role_note": "Candidate/intervention lookup only; not an efficacy or safety claim.",
                    }
                )
            except Exception as exc:  # pragma: no cover - live network defensive branch
                warnings.append(f"{name}: {exc}")
        return ToolResult(
            status="success" if compounds else "partial",
            input=payload,
            output={"compounds": compounds},
            sources=[{"name": "PubChem PUG REST", "url": "https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest"}],
            confidence=0.75 if compounds else 0.25,
            warnings=warnings,
        )


class ClinicalTrialsSearchTool(ScientificTool):
    name = "clinical_trials_search_tool"
    description = "Searches ClinicalTrials.gov v2 for translational or interventional study evidence."
    example_input = {"condition": "rheumatoid arthritis", "query": "TNF", "page_size": 5}

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "condition": {"type": "string"},
                "query": {"type": "string"},
                "page_size": {"type": "integer", "default": 5},
            },
            "required": ["condition"],
        }

    def _run(self, payload: dict[str, Any]) -> ToolResult:
        condition = str(payload.get("condition") or "").strip()
        query = str(payload.get("query") or "").strip()
        if not condition:
            return ToolResult(
                status="failure",
                input=payload,
                output={"message": "condition is required."},
                confidence=0.0,
                warnings=["No disease/condition was supplied."],
            )
        page_size = max(1, min(int(payload.get("page_size") or 5), 10))
        params = {"query.cond": condition, "pageSize": page_size, "format": "json"}
        if query:
            params["query.term"] = query
        url = "https://clinicaltrials.gov/api/v2/studies?" + urlencode(params)
        data = fetch_json(url)
        studies = []
        for item in data.get("studies", [])[:page_size]:
            protocol = item.get("protocolSection", {}) if isinstance(item, dict) else {}
            identification = protocol.get("identificationModule", {})
            status = protocol.get("statusModule", {})
            design = protocol.get("designModule", {})
            conditions = protocol.get("conditionsModule", {})
            interventions = protocol.get("armsInterventionsModule", {})
            outcomes = protocol.get("outcomesModule", {})
            nct_id = identification.get("nctId")
            interventions_list = [
                entry.get("name")
                for entry in interventions.get("interventions", [])
                if isinstance(entry, dict) and entry.get("name")
            ]
            studies.append(
                {
                    "nct_id": nct_id,
                    "title": ascii_safe(identification.get("briefTitle") or identification.get("officialTitle")),
                    "status": status.get("overallStatus"),
                    "phase": design.get("phases", []),
                    "study_type": design.get("studyType"),
                    "conditions": conditions.get("conditions", []),
                    "interventions": interventions_list[:8],
                    "primary_outcomes": [
                        outcome.get("measure")
                        for outcome in outcomes.get("primaryOutcomes", [])[:4]
                        if isinstance(outcome, dict) and outcome.get("measure")
                    ],
                    "url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else None,
                }
            )
        return ToolResult(
            status="success" if studies else "partial",
            input=payload,
            output={
                "condition": condition,
                "query": query,
                "count": len(studies),
                "studies": studies,
                "next_page_token_present": bool(data.get("nextPageToken")),
            },
            sources=[{"name": "ClinicalTrials.gov", "url": url}],
            confidence=0.78 if studies else 0.3,
            warnings=[] if studies else ["No ClinicalTrials.gov studies returned for this condition/query."],
        )


class ReactomePathwaySearchTool(ScientificTool):
    name = "reactome_pathway_search_tool"
    description = "Searches Reactome for human pathway/mechanism records related to a gene or pathway phrase."
    example_input = {"query": "TNF", "species": "Homo sapiens", "page_size": 5}

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "species": {"type": "string", "default": "Homo sapiens"},
                "page_size": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        }

    def _run(self, payload: dict[str, Any]) -> ToolResult:
        query = str(payload.get("query") or "").strip()
        if not query:
            return ToolResult(
                status="failure",
                input=payload,
                output={"message": "query is required."},
                confidence=0.0,
                warnings=["No pathway query was supplied."],
            )
        species = str(payload.get("species") or "Homo sapiens").strip()
        page_size = max(1, min(int(payload.get("page_size") or 5), 10))
        params = {
            "query": query,
            "species": species,
            "types": "Pathway",
            "pageSize": page_size,
            "page": 1,
        }
        url = "https://reactome.org/ContentService/search/query?" + urlencode(params)
        data = fetch_json(url)
        pathways = []
        for item in data.get("results", [])[:page_size]:
            if not isinstance(item, dict):
                continue
            stable_id = item.get("stId") or item.get("dbId")
            pathways.append(
                {
                    "stable_id": stable_id,
                    "name": ascii_safe(item.get("name") or item.get("displayName")),
                    "type": item.get("schemaClass") or item.get("type"),
                    "species": item.get("speciesName") or species,
                    "url": f"https://reactome.org/content/detail/{stable_id}" if stable_id else None,
                }
            )
        return ToolResult(
            status="success" if pathways else "partial",
            input=payload,
            output={
                "query": query,
                "species": species,
                "row_count": int(data.get("rowCount") or len(pathways)),
                "pathways": pathways,
            },
            sources=[{"name": "Reactome Content Service", "url": url}],
            confidence=0.72 if pathways else 0.25,
            warnings=[] if pathways else ["Reactome returned no pathway records for this query."],
        )


class OpenFDAAdverseEventTool(ScientificTool):
    name = "openfda_adverse_event_tool"
    description = "Looks up openFDA FAERS adverse-event report counts and common reactions for an intervention name."
    example_input = {"drug_name": "adalimumab", "limit": 5}

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "drug_name": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["drug_name"],
        }

    def _run(self, payload: dict[str, Any]) -> ToolResult:
        drug_name = str(payload.get("drug_name") or "").strip()
        if not drug_name:
            return ToolResult(
                status="failure",
                input=payload,
                output={"message": "drug_name is required."},
                confidence=0.0,
                warnings=["No drug/intervention name was supplied."],
            )
        limit = max(1, min(int(payload.get("limit") or 5), 10))
        search = f'patient.drug.medicinalproduct:"{drug_name}"'
        url = "https://api.fda.gov/drug/event.json?" + urlencode({"search": search, "limit": limit})
        data = fetch_json(url)
        total = int(data.get("meta", {}).get("results", {}).get("total") or 0)
        reactions: dict[str, int] = {}
        serious_reports = 0
        reports = []
        for report in data.get("results", [])[:limit]:
            patient = report.get("patient", {}) if isinstance(report, dict) else {}
            serious = str(report.get("serious") or "") == "1"
            serious_reports += int(serious)
            report_reactions = []
            for reaction in patient.get("reaction", []) if isinstance(patient, dict) else []:
                term = ascii_safe(reaction.get("reactionmeddrapt")) if isinstance(reaction, dict) else None
                if not term:
                    continue
                reactions[term] = reactions.get(term, 0) + 1
                report_reactions.append(term)
            reports.append(
                {
                    "safetyreportid": report.get("safetyreportid"),
                    "serious": serious,
                    "receivedate": report.get("receivedate"),
                    "primarysourcecountry": report.get("primarysourcecountry"),
                    "reactions": report_reactions[:8],
                }
            )
        common_reactions = [
            {"reaction": reaction, "count_in_returned_reports": count}
            for reaction, count in sorted(reactions.items(), key=lambda item: (-item[1], item[0]))[:10]
        ]
        return ToolResult(
            status="success" if total else "partial",
            input=payload,
            output={
                "drug_name": drug_name,
                "total_matching_reports": total,
                "returned_reports": len(reports),
                "serious_reports_in_returned": serious_reports,
                "common_reactions": common_reactions,
                "reports": reports,
                "interpretation_note": (
                    "FAERS/openFDA reports are safety signals, not incidence rates or proof of causality."
                ),
            },
            sources=[{"name": "openFDA Drug Adverse Events", "url": url}],
            confidence=0.68 if total else 0.2,
            warnings=[] if total else ["openFDA returned no adverse-event reports for this drug name."],
        )
