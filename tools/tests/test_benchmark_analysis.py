import json
from pathlib import Path

from tools.analyze_autoscientist_benchmark import analyze_benchmark_dir, write_analysis


def test_analyze_benchmark_dir_reports_gates_and_ablation_delta(tmp_path: Path) -> None:
    bench = tmp_path / "bench"
    bench.mkdir()
    (bench / "benchmark_summary.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "task_count": 1,
                "result_count": 2,
                "realness_gates": {"passed": True, "failures": []},
                "state_graph": {"summary": {"nodes": 10}},
                "trained_policy": {"artifact_path": "policy.json", "training_summary": {"num_examples": 10}, "metrics": {}},
                "neural_policy": {
                    "artifact_path": "neural/manifest.json",
                    "metrics": {
                        "num_examples": 10,
                        "top1_holdout_accuracy": 0.7,
                        "top3_holdout_accuracy": 1.0,
                        "mrr_holdout": 0.85,
                        "majority_top1_holdout_accuracy": 0.2,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    base = {
        "schema": "autosci.benchmark_task_result.v0.1",
        "task": {"id": "task_1"},
        "run_id": "run_1",
        "status": "completed",
        "evidence_count": 3,
        "tool_calls": [{"tool_name": "pubmed_literature_search_tool"}],
        "integrations": {
            "public_biomedical": {"executed": True},
            "tooluniverse": {"executed": True},
            "local_board": {"executed": True},
        },
        "replay": {"available": True},
        "sciflow_policy": {"status": "success"},
        "value_assessment": {"score": 95},
    }
    (bench / "task_1__full.json").write_text(json.dumps({**base, "ablation": "full"}), encoding="utf-8")
    (bench / "task_1__no_memory.json").write_text(
        json.dumps({**base, "ablation": "no_memory", "replay": {"available": False}, "value_assessment": {"score": 82}}),
        encoding="utf-8",
    )

    analysis = analyze_benchmark_dir(bench)
    result = write_analysis(analysis, bench / "analysis")

    assert analysis["realness_gates"]["passed"] is True
    assert analysis["ablation_comparison"]["no_memory"]["score_delta_full_minus_ablation"] == 13
    assert analysis["integration_coverage"]["public_biomedical"]["coverage_rate"] == 1.0
    assert Path(result["analysis_markdown"]).exists()
