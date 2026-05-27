#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


CASE_TITLES = {
    "egfr-osimertinib-resistance": "EGFR Osimertinib Resistance in NSCLC",
    "braf-v600e-melanoma": "BRAF V600E Targeted Therapy in Melanoma",
    "ret-fusion-thyroid": "RET Fusions and Mutations in Thyroid Cancer",
    "kras-g12c-nsclc": "KRAS G12C Inhibition in NSCLC",
    "met-exon14-nsclc": "MET Exon 14 Skipping in NSCLC",
}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def text(value: Any, limit: int = 280) -> str:
    raw = " ".join(str(value or "").split())
    if len(raw) <= limit:
        return raw
    return raw[: limit - 1].rstrip() + "..."


def slug_from_path(path: Path) -> str:
    name = path.parent.name
    parts = name.rsplit("_", 1)
    return parts[0] if len(parts) == 2 and parts[1].isdigit() else name


def load_case(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = payload.get("report", {})
    slug = slug_from_path(path)
    evidence = report.get("evidence", []) or []
    experiments = report.get("experiments") or report.get("next_experiments") or []
    tools = payload.get("provenance", {}).get("tool_calls", []) or []
    steps = payload.get("provenance", {}).get("agent_steps", []) or []
    board_posts = report.get("board_posts", []) or []
    hyp_post = next((p.get("content", {}) for p in board_posts if p.get("post_type") == "hypothesis"), {})
    positions = hyp_post.get("agent_debate", {}).get("scientist_positions", []) or []
    readiness = report.get("scientific_strategy", {}).get("readiness", {}) or {}
    quality = report.get("quality_dashboard", {}) or {}
    return {
        "slug": slug,
        "title": CASE_TITLES.get(slug, slug.replace("-", " ").title()),
        "source_path": path,
        "report_path": path.with_name("report.md"),
        "payload": payload,
        "report": report,
        "evidence": evidence,
        "experiments": experiments,
        "tools": tools,
        "steps": steps,
        "positions": positions,
        "readiness": readiness,
        "quality": quality,
    }


def count(items: list[dict[str, Any]], key: str, fallback: str = "unknown") -> Counter[str]:
    values: Counter[str] = Counter()
    for item in items:
        value = item
        for part in key.split("."):
            value = value.get(part, {}) if isinstance(value, dict) else {}
        values[str(value or fallback)] += 1
    return values


def pct(num: int | float, den: int | float) -> int:
    return round((float(num) / float(den)) * 100) if den else 0


def metric_card(label: str, value: Any, note: str = "") -> str:
    return f'<article class="metric"><span>{esc(label)}</span><strong>{esc(value)}</strong><small>{esc(note)}</small></article>'


def bar(label: str, value: Any, width: int, note: str) -> str:
    return (
        '<div class="bar">'
        f'<div><strong>{esc(label)}</strong><small>{esc(note)}</small></div>'
        f'<div class="track"><span style="width:{max(0, min(100, width))}%"></span></div>'
        f'<b>{esc(value)}</b>'
        '</div>'
    )


def evidence_label(item: dict[str, Any]) -> str:
    score = item.get("score") if isinstance(item.get("score"), dict) else {}
    return str(item.get("support_label") or score.get("label") or "unscored")


def support_score(item: dict[str, Any]) -> Any:
    score = item.get("score") if isinstance(item.get("score"), dict) else {}
    return item.get("support_score", score.get("score", ""))


def display_summary(report: dict[str, Any], limit: int = 420) -> str:
    claims = [str(item) for item in report.get("key_claims", []) if item]
    if claims:
        return text(" ".join(claims[:3]), limit)
    summary = report.get("summary")
    if isinstance(summary, str):
        return text(summary, limit)
    hypothesis = report.get("hypothesis", {})
    if isinstance(hypothesis, dict):
        return text(hypothesis.get("text"), limit)
    return text(hypothesis, limit)


def render_table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>")
    return f"<div class=\"table\"><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


def copy_artifacts(case: dict[str, Any], run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(case["source_path"], run_dir / "provenance.json")
    if case["report_path"].exists():
        shutil.copy2(case["report_path"], run_dir / "report.md")


def render_case_page(case: dict[str, Any]) -> str:
    payload = case["payload"]
    report = case["report"]
    labels = Counter(evidence_label(item) for item in case["evidence"])
    tool_status = count(case["tools"], "status")
    tool_sources = count(case["tools"], "tool_source")
    vote_counts = Counter(str(p.get("vote") or "review") for p in case["positions"])
    readiness = case["readiness"]
    quality = case["quality"]
    run_id = payload.get("run_id")
    confidence = payload.get("final_confidence")
    success = tool_status.get("success", 0)
    tool_total = len(case["tools"])
    title = case["title"]

    evidence_rows = [
        [
            idx + 1,
            evidence_label(item),
            support_score(item),
            item.get("source", ""),
            text(item.get("text") or item.get("structured"), 360),
        ]
        for idx, item in enumerate(case["evidence"])
    ]
    tool_rows = [
        [
            idx + 1,
            item.get("tool_name"),
            item.get("tool_source"),
            item.get("status"),
            item.get("latency_ms"),
            text(item.get("input"), 180),
            text(item.get("output"), 260),
        ]
        for idx, item in enumerate(case["tools"])
    ]
    debate_rows = [
        [
            item.get("agent_name"),
            item.get("discipline"),
            item.get("vote"),
            text(item.get("position"), 360),
            text(item.get("concerns"), 260),
        ]
        for item in case["positions"]
    ]
    experiment_rows = [
        [
            idx + 1,
            item.get("name"),
            item.get("type"),
            item.get("cost"),
            item.get("feasibility"),
            item.get("expected_information_gain"),
            item.get("decision_impact_score"),
            item.get("gate_quality"),
            text(item.get("decision_gate"), 260),
        ]
        for idx, item in enumerate(case["experiments"])
    ]
    coverage_rows = [
        [
            row.get("id"),
            row.get("label"),
            row.get("status"),
            ", ".join(str(v) for v in (row.get("matched_sources") or [])[:6]),
        ]
        for row in (report.get("evidence_coverage_matrix", {}).get("requirements", []) or [])
    ]
    trace_rows = [
        [
            idx + 1,
            item.get("agent_name"),
            item.get("state_name"),
            item.get("started_at"),
            item.get("completed_at"),
            text(item.get("output"), 320),
        ]
        for idx, item in enumerate(case["steps"])
    ]
    claim_rows = [
        [
            idx + 1,
            item.get("text") or item.get("claim"),
            item.get("claim_boundary") or item.get("claim_type"),
            item.get("support_status") or f"{len(item.get('supporting_evidence_sources') or [])} support",
            ", ".join(str(v) for v in (item.get("evidence_gaps") or [])),
        ]
        for idx, item in enumerate(report.get("claim_graph", {}).get("claims", []) or [])
    ]
    claim_matrix_rows = [
        [
            row.get("id"),
            row.get("claim_type"),
            row.get("support_status"),
            text(row.get("query"), 220),
            ", ".join(str(v.get("source")) for v in (row.get("matched_evidence") or [])[:4]),
        ]
        for row in (report.get("claim_evidence_matrix", {}).get("claims", []) or [])
    ]
    quality_rows = [
        ["Evidence relevance", quality.get("evidence", {}).get("relevance_rate"), text(quality.get("evidence", {}).get("labels"), 260)],
        ["Tool success", quality.get("tools", {}).get("success_rate"), text(quality.get("tools", {}).get("statuses"), 260)],
        ["Planned claim coverage", quality.get("claims", {}).get("coverage_score"), f"missing {quality.get('claims', {}).get('missing')}"],
        ["Requirement coverage", quality.get("requirements", {}).get("coverage_score"), f"missing {quality.get('requirements', {}).get('missing')}"],
        ["Experiment gates", quality.get("experiments", {}).get("usable_or_strong"), f"strong {quality.get('experiments', {}).get('strong')}"],
    ]

    return html_doc(
        esc(title),
        f"""
<header class="top"><a href="../index.html">AutoScientist</a><span>powered by ToolUniverse</span></header>
<main>
  <section class="hero detail">
    <div>
      <div class="kicker">Full provenance dossier</div>
      <h1>{esc(title)}</h1>
      <p>{esc(display_summary(report, 460))}</p>
      <div class="actions">
        <a class="btn" href="runs/{esc(case['slug'])}/report.md">Markdown report</a>
        <a class="btn alt" href="runs/{esc(case['slug'])}/provenance.json">Full JSON provenance</a>
      </div>
    </div>
    <div class="panel">
      <span>Run</span><strong>{esc(run_id)}</strong>
      <span>Readiness</span><strong>{esc(readiness.get("tier"))} ({esc(readiness.get("score"))}/100)</strong>
      <span>Confidence</span><strong>{esc(confidence)}</strong>
    </div>
  </section>
  <section class="metrics">
    {metric_card("Agent steps", len(case["steps"]))}
    {metric_card("Tool calls", tool_total, f"{success} success")}
    {metric_card("Evidence", len(case["evidence"]), ", ".join(f"{k}:{v}" for k, v in labels.items()))}
    {metric_card("Debate", len(case["positions"]), ", ".join(f"{k}:{v}" for k, v in vote_counts.items()))}
    {metric_card("Experiments", len(case["experiments"]))}
    {metric_card("Claims", len(report.get("claim_graph", {}).get("claims", []) or []))}
    {metric_card("Quality flags", len(quality.get("flags", []) or []))}
  </section>
  <section class="section two">
    <div class="card">
      <h2>Run Calibration</h2>
      {bar("Tool success", f"{success}/{tool_total}", pct(success, tool_total), ", ".join(f"{k}:{v}" for k, v in tool_status.items()))}
      {bar("Coverage", report.get("evidence_coverage_matrix", {}).get("coverage_score", 0), pct(float(report.get("evidence_coverage_matrix", {}).get("coverage_score", 0)), 1), "case evidence requirements")}
      {bar("Claim evidence", report.get("claim_evidence_matrix", {}).get("coverage_score", 0), pct(float(report.get("claim_evidence_matrix", {}).get("coverage_score", 0)), 1), "planned claim retrieval")}
      {bar("Confidence", confidence, pct(float(confidence or 0), 1), "final bounded confidence")}
      <p>{esc(text(readiness.get("rationale"), 420))}</p>
      <ul>{''.join(f"<li>{esc(note)}</li>" for note in readiness.get("calibration_notes", []) or [])}</ul>
    </div>
    <div class="card">
      <h2>ToolUniverse And Public Tools</h2>
      <p>{esc(', '.join(f'{k}: {v}' for k, v in tool_sources.items()))}</p>
      <p>BioTruth critic: {esc(report.get("biotruth_critic", {}).get("verdict"))}, weighted score {esc(report.get("biotruth_critic", {}).get("weighted_score"))}. Evidence hierarchy {esc(report.get("evidence_hierarchy", {}).get("hierarchy_score"))}.</p>
      <p>Actionability: {esc(report.get("actionability_profile", {}).get("recommended_decision"))} / {esc(report.get("actionability_profile", {}).get("level"))}.</p>
    </div>
  </section>
  <section class="section"><h2>Quality Dashboard</h2>{render_table(["Signal", "Value", "Detail"], quality_rows)}<ul>{''.join(f"<li>{esc(flag)}</li>" for flag in quality.get("flags", []) or [])}</ul></section>
  <section class="section"><h2>Scientist Debate</h2>{render_table(["Agent", "Discipline", "Vote", "Position", "Concerns"], debate_rows)}</section>
  <section class="section"><h2>Evidence Items</h2>{render_table(["#", "Label", "Score", "Source", "Evidence text"], evidence_rows)}</section>
  <section class="section"><h2>Claim Graph</h2>{render_table(["#", "Claim", "Type", "Support", "Gaps"], claim_rows)}</section>
  <section class="section"><h2>Planned Claim Evidence</h2>{render_table(["ID", "Type", "Status", "Retrieval query", "Matched evidence"], claim_matrix_rows)}</section>
  <section class="section"><h2>Evidence Coverage Matrix</h2>{render_table(["ID", "Requirement", "Status", "Matched sources"], coverage_rows)}</section>
  <section class="section"><h2>Experiment Gates</h2>{render_table(["#", "Name", "Type", "Cost", "Feasibility", "Information gain", "Impact", "Gate quality", "Decision gate"], experiment_rows)}</section>
  <section class="section"><h2>Tool Calls</h2>{render_table(["#", "Tool", "Source", "Status", "Latency ms", "Input", "Output"], tool_rows)}</section>
  <section class="section"><h2>Agent Trace</h2>{render_table(["#", "Agent", "State", "Started", "Completed", "Output summary"], trace_rows)}</section>
</main>
""",
    )


def render_index(cases: list[dict[str, Any]]) -> str:
    total_tools = sum(len(c["tools"]) for c in cases)
    total_steps = sum(len(c["steps"]) for c in cases)
    total_evidence = sum(len(c["evidence"]) for c in cases)
    successes = sum(count(c["tools"], "status").get("success", 0) for c in cases)
    case_cards = []
    for case in cases:
        payload = case["payload"]
        report = case["report"]
        readiness = case["readiness"]
        labels = Counter(evidence_label(item) for item in case["evidence"])
        tool_status = count(case["tools"], "status")
        success = tool_status.get("success", 0)
        card_class = "caseCard"
        if readiness.get("tier") == "hypothesis_only":
            card_class += " caution"
        case_cards.append(
            f"""
<article class="{card_class}">
  <div class="caseTop"><span>{esc(case['slug'])}</span><strong>{esc(readiness.get('tier'))}</strong></div>
  <h3>{esc(case['title'])}</h3>
  <p>{esc(display_summary(report, 320))}</p>
  <div class="miniStats">
    <span>confidence <b>{esc(payload.get('final_confidence'))}</b></span>
    <span>readiness <b>{esc(readiness.get('score'))}/100</b></span>
    <span>tools <b>{success}/{len(case['tools'])}</b></span>
    <span>evidence <b>{len(case['evidence'])}</b></span>
  </div>
  <p class="labels">{esc(', '.join(f'{k}:{v}' for k, v in labels.items()))}</p>
  <a class="btn small" href="showcase/{esc(case['slug'])}.html">Open full dossier</a>
</article>
"""
        )

    body = f"""
<header class="top"><a href="#">AutoScientist</a><span>powered by ToolUniverse</span></header>
<main>
  <section class="hero">
    <div>
      <div class="kicker">{len(cases)} diverse oncology capability runs</div>
      <h1>AutoScientist audits cancer hypotheses with tools, agents, evidence, and calibrated limits.</h1>
      <p>These are full-system showcase runs, not a benchmark leaderboard. Each dossier includes ToolUniverse/OpenTargets calls, public biomedical evidence, claim graphs, scientist debate, critic calibration, experiment gates, and replayable provenance.</p>
      <div class="actions">
        <a class="btn" href="#cases">Explore cases</a>
        <a class="btn alt" href="showcase/runs">Open artifacts</a>
      </div>
    </div>
    <div class="panel brand">
      <span>AutoScientist</span>
      <strong>powered by ToolUniverse</strong>
      <small>public biomedical tools, OpenTargets grounding, multi-agent debate, and audit trails</small>
    </div>
  </section>
  <section class="metrics">
    {metric_card("Cases", len(cases), ", ".join(c["slug"].split("-")[0].upper() for c in cases))}
    {metric_card("Agent steps", total_steps)}
    {metric_card("Tool calls", total_tools, f"{successes} success")}
    {metric_card("Evidence items", total_evidence)}
    {metric_card("Experiments", sum(len(c["experiments"]) for c in cases))}
    {metric_card("Claims mapped", sum(len(c["report"].get("claim_graph", {}).get("claims", []) or []) for c in cases))}
  </section>
  <section class="section">
    <div class="intro"><div class="kicker">Genericity check</div><h2>Data-driven publishing, calibrated scoring.</h2></div>
    <div class="two">
      <div class="card"><h3>What is generic</h3><p>The static pages are generated from provenance JSON. Readiness calibration uses critic severity, evidence relevance, abstention policy, BioTruth/actionability signals, and tool outcomes rather than case-specific score constants.</p></div>
      <div class="card"><h3>What is curated</h3><p>The showcase objectives are curated cancer stress tests, and the runtime still has oncology-domain fallback templates for common target families. The public claims therefore stay about system capability, not unbiased clinical truth.</p></div>
    </div>
  </section>
  <section id="cases" class="section">
    <div class="intro"><div class="kicker">Case dossiers</div><h2>Every run keeps the same audit structure.</h2></div>
    <div class="caseGrid">{''.join(case_cards)}</div>
  </section>
  <section class="section">
    <div class="intro"><div class="kicker">Cross-case signal</div><h2>The system does not force all cases to look good.</h2></div>
    <div class="card">
      {render_table(["Case", "Run ID", "Confidence", "Readiness", "Evidence", "Tool calls", "Debate"], [
          [
              c["title"],
              c["payload"].get("run_id"),
              c["payload"].get("final_confidence"),
              f"{c['readiness'].get('tier')} ({c['readiness'].get('score')}/100)",
              len(c["evidence"]),
              len(c["tools"]),
              ", ".join(f"{k}:{v}" for k, v in Counter(str(p.get("vote") or "review") for p in c["positions"]).items()),
          ]
          for c in cases
      ])}
    </div>
  </section>
</main>
"""
    return html_doc("AutoScientist powered by ToolUniverse", body)


def render_artifact_index(cases: list[dict[str, Any]]) -> str:
    rows = [
        [
            case["title"],
            case["payload"].get("run_id"),
            f"../{case['slug']}.html",
            f"{case['slug']}/report.md",
            f"{case['slug']}/provenance.json",
        ]
        for case in cases
    ]
    body_rows = []
    for title, run_id, page, report, provenance in rows:
        body_rows.append(
            "<tr>"
            f"<td>{esc(title)}</td>"
            f"<td>{esc(run_id)}</td>"
            f"<td><a href=\"{esc(page)}\">Case page</a></td>"
            f"<td><a href=\"{esc(report)}\">Markdown report</a></td>"
            f"<td><a href=\"{esc(provenance)}\">JSON provenance</a></td>"
            "</tr>"
        )
    body = f"""
<header class="top"><a href="../../index.html">AutoScientist</a><span>powered by ToolUniverse</span></header>
<main>
  <section class="hero detail">
    <div>
      <div class="kicker">Replayable artifacts</div>
      <h1>Reports and provenance for every showcase run.</h1>
      <p>Each artifact package preserves the generated report and full structured provenance for tool calls, evidence, debate, claim graphs, calibration, experiment gates, and trace events.</p>
    </div>
    <div class="panel brand"><span>Artifact index</span><strong>{len(cases)} runs</strong><small>static, inspectable, and versioned in GitHub Pages</small></div>
  </section>
  <section class="section">
    <div class="table"><table><thead><tr><th>Case</th><th>Run ID</th><th>Dossier</th><th>Report</th><th>Provenance</th></tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>
  </section>
</main>
"""
    return html_doc("AutoScientist showcase artifacts", body)


CSS = """
:root{--bg:#f7f8fb;--ink:#111827;--muted:#5b6472;--line:#dfe4ec;--card:#fff;--accent:#0f766e;--blue:#1d4ed8;--warn:#a16207}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.45}a{color:inherit}.top{position:sticky;top:0;z-index:10;display:flex;justify-content:space-between;align-items:center;padding:16px 28px;background:rgba(247,248,251,.92);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}.top a{font-weight:800;text-decoration:none}.top span{color:var(--muted);font-size:14px}main{max-width:1220px;margin:0 auto;padding:28px}.hero{min-height:430px;display:grid;grid-template-columns:minmax(0,1.4fr) 420px;gap:28px;align-items:center}.hero.detail{min-height:330px}.kicker{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);font-weight:800}h1{font-size:clamp(40px,6vw,78px);line-height:.96;margin:10px 0 18px;letter-spacing:0}h2{font-size:28px;margin:0 0 14px}h3{font-size:18px;margin:0 0 10px}p{color:var(--muted);font-size:16px}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:22px}.btn{display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:0 16px;border-radius:8px;background:var(--ink);color:#fff;text-decoration:none;font-weight:750}.btn.alt{background:#fff;color:var(--ink);border:1px solid var(--line)}.btn.small{min-height:36px;font-size:14px}.panel,.card,.metric,.caseCard{background:var(--card);border:1px solid var(--line);border-radius:8px;box-shadow:0 18px 45px rgba(15,23,42,.06)}.panel{padding:26px;display:grid;gap:10px}.panel span{color:var(--muted);font-size:13px}.panel strong{font-size:22px}.panel.brand{min-height:260px;align-content:center;background:linear-gradient(135deg,#ffffff,#e8f5f3)}.panel.brand strong{font-size:36px;line-height:1}.metrics{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin:20px 0 36px}.metric{padding:18px}.metric span,.metric small{display:block;color:var(--muted);font-size:13px}.metric strong{display:block;font-size:28px;margin:5px 0}.section{margin:48px 0}.intro{max-width:760px;margin-bottom:18px}.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}.card{padding:20px}.caseGrid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.caseCard{padding:20px;display:flex;flex-direction:column;gap:10px}.caseCard.caution{border-color:#e7c66b}.caseTop{display:flex;justify-content:space-between;gap:12px;color:var(--muted);font-size:12px}.caseTop strong{color:var(--warn)}.miniStats{display:grid;grid-template-columns:1fr 1fr;gap:8px}.miniStats span{padding:8px;background:#f2f5f9;border-radius:6px;color:var(--muted);font-size:13px}.labels{font-size:13px}.bar{display:grid;grid-template-columns:220px 1fr 70px;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}.bar small{display:block;color:var(--muted)}.track{height:10px;background:#edf1f6;border-radius:99px;overflow:hidden}.track span{display:block;height:100%;background:linear-gradient(90deg,var(--accent),var(--blue))}.table{overflow:auto;border:1px solid var(--line);border-radius:8px;background:#fff}table{border-collapse:collapse;min-width:960px;width:100%}th,td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left;font-size:13px}th{position:sticky;top:0;background:#f2f5f9;color:#374151}td{color:#344054}ul{padding-left:18px;color:var(--muted)}@media(max-width:900px){main{padding:18px}.hero{grid-template-columns:1fr;min-height:auto}.metrics,.caseGrid,.two{grid-template-columns:1fr}.bar{grid-template-columns:1fr}.top{padding:14px 18px}h1{font-size:42px}}
"""


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <style>{css}</style>
</head>
<body>
__BODY__
</body>
</html>
""".replace("{css}", CSS)


def html_doc(title: str, body: str) -> str:
    return HTML_TEMPLATE.replace("__TITLE__", title).replace("__BODY__", body)


def latest_default_paths(base: Path) -> list[Path]:
    wanted = [
        "egfr-osimertinib-resistance",
        "braf-v600e-melanoma",
        "ret-fusion-thyroid",
        "kras-g12c-nsclc",
        "met-exon14-nsclc",
    ]
    paths = []
    for slug in wanted:
        matches = sorted(base.glob(f"{slug}_*/provenance.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            paths.append(matches[0])
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Build GitHub Pages showcase from AutoScientist provenance files.")
    parser.add_argument("provenance", nargs="*", type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs"))
    args = parser.parse_args()

    paths = args.provenance or latest_default_paths(Path("outputs/showcase"))
    if not paths:
        raise SystemExit("No provenance files found.")
    cases = [load_case(path) for path in paths]
    out = args.output
    showcase_dir = out / "showcase"
    runs_dir = showcase_dir / "runs"
    showcase_dir.mkdir(parents=True, exist_ok=True)

    for case in cases:
        run_dir = runs_dir / case["slug"]
        copy_artifacts(case, run_dir)
        (showcase_dir / f"{case['slug']}.html").write_text(render_case_page(case), encoding="utf-8")

    index = render_index(cases)
    (out / "index.html").write_text(index, encoding="utf-8")
    (runs_dir / "index.html").write_text(render_artifact_index(cases), encoding="utf-8")
    Path("index.html").write_text(index.replace('href="showcase/', 'href="docs/showcase/'), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
