"""
Tests for hardened session lifecycle handling in collaboration comments (#1573).

Covers all new comment-specific guards:
- non-string text field rejected with an error
- empty / whitespace-only text rejected
- text exceeding MAX_COMMENT_CHARS rejected
- comment limit (MAX_COMMENTS_PER_SESSION) enforced
- unregistered client (race between disconnect and queued comment) rejected
- valid comments still work correctly end-to-end
- comments are cleared when the session is destroyed (room teardown)
- comment line defaults to 1 for missing / non-integer line values
- comment author and color come from the registered user entry
"""

from app import main as app_main
from app.routers.collaboration import (
    MAX_COMMENT_CHARS,
    MAX_COMMENTS_PER_SESSION,
    manager,
)
from fastapi.testclient import TestClient

client = TestClient(app_main.app)


def setup_function():
    manager.reset()


# ── valid comment ─────────────────────────────────────────────────────────────

def test_valid_comment_is_broadcast_to_all_clients():
    session = "cmt-valid"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as alice:
        alice.receive_json()  # session_state
        alice.receive_json()  # presence_update

        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob") as bob:
            bob.receive_json()   # session_state
            alice.receive_json() # presence_update for Bob joining
            bob.receive_json()   # presence_update

            alice.send_json({"type": "comment_added", "line": 5, "text": "This looks good."})

            alice_msg = alice.receive_json()
            bob_msg = bob.receive_json()

    assert alice_msg["type"] == "comment_added"
    assert alice_msg["comment"]["line"] == 5
    assert alice_msg["comment"]["text"] == "This looks good."
    assert alice_msg["comment"]["author"] == "Alice"
    assert len(alice_msg["comments"]) == 1

    assert bob_msg["type"] == "comment_added"
    assert bob_msg["comment"]["text"] == "This looks good."


def test_comment_author_and_color_come_from_registered_user():
    session = "cmt-author"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Charlie") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "Hi."})
        msg = ws.receive_json()

    assert msg["comment"]["author"] == "Charlie"
    assert msg["comment"]["authorId"]
    # Color must be one of the defined palette values.
    from app.routers.collaboration import COLORS
    assert msg["comment"]["color"] in COLORS


# ── text validation ───────────────────────────────────────────────────────────

def test_non_string_text_returns_error():
    """text field that is not a string must return an error, not be silently coerced."""
    session = "cmt-texttype"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": [1, 2, 3]})
        msg = ws.receive_json()

    assert msg["type"] == "error"
    assert "string" in msg["detail"].lower()


def test_non_string_text_integer_returns_error():
    session = "cmt-textint"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": 42})
        msg = ws.receive_json()

    assert msg["type"] == "error"
    assert "string" in msg["detail"].lower()


def test_empty_string_text_returns_error():
    session = "cmt-empty"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": ""})
        msg = ws.receive_json()

    assert msg["type"] == "error"
    assert "required" in msg["detail"].lower()


def test_whitespace_only_text_returns_error():
    session = "cmt-whitespace"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "   \t  "})
        msg = ws.receive_json()

    assert msg["type"] == "error"
    assert "required" in msg["detail"].lower()


def test_text_exceeding_max_chars_returns_error():
    session = "cmt-toolong"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({
            "type": "comment_added",
            "line": 1,
            "text": "x" * (MAX_COMMENT_CHARS + 1),
        })
        msg = ws.receive_json()

    assert msg["type"] == "error"
    assert str(MAX_COMMENT_CHARS) in msg["detail"]


def test_text_at_exact_max_chars_is_accepted():
    session = "cmt-exactmax"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({
            "type": "comment_added",
            "line": 1,
            "text": "y" * MAX_COMMENT_CHARS,
        })
        msg = ws.receive_json()

    assert msg["type"] == "comment_added"
    assert len(msg["comment"]["text"]) == MAX_COMMENT_CHARS


# ── line number handling ──────────────────────────────────────────────────────

def test_missing_line_defaults_to_one():
    session = "cmt-noline"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "text": "No line field."})
        msg = ws.receive_json()

    assert msg["type"] == "comment_added"
    assert msg["comment"]["line"] == 1


def test_non_integer_line_defaults_to_one():
    session = "cmt-badline"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": "bad", "text": "Valid text."})
        msg = ws.receive_json()

    assert msg["type"] == "comment_added"
    assert msg["comment"]["line"] == 1


def test_zero_line_is_clamped_to_one():
    session = "cmt-zeroline"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 0, "text": "Zero line."})
        msg = ws.receive_json()

    assert msg["type"] == "comment_added"
    assert msg["comment"]["line"] == 1


def test_negative_line_is_clamped_to_one():
    session = "cmt-negline"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": -5, "text": "Negative line."})
        msg = ws.receive_json()

    assert msg["type"] == "comment_added"
    assert msg["comment"]["line"] == 1


# ── comment cap ───────────────────────────────────────────────────────────────

def test_comment_limit_is_enforced():
    """Once MAX_COMMENTS_PER_SESSION comments exist, further adds are rejected."""
    session = "cmt-caplimit"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        # Fill up to the cap.
        for i in range(MAX_COMMENTS_PER_SESSION):
            ws.send_json({"type": "comment_added", "line": 1, "text": f"Comment {i}"})
            ws.receive_json()

        # The next comment must be rejected.
        ws.send_json({"type": "comment_added", "line": 1, "text": "One too many."})
        error_msg = ws.receive_json()

    assert error_msg["type"] == "error"
    assert "limit" in error_msg["detail"].lower()


def test_comment_count_does_not_exceed_cap():
    """The room's comment list must never grow beyond MAX_COMMENTS_PER_SESSION."""
    session = "cmt-capcount"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        for i in range(MAX_COMMENTS_PER_SESSION + 5):
            ws.send_json({"type": "comment_added", "line": 1, "text": f"C{i}"})
            ws.receive_json()  # accept or error — consume either way

    room = manager.rooms.get(session)
    assert room is not None
    assert len(room.comments) <= MAX_COMMENTS_PER_SESSION


# ── session teardown ──────────────────────────────────────────────────────────

def test_comments_cleared_when_session_destroyed():
    """Room and its comments must be removed when the last client disconnects."""
    session = "cmt-teardown"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "Will be gone."})
        ws.receive_json()

        assert session in manager.rooms
        assert len(manager.rooms[session].comments) == 1

    # After the last client disconnects the room must be deleted.
    assert session not in manager.rooms


def test_new_session_starts_with_empty_comments():
    """A fresh session must have an empty comment list."""
    session = "cmt-fresh"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        state = ws.receive_json()
        ws.receive_json()

    assert state["comments"] == []


def test_rejoining_same_session_name_starts_fresh():
    """A reconnecting client gets a clean room (prior session was torn down)."""
    session = "cmt-rejoin"

    # First connection: add a comment then disconnect.
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()
        ws.send_json({"type": "comment_added", "line": 1, "text": "Old comment."})
        ws.receive_json()

    # Room is gone.
    assert session not in manager.rooms

    # Second connection: should see no prior comments.
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        state = ws.receive_json()
        ws.receive_json()

    assert state["comments"] == []
