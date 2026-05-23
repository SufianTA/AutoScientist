from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path
from typing import Any


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)(['\"\s:=]+)([A-Za-z0-9_\-./+=]{12,})"),
]
TEXT_SUFFIXES = {".json", ".md", ".txt", ".csv", ".log", ".yaml", ".yml"}


def collect_review_package(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    bench_dir = Path(args.bench_dir) if args.bench_dir else latest_dir(Path(args.benchmark_root))
    if bench_dir is None:
        raise SystemExit(f"No benchmark directory found under {args.benchmark_root}")
    output_dir = Path(args.output_dir)
    package_name = args.name or f"autoscientist_review_package_{int(started)}"
    staging = output_dir / package_name
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    artifact_index = []
    copy_tree_sanitized(bench_dir, staging / "benchmark_run", artifact_index)
    for extra in args.extra:
        path = Path(extra)
        if path.exists():
            copy_path_sanitized(path, staging / "extra" / path.name, artifact_index)
    manifest = {
        "schema": "autosci.review_package.v1",
        "created_at_unix": int(started),
        "source_benchmark_dir": str(bench_dir),
        "package_name": package_name,
        "artifact_count": len(artifact_index),
        "artifacts": artifact_index,
        "usage": {
            "start_here": "benchmark_run/benchmark_summary.md",
            "biotruth_scores": "benchmark_run/biotruth_scores.md",
            "biotruth_packets": "benchmark_run/biotruth_score_packets.jsonl",
            "analysis": "benchmark_run/analysis/",
            "state_graph": "benchmark_run/scistate_graph.json",
            "tasks": "benchmark_run/benchmark_tasks.json",
        },
        "caveats": [
            "SciFlow Policy is a workflow-controller model, not a biomedical foundation model.",
            "BioTruth heuristic scores are triage signals; judge-mode or expert review is required for biological correctness claims.",
            "The active benchmark path uses public biomedical data, ToolUniverse/OpenTargets, SciState Graph, and SciFlow Policy.",
        ],
    }
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    (staging / "README.md").write_text(render_readme(manifest), encoding="utf-8")
    secret_hits = scan_for_secrets(staging)
    zip_path = output_dir / f"{package_name}.zip"
    result = {
        "schema": "autosci.review_package_result.v1",
        "package_dir": str(staging),
        "zip_path": str(zip_path),
        "manifest_path": str(staging / "manifest.json"),
        "readme_path": str(staging / "README.md"),
        "artifact_count": len(artifact_index),
        "secret_like_matches": secret_hits,
    }
    (staging / "package_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    if secret_hits and not args.allow_secret_matches:
        raise SystemExit(f"Secret-like strings remain in package staging: {secret_hits[:5]}")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in staging.rglob("*"):
            archive.write(path, path.relative_to(staging.parent))
    return result


def latest_dir(root: Path) -> Path | None:
    if not root.exists():
        return None
    dirs = [path for path in root.iterdir() if path.is_dir()]
    if not dirs:
        return None
    return sorted(dirs, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def copy_tree_sanitized(source: Path, destination: Path, artifact_index: list[dict[str, Any]]) -> None:
    for path in source.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(source)
        copy_path_sanitized(path, destination / relative, artifact_index)


def copy_path_sanitized(source: Path, destination: Path, artifact_index: list[dict[str, Any]]) -> None:
    if source.name in {".env", "bioautosci.settings.json", "settings.local.json"}:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() in TEXT_SUFFIXES:
        text = source.read_text(encoding="utf-8", errors="replace")
        destination.write_text(redact(text), encoding="utf-8")
    else:
        shutil.copy2(source, destination)
    artifact_index.append(
        {
            "source": str(source),
            "path": str(destination),
            "bytes": destination.stat().st_size,
            "kind": source.suffix.lower().lstrip(".") or "file",
        }
    )


def redact(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        def replace(match: re.Match[str]) -> str:
            if match.lastindex and match.lastindex >= 3:
                return f"{match.group(1)}{match.group(2)}[REDACTED]"
            return "[REDACTED]"

        redacted = pattern.sub(replace, redacted)
    return redacted


def scan_for_secrets(root: Path) -> list[dict[str, Any]]:
    hits = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append({"path": str(path), "pattern": pattern.pattern})
    return hits


def render_readme(manifest: dict[str, Any]) -> str:
    lines = [
        "# AutoScientist Review Package",
        "",
        "Start with `benchmark_run/benchmark_summary.md`.",
        "",
        "This package contains the benchmark outputs, state graph, policy/package artifacts, task manifest, and replay-oriented JSON files needed to audit the run.",
        "",
        "## Contents",
        "",
        "- `benchmark_run/benchmark_summary.md`: concise benchmark summary and ablation deltas.",
        "- `benchmark_run/biotruth_scores.md`: BioTruth correctness scores when generated.",
        "- `benchmark_run/biotruth_score_packets.jsonl`: compact review packets for expert or rubric-judge scoring.",
        "- `benchmark_run/analysis/`: deeper benchmark analysis and limitations.",
        "- `benchmark_run/benchmark_summary.json`: machine-readable summary.",
        "- `benchmark_run/benchmark_tasks.json`: generated task set and public context.",
        "- `benchmark_run/scistate_graph.json`: exported SciState Graph.",
        "- `benchmark_run/packages/`: packaged SciFlow Policy artifacts when generated.",
        "",
        "## Caveats",
        "",
    ]
    lines.extend(f"- {item}" for item in manifest["caveats"])
    lines.extend(["", "## Artifact Index", ""])
    for artifact in manifest["artifacts"][:200]:
        lines.append(f"- `{artifact['path']}` ({artifact['bytes']} bytes)")
    if len(manifest["artifacts"]) > 200:
        lines.append(f"- ... {len(manifest['artifacts']) - 200} more artifacts")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect a sanitized AutoScientist benchmark package for sharing.")
    parser.add_argument("--benchmark-root", default="outputs/autoscientist_bench")
    parser.add_argument("--bench-dir", default="")
    parser.add_argument("--output-dir", default="outputs/review_packages")
    parser.add_argument("--name", default="")
    parser.add_argument("--extra", action="append", default=[])
    parser.add_argument("--allow-secret-matches", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    result = collect_review_package(parse_args(argv or sys.argv[1:]))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
