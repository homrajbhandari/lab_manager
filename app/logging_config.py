"""Application logging configuration.

Goals
-----
* Production logs are JSON, one event per line, easy to ship to an ELK
  / Loki / Cloud Logging aggregator.
* Development logs are human-readable, with colour if stdout is a TTY.
* Every log record carries a ``trace_id`` / ``request_id`` field when one
  is in scope, so a single request can be followed across the stack.
* Sentry is optional — if ``SENTRY_DSN`` is set we install the SDK and
  forward ERROR/CRITICAL records as events.

A single helper, :func:`configure_logging`, is the only entry point.
Call it once from ``app.main`` (or the entrypoint script) and let the
rest of the codebase use ``logging.getLogger(__name__)`` as usual.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
from contextvars import ContextVar
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Per-request context. Populated by middleware in app.main.
# ---------------------------------------------------------------------------
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_var: ContextVar[Optional[int]] = ContextVar("user_id", default=None)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------
class JSONFormatter(logging.Formatter):
    """Render records as single-line JSON suitable for log aggregators."""

    # Standard ``LogRecord`` attributes we never want to copy verbatim.
    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - stdlib API
        payload: dict[str, Any] = {
            "ts":      time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
                      + f".{int(record.msecs):03d}Z",
            "level":   record.levelname,
            "logger":  record.name,
            "message": record.getMessage(),
        }

        # Inject request-scoped context if set.
        if (trace_id := trace_id_var.get()) is not None:
            payload["trace_id"] = trace_id
        if (request_id := request_id_var.get()) is not None:
            payload["request_id"] = request_id
        if (user_id := user_id_var.get()) is not None:
            payload["user_id"] = user_id

        # Copy any extra=... fields the caller passed.
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except TypeError:
                payload[key] = repr(value)

        if record.exc_info:
            payload["exception"] = {
                "type":   record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                "message": str(record.exc_info[1]) if record.exc_info[1] else "",
                "traceback": "".join(traceback.format_exception(*record.exc_info)),
            }

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class HumanFormatter(logging.Formatter):
    """Coloured output for local development."""

    GREY   = "\x1b[90m"
    BLUE   = "\x1b[34m"
    YELLOW = "\x1b[33m"
    RED    = "\x1b[31m"
    BOLD   = "\x1b[1m"
    RESET  = "\x1b[0m"

    LEVEL_COLOURS = {
        logging.DEBUG:    BLUE,
        logging.INFO:     GREY,
        logging.WARNING:  YELLOW,
        logging.ERROR:    RED,
        logging.CRITICAL: BOLD + RED,
    }

    def __init__(self, *, use_color: bool) -> None:
        super().__init__()
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        colour = self.LEVEL_COLOURS.get(record.levelno, "") if self.use_color else ""
        reset  = self.RESET if self.use_color else ""

        ts = time.strftime("%H:%M:%S", time.gmtime(record.created))
        base = (
            f"{self.GREY if self.use_color else ''}{ts}{reset} "
            f"{colour}{record.levelname:<8}{reset} "
            f"{record.name}: {record.getMessage()}"
        )

        # Append trace id when present so dev still gets a quick correlation hook.
        if (request_id := request_id_var.get()) is not None:
            base += f"  {self.GREY}req={request_id}{reset}"

        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)

        return base


# ---------------------------------------------------------------------------
# Sentry bridge (optional)
# ---------------------------------------------------------------------------
def _install_sentry(dsn: str, environment: str) -> None:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:
        logging.getLogger(__name__).warning(
            "SENTRY_DSN set but sentry-sdk is not installed — skipping"
        )
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05")),
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.0")),
        integrations=[
            LoggingIntegration(
                level=logging.INFO,        # breadcrumbs
                event_level=logging.ERROR, # capture as events
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def configure_logging(
    *,
    level: Optional[str] = None,
    fmt:   Optional[str] = None,
    app_env: Optional[str] = None,
) -> None:
    """Configure the root logger exactly once.

    Safe to call multiple times — subsequent calls are no-ops unless the
    level/format arguments change.
    """
    level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    fmt   = (fmt   or os.getenv("LOG_FORMAT", "text")).lower()
    app_env = (app_env or os.getenv("APP_ENV", "development")).lower()

    root = logging.getLogger()
    if getattr(root, "_lab_manager_configured", False):
        return

    root.setLevel(level)

    # Remove any pre-existing handlers (e.g. uvicorn's) so we have one stream.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    if fmt == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(HumanFormatter(use_color=sys.stdout.isatty()))
    root.addHandler(handler)

    # Quiet down chatty third-party loggers.
    logging.getLogger("uvicorn.access").setLevel(os.getenv("UVICORN_ACCESS_LOG_LEVEL", "INFO"))
    logging.getLogger("sqlalchemy.engine").setLevel(os.getenv("SQL_LOG_LEVEL", "WARNING"))

    root._lab_manager_configured = True  # type: ignore[attr-defined]

    if (dsn := os.getenv("SENTRY_DSN")):
        _install_sentry(dsn, environment=app_env)

    logging.getLogger(__name__).info(
        "Logging configured level=%s format=%s env=%s", level, fmt, app_env
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
