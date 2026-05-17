from __future__ import annotations

import re


ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
SECRET_PREFIXES = [
    "sk" + "-ant-",
    "sk" + "-proj-",
    "AI" + "za",
    "xox",
]
SECRET_VALUE_RE = re.compile(
    "|".join(
        [
            re.escape(SECRET_PREFIXES[0]),
            re.escape(SECRET_PREFIXES[1]),
            r"sk-[A-Za-z0-9_-]{20,}",
            re.escape(SECRET_PREFIXES[2]) + r"[0-9A-Za-z_-]{20,}",
            re.escape(SECRET_PREFIXES[3]) + r"[baprs]-",
            "BEGIN " + "PRIVATE KEY",
        ]
    ),
    re.IGNORECASE,
)


def looks_like_secret(value: str | None) -> bool:
    if not value:
        return False
    text = value.strip()
    return bool(SECRET_VALUE_RE.search(text)) or len(text) > 128


def validate_env_var_name(value: str | None, field_name: str) -> str:
    if value is None:
        return ""
    text = value.strip()
    if not text:
        return ""
    if looks_like_secret(text):
        raise ValueError(f"{field_name} must be an environment variable name, not a raw secret")
    if not ENV_VAR_RE.fullmatch(text):
        raise ValueError(f"{field_name} must contain only letters, numbers, and underscores")
    return text
