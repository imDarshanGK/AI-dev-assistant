import logging

import pytest
from app import logging_config
from app.logging_config import (
    COMPONENT_LOGGER_MAP,
    _collect_component_overrides,
    _normalise_level,
    configure_logging,
    get_effective_levels,
)


def test_normalise_level_accepts_valid_levels():
    assert _normalise_level("debug", "INFO") == "DEBUG"
    assert _normalise_level("WARNING", "INFO") == "WARNING"


def test_normalise_level_falls_back_on_invalid_value():
    assert _normalise_level("not-a-level", "INFO") == "INFO"
    assert _normalise_level(None, "WARNING") == "WARNING"


def test_collect_component_overrides_reads_env_vars(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL_AI_PROVIDER", "DEBUG")
    monkeypatch.setenv("LOG_LEVEL_SCHEDULER", "WARNING")

    overrides = _collect_component_overrides()

    assert overrides[COMPONENT_LOGGER_MAP["ai_provider"]] == "DEBUG"
    assert overrides[COMPONENT_LOGGER_MAP["scheduler"]] == "WARNING"


def test_collect_component_overrides_ignores_unset_components(monkeypatch):
    for component in COMPONENT_LOGGER_MAP:
        monkeypatch.delenv(f"LOG_LEVEL_{component.upper()}", raising=False)

    overrides = _collect_component_overrides()

    assert overrides == {}


def test_collect_component_overrides_falls_back_on_invalid_value(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL_CACHE", "NOT_A_REAL_LEVEL")

    overrides = _collect_component_overrides()

    # Falls back to the global default level rather than crashing or
    # being silently dropped.
    assert (
        overrides[COMPONENT_LOGGER_MAP["cache"]]
        == logging_config.settings.log_level.upper()
    )


def test_get_effective_levels_returns_every_known_component(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL_AI_PROVIDER", raising=False)

    levels = get_effective_levels()

    assert set(levels.keys()) == set(COMPONENT_LOGGER_MAP.keys())
    for level in levels.values():
        assert level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def test_get_effective_levels_reflects_override(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL_AI_PROVIDER", "ERROR")

    levels = get_effective_levels()

    assert levels["ai_provider"] == "ERROR"


def test_configure_logging_applies_global_default(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    for component in COMPONENT_LOGGER_MAP:
        monkeypatch.delenv(f"LOG_LEVEL_{component.upper()}", raising=False)

    monkeypatch.setattr(logging_config.settings, "log_level", "WARNING")

    configure_logging()

    app_logger = logging.getLogger("app")
    assert app_logger.level == logging.WARNING


def test_configure_logging_applies_component_override(monkeypatch):
    monkeypatch.setattr(logging_config.settings, "log_level", "INFO")
    monkeypatch.setenv("LOG_LEVEL_SCHEDULER", "DEBUG")

    configure_logging()

    scheduler_logger = logging.getLogger(COMPONENT_LOGGER_MAP["scheduler"])
    assert scheduler_logger.level == logging.DEBUG

    monkeypatch.delenv("LOG_LEVEL_SCHEDULER", raising=False)


def test_configure_logging_is_safe_to_call_multiple_times(monkeypatch):
    monkeypatch.setattr(logging_config.settings, "log_level", "INFO")

    configure_logging()
    configure_logging()
    configure_logging()

    app_logger = logging.getLogger("app")
    assert len(app_logger.handlers) <= 1


@pytest.mark.parametrize("json_enabled", [True, False])
def test_configure_logging_respects_json_flag(monkeypatch, json_enabled):
    monkeypatch.setattr(logging_config.settings, "log_json", json_enabled)
    monkeypatch.setattr(logging_config.settings, "log_level", "INFO")

    configure_logging()
