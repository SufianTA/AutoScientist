import json

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.models import BoardPost, EvidenceItem, Hypothesis, Run
from app.db.session import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


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
        "evidence": [
            {
                "source": item.source,
                "text": item.evidence_text,
                "support_label": item.support_label,
                "support_score": item.support_score,
            }
            for item in evidence
        ],
        "board_posts": [
            {
                "post_type": post.post_type,
                "agent_author": post.agent_author,
                "content": post.content_json,
            }
            for post in posts
        ],
        "guardrails": [
            "Candidate hypothesis only.",
            "Computationally prioritized and evidence-supported, not validated.",
            "Requires experimental validation before clinical interpretation.",
        ],
    }


def render_markdown_report(report: dict) -> str:
    hypothesis = report["hypothesis"]
    lines = [
        f"# {hypothesis['title']}",
        "",
        f"Run: `{report['run']['id']}`",
        f"Status: `{report['run']['status']}`",
        f"Confidence: `{hypothesis['confidence']}`",
        "",
        "## Candidate Hypothesis",
        "",
        hypothesis["text"] or "No hypothesis text generated.",
        "",
        "## Evidence",
        "",
        "| Source | Label | Score | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["evidence"]:
        text = str(item["text"]).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {item['source']} | {item['support_label']} | {item['support_score']} | {text} |"
        )
    lines.extend(["", "## Research Board Posts", ""])
    for post in report["board_posts"]:
        lines.extend(
            [
                f"### {post['post_type']} by {post['agent_author']}",
                "",
                "```json",
                json.dumps(post["content"], indent=2),
                "```",
                "",
            ]
        )
    lines.extend(["## Guardrails", ""])
    for guardrail in report["guardrails"]:
        lines.append(f"- {guardrail}")
    return "\n".join(lines) + "\n"
