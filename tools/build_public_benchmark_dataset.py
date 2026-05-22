from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_INPUT_MANIFEST = Path("benchmarks/autoscientist_bench_v0_1.json")
DEFAULT_OUTPUT_MANIFEST = Path("benchmarks/autoscientist_bench_v0_2_public.json")
OPEN_TARGETS_GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"
NCBI_EUTILS_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


PUBLIC_TASK_TEMPLATES = [
    {
        "id": "target_prioritization",
        "objective_template": (
            "Prioritize therapeutic hypotheses for {gene_symbol} in {disease_name}; use public biomedical "
            "evidence, Open Targets association context, PubMed grounding, weak/failed branches, confidence "
            "scoring, and validation experiments."
        ),
        "expected_capabilities": ["public_biomedical", "tooluniverse", "sciflow_policy"],
    },
    {
        "id": "mechanism_safety_review",
        "objective_template": (
            "Assess whether {gene_symbol}-linked biology is a plausible and safe intervention direction for "
            "{disease_name}; separate direct evidence, indirect mechanism, safety concerns, and missing validation."
        ),
        "expected_capabilities": ["public_biomedical", "tooluniverse", "sciflow_policy"],
    },
    {
        "id": "experiment_design",
        "objective_template": (
            "Design the next experiments to test a bounded {gene_symbol} hypothesis in {disease_name}; include "
            "expected information gain, failure modes, provenance, and public evidence requirements."
        ),
        "expected_capabilities": ["public_biomedical", "tooluniverse", "sciflow_policy"],
    },
    {
        "id": "omics_context_validation",
        "objective_template": (
            "Use an omics-aware workflow to evaluate the cell-context validity of a {gene_symbol} hypothesis in "
            "{disease_name}; require transcriptomic or single-cell reasoning, Medea review, public evidence, "
            "failure modes, and concrete validation experiments."
        ),
        "expected_capabilities": ["public_biomedical", "tooluniverse", "medea", "sciflow_policy"],
    },
]


