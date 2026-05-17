from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def candidate_env_files(extra_paths: list[Path] | None = None) -> list[Path]:
    app_file = Path(__file__).resolve()
    api_root = app_file.parents[1]
    repo_root = app_file.parents[3]
    return [
        repo_root / ".env",
        api_root / ".env",
        Path.cwd() / ".env",
        *(extra_paths or []),
    ]


def load_environment(extra_paths: list[Path] | None = None) -> list[str]:
    loaded: list[str] = []
    seen: set[Path] = set()
    for env_file in candidate_env_files(extra_paths):
        resolved = env_file.resolve()
        if resolved in seen or not resolved.exists():
            continue
        load_dotenv(resolved, override=False)
        loaded.append(str(resolved))
        seen.add(resolved)
    return loaded
