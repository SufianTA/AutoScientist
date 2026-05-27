from pathlib import Path

from tools.run_biotruth_pipeline import parse_args, pipeline_acceptance, run_pipeline


def test_biotruth_pipeline_prepare_mode_builds_manifest_and_tasks(tmp_path: Path) -> None:
    manifest = tmp_path / "biotruth.json"
    output_dir = tmp_path / "runs"
    args = parse_args(
        [
            "--mode",
            "prepare",
            "--manifest",
            str(manifest),
            "--max-cases",
            "1",
            "--templates-per-case",
            "2",
            "--offline-public-context",
            "--allow-mock",
            "--output-dir",
            str(output_dir),
            "--skip-review-package",
        ]
    )

    summary = run_pipeline(args)

    assert summary["acceptance"]["passed"] is True
    assert summary["manifest"]["expanded_task_count"] == 2
    assert summary["benchmark_summary"]["status"] == "prepared"
    assert Path(summary["summary_path"]).exists()
    assert manifest.exists()
    assert manifest.with_name(f"{manifest.stem}_tasks.jsonl").exists()


def test_pipeline_acceptance_uses_current_score_summary() -> None:
    args = parse_args(["--mode", "full", "--allow-mock"])
    benchmark_summary = {
        "status": "completed",
        "summary_by_ablation": {
            "full": {
                "runs": 1,
                "completed": 1,
            }
        },
    }
    score_result = {
        "summary": {
            "by_ablation": {
                "full": {
                    "mean_weighted_score": 91.0,
                    "critical_failure_rate": 0.0,
                }
            }
        }
    }

    acceptance = pipeline_acceptance(benchmark_summary, score_result, args)

    assert acceptance["passed"] is True
    assert acceptance["failures"] == []


def test_pipeline_acceptance_rejects_stale_or_failed_score_summary() -> None:
    args = parse_args(["--mode", "full", "--allow-mock"])
    benchmark_summary = {
        "status": "completed",
        "summary_by_ablation": {
            "full": {
                "runs": 1,
                "completed": 1,
            }
        },
    }
    score_result = {
        "summary": {
            "by_ablation": {
                "full": {
                    "mean_weighted_score": 66.0,
                    "critical_failure_rate": 1.0,
                }
            }
        }
    }

    acceptance = pipeline_acceptance(benchmark_summary, score_result, args)

    assert acceptance["passed"] is False
    assert "Full-system critical failure rate exceeded threshold." in acceptance["failures"]
