from fastapi import APIRouter

from app.services.llm_provider import list_providers, validate_provider_config

router = APIRouter(prefix="/framework", tags=["framework"])


@router.get("/agent-runtimes")
def agent_runtimes() -> dict:
    return {
        "default": "langgraph",
        "runtimes": [
            {
                "id": "langgraph",
                "display_name": "LangGraph",
                "status": "default",
                "notes": "Open-source state graph runtime for local, auditable scientific workflows.",
            },
            {
                "id": "custom_state_machine",
                "display_name": "BioAutoScientist state machine",
                "status": "available",
                "notes": "Deterministic fallback runtime used for tests and mock demo runs.",
            },
            {
                "id": "openclaw",
                "display_name": "OpenClaw",
                "status": "optional_placeholder",
                "notes": "Optional future adapter; not used as the constrained scientific core.",
            },
        ],
    }


@router.get("/llm-providers")
def llm_providers() -> dict:
    return {"providers": list_providers()}


@router.get("/llm-providers/{provider}/validate")
def validate_llm_provider(provider: str, api_key_env_var: str | None = None) -> dict:
    return validate_provider_config(provider, api_key_env_var)

