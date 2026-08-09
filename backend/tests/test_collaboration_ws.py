"""Tests for real-time collaboration WebSocket sessions."""

import pytest
from app import main as app_main
from app.routers.collaboration import manager
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

client = TestClient(app_main.app)


def setup_function():
    manager.reset()


def test_collaboration_join_returns_session_state():
    with client.websocket_connect(
        "/collaboration/ws/session-a?name=Alice"
    ) as websocket:
        state = websocket.receive_json()

        assert state["type"] == "session_state"
        assert state["sessionId"] == "session-a"
        assert state["clientId"]
        assert state["version"] == 0
        assert state["code"] == ""
        assert state["comments"] == []
        assert len(state["users"]) == 1
        assert state["users"][0]["name"] == "Alice"


def test_collaboration_broadcasts_code_updates_to_other_clients():
    with client.websocket_connect("/collaboration/ws/session-b?name=Alice") as alice:
        alice_state = alice.receive_json()
        alice.receive_json()  # Alice presence update

        with client.websocket_connect("/collaboration/ws/session-b?name=Bob") as bob:
            bob.receive_json()  # Bob session state
            alice.receive_json()  # Presence update after Bob joins
            bob.receive_json()  # Bob presence update

            alice.send_json(
                {
                    "type": "code_update",
                    "code": "print('hello from Alice')",
                    "language": "python",
                    "version": alice_state["version"],
                }
            )

            update = bob.receive_json()

            assert update["type"] == "code_update"
            assert update["code"] == "print('hello from Alice')"
            assert update["language"] == "python"
            assert update["version"] == 1
            assert update["senderId"] == alice_state["clientId"]


def test_collaboration_rejects_stale_code_update_with_sync_required():
    with client.websocket_connect("/collaboration/ws/session-c?name=Alice") as alice:
        alice_state = alice.receive_json()
        alice.receive_json()

        with client.websocket_connect("/collaboration/ws/session-c?name=Bob") as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            alice.send_json(
                {
                    "type": "code_update",
                    "code": "x = 1",
                    "language": "python",
                    "version": alice_state["version"],
                }
            )
            bob.receive_json()

            bob.send_json(
                {
                    "type": "code_update",
                    "code": "stale update",
                    "language": "python",
                    "version": 0,
                }
            )

            sync = bob.receive_json()

            assert sync["type"] == "sync_required"
            assert sync["code"] == "x = 1"
            assert sync["version"] == 1


def test_collaboration_broadcasts_cursor_updates():
    with client.websocket_connect("/collaboration/ws/session-d?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        with client.websocket_connect("/collaboration/ws/session-d?name=Bob") as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            bob.send_json(
                {
                    "type": "cursor_update",
                    "cursor": {
                        "line": 3,
                        "column": 8,
                        "selectionStart": 12,
                        "selectionEnd": 12,
                    },
                }
            )

            update = alice.receive_json()

            assert update["type"] == "cursor_update"
            assert update["user"]["name"] == "Bob"
            assert update["user"]["cursor"]["line"] == 3
            assert update["user"]["cursor"]["column"] == 8


def test_collaboration_broadcasts_comments():
    with client.websocket_connect("/collaboration/ws/session-e?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        with client.websocket_connect("/collaboration/ws/session-e?name=Bob") as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            alice.send_json(
                {
                    "type": "comment_added",
                    "line": 2,
                    "text": "Check this condition before running analysis.",
                }
            )

            update = bob.receive_json()

            assert update["type"] == "comment_added"
            assert update["comment"]["line"] == 2
            assert update["comment"]["author"] == "Alice"
            assert (
                update["comment"]["text"]
                == "Check this condition before running analysis."
            )
            assert len(update["comments"]) == 1


def test_collaboration_ping_returns_pong():
    with client.websocket_connect(
        "/collaboration/ws/session-f?name=Alice"
    ) as websocket:
        websocket.receive_json()
        websocket.receive_json()

        websocket.send_json({"type": "ping"})
        response = websocket.receive_json()

        assert response["type"] == "pong"


def test_presence_sync_broadcasts_on_join_and_leave():
    # Alice connects
    with client.websocket_connect(
        "/collaboration/ws/presence-test?name=Alice"
    ) as alice:
        alice_state = alice.receive_json()
        alice_presence1 = alice.receive_json()

        assert alice_state["type"] == "session_state"
        assert alice_presence1["type"] == "presence_update"
        assert len(alice_presence1["users"]) == 1
        assert alice_presence1["users"][0]["name"] == "Alice"

        # Bob connects
        with client.websocket_connect(
            "/collaboration/ws/presence-test?name=Bob"
        ) as bob:
            bob_state = bob.receive_json()

            # Alice receives presence update for Bob's join
            alice_presence2 = alice.receive_json()
            # Bob receives presence update after joining
            bob_presence = bob.receive_json()

            assert alice_presence2["type"] == "presence_update"
            assert len(alice_presence2["users"]) == 2
            names = {u["name"] for u in alice_presence2["users"]}
            assert names == {"Alice", "Bob"}

            assert bob_presence["type"] == "presence_update"
            assert len(bob_presence["users"]) == 2

        # Bob has disconnected. Alice should receive a presence update with only Alice remaining.
        alice_presence3 = alice.receive_json()
        assert alice_presence3["type"] == "presence_update"
        assert len(alice_presence3["users"]) == 1
        assert alice_presence3["users"][0]["name"] == "Alice"


