from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import ToolCall
from app.db.session import get_db
from app.services.open_scientist_adapters import OpenScientistCapabilityRegistry
from app.services.tooluniverse_adapter import ToolUniverseAdapter

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolExecuteRequest(BaseModel):
    tool_name: str
    input: dict[str, Any]
    run_id: str | None = None
    step_id: str | None = None


def get_adapter() -> ToolUniverseAdapter:
    settings = get_settings()
    return ToolUniverseAdapter(mode=settings.tool_mode, scan_all=settings.tooluniverse_scan_all)


@router.get("/inventory")
def inventory(adapter: ToolUniverseAdapter = Depends(get_adapter)) -> dict:
    return {"tools": adapter.list_tools()}


@router.get("/health")
def tool_health(adapter: ToolUniverseAdapter = Depends(get_adapter)) -> dict:
    return {
        "tooluniverse": adapter.tooluniverse_health(),
        "open_scientist": OpenScientistCapabilityRegistry().health(),
    }


@router.post("/execute")
def execute_tool(
    payload: ToolExecuteRequest,
    db: Session = Depends(get_db),
    adapter: ToolUniverseAdapter = Depends(get_adapter),
) -> dict:
    try:
        result = adapter.execute(payload.tool_name, payload.input)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    call = ToolCall(
        run_id=payload.run_id,
        step_id=payload.step_id,
        tool_name=payload.tool_name,
        tool_source="custom",
        input_json=payload.input,
        output_json=result,
        status=result["status"],
        latency_ms=result["runtime_ms"],
    )
    db.add(call)
    db.commit()
    return {"tool_call_id": call.id, "result": result}
