from __future__ import annotations

import json
from pathlib import Path

from tools.build_discovery_insight_report import build_report, render_markdown


def test_build_report_summarizes_cases_tools_and_weak_branches(tmp_path: Path) -> None:
    bench_dir = tmp_path / "bench"
    bench_dir.mkdir()
    (bench_dir / "benchmark_summary.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "task_count": 1,
                "result_count": 1,
                "elapsed_seconds": 12.0,
                "summary_by_ablation": {"full": {"runs": 1}},
                "realness_gates": {"passed": True},
            }
        ),
        encoding="utf-8",
    )
    result = {
        "schema": "autosci.benchmark_task_result.v0.1",
        "task": {
            "id": "il6_ra__target_validity_review__r1",
            "case_id": "il6_rheumatoid_arthritis",
            "template_id": "target_validity_review",
            "domain": "autoimmune_inflammation",
            "gene_symbol": "IL6",
            "disease_name": "rheumatoid arthritis",
        },
        "ablation": "full",
        "status": "completed",
        "final_confidence": 0.8,
        "evidence_count": 2,
        "report": {
            "evidence": [
                {
                    "source": "PubMed broad query",
                    "support_label": "irrelevant",
                    "text": "A broad query returned off-target evidence.",
                }
            ]
        },
        "experiments": [{"name": "Run synovial cytokine readout"}],
        "tool_calls": [
            {"tool_name": "pubmed_literature_search_tool", "tool_source": "live_public_biomedical"},
            {"tool_name": "OpenTargets_get_associated_diseases_by_target", "tool_source": "tooluniverse"},
        ],
    }
    (bench_dir / "il6_ra__target_validity_review__r1__full.json").write_text(json.dumps(result), encoding="utf-8")

    report = build_report(bench_dir)
    markdown = render_markdown(report)

    assert report["benchmark"]["status"] == "completed"
    assert report["domain_summary"]["autoimmune_inflammation"]["runs"] == 1
    assert report["case_summaries"][0]["case_id"] == "il6_rheumatoid_arthritis"
    assert report["tool_usage"]["sources"][0][0] == "live_public_biomedical"
    assert report["weak_or_failed_branches"][0]["source"] == "PubMed broad query"
    assert "Claim Being Tested" in markdown
    assert "Preserved Weak Or Failed Branches" in markdown
