"""
Centralized logging configuration for QyverixAI backend.

Supports a global default log level plus per-component overrides, all
configurable via environment variables — no code changes required to
change verbosity in production or while debugging a specific module.

Usage
-----
    LOG_LEVEL=INFO                  # global default for everything under "app"
    LOG_LEVEL_AI_PROVIDER=DEBUG     # verbose logs only for ai_provider.py
    LOG_LEVEL_SCHEDULER=WARNING     # quiet down the scheduler
    LOG_LEVEL_CACHE=DEBUG
    LOG_FORMAT="%(asctime)s %(levelname)s %(name)s: %(message)s"
    LOG_JSON=false                  # set true for structured JSON logs

Call ``configure_logging()`` once at application startup (already wired
into ``main.py``'s lifespan). Each module continues to use the standard
``logging.getLogger(__name__)`` pattern — no per-module code changes are
needed for this feature to take effect.
"""

from __future__ import annotations

import json
import logging
import logging.config
import os
from datetime import UTC, datetime

from .config import settings

# Maps a short, human-friendly component name (used in the
# LOG_LEVEL_<COMPONENT> env var) to the actual logger name used in the
# codebase via logging.getLogger(__name__) or logging.getLogger("...").
#
# Add a new entry here whenever a new component should support its own
# independent log level.
COMPONENT_LOGGER_MAP: dict[str, str] = {
    "api": "ai_assistant.api",
    "ai_provider": "ai_provider",
    "llm_analysis": "ai_assistant.api",
    "cache": "ai_assistant.api",
    "scheduler": "app.services.scheduler",
    "email": "app.services.email_service",
    "error_tracking": "ai_assistant.api",
    "upload": "app.routers.upload_file",
    "file_validator": "app.utils.file_validator",
    "main": "app.main",
    "collaboration": "app.routers.collaboration",
}

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _normalise_level(raw: str | None, fallback: str) -> str:
    """Validate a level string, falling back to ``fallback`` if invalid."""
    if not raw:
        return fallback
    level = raw.strip().upper()
    return level if level in _VALID_LEVELS else fallback


def _collect_component_overrides() -> dict[str, str]:
    """Read all ``LOG_LEVEL_<COMPONENT>`` environment variables.

    Returns a mapping of actual logger name -> level string, ready to be
    merged into the logging dictConfig.
    """
    overrides: dict[str, str] = {}
    for component, logger_name in COMPONENT_LOGGER_MAP.items():
        env_key = f"LOG_LEVEL_{component.upper()}"
        raw_value = os.getenv(env_key)
        if raw_value is None:
            continue
        level = _normalise_level(raw_value, settings.log_level)
        overrides[logger_name] = level
    return overrides


class _JsonFormatter(logging.Formatter):
    """Minimal structured JSON log formatter (opt-in via LOG_JSON=true)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def get_effective_levels() -> dict[str, str]:
    """Return the resolved log level for every known component.

    Useful for the /health or /metrics endpoints, and for tests, to verify
    the configuration that was actually applied.
    """
    default_level = _normalise_level(settings.log_level, "INFO")
    overrides = _collect_component_overrides()
    resolved: dict[str, str] = {}
    for component, logger_name in COMPONENT_LOGGER_MAP.items():
        resolved[component] = overrides.get(logger_name, default_level)
    return resolved


def configure_logging() -> None:
    """Apply global + per-component logging configuration.

    Safe to call multiple times (e.g. in tests) — each call fully replaces
    the previous logging configuration via dictConfig's incremental=False
    default, avoiding duplicate handlers.
    """
    default_level = _normalise_level(settings.log_level, "INFO")
    overrides = _collect_component_overrides()

    formatter_name = "json" if settings.log_json else "standard"

    loggers_config: dict[str, dict] = {
        "app": {
            "level": default_level,
            "handlers": ["console"],
            "propagate": False,
        }
    }
    # ai_assistant.api and ai_provider are historical logger names used
    # directly (not nested under "app"), so they need explicit entries too.
    for logger_name in set(COMPONENT_LOGGER_MAP.values()):
        if logger_name.startswith("app."):
            continue
        loggers_config[logger_name] = {
            "level": overrides.get(logger_name, default_level),
            "handlers": ["console"],
            "propagate": False,
        }

    # Apply per-component overrides onto the "app.*" tree.
    for logger_name, level in overrides.items():
        if logger_name.startswith("app."):
            loggers_config[logger_name] = {
                "level": level,
                "handlers": ["console"],
                "propagate": False,
            }

    logging_dict_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": settings.log_format,
            },
            "json": {
                "()": _JsonFormatter,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": formatter_name,
            },
        },
        "root": {
            "level": default_level,
            "handlers": ["console"],
        },
        "loggers": loggers_config,
    }

    logging.config.dictConfig(logging_dict_config)

    summary_logger = logging.getLogger("app.logging_config")
    if overrides:
        override_summary = ", ".join(f"{k}={v}" for k, v in overrides.items())
        summary_logger.info(
            "Logging configured — default=%s, overrides: %s",
            default_level,
            override_summary,
        )
    else:
        summary_logger.info(
            "Logging configured — default=%s, no overrides", default_level
        )
