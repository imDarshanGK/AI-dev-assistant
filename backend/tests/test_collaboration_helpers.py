"""
Unit tests for the shared helper functions extracted during the
collaboration WebSocket refactoring (issue #1572).

Tests cover:
- _coerce_int: safe integer coercion used for version, cursor fields, line numbers
- _send_error: the log + metric + send triple

These helpers are pure / easily awaitable and do not require the full
FastAPI TestClient, so they run quickly without any network overhead.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routers.collaboration import _coerce_int, _send_error


# ── _coerce_int ───────────────────────────────────────────────────────────────


class TestCoerceInt:
    """_coerce_int(value, default) -> int | None"""

    def test_integer_value_returned_unchanged(self):
        assert _coerce_int(5, default=0) == 5

    def test_zero_is_a_valid_int(self):
        assert _coerce_int(0, default=1) == 0

    def test_negative_integer_returned_unchanged(self):
        assert _coerce_int(-3, default=0) == -3

    def test_float_is_truncated_to_int(self):
        assert _coerce_int(3.9, default=0) == 3

    def test_numeric_string_coerced(self):
        assert _coerce_int("42", default=0) == 42

    def test_none_uses_default(self):
        assert _coerce_int(None, default=7) == 7

    def test_non_numeric_string_returns_none(self):
        assert _coerce_int("bad", default=0) is None

    def test_empty_string_returns_none(self):
        assert _coerce_int("", default=0) is None

    def test_list_value_returns_none(self):
        assert _coerce_int([1, 2], default=0) is None

    def test_dict_value_returns_none(self):
        assert _coerce_int({"x": 1}, default=0) is None

    def test_bool_true_coerces_to_one(self):
        # bool is a subclass of int in Python; int(True) == 1
        assert _coerce_int(True, default=0) == 1

    def test_bool_false_coerces_to_zero(self):
        assert _coerce_int(False, default=5) == 0

    def test_default_used_only_when_value_is_none(self):
        # Passing 0 explicitly must NOT fall back to default
        assert _coerce_int(0, default=99) == 0


# ── _send_error ───────────────────────────────────────────────────────────────


class TestSendError:
    """_send_error is async; each test runs a minimal event loop."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_logs_warning_message(self):
        socket = AsyncMock()
        with patch("app.routers.collaboration.logger") as mock_logger, \
             patch("app.routers.collaboration.record_collab_error"):
            self._run(
                _send_error(
                    socket=socket,
                    session_id="s1",
                    error_reason="test_reason",
                    log_message="something went wrong",
                    detail="client-facing detail",
                )
            )
        mock_logger.warning.assert_called_once_with("something went wrong")

    def test_records_error_metric(self):
        socket = AsyncMock()
        with patch("app.routers.collaboration.logger"), \
             patch("app.routers.collaboration.record_collab_error") as mock_metric:
            self._run(
                _send_error(
                    socket=socket,
                    session_id="s2",
                    error_reason="my_reason",
                    log_message="msg",
                    detail="detail",
                )
            )
        mock_metric.assert_called_once_with("s2", "my_reason")

    def test_sends_error_frame_to_socket(self):
        socket = AsyncMock()
        with patch("app.routers.collaboration.logger"), \
             patch("app.routers.collaboration.record_collab_error"):
            self._run(
                _send_error(
                    socket=socket,
                    session_id="s3",
                    error_reason="r",
                    log_message="msg",
                    detail="the error detail",
                )
            )
        socket.send_json.assert_awaited_once_with(
            {"type": "error", "detail": "the error detail"}
        )

    def test_none_socket_skips_send(self):
        """When the socket is None the send must be skipped without error."""
        with patch("app.routers.collaboration.logger"), \
             patch("app.routers.collaboration.record_collab_error"):
            # Should not raise.
            self._run(
                _send_error(
                    socket=None,
                    session_id="s4",
                    error_reason="r",
                    log_message="msg",
                    detail="detail",
                )
            )

    def test_all_three_actions_called_for_valid_socket(self):
        """Smoke test: log + metric + send all happen in a single call."""
        socket = AsyncMock()
        with patch("app.routers.collaboration.logger") as mock_logger, \
             patch("app.routers.collaboration.record_collab_error") as mock_metric:
            self._run(
                _send_error(
                    socket=socket,
                    session_id="s5",
                    error_reason="triple_check",
                    log_message="triple log",
                    detail="triple detail",
                )
            )
        assert mock_logger.warning.call_count == 1
        assert mock_metric.call_count == 1
        assert socket.send_json.await_count == 1
