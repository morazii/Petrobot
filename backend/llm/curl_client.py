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
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"curl call failed ({proc.returncode}): {proc.stderr.strip()}")

    if not proc.stdout.strip():
        raise RuntimeError("curl call returned an empty response body.")

    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        stderr = proc.stderr.strip()
        raise RuntimeError(f"provider response is not valid JSON: {exc}; stderr={stderr}") from exc

    if isinstance(parsed, dict) and parsed.get("error"):
        raise RuntimeError(f"provider error: {parsed['error']}")

    return parsed