def test_presence_sync_handles_name_sanitization():
    # 1. Empty name parameter (or not provided)
    with client.websocket_connect("/collaboration/ws/name-test") as ws1:
        state1 = ws1.receive_json()
        assert state1["users"][0]["name"] == "Anonymous"

    # 2. Whitespace-only name parameter
    with client.websocket_connect("/collaboration/ws/name-test?name=%20%20%20") as ws2:
        state2 = ws2.receive_json()
        assert state2["users"][0]["name"] == "Anonymous"

    # 3. Truncate long name parameter (>40 characters) - FastAPI constraint raises WebSocketDisconnect (1008)
    long_name = "A" * 50
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/collaboration/ws/name-test?name={long_name}"):
            pass
    assert exc_info.value.code == 1008


def test_presence_sync_session_cleanup():
    # Alice joins and updates code
    with client.websocket_connect("/collaboration/ws/cleanup-test?name=Alice") as alice:
        alice_state = alice.receive_json()
        alice.receive_json()  # presence_update

        alice.send_json(
            {
                "type": "code_update",
                "code": "print('hello')",
                "language": "python",
                "version": alice_state["version"],
            }
        )
        alice.receive_json()  # receive echo of code update

    # Alice disconnected, room should be deleted.
    # Bob joins the same room. Room should be recreated with fresh state.
    with client.websocket_connect("/collaboration/ws/cleanup-test?name=Bob") as bob:
        bob_state = bob.receive_json()
        assert bob_state["code"] == ""
        assert bob_state["version"] == 0
        assert len(bob_state["users"]) == 1
        assert bob_state["users"][0]["name"] == "Bob"


def test_collaboration_rejects_unsupported_message_type():
    with client.websocket_connect(
        "/collaboration/ws/session-g?name=Alice"
    ) as websocket:
        websocket.receive_json()
        websocket.receive_json()

        websocket.send_json({"type": "unknown_event"})
        response = websocket.receive_json()

        assert response == {
            "type": "error",
            "detail": "Unsupported collaboration message type: unknown_event",
            "status": 400,
        }

def test_collaboration_handles_invalid_json():
    with client.websocket_connect("/collaboration/ws/session-invalid?name=Alice") as websocket:
        websocket.receive_json()
        websocket.receive_json()

        websocket.send_text("not a valid json")
        response = websocket.receive_json()

        assert response == {
            "type": "error",
            "detail": "Invalid JSON payload",
            "status": 400,
        }

def test_collaboration_handles_missing_and_malformed_code_updates():
    with client.websocket_connect("/collaboration/ws/session-malformed1?name=Alice") as websocket:
        websocket.receive_json()
        websocket.receive_json()

        # Missing code
        websocket.send_json({"type": "code_update", "version": 1})
        response = websocket.receive_json()
        assert response == {"type": "error", "detail": "code is required", "status": 400}

        # Malformed version
        websocket.send_json({"type": "code_update", "code": "print(1)", "version": "abc"})
        response = websocket.receive_json()
        assert response == {"type": "error", "detail": "version must be an integer", "status": 400}

        # Code too long
        websocket.send_json({"type": "code_update", "code": "A" * 50001, "version": 1})
        response = websocket.receive_json()
        assert response == {"type": "error", "detail": "code exceeds 50000 characters", "status": 400}

def test_collaboration_handles_missing_and_malformed_cursor_updates():
    with client.websocket_connect("/collaboration/ws/session-malformed2?name=Alice") as websocket:
        websocket.receive_json()
        websocket.receive_json()

        # Missing cursor
        websocket.send_json({"type": "cursor_update"})
        response = websocket.receive_json()
        assert response == {"type": "error", "detail": "cursor is required", "status": 400}

        # Malformed cursor fields
        websocket.send_json({"type": "cursor_update", "cursor": {"line": "abc"}})
        response = websocket.receive_json()
        assert response == {"type": "error", "detail": "cursor fields must be integers", "status": 400}

def test_collaboration_handles_missing_and_malformed_comment_updates():
    with client.websocket_connect("/collaboration/ws/session-malformed3?name=Alice") as websocket:
        websocket.receive_json()
        websocket.receive_json()

        # Missing text
        websocket.send_json({"type": "comment_added", "line": 1})
        response = websocket.receive_json()
        assert response == {"type": "error", "detail": "comment text is required", "status": 400}

        # Empty text
        websocket.send_json({"type": "comment_added", "text": "   ", "line": 1})
        response = websocket.receive_json()
        assert response == {"type": "error", "detail": "comment text cannot be empty", "status": 400}


