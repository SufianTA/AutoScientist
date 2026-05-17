import json

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.models import BoardPost, EvidenceItem, Hypothesis, Run
from app.db.session import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


def ascii_safe(value: object) -> str:
    text = str(value)
    replacements = {
        "α": "alpha",
        "β": "beta",
        "γ": "gamma",
        "δ": "delta",
        "κ": "kappa",
        "μ": "mu",
        "–": "-",
        "—": "-",
        "“": '"',
        "”": '"',
        "’": "'",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("ascii", errors="ignore").decode("ascii")


@router.get("/{run_id}")
def get_report(run_id: str, db: Session = Depends(get_db)) -> dict:
    return build_report(run_id, db)


@router.get("/{run_id}/download")
def download_report(run_id: str, format: str = "markdown", db: Session = Depends(get_db)) -> Response:
    report = build_report(run_id, db)
    if format == "json":
        return Response(
            content=json.dumps(report, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{run_id}_report.json"'},
        )
    if format not in {"markdown", "md"}:
        raise HTTPException(status_code=400, detail="format must be markdown or json")
    markdown = render_markdown_report(report)
    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{run_id}_report.md"'},
    )


def build_report(run_id: str, db: Session) -> dict:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    hypothesis = db.query(Hypothesis).filter(Hypothesis.run_id == run_id).first()
    evidence = db.query(EvidenceItem).filter(EvidenceItem.run_id == run_id).all()
    posts = db.query(BoardPost).filter(BoardPost.run_id == run_id).all()
    local_only = bool(evidence) and all(str(item.source).startswith("local_") for item in evidence)
    evidence_payload = [
        {
            "source": item.source,
            "text": item.evidence_text,
            "structured": item.structured_json,
            "support_label": item.support_label,
            "support_score": item.support_score,
        }
        for item in evidence
    ]
    if local_only:
        guardrails = [
            "Candidate hypothesis only.",
            "Local planning mode only; no external evidence was retrieved, so this is not evidence-supported.",
            "Run strict real-data mode with a configured LLM before scientific interpretation.",
        ]
    else:
        guardrails = [
            "Candidate hypothesis only.",
            "Computationally prioritized and evidence-supported, not validated.",
            "Requires experimental validation before clinical interpretation.",
        ]
    return {
        "run": {
            "id": run.id,
            "status": run.status,
            "final_confidence": run.final_confidence,
        },
        "hypothesis": {
            "title": hypothesis.title if hypothesis else "No hypothesis generated",
            "text": hypothesis.hypothesis_text if hypothesis else "",
            "confidence": hypothesis.confidence if hypothesis else None,
            "status": hypothesis.status if hypothesis else None,
        },
        "evidence": evidence_payload,
        "board_posts": [
            {
                "post_type": post.post_type,
                "agent_author": post.agent_author,
                "content": post.content_json,
            }
            for post in posts
        ],
        "guardrails": guardrails,
    }


def render_markdown_report(report: dict) -> str:
    hypothesis = report["hypothesis"]
    hypothesis_post = next(
        (post["content"] for post in report["board_posts"] if post["post_type"] == "hypothesis"),
        {},
    )
    lines = [
        f"# {ascii_safe(hypothesis['title'])}",
        "",
        f"Run: `{report['run']['id']}`",
        f"Status: `{report['run']['status']}`",
        f"Confidence: `{hypothesis['confidence']}`",
        f"Confidence interpretation: `{hypothesis_post.get('confidence_interpretation', 'not available')}`",
        "",
        "## Candidate Hypothesis",
        "",
        ascii_safe(hypothesis["text"]) or "No hypothesis text generated.",
        "",
        "## Scientific Assessment",
        "",
    ]
    for item in hypothesis_post.get("scientific_assessment", []):
        lines.append(f"- {ascii_safe(item)}")
    lines.extend(
        [
            "",
            "## Candidate Intervention Summary",
            "",
            ascii_safe(
                hypothesis_post.get(
                    "candidate_intervention_summary",
                    "No candidate intervention summary generated.",
                )
            ),
            "",
            "## Evidence",
            "",
            "| Source | Label | Score | Evidence |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in report["evidence"]:
        text = ascii_safe(item["text"]).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {item['source']} | {item['support_label']} | {item['support_score']} | {text} |"
        )
    lines.extend(["", "## Citations And Retrieved Records", ""])
    for citation in hypothesis_post.get("citations", []):
        label = ascii_safe(citation.get("title") or citation.get("source"))
        url = citation.get("url", "")
        details = []
        for key in ("pmid", "cid", "gene_id", "journal", "pubdate"):
            if citation.get(key):
                details.append(f"{key}: {citation[key]}")
        suffix = f" ({'; '.join(details)})" if details else ""
        lines.append(f"- [{label}]({url}){suffix}")
    lines.extend(["", "## Limitations", ""])
    for limitation in hypothesis_post.get("limitations", []):
        lines.append(f"- {ascii_safe(limitation)}")
    debate = hypothesis_post.get("agent_debate", {})
    if debate:
        lines.extend(["", "## Agent Debate And Revision", ""])
        lines.append(f"Collaboration model: `{debate.get('collaboration_model', 'not recorded')}`")
        lines.append("")
        for position in debate.get("scientist_positions", []):
            lines.append(
                f"- **{position.get('agent_name')}** ({position.get('vote', 'review')}): "
                f"{ascii_safe(position.get('position', ''))}"
            )
        adjudication = debate.get("pi_adjudication", {})
        if adjudication:
            lines.extend(["", "PI adjudication:", ""])
            if adjudication.get("rationale"):
                lines.append(f"- Rationale: {ascii_safe(adjudication.get('rationale'))}")
            for item in adjudication.get("softened_or_rejected_claims", []):
                lines.append(f"- Softened/rejected: {ascii_safe(item)}")
    lines.extend(["", "## Proposed Next Experiments", ""])
    for experiment in hypothesis_post.get("next_experiments", []):
        lines.append(
            f"- {ascii_safe(experiment.get('name'))} "
            f"[{experiment.get('type')}; feasibility: {experiment.get('feasibility')}; "
            f"information gain: {experiment.get('expected_information_gain')}]"
        )
    lines.extend(["", "## Research Board Posts", ""])
    for post in report["board_posts"]:
        content = post["content"]
        lines.extend([f"### {post['post_type']} by {post['agent_author']}", ""])
        if post["post_type"] == "hypothesis":
            lines.append(f"- Title: {ascii_safe(content.get('title', 'not available'))}")
            lines.append(f"- Confidence: {content.get('confidence', 'not available')}")
            if content.get("critique"):
                critique = content["critique"]
                if isinstance(critique, dict):
                    lines.append(f"- Critique: {ascii_safe(critique.get('critique', critique))}")
            lines.append("- Full raw board content is available in the JSON report/provenance export.")
        elif post["post_type"] == "critique":
            lines.append(f"- Severity: {content.get('severity', 'not available')}")
            lines.append(f"- Critique: {ascii_safe(content.get('critique', content))}")
            if content.get("recommended_fix"):
                lines.append(f"- Recommended fix: {ascii_safe(content.get('recommended_fix'))}")
        else:
            lines.append("- Full raw board content is available in the JSON report/provenance export.")
        lines.append("")
    lines.extend(["## Guardrails", ""])
    for guardrail in report["guardrails"]:
        lines.append(f"- {guardrail}")
    return "\n".join(lines) + "\n"
