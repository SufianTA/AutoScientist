from __future__ import annotations

import os
from typing import Any


SUPPORTED_PROVIDERS = {
    "mock": {
        "display_name": "Mock local provider",
        "requires_key": False,
        "default_model": "mock-scientist",
    },
    "openai": {
        "display_name": "OpenAI",
        "requires_key": True,
        "default_model": "gpt-4.1",
        "default_api_key_env_var": "OPENAI_API_KEY",
    },
    "anthropic": {
        "display_name": "Anthropic",
        "requires_key": True,
        "default_model": "claude-3-5-sonnet-latest",
        "default_api_key_env_var": "ANTHROPIC_API_KEY",
    },
    "gemini": {
        "display_name": "Google Gemini",
        "requires_key": True,
        "default_model": "gemini-1.5-pro",
        "default_api_key_env_var": "GEMINI_API_KEY",
    },
    "openai_compatible": {
        "display_name": "OpenAI-compatible endpoint",
        "requires_key": False,
        "default_model": "local-model",
        "default_api_key_env_var": "OPENAI_COMPATIBLE_API_KEY",
    },
    "local_http": {
        "display_name": "Local HTTP model",
        "requires_key": False,
        "default_model": "local-http-model",
    },
}


def list_providers() -> list[dict[str, Any]]:
    return [{"id": key, **value} for key, value in SUPPORTED_PROVIDERS.items()]


def validate_provider_config(provider: str, api_key_env_var: str | None = None) -> dict[str, Any]:
    spec = SUPPORTED_PROVIDERS.get(provider)
    if spec is None:
        return {"provider": provider, "valid": False, "error": "Unsupported provider"}
    env_var = api_key_env_var or spec.get("default_api_key_env_var")
    has_key = bool(env_var and os.getenv(env_var))
    valid = not spec["requires_key"] or has_key
    return {
        "provider": provider,
        "valid": valid,
        "requires_key": spec["requires_key"],
        "api_key_env_var": env_var,
        "has_key": has_key,
        "default_model": spec["default_model"],
        "error": None if valid else f"Missing API key env var: {env_var}",
    }

