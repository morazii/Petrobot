"""Minimal curl wrapper for provider API calls."""

from __future__ import annotations

import json
import subprocess


def post_json(url: str, headers: dict[str, str], payload: dict, timeout_s: int = 60) -> dict:
    cmd = [
        "curl.exe",
        "-sS",
        "-L",
        "--max-time",
        str(timeout_s),
        "--connect-timeout",
        "10",
        "-X",
        "POST",
        url,
        "-H",
        "Content-Type: application/json",
    ]
    for key, val in headers.items():
        cmd.extend(["-H", f"{key}: {val}"])
    cmd.extend(["--data-binary", "@-"])

    body = json.dumps(payload, ensure_ascii=False)
    proc = subprocess.run(
        cmd,
        input=body,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(f"curl call failed ({proc.returncode}): {stderr}")

    stdout = (proc.stdout or "").strip()
    if not stdout:
        raise RuntimeError("curl call returned an empty response body.")

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as exc:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(f"provider response is not valid JSON: {exc}; stderr={stderr}") from exc

    if isinstance(parsed, dict) and parsed.get("error"):
        raise RuntimeError(f"provider error: {parsed['error']}")

    return parsed
