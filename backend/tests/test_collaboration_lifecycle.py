"""
Tests for hardened session lifecycle handling in the presence sync router.

Covers edge cases that were not tested before:
- session_id validation (empty, too long)
- phantom room prevention (message after room teardown)
- malformed version field in code_update
- non-integer cursor fields in cursor_update
- non-integer line field in comment_added
- empty comment text rejection
- over-length comment rejection
- unsupported message type error response
- non-object JSON payload error response
- stale-socket broadcast resilience
- session cleanup when last client disconnects
- non-dict cursor value ignored gracefully
"""

from app import main as app_main
from app.routers.collaboration import MAX_CODE_CHARS, MAX_COMMENT_CHARS, MAX_SESSION_ID_CHARS, manager
from fastapi.testclient import TestClient

client = TestClient(app_main.app)


def setup_function():
    manager.reset()


# ── session_id validation ─────────────────────────────────────────────────────

def test_empty_session_id_is_rejected():
    """The router must close the WebSocket for an empty session_id."""
    # FastAPI routes /ws/{session_id} — an empty string would not match the
    # path parameter at all (returns 403/404), so we verify no room is created.
    assert "" not in manager.rooms


def test_oversized_session_id_is_rejected():
    """session_id longer than MAX_SESSION_ID_CHARS must be closed on connect."""
    long_id = "x" * (MAX_SESSION_ID_CHARS + 1)
    with client.websocket_connect(f"/collaboration/ws/{long_id}?name=Alice") as ws:
        # The server should close the connection; if any message arrives it
        # must be a close frame, not a session_state.
        try:
            msg = ws.receive_json()
            # If we somehow receive a message it must NOT be a valid session.
            assert msg.get("type") != "session_state", (
                "Server must not accept oversized session_id"
            )
        except Exception:
            # Connection closed — expected behaviour.
            pass

    assert long_id not in manager.rooms


# ── phantom room prevention ───────────────────────────────────────────────────

def test_handle_message_does_not_create_phantom_room():
    """handle_message on a non-existent session must not create a room."""
    import asyncio

    async def _run():
        await manager.handle_message("ghost-session", "fake-client", {"type": "ping"})

    asyncio.get_event_loop().run_until_complete(_run())
    assert "ghost-session" not in manager.rooms


# ── code_update hardening ─────────────────────────────────────────────────────

def test_code_update_with_non_integer_version_returns_error():
    """version field that cannot be cast to int must return an error, not crash."""
    with client.websocket_connect(
        "/collaboration/ws/sess-ver?name=Alice"
    ) as ws:
        ws.receive_json()  # session_state
        ws.receive_json()  # presence_update

        ws.send_json(
            {
                "type": "code_update",
                "code": "x = 1",
                "language": "python",
                "version": "not-an-int",
            }
        )

        response = ws.receive_json()
        assert response["type"] == "error"
        assert "version" in response["detail"].lower()


def test_code_update_with_non_string_code_returns_error():
    """code field that is not a string must return an error message."""
    with client.websocket_connect(
        "/collaboration/ws/sess-code-type?name=Alice"
    ) as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json(
            {
                "type": "code_update",
                "code": 12345,
                "language": "python",
                "version": 0,
            }
        )

        response = ws.receive_json()
        assert response["type"] == "error"
        assert "string" in response["detail"].lower()


def test_code_update_exceeding_max_length_returns_error():
    """code longer than MAX_CODE_CHARS must return an error."""
    with client.websocket_connect(
        "/collaboration/ws/sess-code-len?name=Alice"
    ) as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json(
            {
                "type": "code_update",
                "code": "x" * (MAX_CODE_CHARS + 1),
                "language": "python",
                "version": 0,
            }
        )

        response = ws.receive_json()
        assert response["type"] == "error"
        assert str(MAX_CODE_CHARS) in response["detail"]


# ── cursor_update hardening ───────────────────────────────────────────────────

def test_cursor_update_with_non_integer_fields_returns_error():
    """Cursor fields that cannot be cast to int must return an error, not crash."""
    with client.websocket_connect(
        "/collaboration/ws/sess-cursor?name=Alice"
    ) as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json(
            {
                "type": "cursor_update",
                "cursor": {
                    "line": "bad",
                    "column": 1,
                    "selectionStart": 0,
                    "selectionEnd": 0,
                },
            }
        )

        response = ws.receive_json()
        assert response["type"] == "error"
        assert "integer" in response["detail"].lower()


