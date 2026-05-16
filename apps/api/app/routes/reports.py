from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import BoardPost, EvidenceItem, Hypothesis, Run
from app.db.session import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{run_id}")
def get_report(run_id: str, db: Session = Depends(get_db)) -> dict:
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

