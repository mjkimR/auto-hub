#!/usr/bin/env python3
"""Send the blocking local Codex reset time to Auto-Hub's global AI catalog."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def rpc(process: subprocess.Popen[str], request_id: int, method: str, params: dict | None = None) -> dict:
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}) + "\n")
    process.stdin.flush()
    while line := process.stdout.readline():
        message = json.loads(line)
        if message.get("id") == request_id:
            if "error" in message:
                raise RuntimeError(message["error"].get("message", "Codex app-server request failed"))
            return message["result"]
    raise RuntimeError("Codex app-server closed before responding")


def hub_url() -> str:
    if value := os.getenv("HUB_API_URL"):
        return value.rstrip("/")
    service = os.getenv("HUB_CLOUD_RUN_SERVICE")
    region = os.getenv("HUB_CLOUD_RUN_REGION")
    if service and region:
        return subprocess.check_output(
            ["gcloud", "run", "services", "describe", service, "--region", region, "--format=value(status.url)"], text=True
        ).strip().rstrip("/")
    raise RuntimeError("Set HUB_API_URL, or HUB_CLOUD_RUN_SERVICE and HUB_CLOUD_RUN_REGION")


def blocking_reset(rate_limits: dict) -> int:
    buckets = rate_limits.get("rateLimitsByLimitId")
    windows = buckets.get("codex") if isinstance(buckets, dict) else rate_limits.get("rateLimits")
    if not isinstance(windows, dict) or windows.get("limitId") not in (None, "codex"):
        raise RuntimeError("Codex did not report its quota bucket; use the UI to set the time explicitly")
    blocking = []
    for key in ("primary", "secondary"):
        window = windows.get(key)
        if window is None:
            continue
        if not isinstance(window, dict):
            raise RuntimeError("Codex reported an invalid quota window")
        used = window.get("usedPercent")
        reset = window.get("resetsAt")
        if not isinstance(used, (int, float)) or isinstance(used, bool):
            raise RuntimeError("Codex reported an invalid quota usage")
        if used >= 100:
            if not isinstance(reset, int) or isinstance(reset, bool) or reset <= 0:
                raise RuntimeError("Codex did not report a valid blocking reset time")
            blocking.append(window)
    if len(blocking) != 1:
        raise RuntimeError("Codex did not report exactly one blocking reset window; use the UI to set the time explicitly")
    return int(blocking[0]["resetsAt"])


def main() -> int:
    api_key = os.getenv("HUB_API_KEY")
    if not api_key:
        raise RuntimeError("Set HUB_API_KEY; this helper never reads or prints deployment secrets")
    process = subprocess.Popen(["codex", "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        rpc(process, 1, "initialize", {"clientInfo": {"name": "auto-hub", "version": "1"}})
        result = rpc(process, 2, "account/rateLimits/read")
    finally:
        process.terminate()
        process.wait(timeout=5)
    reset_at = datetime.fromtimestamp(blocking_reset(result), UTC)
    payload = json.dumps({"available_at": reset_at.isoformat(), "source": "local-codex-cli"}).encode()
    request = Request(
        f"{hub_url()}/api/v1/ai-catalogs/personal-codex/availability",
        data=payload,
        method="PUT",
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
    )
    try:
        with urlopen(request, timeout=20) as response:
            response.read()
    except HTTPError as exc:
        raise RuntimeError(f"Hub rejected the update ({exc.code})") from None
    print(f"personal-codex availability set to {reset_at.isoformat()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.SubprocessError) as exc:
        print(f"sync-codex-quota: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
