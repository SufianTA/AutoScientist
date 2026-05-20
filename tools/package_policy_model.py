from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

from app.db.models import RunReplay, ToolBenchmark, WorkflowPolicyModel
from app.db.session import SessionLocal
from app.services.scientific_memory import memory_summary


def package_model(args: argparse.Namespace) -> dict[str, Any]:
    db = SessionLocal()
    try:
        model = select_model(db, args.model_id)
        output_dir = Path(args.output_dir) / f"{model.name}_{model.version}"
        output_dir.mkdir(parents=True, exist_ok=True)
        model_path = Path(model.artifact_path)
        packaged_model = output_dir / "model.json"
        shutil.copyfile(model_path, packaged_model)

        replays = db.query(RunReplay).order_by(RunReplay.created_at.desc()).limit(args.replay_limit).all()
        benchmarks = db.query(ToolBenchmark).order_by(ToolBenchmark.call_count.desc()).all()
        package_manifest = {
            "schema": "autosci.workflow_policy_package.v1",
            "created_at_unix": int(time.time()),
            "model": serialize_model(model, packaged_model),
            "memory_summary": memory_summary(db),
            "tool_benchmarks": [serialize_tool_benchmark(item) for item in benchmarks],
            "replay_index": [
                {
                    "run_id": replay.run_id,
                    "replay_hash": replay.replay_hash,
                    "created_at": replay.created_at.isoformat(),
                }
                for replay in replays
            ],
            "usage": {
                "train": "POST /memory/policy/train",
                "predict": "POST /memory/policy/predict",
                "inspect_memory": "GET /memory/summary",
                "replay": "GET /memory/runs/{run_id}/replay",
            },
        }
        (output_dir / "manifest.json").write_text(json.dumps(package_manifest, indent=2, default=str), encoding="utf-8")
        (output_dir / "MODEL_CARD.md").write_text(render_model_card(package_manifest), encoding="utf-8")
        (output_dir / "README.md").write_text(render_readme(package_manifest), encoding="utf-8")
        replay_dir = output_dir / "replays"
        replay_dir.mkdir(exist_ok=True)
        for replay in replays:
            (replay_dir / f"{replay.run_id}.json").write_text(
                json.dumps(
                    {
                        "run_id": replay.run_id,
                        "replay_hash": replay.replay_hash,
                        "bundle": replay.bundle_json,
                    },
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
        zip_path = output_dir.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in output_dir.rglob("*"):
                archive.write(path, path.relative_to(output_dir.parent))
        return {
            "package_dir": str(output_dir),
            "zip_path": str(zip_path),
            "manifest": str(output_dir / "manifest.json"),
            "model_card": str(output_dir / "MODEL_CARD.md"),
            "readme": str(output_dir / "README.md"),
            "model": serialize_model(model, packaged_model),
        }
    finally:
        db.close()


def select_model(db: Any, model_id: str | None) -> WorkflowPolicyModel:
    if model_id:
        model = db.get(WorkflowPolicyModel, model_id)
    else:
        model = db.query(WorkflowPolicyModel).order_by(WorkflowPolicyModel.created_at.desc()).first()
    if model is None:
        raise SystemExit("No workflow policy model found. Run /memory/policy/train or tools/run_benchmark_suite.py first.")
    return model


def serialize_model(model: WorkflowPolicyModel, packaged_model_path: Path) -> dict[str, Any]:
    return {
        "id": model.id,
        "name": model.name,
        "version": model.version,
        "model_type": model.model_type,
        "source_artifact_path": model.artifact_path,
        "packaged_artifact_path": str(packaged_model_path),
        "training_summary": model.training_summary_json,
        "metrics": model.metrics_json,
        "created_at": model.created_at.isoformat(),
    }


def serialize_tool_benchmark(item: ToolBenchmark) -> dict[str, Any]:
    return {
        "tool_name": item.tool_name,
        "tool_source": item.tool_source,
        "call_count": item.call_count,
        "success_count": item.success_count,
        "failure_count": item.failure_count,
        "success_rate": item.success_count / item.call_count if item.call_count else None,
        "avg_latency_ms": item.avg_latency_ms,
        "avg_usefulness": item.avg_usefulness,
        "last_run_id": item.last_run_id,
    }


def render_model_card(manifest: dict[str, Any]) -> str:
    model = manifest["model"]
    metrics = model["metrics"]
    summary = model["training_summary"]
    lines = [
        "# AutoScientist Scientific Workflow Policy Model",
        "",
        "## Intended Use",
        "",
        "This is not a biomedical language model and should not be used to make clinical claims. "
        "It is a workflow-policy model that ranks next scientific actions for AutoScientist, "
        "such as state transitions and tool calls, using prior run traces and outcomes.",
        "",
        "## Model",
        "",
        f"- Name: `{model['name']}`",
        f"- Version: `{model['version']}`",
        f"- Type: `{model['model_type']}`",
        f"- Artifact: `model.json`",
        "",
        "## Training Data",
        "",
        f"- Examples: `{summary.get('num_examples')}`",
        f"- Distinct actions: `{summary.get('num_actions')}`",
        "- Source: AutoScientist run traces, tool calls, replay bundles, and run confidence.",
        "",
        "## Metrics",
        "",
        f"- Top-1 training accuracy: `{metrics.get('top1_training_accuracy')}`",
        "",
        "## Limitations",
        "",
        "- Current policy is a transparent count/feature baseline, not a neural transformer.",
        "- It learns from available traces, so quality improves as more benchmark runs are added.",
        "- It should recommend workflow actions, not scientific truth.",
        "",
        "## Recommended Next Step",
        "",
        "Use this package as the first dataset/model artifact for a richer Scientific Memory Transformer.",
    ]
    return "\n".join(lines)


def render_readme(manifest: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# AutoScientist Policy Package",
            "",
            "Contents:",
            "",
            "- `model.json`: workflow-policy model artifact.",
            "- `MODEL_CARD.md`: intended use, metrics, and limitations.",
            "- `manifest.json`: package metadata, memory summary, and tool benchmark summary.",
            "- `replays/`: replay bundles for recent benchmark runs.",
            "",
            "Use with AutoScientist:",
            "",
            "```bash",
            "python tools/package_policy_model.py",
            "curl -X POST http://127.0.0.1:8000/memory/policy/predict \\",
            "  -H 'Content-Type: application/json' \\",
            "  -d '{\"context\":{\"objective\":\"RA CD4 target prioritization\",\"state_name\":\"TOOL_SELECTION\"},\"top_k\":5}'",
            "```",
            "",
            f"Packaged model version: `{manifest['model']['version']}`",
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package a workflow-policy model for sharing.")
    parser.add_argument("--model-id", default="")
    parser.add_argument("--output-dir", default="outputs/packages")
    parser.add_argument("--replay-limit", type=int, default=10)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    package = package_model(parse_args(argv or sys.argv[1:]))
    print(json.dumps(package, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
