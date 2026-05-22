from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from app.env import load_environment
from app.services.tooluniverse_adapter import ToolUniverseAdapter


def run_preflight(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    loaded_env = load_environment()
    checks = [
        check_python(),
        check_git(),
        check_disk(Path(args.workspace), min_free_gb=args.min_free_gb),
        check_env_keys(),
        check_module("fastapi"),
        check_module("sqlalchemy"),
        check_module("langgraph"),
        check_torch(require_gpu=args.require_gpu),
        check_gpu(require_gpu=args.require_gpu),
        check_network("NCBI E-utilities", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=PCSK9&retmode=json&retmax=0"),
        check_open_targets_graphql(),
    ]
    if not args.skip_tooluniverse:
        checks.append(check_tooluniverse(require=args.require_tooluniverse))
    result = {
        "schema": "autosci.machine_preflight.v1",
        "created_at_unix": int(started),
        "elapsed_seconds": round(time.time() - started, 2),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version,
            "executable": sys.executable,
            "cwd": str(Path.cwd()),
            "loaded_env_files": loaded_env,
            "git_revision": git_revision(),
        },
        "overall_status": overall_status(checks),
        "checks": checks,
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"machine_preflight_{int(started)}.json"
    md_path = output_dir / f"machine_preflight_{int(started)}.md"
    json_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(result), encoding="utf-8")
    result["json_path"] = str(json_path)
    result["markdown_path"] = str(md_path)
    json_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result


def check_python() -> dict[str, Any]:
    version = sys.version_info
    status = "pass" if version >= (3, 10) else "fail"
    return check("python", status, f"{version.major}.{version.minor}.{version.micro}", critical=True)


def check_git() -> dict[str, Any]:
    git = shutil.which("git")
    return check("git", "pass" if git else "fail", git or "git not found", critical=True)


def check_disk(workspace: Path, *, min_free_gb: float) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(workspace)
    free_gb = round(usage.free / (1024**3), 2)
    status = "pass" if free_gb >= 20 else "warn" if free_gb >= min_free_gb else "fail"
    return check("disk", status, f"{free_gb} GB free at {workspace}", critical=free_gb < min_free_gb)


def check_env_keys() -> dict[str, Any]:
    keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"]
    present = {name: bool(os.getenv(name)) for name in keys}
    provider_count = sum(1 for name in keys if present[name])
    status = "pass" if provider_count else "warn"
    return check("env_keys", status, "provider key present" if provider_count else "no provider key found", details=present)


def check_module(module_name: str) -> dict[str, Any]:
    available = importlib.util.find_spec(module_name) is not None
    return check(f"module:{module_name}", "pass" if available else "fail", "importable" if available else "missing", critical=True)


def check_torch(*, require_gpu: bool) -> dict[str, Any]:
    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
        status = "pass" if cuda_available or not require_gpu else "fail"
        return check(
            "torch",
            status,
            f"torch {torch.__version__}, cuda_available={cuda_available}",
            critical=require_gpu and not cuda_available,
        )
    except Exception as exc:
        return check("torch", "fail" if require_gpu else "warn", str(exc)[:300], critical=require_gpu)


def check_gpu(*, require_gpu: bool) -> dict[str, Any]:
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return check("gpu:nvidia-smi", "fail" if require_gpu else "warn", "nvidia-smi not found", critical=require_gpu)
    try:
        completed = subprocess.run(
            [nvidia_smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        output = (completed.stdout or completed.stderr).strip()
        status = "pass" if completed.returncode == 0 and output else "fail"
        return check("gpu:nvidia-smi", status, output[:1000], critical=require_gpu and status != "pass")
    except Exception as exc:
        return check("gpu:nvidia-smi", "fail" if require_gpu else "warn", str(exc)[:300], critical=require_gpu)


def check_network(name: str, url: str) -> dict[str, Any]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "AutoScientist-Preflight/0.1"})
        with urllib.request.urlopen(request, timeout=12) as response:
            status = "pass" if 200 <= response.status < 500 else "warn"
            return check(f"network:{name}", status, f"HTTP {response.status}", details={"url": url})
    except Exception as exc:
        return check(f"network:{name}", "warn", str(exc)[:300], details={"url": url})


def check_open_targets_graphql() -> dict[str, Any]:
    url = "https://api.platform.opentargets.org/api/v4/graphql"
    payload = json.dumps({"query": "{ __typename }"}).encode("utf-8")
    try:
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "AutoScientist-Preflight/0.1"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            body = response.read().decode("utf-8", errors="replace")
            status = "pass" if 200 <= response.status < 300 and "__typename" in body else "warn"
            return check("network:Open Targets GraphQL", status, f"HTTP {response.status}", details={"url": url})
    except Exception as exc:
        return check("network:Open Targets GraphQL", "warn", str(exc)[:300], details={"url": url})


def check_tooluniverse(*, require: bool) -> dict[str, Any]:
    health = ToolUniverseAdapter().tooluniverse_health()
    available = bool(health.get("available"))
    return check(
        "tooluniverse",
        "pass" if available else "fail" if require else "warn",
        health.get("status") or "unknown",
        critical=require and not available,
        details=health,
    )


def check(name: str, status: str, message: str, *, critical: bool = False, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "critical": critical,
        "message": message,
        "details": details or {},
    }


def overall_status(checks: list[dict[str, Any]]) -> str:
    if any(item["status"] == "fail" and item.get("critical") for item in checks):
        return "fail"
    if any(item["status"] in {"fail", "warn"} for item in checks):
        return "warn"
    return "pass"


def git_revision() -> str:
    try:
        completed = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        return completed.stdout.strip() if completed.returncode == 0 else ""
    except Exception:
        return ""


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# AutoScientist Machine Preflight",
        "",
        f"Overall status: `{result['overall_status']}`",
        f"Elapsed seconds: `{result['elapsed_seconds']}`",
        f"Python: `{result['platform']['executable']}`",
        f"Git revision: `{result['platform'].get('git_revision')}`",
        "",
        "| Check | Status | Critical | Message |",
        "| --- | --- | --- | --- |",
    ]
    for item in result["checks"]:
        message = str(item["message"]).replace("|", "\\|").replace("\n", " ")[:240]
        lines.append(f"| {item['name']} | `{item['status']}` | `{item['critical']}` | {message} |")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether a machine is ready to run AutoScientist.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--output-dir", default="outputs/preflight")
    parser.add_argument("--min-free-gb", type=float, default=2.0)
    parser.add_argument("--require-gpu", action="store_true")
    parser.add_argument("--require-tooluniverse", action="store_true")
    parser.add_argument("--skip-tooluniverse", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    result = run_preflight(parse_args(argv or sys.argv[1:]))
    print(json.dumps({
        "overall_status": result["overall_status"],
        "json_path": result["json_path"],
        "markdown_path": result["markdown_path"],
    }, indent=2))
    return 1 if result["overall_status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
