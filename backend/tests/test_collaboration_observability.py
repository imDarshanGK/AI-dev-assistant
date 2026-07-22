"""
Tests for Prometheus observability metrics exposed by the collaboration
WebSocket router.

Strategy
--------
The prometheus_client Counter and Gauge objects are module-level singletons,
so we cannot re-create them between test runs.  Instead each test uses a
unique ``session_id`` (prefixed ``obs-``) so that label combinations are
fresh and we can assert the *absolute* sample value equals the expected count
for that run.

``METRICS_ENABLED`` is not overridden here — the default is True, so all
metrics should be collected normally.
"""

import os

import pytest

from app import main as app_main
from app.observability import (
    COLLAB_ACTIVE_CONNECTIONS,
    COLLAB_CONNECTIONS_TOTAL,
    COLLAB_ERRORS_TOTAL,
    COLLAB_MESSAGES_TOTAL,
)
from app.routers.collaboration import MAX_CODE_CHARS, MAX_COMMENT_CHARS, manager
from fastapi.testclient import TestClient

client = TestClient(app_main.app)


def setup_function():
    manager.reset()


# ── helpers ───────────────────────────────────────────────────────────────────

def _active(session_id: str) -> float:
    """Return the current value of the active-connections gauge for a session."""
    try:
        return COLLAB_ACTIVE_CONNECTIONS.labels(session_id=session_id)._value.get()
    except KeyError:
        return 0.0


def _total_connections(session_id: str) -> float:
    """Return the cumulative connections counter for a session."""
    try:
        return COLLAB_CONNECTIONS_TOTAL.labels(session_id=session_id)._value.get()
    except KeyError:
        return 0.0


def _messages(session_id: str, message_type: str) -> float:
    """Return the cumulative messages counter for a session + message_type."""
    try:
        return COLLAB_MESSAGES_TOTAL.labels(
            session_id=session_id, message_type=message_type
        )._value.get()
    except KeyError:
        return 0.0


def _errors(session_id: str, error_reason: str) -> float:
    """Return the cumulative errors counter for a session + error_reason."""
    try:
        return COLLAB_ERRORS_TOTAL.labels(
            session_id=session_id, error_reason=error_reason
        )._value.get()
    except KeyError:
        return 0.0


# ── connection lifecycle metrics ──────────────────────────────────────────────

def test_connect_increments_active_and_total_counters():
    session = "obs-connect-1"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()  # session_state
        ws.receive_json()  # presence_update

        assert _active(session) == 1.0
        assert _total_connections(session) == 1.0

    # After disconnect the active gauge must return to 0.
    assert _active(session) == 0.0
    # Total connections is a monotonic counter — must stay at 1.
    assert _total_connections(session) == 1.0


def test_two_clients_increment_active_gauge_independently():
    session = "obs-connect-2"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        assert _active(session) == 1.0
        assert _total_connections(session) == 1.0

        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob") as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            assert _active(session) == 2.0
            assert _total_connections(session) == 2.0

        # Bob disconnected — gauge decrements.
        assert _active(session) == 1.0

    # Alice disconnected — gauge reaches 0.
    assert _active(session) == 0.0
    assert _total_connections(session) == 2.0


# ── message metrics ───────────────────────────────────────────────────────────

def test_code_update_increments_messages_counter():
    session = "obs-code-msg"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        state = ws.receive_json()
        ws.receive_json()

        ws.send_json({
            "type": "code_update",
            "code": "x = 1",
            "language": "python",
            "version": state["version"],
        })
        ws.receive_json()  # broadcast back

    assert _messages(session, "code_update") == 1.0


def test_cursor_update_increments_messages_counter():
    session = "obs-cursor-msg"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob") as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            bob.send_json({
                "type": "cursor_update",
                "cursor": {"line": 2, "column": 5, "selectionStart": 0, "selectionEnd": 0},
            })
            alice.receive_json()  # cursor broadcast to Alice

    assert _messages(session, "cursor_update") == 1.0


def test_comment_added_increments_messages_counter():
    session = "obs-comment-msg"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "Looks good."})
        ws.receive_json()  # comment broadcast

    assert _messages(session, "comment_added") == 1.0


# ── error metrics ─────────────────────────────────────────────────────────────

def test_unsupported_message_type_increments_error_counter():
    session = "obs-err-unknown"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "unknown_action"})
        ws.receive_json()  # error frame

    assert _errors(session, "unsupported_message_type") == 1.0


def test_invalid_code_type_increments_error_counter():
    session = "obs-err-codetype"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "code_update", "code": 999, "language": "python", "version": 0})
        ws.receive_json()  # error frame

    assert _errors(session, "invalid_code_type") == 1.0


def test_code_too_long_increments_error_counter():
    session = "obs-err-codelen"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({
            "type": "code_update",
            "code": "x" * (MAX_CODE_CHARS + 1),
            "language": "python",
            "version": 0,
        })
        ws.receive_json()  # error frame

    assert _errors(session, "code_too_long") == 1.0


def test_non_integer_version_increments_error_counter():
    session = "obs-err-version"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "code_update", "code": "x=1", "language": "python", "version": "bad"})
        ws.receive_json()  # error frame

    assert _errors(session, "non_integer_version") == 1.0


def test_empty_comment_increments_error_counter():
    session = "obs-err-emptycmt"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "   "})
        ws.receive_json()  # error frame

    assert _errors(session, "empty_comment_text") == 1.0


def test_comment_too_long_increments_error_counter():
    session = "obs-err-cmtlen"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({
            "type": "comment_added",
            "line": 1,
            "text": "y" * (MAX_COMMENT_CHARS + 1),
        })
        ws.receive_json()  # error frame

    assert _errors(session, "comment_too_long") == 1.0


def test_non_object_payload_increments_error_counter():
    session = "obs-err-payload"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_text("[1, 2, 3]")
        ws.receive_json()  # error frame

    assert _errors(session, "non_object_payload") == 1.0


# ── metrics_enabled=false guard ───────────────────────────────────────────────

def test_metrics_disabled_skips_all_counters(monkeypatch):
    """When METRICS_ENABLED=false no counter/gauge updates should be made."""
    monkeypatch.setenv("METRICS_ENABLED", "false")

    session = "obs-disabled"
    before_total = _total_connections(session)
    before_active = _active(session)

    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({
            "type": "code_update",
            "code": "print('hi')",
            "language": "python",
            "version": 0,
        })
        ws.receive_json()

    # With metrics disabled the counters must not have moved.
    assert _total_connections(session) == before_total
    assert _active(session) == before_active
    assert _messages(session, "code_update") == 0.0


# ── metric names exposed on /metrics endpoint ─────────────────────────────────

def test_collaboration_metrics_appear_on_scrape_endpoint():
    """All four collaboration metric families must be present in the /metrics output."""
    # Trigger a connection so the label set is populated in the registry.
    session = "obs-scrape"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text

    assert "qyverixai_collaboration_active_connections" in body
    assert "qyverixai_collaboration_connections_total" in body
    assert "qyverixai_collaboration_messages_total" in body
    assert "qyverixai_collaboration_errors_total" in body
