from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urljoin, urlencode
from urllib.request import Request, urlopen

from app.env import load_environment


load_environment()


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
        "default_model": "claude-sonnet-4-6",
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


def require_real_provider(config: dict[str, Any]) -> None:
    provider = config.get("llm_provider", "mock")
    if provider == "mock":
        raise RuntimeError(
            "Real autonomous mode requires a non-mock LLM provider. "
            "Use -LlmProvider openai, anthropic, gemini, openai_compatible, or local_http."
        )
    validation = validate_provider_config(provider, config.get("llm_api_key_env_var") or None)
    if not validation["valid"]:
        raise RuntimeError(validation["error"] or f"Invalid LLM provider config for {provider}.")
    if provider in {"openai_compatible", "local_http"} and not config.get("llm_base_url"):
        raise RuntimeError(f"{provider} requires llm_base_url / -LlmBaseUrl.")


def call_llm(
    *,
    provider: str,
    model: str,
    prompt: str,
    system_prompt: str = "",
    api_key_env_var: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> dict[str, Any]:
    if provider == "mock":
        raise RuntimeError("Mock provider cannot be used for a real LLM call.")
    started = time.perf_counter()
    if provider == "openai":
        output = _call_openai(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            api_key=_api_key(provider, api_key_env_var),
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif provider == "anthropic":
        output = _call_anthropic(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            api_key=_api_key(provider, api_key_env_var),
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif provider == "gemini":
        output = _call_gemini(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            api_key=_api_key(provider, api_key_env_var),
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif provider == "openai_compatible":
        output = _call_openai_compatible(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            api_key=_optional_api_key(provider, api_key_env_var),
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif provider == "local_http":
        output = _call_local_http(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        raise RuntimeError(f"Unsupported LLM provider: {provider}")
    return {
        "provider": provider,
        "model": model,
        "status": "success",
        "text": output,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


def call_llm_json(**kwargs: Any) -> dict[str, Any]:
    result = call_llm(**kwargs)
    result["json"] = parse_json_object(result["text"])
    return result


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        value = json.loads(stripped)
        return value if isinstance(value, dict) else {"value": value}
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(stripped[start : end + 1])
                return value if isinstance(value, dict) else {"value": value}
            except json.JSONDecodeError as exc:
                raise RuntimeError("LLM did not return a parseable JSON object.") from exc
        raise RuntimeError("LLM did not return a parseable JSON object.")


def _api_key(provider: str, api_key_env_var: str | None) -> str:
    key = _optional_api_key(provider, api_key_env_var)
    if not key:
        default = SUPPORTED_PROVIDERS[provider].get("default_api_key_env_var")
        raise RuntimeError(f"Missing API key env var: {api_key_env_var or default}")
    return key


def _optional_api_key(provider: str, api_key_env_var: str | None) -> str | None:
    env_var = api_key_env_var or SUPPORTED_PROVIDERS[provider].get("default_api_key_env_var")
    return os.getenv(env_var) if env_var else None


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int = 90) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM provider HTTP {exc.code}: {detail[:1000]}") from exc


def _call_openai(
    *,
    model: str,
    prompt: str,
    system_prompt: str,
    api_key: str,
    temperature: float,
    max_tokens: int,
) -> str:
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
        ],
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    response = _post_json(
        "https://api.openai.com/v1/responses",
        payload,
        {"Authorization": f"Bearer {api_key}"},
    )
    if response.get("output_text"):
        return response["output_text"]
    parts: list[str] = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                parts.append(text)
    if parts:
        return "\n".join(parts)
    raise RuntimeError(f"OpenAI response did not contain text: {str(response)[:1000]}")


def _call_anthropic(
    *,
    model: str,
    prompt: str,
    system_prompt: str,
    api_key: str,
    temperature: float,
    max_tokens: int,
) -> str:
    response = _post_json(
        "https://api.anthropic.com/v1/messages",
        {
            "model": model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    parts = [item.get("text", "") for item in response.get("content", []) if item.get("type") == "text"]
    if parts:
        return "\n".join(parts)
    raise RuntimeError(f"Anthropic response did not contain text: {str(response)[:1000]}")


def _call_gemini(
    *,
    model: str,
    prompt: str,
    system_prompt: str,
    api_key: str,
    temperature: float,
    max_tokens: int,
) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + model
        + ":generateContent?"
        + urlencode({"key": api_key})
    )
    response = _post_json(
        url,
        {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        },
        {},
    )
    parts: list[str] = []
    for candidate in response.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if part.get("text"):
                parts.append(part["text"])
    if parts:
        return "\n".join(parts)
    raise RuntimeError(f"Gemini response did not contain text: {str(response)[:1000]}")


def _call_openai_compatible(
    *,
    model: str,
    prompt: str,
    system_prompt: str,
    api_key: str | None,
    base_url: str | None,
    temperature: float,
    max_tokens: int,
) -> str:
    if not base_url:
        raise RuntimeError("OpenAI-compatible provider requires a base URL.")
    url = urljoin(base_url.rstrip("/") + "/", "v1/chat/completions")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    response = _post_json(
        url,
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        headers,
    )
    choices = response.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "")
    raise RuntimeError(f"OpenAI-compatible response did not contain text: {str(response)[:1000]}")


def _call_local_http(
    *,
    model: str,
    prompt: str,
    system_prompt: str,
    base_url: str | None,
    temperature: float,
    max_tokens: int,
) -> str:
    if not base_url:
        raise RuntimeError("Local HTTP provider requires a base URL.")
    response = _post_json(
        base_url,
        {
            "model": model,
            "system": system_prompt,
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        {},
    )
    for key in ("text", "output", "response", "content"):
        if isinstance(response.get(key), str):
            return response[key]
    raise RuntimeError(f"Local HTTP response did not contain text/output/response/content: {str(response)[:1000]}")
