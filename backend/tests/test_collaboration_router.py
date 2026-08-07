"""Regression tests for the collaboration WebSocket router."""

from __future__ import annotations

import pytest
from app import main as app_main
from app.routers.collaboration import manager
from fastapi.testclient import TestClient

client = TestClient(app_main.app)


def setup_function():
    manager.reset()


# ── URL routing ───────────────────────────────────────────────────────────────


def test_router_accepts_valid_session_id():
    with client.websocket_connect("/collaboration/ws/valid-session?name=Alice") as ws:
        state = ws.receive_json()
        assert state["type"] == "session_state"
        assert state["sessionId"] == "valid-session"


def test_router_accepts_numeric_session_id():
    with client.websocket_connect("/collaboration/ws/12345?name=Alice") as ws:
        state = ws.receive_json()
        assert state["type"] == "session_state"
        assert state["sessionId"] == "12345"


def test_router_accepts_session_id_with_hyphens():
    with client.websocket_connect("/collaboration/ws/my-session-abc?name=Alice") as ws:
        state = ws.receive_json()
        assert state["type"] == "session_state"
        assert state["sessionId"] == "my-session-abc"


def test_router_assigns_unique_client_id_per_connection():
    with client.websocket_connect("/collaboration/ws/unique-id-test?name=Alice") as ws1:
        state1 = ws1.receive_json()
        ws1.receive_json()

        with client.websocket_connect(
            "/collaboration/ws/unique-id-test?name=Bob"
        ) as ws2:
            state2 = ws2.receive_json()

            assert state1["clientId"] != state2["clientId"]


# ── Session isolation ─────────────────────────────────────────────────────────


def test_two_sessions_are_isolated():
    with client.websocket_connect("/collaboration/ws/session-x?name=Alice") as ws_x:
        state_x = ws_x.receive_json()
        ws_x.receive_json()

        ws_x.send_json(
            {
                "type": "code_update",
                "code": "print('session x')",
                "language": "python",
                "version": state_x["version"],
            }
        )
        ws_x.receive_json()

        with client.websocket_connect("/collaboration/ws/session-y?name=Bob") as ws_y:
            state_y = ws_y.receive_json()

            assert state_y["code"] == ""
            assert state_y["version"] == 0


def test_code_in_one_session_does_not_appear_in_another():
    with client.websocket_connect("/collaboration/ws/iso-a?name=Alice") as ws_a:
        state_a = ws_a.receive_json()
        ws_a.receive_json()

        ws_a.send_json(
            {
                "type": "code_update",
                "code": "x = 42",
                "language": "python",
                "version": state_a["version"],
            }
        )
        ws_a.receive_json()

    with client.websocket_connect("/collaboration/ws/iso-b?name=Bob") as ws_b:
        state_b = ws_b.receive_json()
        assert state_b["code"] == ""


# ── Concurrent sessions ───────────────────────────────────────────────────────


def test_multiple_sessions_run_concurrently():
    with client.websocket_connect("/collaboration/ws/concurrent-1?name=Alice") as ws1:
        with client.websocket_connect("/collaboration/ws/concurrent-2?name=Bob") as ws2:
            with client.websocket_connect(
                "/collaboration/ws/concurrent-3?name=Carol"
            ) as ws3:
                state1 = ws1.receive_json()
                state2 = ws2.receive_json()
                state3 = ws3.receive_json()

                assert state1["sessionId"] == "concurrent-1"
                assert state2["sessionId"] == "concurrent-2"
                assert state3["sessionId"] == "concurrent-3"


def test_concurrent_sessions_have_independent_user_lists():
    with client.websocket_connect("/collaboration/ws/users-a?name=Alice") as ws_a:
        ws_a.receive_json()
        ws_a.receive_json()

        with client.websocket_connect("/collaboration/ws/users-b?name=Bob") as ws_b:
            state_b = ws_b.receive_json()

            assert len(state_b["users"]) == 1
            assert state_b["users"][0]["name"] == "Bob"


# ── Session cleanup and recreation ───────────────────────────────────────────


def test_session_is_recreated_fresh_after_all_clients_leave():
    with client.websocket_connect("/collaboration/ws/recreate?name=Alice") as ws:
        state = ws.receive_json()
        ws.receive_json()

        ws.send_json(
            {
                "type": "code_update",
                "code": "old code",
                "language": "python",
                "version": state["version"],
            }
        )
        ws.receive_json()

    with client.websocket_connect("/collaboration/ws/recreate?name=Bob") as ws2:
        new_state = ws2.receive_json()
        assert new_state["code"] == ""
        assert new_state["version"] == 0


# ── Name query parameter ──────────────────────────────────────────────────────


def test_default_name_is_anonymous_when_not_provided():
    with client.websocket_connect("/collaboration/ws/anon-test") as ws:
        state = ws.receive_json()
        assert state["users"][0]["name"] == "Anonymous"


def test_name_is_reflected_in_session_state():
    with client.websocket_connect(
        "/collaboration/ws/name-reflect?name=Dhanashree"
    ) as ws:
        state = ws.receive_json()
        assert state["users"][0]["name"] == "Dhanashree"


# ── Initial session state ─────────────────────────────────────────────────────


def test_initial_session_state_has_empty_comments():
    with client.websocket_connect("/collaboration/ws/comments-init?name=Alice") as ws:
        state = ws.receive_json()
        assert state["comments"] == []


def test_initial_session_version_is_zero():
    with client.websocket_connect("/collaboration/ws/version-init?name=Alice") as ws:
        state = ws.receive_json()
        assert state["version"] == 0


def test_initial_session_code_is_empty():
    with client.websocket_connect("/collaboration/ws/code-init?name=Alice") as ws:
        state = ws.receive_json()
        assert state["code"] == ""
