"""Unit tests for backend/app/logging_config.py.

Run: cd backend && pytest tests/test_logging_config.py -v
"""

import json
import logging

import pytest
from app import logging_config
from app.logging_config import JsonFormatter, configure_logging


@pytest.fixture(autouse=True)
def _restore_root_logging():
    """Snapshot and restore the root logger so these tests don't leak
    configuration into the rest of the suite."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


def test_plain_format_is_default(monkeypatch):
    monkeypatch.setattr(logging_config.settings, "log_format", "plain")
    monkeypatch.setattr(logging_config.settings, "log_level", "DEBUG")
    configure_logging()

    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert not isinstance(root.handlers[0].formatter, JsonFormatter)


def test_json_format_emits_valid_json(monkeypatch):
    monkeypatch.setattr(logging_config.settings, "log_format", "json")
    monkeypatch.setattr(logging_config.settings, "log_level", "INFO")
    configure_logging()

    formatter = logging.getLogger().handlers[0].formatter
    assert isinstance(formatter, JsonFormatter)

    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    payload = json.loads(formatter.format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["message"] == "hello world"


def test_invalid_level_falls_back_to_info(monkeypatch):
    monkeypatch.setattr(logging_config.settings, "log_format", "plain")
    monkeypatch.setattr(logging_config.settings, "log_level", "NOPE")
    configure_logging()

    assert logging.getLogger().level == logging.INFO


def test_configure_logging_is_idempotent(monkeypatch):
    monkeypatch.setattr(logging_config.settings, "log_format", "plain")
    configure_logging()
    first = len(logging.getLogger().handlers)
    configure_logging()
    second = len(logging.getLogger().handlers)

    assert second == first
