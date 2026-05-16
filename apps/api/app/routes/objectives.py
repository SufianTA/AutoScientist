from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import Objective
from app.db.session import get_db

router = APIRouter(prefix="/objectives", tags=["objectives"])


class ObjectiveCreate(BaseModel):
    title: str
    objective: str
    mode: str = "full_auto_with_human_review"
    constraints: dict[str, Any] = Field(default_factory=dict)


@router.post("")
def create_objective(payload: ObjectiveCreate, db: Session = Depends(get_db)) -> dict:
    objective = Objective(
        title=payload.title,
        objective_text=payload.objective,
        constraints_json={"mode": payload.mode, **payload.constraints},
    )
    db.add(objective)
    db.commit()
    db.refresh(objective)
    return {
        "id": objective.id,
        "title": objective.title,
        "objective": objective.objective_text,
        "constraints": objective.constraints_json,
        "created_at": objective.created_at.isoformat(),
    }


@router.get("")
def list_objectives(db: Session = Depends(get_db)) -> list[dict]:
    objectives = db.query(Objective).order_by(Objective.created_at.desc()).all()
    return [
        {
            "id": item.id,
            "title": item.title,
            "objective": item.objective_text,
            "constraints": item.constraints_json,
            "created_at": item.created_at.isoformat(),
        }
        for item in objectives
    ]

