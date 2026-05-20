from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from app.db.session import SessionLocal
from app.services.scientific_memory import build_scientific_state_graph


def export_graph(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        graph = build_scientific_state_graph(db, run_id=args.run_id or None, limit=args.limit)
    finally:
        db.close()
    suffix = args.run_id or int(time.time())
    json_path = output_dir / f"scientific_state_graph_{suffix}.json"
    md_path = output_dir / f"scientific_state_graph_{suffix}.md"
    json_path.write_text(json.dumps(graph, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(graph), encoding="utf-8")
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "summary": graph["summary"],
    }


def render_markdown(graph: dict[str, Any]) -> str:
    summary = graph["summary"]
    lines = [
        "# AutoScientist Scientific State Graph",
        "",
        f"Nodes: `{summary['nodes']}`",
        f"Edges: `{summary['edges']}`",
        f"Hypotheses: `{summary['hypotheses']}`",
        f"Entities: `{summary['entities']}`",
        f"Experiments: `{summary['experiments']}`",
        f"Tools: `{summary['tools']}`",
        "",
        "## Hypotheses",
        "",
        "| Hypothesis | Confidence | Status | Evidence Sources |",
        "| --- | ---: | --- | --- |",
    ]
    for node in graph["nodes"]:
        if node["kind"] != "hypothesis":
            continue
        props = node.get("properties", {})
        evidence = props.get("evidence_summary") or {}
        sources = ", ".join(evidence.get("sources") or [])
        lines.append(
            f"| {_cell(node['label'])} | {props.get('confidence')} | "
            f"{props.get('status')} | {_cell(sources)} |"
        )
    lines.extend(["", "## Experiments", "", "| Experiment | Type | Information Gain | Feasibility |", "| --- | --- | --- | --- |"])
    for node in graph["nodes"]:
        if node["kind"] != "experiment":
            continue
        props = node.get("properties", {})
        lines.append(
            f"| {_cell(node['label'])} | {props.get('experiment_type')} | "
            f"{props.get('expected_information_gain')} | {props.get('feasibility')} |"
        )
    lines.extend(["", "## Top Tools", "", "| Tool | Source | Calls | Success Rate | Usefulness |", "| --- | --- | ---: | ---: | ---: |"])
    tool_nodes = [node for node in graph["nodes"] if node["kind"] == "tool"]
    for node in sorted(tool_nodes, key=lambda item: item.get("properties", {}).get("call_count") or 0, reverse=True)[:20]:
        props = node.get("properties", {})
        lines.append(
            f"| {_cell(node['label'])} | {props.get('source')} | "
            f"{props.get('call_count')} | {props.get('success_rate')} | {props.get('avg_usefulness')} |"
        )
    return "\n".join(lines)


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the derived AutoScientist scientific state graph.")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--output-dir", default="outputs/state_graphs")
    parser.add_argument("--limit", type=int, default=500)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    result = export_graph(parse_args(argv or sys.argv[1:]))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