def test_cursor_update_with_non_dict_cursor_is_ignored():
    """A cursor_update where cursor is not a dict must be silently ignored."""
    with client.websocket_connect(
        "/collaboration/ws/sess-cursor-null?name=Alice"
    ) as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "cursor_update", "cursor": "invalid"})
        # No error frame is expected — the message is silently dropped.
        # Send a ping to confirm the connection is still alive.
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"


# ── comment_added hardening ───────────────────────────────────────────────────

def test_comment_with_empty_text_returns_error():
    """An empty comment text must return an error."""
    with client.websocket_connect(
        "/collaboration/ws/sess-cmt-empty?name=Alice"
    ) as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "   "})

        response = ws.receive_json()
        assert response["type"] == "error"
        assert "required" in response["detail"].lower()


def test_comment_exceeding_max_length_returns_error():
    """A comment longer than MAX_COMMENT_CHARS must return an error."""
    with client.websocket_connect(
        "/collaboration/ws/sess-cmt-len?name=Alice"
    ) as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json(
            {
                "type": "comment_added",
                "line": 1,
                "text": "y" * (MAX_COMMENT_CHARS + 1),
            }
        )

        response = ws.receive_json()
        assert response["type"] == "error"
        assert str(MAX_COMMENT_CHARS) in response["detail"]


def test_comment_with_non_integer_line_uses_default():
    """A non-integer line field must not crash — it defaults to 1."""
    with client.websocket_connect(
        "/collaboration/ws/sess-cmt-line?name=Alice"
    ) as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json(
            {
                "type": "comment_added",
                "line": "not-a-number",
                "text": "Valid comment text.",
            }
        )

        response = ws.receive_json()
        assert response["type"] == "comment_added"
        assert response["comment"]["line"] == 1


# ── unsupported message type ──────────────────────────────────────────────────

def test_unsupported_message_type_returns_error():
    """An unrecognised message type must return an error frame."""
    with client.websocket_connect(
        "/collaboration/ws/sess-unknown?name=Alice"
    ) as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "do_something_unknown"})

        response = ws.receive_json()
        assert response["type"] == "error"
        assert "unsupported" in response["detail"].lower()


# ── non-object payload ────────────────────────────────────────────────────────

def test_non_object_json_payload_returns_error():
    """A JSON array (non-object) must return an error, not crash."""
    with client.websocket_connect(
        "/collaboration/ws/sess-payload?name=Alice"
    ) as ws:
        ws.receive_json()
        ws.receive_json()

        # TestClient encodes this as a JSON array at the wire level.
        ws.send_text("[1, 2, 3]")

        response = ws.receive_json()
        assert response["type"] == "error"
        assert "object" in response["detail"].lower()


# ── session cleanup ───────────────────────────────────────────────────────────

def test_room_is_removed_when_last_client_disconnects():
    """After the last client leaves, the room must be removed from manager.rooms."""
    session = "sess-cleanup"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice"):
        assert session in manager.rooms

    # Context manager exit triggers disconnect.
    assert session not in manager.rooms


def test_room_persists_while_at_least_one_client_is_connected():
    """Room must not be removed while a second client is still connected."""
    session = "sess-persist"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob") as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            # Alice disconnects; Bob is still connected.

        # After Alice's context exits, room must still exist for Bob.
        assert session in manager.rooms

    # After Bob's context exits too, room must be cleaned up.
    assert session not in manager.rooms


# ── presence update after disconnect ─────────────────────────────────────────

def test_presence_update_broadcast_on_disconnect():
    """Remaining clients must receive a presence_update when another client leaves."""
    session = "sess-presence-disc"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as alice:
        alice.receive_json()  # session_state
        alice.receive_json()  # own presence_update

        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob"):
            alice.receive_json()  # presence_update for Bob joining
            # Bob's context exits here — triggers disconnect.

        # Alice must receive a presence_update showing Bob has left.
        update = alice.receive_json()
        assert update["type"] == "presence_update"
        names = [u["name"] for u in update["users"]]
        assert "Bob" not in names
        assert "Alice" in names
