from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import ModelTool
from app.db.session import get_db
from app.services.model_onboarding import register_model_tool, serialize_model_tool

router = APIRouter(prefix="/models", tags=["models"])


class ModelToolCreate(BaseModel):
    name: str
    description: str
    provider: str = "local_http"
    endpoint_url: str | None = None
    api_key_env_var: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)


@router.get("")
def list_model_tools(db: Session = Depends(get_db)) -> dict:
    tools = db.query(ModelTool).order_by(ModelTool.created_at.desc()).all()
    return {"model_tools": [serialize_model_tool(tool) for tool in tools]}


@router.post("")
def create_model_tool(payload: ModelToolCreate, db: Session = Depends(get_db)) -> dict:
    tool = register_model_tool(
        db,
        name=payload.name,
        description=payload.description,
        provider=payload.provider,
        endpoint_url=payload.endpoint_url,
        api_key_env_var=payload.api_key_env_var,
        input_schema=payload.input_schema,
        output_schema=payload.output_schema,
    )
    return {"model_tool": serialize_model_tool(tool)}