def load_seed_cases(path: Path) -> list[dict[str, Any]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    cases = manifest.get("seed_cases", [])
    if not cases:
        raise ValueError(f"No seed_cases found in {path}")
    return cases


def build_public_manifest(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    source_cases = load_seed_cases(Path(args.input_manifest))
    selected = source_cases[: max(1, args.max_targets)]
    generated_cases = []
    failures = []
    for case in selected:
        try:
            generated_cases.extend(generate_cases_for_target(case, args))
        except Exception as exc:
            failures.append({"case_id": case.get("id"), "gene_symbol": case.get("gene_symbol"), "error": str(exc)[:500]})
    if not generated_cases:
        raise RuntimeError(f"No public benchmark cases generated. Failures: {failures}")
    return {
        "schema": "autosci.benchmark_manifest.v0.2",
        "name": "AutoScientist-Bench-Public",
        "version": "0.2",
        "created_at_unix": int(started),
        "purpose": (
            "Public-data benchmark manifest generated from Open Targets target-disease associations and NCBI "
            "PubMed/Gene counts to evaluate AutoScientist as a reproducible scientific execution system."
        ),
        "source_manifest": str(args.input_manifest),
        "public_sources": [
            {
                "name": "Open Targets Platform GraphQL API",
                "url": OPEN_TARGETS_GRAPHQL_URL,
                "role": "Target-disease association and target metadata.",
            },
            {
                "name": "NCBI E-utilities",
                "url": NCBI_EUTILS_URL,
                "role": "PubMed/Gene public literature and gene-count grounding.",
            },
        ],
        "selection_policy": {
            "max_targets": args.max_targets,
            "associations_per_target": args.associations_per_target,
            "min_open_targets_score": args.min_open_targets_score,
            "min_pubmed_count": args.min_pubmed_count,
            "include_omics_template": bool(args.include_omics_template),
        },
        "task_templates": [
            template for template in PUBLIC_TASK_TEMPLATES if args.include_omics_template or template["id"] != "omics_context_validation"
        ],
        "seed_cases": generated_cases,
        "generation_failures": failures,
        "caveats": [
            "Open Targets association scores rank evidence strength and should not be interpreted as clinical confidence.",
            "PubMed counts are weak grounding signals; final scoring must inspect evidence quality and provenance.",
            "This manifest evaluates reproducible tool use, memory, and workflow control, not de novo biological truth.",
        ],
    }


def generate_cases_for_target(case: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    target_id = str(case.get("target_ensembl_id") or "")
    if not target_id:
        return []
    target = fetch_open_targets_associations(target_id, size=args.associations_per_target)
    target_meta = target.get("target") or {}
    rows = target_meta.get("associatedDiseases", {}).get("rows", [])
    generated = []
    for rank, row in enumerate(rows, start=1):
        disease = row.get("disease") or {}
        score = float(row.get("score") or 0.0)
        if score < args.min_open_targets_score:
            continue
        disease_name = disease.get("name") or ""
        gene_symbol = target_meta.get("approvedSymbol") or case.get("gene_symbol") or ""
        pubmed = fetch_ncbi_count(f"{gene_symbol} {disease_name}", db="pubmed", timeout_seconds=args.public_timeout_seconds)
        if int(pubmed.get("count") or 0) < args.min_pubmed_count:
            continue
        gene_count = fetch_ncbi_count(
            f"{gene_symbol}[Gene Name] AND Homo sapiens[Organism]",
            db="gene",
            timeout_seconds=args.public_timeout_seconds,
        )
        generated.append(
            {
                "id": slugify(f"{gene_symbol}_{disease_name}"),
                "domain": case.get("domain", "biomedicine"),
                "gene_symbol": gene_symbol,
                "target_ensembl_id": target_id,
                "target_name": target_meta.get("approvedName"),
                "disease_name": disease_name,
                "disease_efo_id": disease.get("id") or "",
                "priority": public_priority(score, int(pubmed.get("count") or 0)),
                "expected_capabilities": ["public_biomedical", "tooluniverse", "sciflow_policy"],
                "public_labels": {
                    "open_targets_association_score": round(score, 6),
                    "open_targets_rank_for_target": rank,
                    "pubmed_gene_disease_count": int(pubmed.get("count") or 0),
                    "ncbi_gene_count": int(gene_count.get("count") or 0),
                },
                "public_context": {
                    "mode": "generated_live",
                    "open_targets_target": {
                        "status": "success",
                        "target": {
                            "id": target_meta.get("id"),
                            "approvedSymbol": target_meta.get("approvedSymbol"),
                            "approvedName": target_meta.get("approvedName"),
                        },
                        "association": row,
                        "url": OPEN_TARGETS_GRAPHQL_URL,
                    },
                    "pubmed_gene_disease": pubmed,
                    "ncbi_gene": gene_count,
                },
            }
        )
    return generated


def fetch_open_targets_associations(target_ensembl_id: str, *, size: int) -> dict[str, Any]:
    query = """
    query TargetAssociations($ensemblId: String!, $size: Int!) {
      target(ensemblId: $ensemblId) {
        id
        approvedSymbol
        approvedName
        associatedDiseases(page: {index: 0, size: $size}) {
          rows {
            score
            disease {
              id
              name
            }
          }
        }
      }
    }
    """
    return json_post(
        OPEN_TARGETS_GRAPHQL_URL,
        {"query": query, "variables": {"ensemblId": target_ensembl_id, "size": size}},
        timeout_seconds=20,
    ).get("data", {})


def fetch_ncbi_count(query: str, *, db: str, timeout_seconds: int) -> dict[str, Any]:
    params = urllib.parse.urlencode({"db": db, "term": query, "retmode": "json", "retmax": "0"})
    url = f"{NCBI_EUTILS_URL}?{params}"
    try:
        data = json_get(url, timeout_seconds=timeout_seconds)
        result = data.get("esearchresult", {})
        return {"status": "success", "query": query, "db": db, "count": int(result.get("count", 0)), "url": url}
    except Exception as exc:
        return {"status": "failure", "query": query, "db": db, "count": 0, "error": str(exc)[:300], "url": url}


def json_get(url: str, *, timeout_seconds: int) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "AutoScientist-Bench/0.2"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def json_post(url: str, payload: dict[str, Any], *, timeout_seconds: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "AutoScientist-Bench/0.2"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def public_priority(open_targets_score: float, pubmed_count: int) -> str:
    if open_targets_score >= 0.75 and pubmed_count >= 25:
        return "high"
    if open_targets_score >= 0.45 and pubmed_count >= 5:
        return "medium"
    return "exploratory"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return re.sub(r"_+", "_", slug)[:120] or "public_case"


def write_outputs(manifest: dict[str, Any], output_path: Path) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    dataset_path = output_path.with_suffix(".jsonl")
    with dataset_path.open("w", encoding="utf-8") as handle:
        for case in manifest["seed_cases"]:
            handle.write(json.dumps(case, default=str) + "\n")
    summary_path = output_path.with_suffix(".md")
    summary_path.write_text(render_summary(manifest, output_path, dataset_path), encoding="utf-8")
    return {
        "manifest_path": str(output_path),
        "dataset_jsonl_path": str(dataset_path),
        "summary_path": str(summary_path),
        "case_count": len(manifest["seed_cases"]),
        "template_count": len(manifest["task_templates"]),
        "task_count": len(manifest["seed_cases"]) * len(manifest["task_templates"]),
    }


def render_summary(manifest: dict[str, Any], output_path: Path, dataset_path: Path) -> str:
    lines = [
        "# AutoScientist-Bench Public v0.2",
        "",
        f"Manifest: `{output_path}`",
        f"Dataset JSONL: `{dataset_path}`",
        f"Cases: `{len(manifest['seed_cases'])}`",
        f"Templates: `{len(manifest['task_templates'])}`",
        f"Expanded tasks: `{len(manifest['seed_cases']) * len(manifest['task_templates'])}`",
        "",
        "## Public Sources",
        "",
    ]
    for source in manifest["public_sources"]:
        lines.append(f"- {source['name']}: {source['url']} - {source['role']}")
    lines.extend(["", "## Cases", "", "| Case | Target | Disease | Open Targets | PubMed | Priority |", "| --- | --- | --- | ---: | ---: | --- |"])
    for case in manifest["seed_cases"]:
        labels = case.get("public_labels", {})
        lines.append(
            f"| `{case['id']}` | {case['gene_symbol']} | {case['disease_name']} | "
            f"{labels.get('open_targets_association_score')} | {labels.get('pubmed_gene_disease_count')} | "
            f"{case.get('priority')} |"
        )
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in manifest.get("caveats", []))
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a public-data AutoScientist benchmark manifest.")
    parser.add_argument("--input-manifest", default=str(DEFAULT_INPUT_MANIFEST))
    parser.add_argument("--output-manifest", default=str(DEFAULT_OUTPUT_MANIFEST))
    parser.add_argument("--max-targets", type=int, default=8)
    parser.add_argument("--associations-per-target", type=int, default=3)
    parser.add_argument("--min-open-targets-score", type=float, default=0.2)
    parser.add_argument("--min-pubmed-count", type=int, default=1)
    parser.add_argument("--public-timeout-seconds", type=int, default=12)
    parser.add_argument("--include-omics-template", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = build_public_manifest(args)
    result = write_outputs(manifest, Path(args.output_manifest))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
