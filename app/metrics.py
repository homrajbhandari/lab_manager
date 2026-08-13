"""Prometheus metrics for the lab-manager FastAPI app.

A single :class:`MetricsMiddleware` records request-level counters and
histograms; a small set of helpers make it easy to record DB and cache
hits from the rest of the codebase.

The metrics endpoint is exposed at ``METRICS_PATH`` (default
``/metrics``). It is mounted by ``app.main`` when
``PROMETHEUS_ENABLED=true`` and is not protected by auth — it is meant
to be reachable only from inside the cluster (the reverse proxy strips
external access to it).
"""

from __future__ import annotations

import os
import time
from typing import Awaitable, Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


# ---------------------------------------------------------------------------
# Metric registration. We avoid pulling in the prometheus_client package
# unless the user actually enabled metrics — but we import it lazily in
# setup_metrics so the rest of the module is import-safe.
# ---------------------------------------------------------------------------
class _Registry:
    """Thin wrapper that lazily instantiates the prometheus_client types."""

    def __init__(self) -> None:
        self.request_count: Optional[object] = None
        self.request_duration: Optional[object] = None
        self.errors_total: Optional[object] = None
        self.db_query_count: Optional[object] = None
        self.db_query_duration: Optional[object] = None
        self.active_connections: Optional[object] = None
        self.cache_hits: Optional[object] = None
        self.cache_misses: Optional[object] = None
        self._registry = None

    def setup(self) -> None:
        from prometheus_client import (  # type: ignore[import-not-found]
            CollectorRegistry, Counter, Gauge, Histogram,
        )

        self._registry = CollectorRegistry()

        self.request_count = Counter(
            "lab_manager_requests_total",
            "Total HTTP requests handled by the app.",
            labelnames=("method", "endpoint", "status"),
            registry=self._registry,
        )
        self.request_duration = Histogram(
            "lab_manager_request_duration_seconds",
            "End-to-end request duration in seconds.",
            labelnames=("method", "endpoint"),
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
            registry=self._registry,
        )
        self.errors_total = Counter(
            "lab_manager_errors_total",
            "HTTP responses with status >= 500 or raised exceptions.",
            labelnames=("method", "endpoint", "kind"),
            registry=self._registry,
        )
        self.db_query_count = Counter(
            "lab_manager_db_queries_total",
            "Number of SQL queries issued.",
            labelnames=("model", "operation"),
            registry=self._registry,
        )
        self.db_query_duration = Histogram(
            "lab_manager_db_query_duration_seconds",
            "SQL query duration in seconds.",
            labelnames=("model", "operation"),
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
            registry=self._registry,
        )
        self.active_connections = Gauge(
            "lab_manager_active_connections",
            "Number of currently in-flight HTTP requests.",
            registry=self._registry,
        )
        self.cache_hits = Counter(
            "lab_manager_cache_hits_total",
            "Cache hits.",
            labelnames=("cache",),
            registry=self._registry,
        )
        self.cache_misses = Counter(
            "lab_manager_cache_misses_total",
            "Cache misses.",
            labelnames=("cache",),
            registry=self._registry,
        )

    @property
    def registry(self):
        if self._registry is None:
            raise RuntimeError("metrics.setup() must be called before use")
        return self._registry


registry = _Registry()


def setup_metrics() -> None:
    """Initialise the prometheus registry. Idempotent."""
    if registry._registry is not None:  # type: ignore[attr-defined]
        return
    registry.setup()


def is_enabled() -> bool:
    return os.getenv("PROMETHEUS_ENABLED", "false").lower() in {"1", "true", "yes"}


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
class MetricsMiddleware(BaseHTTPMiddleware):
    """Records request count / duration / errors for every request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not is_enabled() or registry._registry is None:  # type: ignore[attr-defined]
            return await call_next(request)

        # Avoid double-counting the metrics endpoint itself.
        if request.url.path == os.getenv("METRICS_PATH", "/metrics"):
            return await call_next(request)

        method  = request.method
        # Use the route template (e.g. /projects/{project_id}) if known,
        # otherwise the raw path — keeps cardinality bounded.
        endpoint = request.scope.get("route").path if request.scope.get("route") else request.url.path  # type: ignore[union-attr]

        registry.active_connections.inc()  # type: ignore[union-attr]
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            registry.errors_total.labels(  # type: ignore[union-attr]
                method=method, endpoint=endpoint, kind="exception"
            ).inc()
            raise
        finally:
            elapsed = time.perf_counter() - started
            registry.request_duration.labels(  # type: ignore[union-attr]
                method=method, endpoint=endpoint
            ).observe(elapsed)
            registry.request_count.labels(  # type: ignore[union-attr]
                method=method, endpoint=endpoint, status=str(status_code)
            ).inc()
            if status_code >= 500:
                registry.errors_total.labels(  # type: ignore[union-attr]
                    method=method, endpoint=endpoint, kind="http_5xx"
                ).inc()
            registry.active_connections.dec()  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def record_db_query(model: str, operation: str, duration_seconds: float) -> None:
    if not is_enabled() or registry.db_query_count is None:  # type: ignore[attr-defined]
        return
    registry.db_query_count.labels(model=model, operation=operation).inc()           # type: ignore[union-attr]
    registry.db_query_duration.labels(model=model, operation=operation).observe(     # type: ignore[union-attr]
        duration_seconds
    )


def record_cache(cache: str, *, hit: bool) -> None:
    if not is_enabled():
        return
    target = registry.cache_hits if hit else registry.cache_misses  # type: ignore[attr-defined]
    if target is not None:
        target.labels(cache=cache).inc()  # type: ignore[union-attr]


async def metrics_endpoint() -> Response:
    """Return the Prometheus exposition format response."""
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    if registry._registry is None:  # type: ignore[attr-defined]
        setup_metrics()
    return Response(
        generate_latest(registry.registry),  # type: ignore[arg-type]
        media_type=CONTENT_TYPE_LATEST,
    )
