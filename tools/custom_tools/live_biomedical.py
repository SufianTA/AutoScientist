from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import urlopen

from tools.custom_tools.base import ScientificTool, ToolResult


def fetch_json(url: str, timeout: int = 20) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(url, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - live network defensive branch
            last_error = exc
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"Live API request failed after retries: {last_error}")


class NCBIGeneProfileTool(ScientificTool):
    name = "ncbi_gene_profile_tool"
    description = "Retrieves a live NCBI Gene summary for a human gene symbol."
    example_input = {"gene_symbol": "ACVR1", "organism": "Homo sapiens"}

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
        gene = payload.get("gene_symbol", "ACVR1")
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
    example_input = {"query": "ACVR1 FOP BMP signaling", "retmax": 5}

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
        query = payload.get("query", "ACVR1 FOP BMP signaling")
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
                    "title": item.get("title"),
                    "journal": item.get("fulljournalname") or item.get("source"),
                    "pubdate": item.get("pubdate"),
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
    example_input = {"names": ["palovarotene", "LDN-193189", "dorsomorphin"]}

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"names": {"type": "array", "items": {"type": "string"}}},
            "required": ["names"],
        }

    def _run(self, payload: dict[str, Any]) -> ToolResult:
        names = payload.get("names") or ["palovarotene", "LDN-193189", "dorsomorphin"]
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
