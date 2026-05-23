import json
from pathlib import Path

from tools.score_biomedical_correctness import (
    build_score_packets,
    heuristic_score,
    load_benchmark_results,
    load_json,
    summarize_scores,
    write_outputs,
)


def test_biotruth_heuristic_scoring_writes_summary(tmp_path: Path) -> None:
    bench = tmp_path / "bench"
    bench.mkdir()
    result = {
        "schema": "autosci.benchmark_task_result.v0.1",
        "task": {
            "id": "il6_rheumatoid_arthritis__target_validity_review",
            "case_id": "il6_rheumatoid_arthritis",
            "template_id": "target_validity_review",
            "domain": "autoimmune_inflammation",
            "gene_symbol": "IL6",
            "disease_name": "rheumatoid arthritis",
            "public_labels": {
                "open_targets_association_score": 0.82,
                "pubmed_gene_disease_count": 100,
            },
        },
        "ablation": "full",
        "run_id": "run_1",
        "status": "completed",
        "integrations": {
            "public_biomedical": {"executed": True, "call_count": 4},
            "tooluniverse": {"executed": True, "call_count": 2},
        },
        "replay": {"available": True},
        "value_assessment": {"score": 95},
        "report": {
            "hypothesis": {
                "title": "IL6 in rheumatoid arthritis",
                "text": "IL6 signaling is mechanistically linked to rheumatoid arthritis with uncertainty and safety caveats.",
            },
            "evidence": [
                {"source": "Open Targets", "text": "IL6 has target-disease evidence."},
                {"source": "PubMed", "text": "IL6 rheumatoid arthritis literature."},
                {"source": "ToolUniverse", "text": "Mechanism and pathway evidence."},
                {"source": "Open Targets", "text": "Clinical and tractability signal."},
                {"source": "PubMed", "text": "Counterevidence and limitations."},
                {"source": "PubMed", "text": "Safety and toxicity considerations."},
            ],
            "experiments": [
                {
                    "name": "Perturb IL6 pathway in disease-relevant cells",
                    "readout": "mechanism, controls, and failure criteria",
                }
            ],
            "guardrails": ["Do not infer clinical use from association score alone."],
        },
        "tool_calls": [
            {"tool_name": "pubmed_literature_search_tool", "tool_source": "live_public_biomedical", "status": "success"},
            {"tool_name": "opentargets_association_tool", "tool_source": "tooluniverse", "status": "success"},
            {"tool_name": "replay_export", "tool_source": "local_board", "status": "success"},
            {"tool_name": "memory_write", "tool_source": "scistate_graph", "status": "success"},
        ],
    }
    (bench / "il6_rheumatoid_arthritis__target_validity_review__full.json").write_text(
        json.dumps(result),
        encoding="utf-8",
    )

    rubric = load_json(Path("benchmarks/biotruth_rubric_v0_1.json"))
    results = load_benchmark_results(bench, ablations=["full"])
    packets = build_score_packets(results, rubric)
    scored = [{"packet": packets[0], "score": heuristic_score(packets[0], rubric)}]

    class Args:
        bench_dir = bench
        mode = "heuristic"

    summary = summarize_scores(scored, Args(), rubric)
    output = write_outputs(scored, summary, bench)

    assert summary["overall"]["mean_weighted_score"] > 50
    assert summary["by_ablation"]["full"]["count"] == 1
    assert Path(output["scores_path"]).exists()
    assert Path(output["markdown_path"]).exists()
