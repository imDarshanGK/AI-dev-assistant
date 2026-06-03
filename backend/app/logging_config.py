"""
QyverixAI — Logging configuration

Central logging setup so every backend service emits records through one shared
formatter and level. Modules acquire their logger with
``logging.getLogger(__name__)`` and inherit this configuration from the root
logger, which keeps log formatting consistent across the whole backend.

Design notes
------------
* ``LOG_LEVEL`` (default ``INFO``) sets the root logger level.
* ``LOG_FORMAT`` selects ``plain`` (human readable, the default) or ``json``
  (one JSON object per line) for structured log shipping.
* ``configure_logging`` is idempotent: ``dictConfig`` replaces the root handler
  on every call, so repeated invocations (tests, reloads) never stack duplicate
  handlers or double-print records.
"""

from __future__ import annotations

import json
import logging
from logging.config import dictConfig

from .config import settings


_PLAIN_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class JsonFormatter(logging.Formatter):
    """Render each log record as a single line of JSON for structured ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, str] = {
            "timestamp": self.formatTime(record, _DATE_FORMAT),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _normalised_level(raw: str) -> int:
    """Map a level name to its numeric value, falling back to ``INFO``."""
    level = logging.getLevelName(raw.strip().upper())
    return level if isinstance(level, int) else logging.INFO


def configure_logging() -> None:
    """Install the shared formatter and level on the root logger.

    Call once during application startup. Every module that uses
    ``logging.getLogger(__name__)`` inherits this configuration, so log output
    is formatted identically across all backend services.
    """
    use_json = settings.log_format.strip().lower() == "json"
    formatter: dict[str, object] = (
        {"()": JsonFormatter}
        if use_json
        else {"format": _PLAIN_FORMAT, "datefmt": _DATE_FORMAT}
    )

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"default": formatter},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {
                "level": _normalised_level(settings.log_level),
                "handlers": ["console"],
            },
        }
    )
