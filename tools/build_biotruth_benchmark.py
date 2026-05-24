from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_SEED_CASES = Path("benchmarks/biotruth_seed_cases_v0_1.json")
DEFAULT_RUBRIC = Path("benchmarks/biotruth_rubric_v0_1.json")
DEFAULT_OUTPUT = Path("benchmarks/autoscientist_biotruth_v0_1.json")
OPEN_TARGETS_GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"
NCBI_EUTILS_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


BIOTRUTH_TASK_TEMPLATES = [
    {
        "id": "target_validity_review",
        "objective_template": (
            "Evaluate whether {gene_symbol} is a scientifically credible therapeutic target for "
            "{disease_name}. Use public target-disease evidence, separate causal from correlative "
            "signals, identify counterevidence, and produce a calibrated confidence judgement."
        ),
        "judge_focus": [
            "target_disease_validity",
            "evidence_grounding",
            "calibration_and_limitations",
        ],
        "expected_capabilities": ["public_biomedical", "tooluniverse", "sciflow_policy", "scistate_graph"],
    },
    {
        "id": "mechanism_safety_review",
        "objective_template": (
            "Explain the plausible mechanism linking {gene_symbol} perturbation to {disease_name}, "
            "then evaluate tractability, known clinical or genetic precedence, safety liabilities, "
            "and translation risks before proposing any therapeutic direction."
        ),
        "judge_focus": [
            "mechanism_plausibility",
            "safety_and_translation",
            "evidence_grounding",
        ],
        "expected_capabilities": ["public_biomedical", "tooluniverse", "sciflow_policy", "scistate_graph"],
    },
    {
        "id": "experiment_decision_plan",
        "objective_template": (
            "Design the next decision-grade experiments for a bounded {gene_symbol} hypothesis in "
            "{disease_name}. Prioritize experiments by expected information gain, required controls, "
            "failure criteria, and how each result would update confidence in the hypothesis."
        ),
        "judge_focus": [
            "experiment_quality",
            "mechanism_plausibility",
            "calibration_and_limitations",
        ],
        "expected_capabilities": ["public_biomedical", "tooluniverse", "sciflow_policy", "scistate_graph"],
    },
    {
        "id": "evidence_grade_and_replay",
        "objective_template": (
            "Produce an audit-ready evidence grade for {gene_symbol} in {disease_name}. The output "
            "must include source-specific evidence, weak or failed branches, uncertainty, provenance, "
            "and replayable reasoning artifacts rather than a single opaque answer."
        ),
        "judge_focus": [
            "evidence_grounding",
            "calibration_and_limitations",
            "auditability",
        ],
        "expected_capabilities": ["public_biomedical", "tooluniverse", "sciflow_policy", "scistate_graph"],
    },
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    seed_doc = load_json(Path(args.seed_cases))
    rubric = load_json(Path(args.rubric))
    seed_cases = seed_doc.get("seed_cases", [])
    if not seed_cases:
        raise ValueError(f"No seed_cases found in {args.seed_cases}")
    requested_case_ids = set(getattr(args, "case_ids", []) or [])
    if requested_case_ids:
        selected = [case for case in seed_cases if case.get("id") in requested_case_ids]
        missing = sorted(requested_case_ids - {case.get("id") for case in selected})
        if missing:
            raise ValueError(f"Unknown BioTruth case ids: {', '.join(missing)}")
    else:
        selected = seed_cases[: max(1, args.max_cases)]
    cases = [enrich_case(case, args) for case in selected]
    templates = BIOTRUTH_TASK_TEMPLATES[: max(1, args.templates_per_case)]
    return {
        "schema": "autosci.biotruth_manifest.v0.1",
        "name": "AutoScientist-BioTruth",
        "version": str(seed_doc.get("version") or rubric.get("version") or "0.1"),
        "created_at_unix": int(started),
        "purpose": (
            "Evaluate AutoScientist for biomedical correctness and usefulness, not just integration "
            "success. Each task is grounded in public target-disease data and scored by a structured "
            "expert-style rubric."
        ),
        "source_seed_cases": str(args.seed_cases),
        "rubric_path": str(args.rubric),
        "rubric": {
            "id": rubric.get("name"),
            "schema": rubric.get("schema"),
            "version": rubric.get("version"),
            "pass_policy": rubric.get("pass_policy", {}),
            "dimension_count": len(rubric.get("dimensions", [])),
        },
        "primary_sources": rubric.get("primary_sources", []),
        "selection_policy": {
            **(seed_doc.get("selection_policy") or {}),
            "max_cases": args.max_cases,
            "templates_per_case": len(templates),
            "association_scan_size": args.association_scan_size,
            "public_context_mode": "offline" if args.offline_public_context else "live",
        },
        "task_templates": templates,
        "seed_cases": cases,
        "expanded_task_count": len(cases) * len(templates),
        "caveats": [
            "This benchmark scores target-disease reasoning quality; it does not prove new biological discovery.",
            "Open Targets association scores are public ranking heuristics and must not be treated as clinical confidence.",
            "PubMed counts are evidence-availability signals, not evidence-quality labels.",
            "Final credibility requires expert or rubric-judge scoring over the exported answer packets.",
        ],
    }


def enrich_case(case: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    enriched = dict(case)
    enriched["expected_capabilities"] = sorted(
        set(case.get("expected_capabilities", []))
        | {"public_biomedical", "tooluniverse", "sciflow_policy", "scistate_graph"}
    )
    if args.offline_public_context:
        enriched["public_labels"] = {"mode": "offline"}
        enriched["public_context"] = {"mode": "offline", "warnings": ["Live public context fetch skipped."]}
        enriched["benchmark_tags"] = benchmark_tags(enriched)
        return enriched

    target_context = fetch_open_targets_target_context(
        str(case.get("target_ensembl_id") or ""),
        association_scan_size=args.association_scan_size,
        timeout_seconds=args.public_timeout_seconds,
    )
    pubmed = fetch_ncbi_count(
        f"{case.get('gene_symbol', '')} {case.get('disease_name', '')}",
        db="pubmed",
        timeout_seconds=args.public_timeout_seconds,
    )
    gene_count = fetch_ncbi_count(
        f"{case.get('gene_symbol', '')}[Gene Name] AND Homo sapiens[Organism]",
        db="gene",
        timeout_seconds=args.public_timeout_seconds,
    )
    association = find_association(
        target_context.get("target", {}).get("associatedDiseases", {}).get("rows", []),
        disease_efo_id=str(case.get("disease_efo_id") or ""),
        disease_name=str(case.get("disease_name") or ""),
    )
    enriched["public_labels"] = {
        "mode": "live",
        "open_targets_target_status": target_context.get("status"),
        "open_targets_association_status": association.get("status"),
        "open_targets_association_score": association.get("score"),
        "open_targets_association_rank": association.get("rank"),
        "open_targets_matched_disease_id": association.get("disease", {}).get("id"),
        "open_targets_matched_disease_name": association.get("disease", {}).get("name"),
        "open_targets_associated_disease_count": (
            target_context.get("target", {}).get("associatedDiseases", {}).get("count")
        ),
        "pubmed_gene_disease_count": pubmed.get("count", 0),
        "ncbi_gene_count": gene_count.get("count", 0),
        "evidence_availability": evidence_availability(association.get("score"), int(pubmed.get("count") or 0)),
    }
    enriched["public_context"] = {
        "mode": "live",
        "open_targets": compact_open_targets_context(target_context),
        "matched_association": association,
        "pubmed_gene_disease": pubmed,
        "ncbi_gene": gene_count,
    }
    enriched["benchmark_tags"] = benchmark_tags(enriched)
    return enriched


def compact_open_targets_context(target_context: dict[str, Any]) -> dict[str, Any]:
    target = target_context.get("target", {}) if isinstance(target_context.get("target"), dict) else {}
    associated = target.get("associatedDiseases", {}) if isinstance(target.get("associatedDiseases"), dict) else {}
    rows = associated.get("rows", []) if isinstance(associated.get("rows"), list) else []
    return {
        "status": target_context.get("status"),
        "target_ensembl_id": target_context.get("target_ensembl_id"),
        "url": target_context.get("url"),
        "errors": target_context.get("errors", []),
        "target": {
            "id": target.get("id"),
            "approvedSymbol": target.get("approvedSymbol"),
            "approvedName": target.get("approvedName"),
            "biotype": target.get("biotype"),
            "tractability": target.get("tractability", []),
        },
        "associated_disease_count": associated.get("count"),
        "scanned_association_rows": len(rows),
    }


def fetch_open_targets_target_context(
    target_ensembl_id: str,
    *,
    association_scan_size: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    if not target_ensembl_id:
        return {"status": "skipped", "error": "Missing target_ensembl_id"}
    detailed_query = """
    query TargetBioTruth($ensemblId: String!, $size: Int!) {
      target(ensemblId: $ensemblId) {
        id
        approvedSymbol
        approvedName
        biotype
        tractability {
          label
          modality
          value
        }
        associatedDiseases(page: {index: 0, size: $size}) {
          count
          rows {
            score
            datatypeScores {
              id
              score
            }
            disease {
              id
              name
            }
          }
        }
      }
    }
    """
    fallback_query = """
    query TargetBioTruth($ensemblId: String!, $size: Int!) {
      target(ensemblId: $ensemblId) {
        id
        approvedSymbol
        approvedName
        biotype
        tractability {
          label
          modality
          value
        }
        associatedDiseases(page: {index: 0, size: $size}) {
          count
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
    variables = {"ensemblId": target_ensembl_id, "size": max(1, association_scan_size)}
    for query in (detailed_query, fallback_query):
        try:
            payload = {"query": query, "variables": variables}
            data = json_post(OPEN_TARGETS_GRAPHQL_URL, payload, timeout_seconds=timeout_seconds)
            target = data.get("data", {}).get("target")
            if target:
                return {
                    "status": "success",
                    "target_ensembl_id": target_ensembl_id,
                    "target": target,
                    "url": OPEN_TARGETS_GRAPHQL_URL,
                    "errors": data.get("errors", []),
                }
        except Exception as exc:
            last_error = str(exc)[:500]
    return {
        "status": "failure",
        "target_ensembl_id": target_ensembl_id,
        "error": last_error if "last_error" in locals() else "Unknown Open Targets failure",
        "url": OPEN_TARGETS_GRAPHQL_URL,
    }


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
    request = urllib.request.Request(url, headers={"User-Agent": "AutoScientist-BioTruth/0.1"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def json_post(url: str, payload: dict[str, Any], *, timeout_seconds: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "AutoScientist-BioTruth/0.1"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def find_association(
    rows: list[dict[str, Any]],
    *,
    disease_efo_id: str,
    disease_name: str,
) -> dict[str, Any]:
    normalized_expected = normalize_name(disease_name)
    expected_tokens = set(normalized_expected.split())
    best: dict[str, Any] | None = None
    best_overlap = 0.0
    for index, row in enumerate(rows, start=1):
        disease = row.get("disease") or {}
        disease_id = str(disease.get("id") or "")
        found_name = str(disease.get("name") or "")
        normalized_found = normalize_name(found_name)
        if disease_efo_id and disease_id == disease_efo_id:
            return association_record(row, index, "exact_id")
        if normalized_expected and normalized_found == normalized_expected:
            return association_record(row, index, "exact_name")
        overlap = token_overlap(expected_tokens, set(normalized_found.split()))
        if overlap > best_overlap:
            best = association_record(row, index, "token_overlap")
            best["name_overlap"] = round(overlap, 4)
            best_overlap = overlap
    if best and best_overlap >= 0.5:
        return best
    return {"status": "not_found", "expected_disease_efo_id": disease_efo_id, "expected_disease_name": disease_name}


def association_record(row: dict[str, Any], rank: int, match_type: str) -> dict[str, Any]:
    return {
        "status": "matched",
        "match_type": match_type,
        "rank": rank,
        "score": round(float(row.get("score") or 0.0), 6),
        "disease": row.get("disease") or {},
        "datatype_scores": row.get("datatypeScores") or [],
    }


def normalize_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", normalized)


def token_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left), len(right))


def evidence_availability(open_targets_score: Any, pubmed_count: int) -> str:
    score = float(open_targets_score or 0.0)
    if score >= 0.65 and pubmed_count >= 50:
        return "high"
    if score >= 0.35 and pubmed_count >= 10:
        return "moderate"
    if score > 0 or pubmed_count > 0:
        return "low"
    return "very_low"


def benchmark_tags(case: dict[str, Any]) -> list[str]:
    labels = case.get("public_labels", {})
    tags = [str(case.get("domain") or "biomedicine")]
    if case.get("gold_label"):
        tags.append(f"gold:{case['gold_label']}")
    if case.get("expected_decision"):
        tags.append(f"decision:{case['expected_decision']}")
    if labels.get("open_targets_association_status") == "matched":
        tags.append("open_targets_matched")
    if int(labels.get("pubmed_gene_disease_count") or 0) >= 25:
        tags.append("literature_rich")
    if case.get("disease_efo_id"):
        tags.append("ontology_labeled")
    return sorted(set(tags))


def expand_tasks(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = []
    for case in manifest.get("seed_cases", []):
        for template in manifest.get("task_templates", []):
            tasks.append(
                {
                    "id": f"{case['id']}__{template['id']}",
                    "case_id": case["id"],
                    "template_id": template["id"],
                    "domain": case.get("domain"),
                    "gene_symbol": case.get("gene_symbol"),
                    "disease_name": case.get("disease_name"),
                    "target_ensembl_id": case.get("target_ensembl_id"),
                    "disease_efo_id": case.get("disease_efo_id"),
                    "objective": template["objective_template"].format(**case),
                    "expected_capabilities": sorted(
                        set(case.get("expected_capabilities", [])) | set(template.get("expected_capabilities", []))
                    ),
                    "judge_focus": template.get("judge_focus", []),
                    "rubric_path": manifest.get("rubric_path"),
                    "public_labels": case.get("public_labels", {}),
                    "gold_label": case.get("gold_label"),
                    "expected_decision": case.get("expected_decision"),
                    "expected_evidence": case.get("expected_evidence", []),
                    "case_rationale": case.get("case_rationale"),
                    "benchmark_tags": case.get("benchmark_tags", []),
                }
            )
    return tasks


def write_outputs(manifest: dict[str, Any], output_path: Path) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tasks = expand_tasks(manifest)
    output_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    tasks_path = output_path.with_name(f"{output_path.stem}_tasks.jsonl")
    with tasks_path.open("w", encoding="utf-8") as handle:
        for task in tasks:
            handle.write(json.dumps(task, default=str) + "\n")
    summary_path = output_path.with_suffix(".md")
    summary_path.write_text(render_summary(manifest, output_path, tasks_path), encoding="utf-8")
    return {
        "manifest_path": str(output_path),
        "tasks_jsonl_path": str(tasks_path),
        "summary_path": str(summary_path),
        "case_count": len(manifest.get("seed_cases", [])),
        "template_count": len(manifest.get("task_templates", [])),
        "expanded_task_count": len(tasks),
    }


def render_summary(manifest: dict[str, Any], output_path: Path, tasks_path: Path) -> str:
    cases = manifest.get("seed_cases", [])
    templates = manifest.get("task_templates", [])
    domain_counts: dict[str, int] = {}
    label_counts: dict[str, int] = {}
    for case in cases:
        domain = str(case.get("domain") or "unknown")
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        label = str(case.get("gold_label") or "unlabeled")
        label_counts[label] = label_counts.get(label, 0) + 1
    matched = sum(1 for case in cases if case.get("public_labels", {}).get("open_targets_association_status") == "matched")
    lines = [
        f"# AutoScientist-BioTruth v{manifest.get('version', '0.1')}",
        "",
        f"Manifest: `{output_path}`",
        f"Expanded task JSONL: `{tasks_path}`",
        f"Cases: `{len(cases)}`",
        f"Templates: `{len(templates)}`",
        f"Expanded tasks: `{len(cases) * len(templates)}`",
        f"Open Targets matched cases: `{matched}/{len(cases)}`",
        "",
        "## Domains",
        "",
    ]
    for domain, count in sorted(domain_counts.items()):
        lines.append(f"- `{domain}`: {count}")
    lines.extend(["", "## Gold Labels", ""])
    for label, count in sorted(label_counts.items()):
        lines.append(f"- `{label}`: {count}")
    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Case | Domain | Label | Expected decision | Target | Disease | Open Targets | PubMed | Evidence availability |",
            "| --- | --- | --- | --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for case in cases:
        labels = case.get("public_labels", {})
        lines.append(
            f"| `{case['id']}` | {case.get('domain')} | {case.get('gold_label') or ''} | "
            f"{case.get('expected_decision') or ''} | {case.get('gene_symbol')} | {case.get('disease_name')} | "
            f"{labels.get('open_targets_association_score')} | "
            f"{labels.get('pubmed_gene_disease_count')} | {labels.get('evidence_availability')} |"
        )
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in manifest.get("caveats", []))
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the BioTruth biomedical correctness benchmark manifest.")
    parser.add_argument("--seed-cases", default=str(DEFAULT_SEED_CASES))
    parser.add_argument("--rubric", default=str(DEFAULT_RUBRIC))
    parser.add_argument("--output-manifest", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--max-cases", type=int, default=25)
    parser.add_argument("--case-ids", nargs="*", default=[])
    parser.add_argument("--templates-per-case", type=int, default=4)
    parser.add_argument("--association-scan-size", type=int, default=150)
    parser.add_argument("--public-timeout-seconds", type=int, default=15)
    parser.add_argument("--offline-public-context", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = build_manifest(args)
    result = write_outputs(manifest, Path(args.output_manifest))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
