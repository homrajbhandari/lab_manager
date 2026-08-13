#!/usr/bin/env python
"""Container healthcheck for the lab-manager app.

The Docker HEALTHCHECK runs this script. It exits 0 only when:
    * the FastAPI /health endpoint responds 200, AND
    * the database engine can execute a trivial query.

If either check fails the container is marked unhealthy and the orchestrator
restarts it (subject to the configured retry policy).

Designed to run with the stdlib only where possible — the app's own
modules are imported lazily so this script can also be used as a
standalone pre-flight check (e.g. from CI smoke tests).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any


DEFAULT_PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HEALTHCHECK_HOST", "127.0.0.1")
URL = os.getenv("HEALTHCHECK_URL", f"http://{HOST}:{DEFAULT_PORT}/health")
TIMEOUT = float(os.getenv("HEALTHCHECK_TIMEOUT", "4"))


def _emit(payload: dict[str, Any]) -> None:
    """Write a one-line JSON status record. Useful for log aggregation."""
    print(json.dumps(payload, sort_keys=True), file=sys.stderr)


def check_http() -> tuple[bool, str]:
    """Hit the /health endpoint. Returns (ok, detail)."""
    try:
        with urllib.request.urlopen(URL, timeout=TIMEOUT) as resp:
            ok = 200 <= resp.status < 300
            body = resp.read().decode("utf-8", errors="replace")
            return ok, f"http {resp.status} body={body[:200]!r}"
    except urllib.error.HTTPError as exc:
        return False, f"http error {exc.code}: {exc.reason}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"connection error: {exc}"


def check_database() -> tuple[bool, str]:
    """Round-trip a trivial SQL statement through the project's engine."""
    try:
        # Imported lazily so the script still works if the app is broken.
        from sqlalchemy import text

        from app.database import engine
    except Exception as exc:  # pragma: no cover - import failures are fatal here
        return False, f"db import failed: {exc}"

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "db ok"
    except Exception as exc:
        return False, f"db error: {exc}"


def check_redis() -> tuple[bool, str]:
    """Best-effort Redis check. Only runs when REDIS_URL is set and reachable."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return True, "redis not configured"

    try:
        import redis  # type: ignore[import-not-found]
    except ImportError:
        return True, "redis package not installed (skipping)"

    try:
        client = redis.Redis.from_url(redis_url, socket_timeout=TIMEOUT)
        if not client.ping():
            return False, "redis ping returned falsy"
        return True, "redis ok"
    except Exception as exc:
        return False, f"redis error: {exc}"


def main() -> int:
    started = time.time()

    results: dict[str, Any] = {
        "url": URL,
        "checks": {},
    }

    http_ok, http_detail = check_http()
    db_ok, db_detail = check_database()
    redis_ok, redis_detail = check_redis()

    results["checks"]["http"]   = {"ok": http_ok,  "detail": http_detail}
    results["checks"]["db"]     = {"ok": db_ok,    "detail": db_detail}
    results["checks"]["redis"]  = {"ok": redis_ok, "detail": redis_detail}

    overall = http_ok and db_ok and redis_ok
    results["ok"] = overall
    results["elapsed_ms"] = int((time.time() - started) * 1000)

    _emit(results)
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
