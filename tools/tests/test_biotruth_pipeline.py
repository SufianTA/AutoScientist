from pathlib import Path

from tools.run_biotruth_pipeline import parse_args, run_pipeline


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
