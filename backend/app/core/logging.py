"""Structured logging.

- Every log line carries `request_id` (and later `run_id`) via contextvars.
- JSON output in staging/prod, pretty console output in dev.
- Secret-looking keys are redacted before anything is written.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import EventDict, FilteringBoundLogger, WrappedLogger

_SECRET_MARKERS = ("key", "token", "secret", "password", "authorization")
# Counters such as `input_tokens` / `output_tokens` are usage numbers, not credentials.
_SAFE_SUFFIXES = ("_tokens",)


def _redact_secrets(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    for name in list(event_dict):
        lowered = name.lower()
        if lowered.endswith(_SAFE_SUFFIXES):
            continue
        if any(marker in lowered for marker in _SECRET_MARKERS):
            event_dict[name] = "***"
    return event_dict


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact_secrets,
    ]
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )

    structlog.configure(
        processors=[*shared, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging (uvicorn, sqlalchemy, alembic) through the same level.
    logging.basicConfig(level=level, stream=sys.stderr, format="%(levelname)s %(name)s %(message)s")


def get_logger(name: str | None = None) -> FilteringBoundLogger:
    logger: FilteringBoundLogger = structlog.get_logger(name)
    return logger
