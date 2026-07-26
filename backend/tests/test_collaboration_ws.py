"""Tests for real-time collaboration WebSocket sessions."""

from app import main as app_main
from app.routers.collaboration import manager
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
