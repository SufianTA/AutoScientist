from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import BoardPost
from app.db.session import get_db

router = APIRouter(prefix="/board", tags=["board"])


class BoardPostCreate(BaseModel):
    post_type: str
    run_id: str | None = None
    hypothesis_id: str | None = None
    agent_author: str
    content: dict[str, Any] = Field(default_factory=dict)


@router.get("/posts")
def list_posts(db: Session = Depends(get_db)) -> dict:
    posts = db.query(BoardPost).order_by(BoardPost.created_at.desc()).all()
    return {
        "posts": [
            {
                "id": post.id,
                "post_type": post.post_type,
                "run_id": post.run_id,
                "hypothesis_id": post.hypothesis_id,
                "agent_author": post.agent_author,
                "content": post.content_json,
                "created_at": post.created_at.isoformat(),
            }
            for post in posts
        ]
    }


@router.post("/posts")
def create_post(payload: BoardPostCreate, db: Session = Depends(get_db)) -> dict:
    post = BoardPost(
        post_type=payload.post_type,
        run_id=payload.run_id,
        hypothesis_id=payload.hypothesis_id,
        agent_author=payload.agent_author,
        content_json=payload.content,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return {"id": post.id, "created_at": post.created_at.isoformat()}

