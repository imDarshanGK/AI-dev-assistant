"""
Tests for comment-specific observability in the collaboration WebSocket (#1577).

Covers the new metrics added for comments:
- COLLAB_COMMENTS_TOTAL counter increments on each accepted comment
- COLLAB_COMMENT_COUNT gauge increments on accepted comment
- COLLAB_COMMENT_COUNT gauge resets to zero when the session is destroyed
- COLLAB_COMMENT_COUNT gauge is accurate for multiple sequential comments
- comment_sync requests are counted in COLLAB_MESSAGES_TOTAL
- error counters fire for all comment rejection paths
- METRICS_ENABLED=false skips all comment metric updates
- new metrics appear on the /metrics scrape endpoint

Uses unique session_id prefixes (obs-cmt-*) so prometheus_client label sets
do not collide with those created in other test files.
"""

from app import main as app_main
from app.observability import (
    COLLAB_COMMENT_COUNT,
    COLLAB_COMMENTS_TOTAL,
    COLLAB_ERRORS_TOTAL,
    COLLAB_MESSAGES_TOTAL,
)
from app.routers.collaboration import MAX_COMMENT_CHARS, manager
from fastapi.testclient import TestClient

client = TestClient(app_main.app)


def setup_function():
    manager.reset()


# ── helpers ───────────────────────────────────────────────────────────────────

def _comment_total(session_id: str) -> float:
    try:
        return COLLAB_COMMENTS_TOTAL.labels(session_id=session_id)._value.get()
    except KeyError:
        return 0.0


def _comment_count(session_id: str) -> float:
    try:
        return COLLAB_COMMENT_COUNT.labels(session_id=session_id)._value.get()
    except KeyError:
        return 0.0


def _messages(session_id: str, message_type: str) -> float:
    try:
        return COLLAB_MESSAGES_TOTAL.labels(
            session_id=session_id, message_type=message_type
        )._value.get()
    except KeyError:
        return 0.0


def _errors(session_id: str, error_reason: str) -> float:
    try:
        return COLLAB_ERRORS_TOTAL.labels(
            session_id=session_id, error_reason=error_reason
        )._value.get()
    except KeyError:
        return 0.0


# ── COLLAB_COMMENTS_TOTAL counter ─────────────────────────────────────────────

def test_comment_total_increments_on_accepted_comment():
    session = "obs-cmt-total1"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "Hello."})
        ws.receive_json()

    assert _comment_total(session) == 1.0


def test_comment_total_does_not_increment_on_rejected_comment():
    session = "obs-cmt-total-rej"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": ""})
        ws.receive_json()  # error frame

    assert _comment_total(session) == 0.0


def test_comment_total_increments_once_per_accepted_comment():
    session = "obs-cmt-total-seq"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        for i in range(5):
            ws.send_json({"type": "comment_added", "line": i + 1, "text": f"C{i}"})
            ws.receive_json()

    assert _comment_total(session) == 5.0


# ── COLLAB_COMMENT_COUNT gauge ────────────────────────────────────────────────

def test_comment_count_gauge_increments_on_accepted_comment():
    session = "obs-cmt-gauge1"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "Gauge check."})
        ws.receive_json()

        assert _comment_count(session) == 1.0

    # After session teardown the gauge must reach zero.
    assert _comment_count(session) == 0.0


def test_comment_count_gauge_is_accurate_across_multiple_adds():
    session = "obs-cmt-gauge-seq"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        for i in range(4):
            ws.send_json({"type": "comment_added", "line": 1, "text": f"G{i}"})
            ws.receive_json()
            assert _comment_count(session) == float(i + 1)

    assert _comment_count(session) == 0.0


def test_comment_count_gauge_resets_to_zero_after_last_client_disconnects():
    """When the last client leaves, the gauge must be decremented to zero."""
    session = "obs-cmt-teardown"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "Teardown."})
        ws.receive_json()

    assert session not in manager.rooms
    assert _comment_count(session) == 0.0


def test_comment_count_gauge_persists_while_session_is_alive():
    """Gauge must stay at the correct value while a second client is connected."""
    session = "obs-cmt-alive"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        alice.send_json({"type": "comment_added", "line": 1, "text": "Alive."})
        alice.receive_json()

        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob") as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            # Bob disconnects; Alice still connected.
        alice.receive_json()  # presence_update for Bob leaving

        # Room still alive — comment count must still be 1.
        assert _comment_count(session) == 1.0

    # Now Alice disconnects too — gauge drops to 0.
    assert _comment_count(session) == 0.0


def test_comment_count_gauge_not_decremented_on_non_last_disconnect():
    """Disconnecting a non-last client must not affect the comment count gauge."""
    session = "obs-cmt-nondec"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob") as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            alice.send_json({"type": "comment_added", "line": 1, "text": "Still here."})
            alice.receive_json()
            bob.receive_json()

            assert _comment_count(session) == 1.0

        # Bob leaves — gauge must still be 1 (session not destroyed).
        alice.receive_json()  # presence_update
        assert _comment_count(session) == 1.0


# ── comment_sync message counter ─────────────────────────────────────────────

def test_comment_sync_is_counted_in_messages_total():
    session = "obs-cmt-sync1"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_sync"})
        ws.receive_json()

    assert _messages(session, "comment_sync") == 1.0


def test_comment_sync_count_accumulates_across_multiple_requests():
    session = "obs-cmt-sync-multi"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        for _ in range(3):
            ws.send_json({"type": "comment_sync"})
            ws.receive_json()

    assert _messages(session, "comment_sync") == 3.0


# ── error counters for comment rejection paths ────────────────────────────────

def test_invalid_comment_text_type_increments_error_counter():
    session = "obs-cmt-err-type"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": 99})
        ws.receive_json()

    assert _errors(session, "invalid_comment_text_type") == 1.0


def test_empty_comment_text_increments_error_counter():
    session = "obs-cmt-err-empty"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "  "})
        ws.receive_json()

    assert _errors(session, "empty_comment_text") == 1.0


def test_comment_too_long_increments_error_counter():
    session = "obs-cmt-err-long"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "x" * (MAX_COMMENT_CHARS + 1)})
        ws.receive_json()

    assert _errors(session, "comment_too_long") == 1.0


# ── METRICS_ENABLED=false guard ───────────────────────────────────────────────

def test_comment_metrics_skipped_when_metrics_disabled(monkeypatch):
    """With METRICS_ENABLED=false no comment counter or gauge must be updated."""
    monkeypatch.setenv("METRICS_ENABLED", "false")

    session = "obs-cmt-disabled"
    before_total = _comment_total(session)
    before_gauge = _comment_count(session)

    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "Disabled."})
        ws.receive_json()

    assert _comment_total(session) == before_total
    assert _comment_count(session) == before_gauge


# ── metric names on /metrics scrape endpoint ──────────────────────────────────

def test_comment_metrics_appear_on_scrape_endpoint():
    """Both new comment metric families must be visible on /metrics."""
    session = "obs-cmt-scrape"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()
        ws.send_json({"type": "comment_added", "line": 1, "text": "Scrape."})
        ws.receive_json()

    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text

    assert "qyverixai_collaboration_comments_total" in body
    assert "qyverixai_collaboration_comment_count" in body
