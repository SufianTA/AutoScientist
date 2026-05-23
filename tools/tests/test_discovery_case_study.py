from __future__ import annotations

import json
from pathlib import Path

from tools.build_discovery_case_study import write_case_studies


def write_result(path: Path, template_id: str, ablation: str = "full") -> None:
    result = {
        "schema": "autosci.benchmark_task_result.v0.1",
        "task": {
            "id": f"il6_ra__{template_id}__r1",
            "case_id": "il6_rheumatoid_arthritis",
            "template_id": template_id,
            "gene_symbol": "IL6",
            "disease_name": "rheumatoid arthritis",
            "domain": "autoimmune_inflammation",
            "priority": "high",
            "objective": "Evaluate IL6 in rheumatoid arthritis.",
            "public_context": {"open_targets": {"status": "matched", "score": 0.51}},
        },
        "ablation": ablation,
        "run_id": f"run_{template_id}_{ablation}",
        "status": "completed",
        "final_confidence": 0.81,
        "replay": {"available": ablation == "full"},
        "sciflow_application": {"applied": ablation == "full"},
        "value_assessment": {
            "score": 100 if ablation != "no_public_tools" else 65,
            "scientific_quality": {"score": 100 if ablation == "full" else 95},
        },
        "hypothesis": {
            "title": "IL6 target-disease review",
            "text": "IL6 has clinically precedented target-disease grounding for rheumatoid arthritis.",
            "confidence": 0.81,
        },
        "evidence_count": 2,
        "report": {
            "evidence": [
                {
                    "source": "Open Targets",
                    "text": "Open Targets reports a matched IL6/rheumatoid arthritis association.",
                    "support_label": "strong_support",
                    "support_score": 0.78,
                },
                {
                    "source": "PubMed broad query",
                    "text": "A broad query returned indirect articles.",
                    "support_label": "irrelevant",
                    "support_score": 0.2,
                },
            ],
            "experiments": [
                {
                    "name": "Run synovial-cell IL6 pathway perturbation",
                    "type": "wet_lab",
                    "feasibility": "medium",
                    "expected_information_gain": "high",
                    "decision_gate": "Proceed if STAT3 and inflammatory cytokine readouts move coherently.",
                }
            ],
        },
        "experiments": [],
        "tool_calls": [
            {
                "tool_name": "pubmed_literature_search_tool",
                "tool_source": "live_public_biomedical",
                "input": {"query": "IL6 rheumatoid arthritis"},
                "output": {
                    "status": "success",
                    "output": {
                        "count": 1,
                        "articles": [
                            {
                                "pmid": "123",
                                "title": "IL6 in rheumatoid arthritis",
                                "journal": "Example",
                                "pubdate": "2026",
                                "url": "https://pubmed.ncbi.nlm.nih.gov/123/",
                            }
                        ],
                    },
                },
            }
        ],
    }
    path.write_text(json.dumps(result), encoding="utf-8")


def test_write_case_study_outputs_markdown_json_and_zip(tmp_path: Path) -> None:
    bench_dir = tmp_path / "bench"
    output_dir = tmp_path / "cases"
    bench_dir.mkdir()
    (bench_dir / "benchmark_summary.md").write_text("# Summary", encoding="utf-8")
    (bench_dir / "scistate_graph.json").write_text("{}", encoding="utf-8")
    write_result(bench_dir / "il6_ra__target_validity_review__r1__full.json", "target_validity_review")
    write_result(bench_dir / "il6_ra__target_validity_review__r1__no_public_tools.json", "target_validity_review", "no_public_tools")

    index = write_case_studies(bench_dir, output_dir, [])

    assert index["case_count"] == 1
    markdown = output_dir / "il6_rheumatoid_arthritis_discovery_case_study.md"
    payload = output_dir / "il6_rheumatoid_arthritis_discovery_case_study.json"
    assert markdown.exists()
    assert payload.exists()
    assert output_dir.with_suffix(".zip").exists()
    text = markdown.read_text(encoding="utf-8")
    assert "What The System Did End To End" in text
    assert "Supporting Evidence Highlights" in text
    assert "Weak Or Failed Branches" in text
    assert "Ablation Evidence" in text
