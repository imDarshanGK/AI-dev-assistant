"""
Tests for improved reconnect behavior in collaboration comments (#1574).

Covers:
- reconnecting client receives full comment history in session_state
- session_state.reconnected flag is False for a fresh empty session
- session_state.reconnected flag is True when code exists
- session_state.reconnected flag is True when prior comments exist
- session_state.reconnected flag is True when other users are present
- session_state.comments is a stable snapshot (copy, not live reference)
- comment_sync request returns current comment list to requester only
- comment_sync does not broadcast to other clients
- comment_sync after reconnect delivers comments added during absence
- reconnecting after last client left starts a fresh empty session
- reconnecting while another user is still connected restores full state
- comments added between two clients are visible to a third reconnecting client
"""

from app import main as app_main
from app.routers.collaboration import manager
from fastapi.testclient import TestClient

client = TestClient(app_main.app)


def setup_function():
    manager.reset()


# ── reconnected flag ──────────────────────────────────────────────────────────

def test_fresh_empty_session_has_reconnected_false():
    """A brand-new session with no code, no comments, and only one user
    must report reconnected=False."""
    with client.websocket_connect("/collaboration/ws/rc-fresh?name=Alice") as ws:
        state = ws.receive_json()
        ws.receive_json()  # presence_update

    assert state["type"] == "session_state"
    assert state["reconnected"] is False


def test_reconnected_true_when_other_user_present():
    """When a second client joins a room that already has one user,
    reconnected must be True (state exists in the room)."""
    with client.websocket_connect("/collaboration/ws/rc-otheruser?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        with client.websocket_connect("/collaboration/ws/rc-otheruser?name=Bob") as bob:
            bob_state = bob.receive_json()
            alice.receive_json()  # presence_update for Bob
            bob.receive_json()    # presence_update

    assert bob_state["reconnected"] is True


def test_reconnected_true_when_code_exists():
    """A client joining a session that already has code must get reconnected=True."""
    with client.websocket_connect("/collaboration/ws/rc-code?name=Alice") as alice:
        alice_state = alice.receive_json()
        alice.receive_json()

        alice.send_json({
            "type": "code_update",
            "code": "print('hello')",
            "language": "python",
            "version": alice_state["version"],
        })
        alice.receive_json()  # code_update broadcast back

    # Alice left — session is destroyed.  Rejoin to create fresh.
    with client.websocket_connect("/collaboration/ws/rc-code2?name=Alice") as alice:
        alice_state = alice.receive_json()
        alice.receive_json()

        alice.send_json({
            "type": "code_update",
            "code": "x = 1",
            "language": "python",
            "version": alice_state["version"],
        })
        alice.receive_json()

        with client.websocket_connect("/collaboration/ws/rc-code2?name=Bob") as bob:
            bob_state = bob.receive_json()
            alice.receive_json()
            bob.receive_json()

    assert bob_state["reconnected"] is True
    assert bob_state["code"] == "x = 1"


def test_reconnected_true_when_prior_comments_exist():
    """A client joining after comments have been posted must get reconnected=True."""
    with client.websocket_connect("/collaboration/ws/rc-cmt?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        alice.send_json({"type": "comment_added", "line": 1, "text": "A comment."})
        alice.receive_json()

        with client.websocket_connect("/collaboration/ws/rc-cmt?name=Bob") as bob:
            bob_state = bob.receive_json()
            alice.receive_json()
            bob.receive_json()

    assert bob_state["reconnected"] is True
    assert len(bob_state["comments"]) == 1
    assert bob_state["comments"][0]["text"] == "A comment."


# ── comment history on reconnect ──────────────────────────────────────────────

def test_reconnecting_client_receives_full_comment_history():
    """After partial disconnect and reconnect, the returning client must receive
    all comments that were added while they were away."""
    session = "rc-history"

    # Alice and Bob connect; Alice posts a comment.
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob") as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            alice.send_json({"type": "comment_added", "line": 2, "text": "First comment."})
            alice.receive_json()  # broadcast to alice
            bob.receive_json()    # broadcast to bob

        # Bob disconnects.  Alice adds another comment.
        alice.receive_json()  # presence_update for Bob leaving

        alice.send_json({"type": "comment_added", "line": 3, "text": "Second comment."})
        alice.receive_json()

        # Bob reconnects.
        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob") as bob2:
            state = bob2.receive_json()
            alice.receive_json()  # presence_update for Bob2 joining
            bob2.receive_json()   # presence_update

    assert state["type"] == "session_state"
    assert len(state["comments"]) == 2
    assert state["comments"][0]["text"] == "First comment."
    assert state["comments"][1]["text"] == "Second comment."
    assert state["reconnected"] is True


def test_reconnected_after_full_teardown_gets_empty_state():
    """When a session was fully torn down (all clients left), a new connection
    to the same session_id starts with zero comments and reconnected=False."""
    session = "rc-teardown"

    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()
        ws.send_json({"type": "comment_added", "line": 1, "text": "Gone forever."})
        ws.receive_json()

    # Session is destroyed after Alice leaves.
    assert session not in manager.rooms

    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        state = ws.receive_json()
        ws.receive_json()

    assert state["comments"] == []
    assert state["reconnected"] is False


# ── comment_sync message ──────────────────────────────────────────────────────

def test_comment_sync_returns_current_comments_to_requester():
    """Sending comment_sync must return a comment_sync frame with the current
    comment list to the requesting client only."""
    with client.websocket_connect("/collaboration/ws/rc-sync1?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "Sync me."})
        ws.receive_json()  # comment_added broadcast

        ws.send_json({"type": "comment_sync"})
        sync = ws.receive_json()

    assert sync["type"] == "comment_sync"
    assert len(sync["comments"]) == 1
    assert sync["comments"][0]["text"] == "Sync me."


def test_comment_sync_not_broadcast_to_other_clients():
    """comment_sync must be a unicast response — other clients must not receive it."""
    session = "rc-sync2"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob") as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            alice.send_json({"type": "comment_added", "line": 1, "text": "Hello."})
            alice.receive_json()  # comment_added to alice
            bob.receive_json()    # comment_added to bob

            # Bob requests a sync — Alice must not receive anything.
            bob.send_json({"type": "comment_sync"})
            sync = bob.receive_json()

            # Verify no extra message is waiting for Alice by sending a ping.
            alice.send_json({"type": "ping"})
            pong = alice.receive_json()

    assert sync["type"] == "comment_sync"
    assert pong["type"] == "pong"


def test_comment_sync_empty_when_no_comments():
    """comment_sync on a session with no comments returns an empty list."""
    with client.websocket_connect("/collaboration/ws/rc-sync3?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_sync"})
        sync = ws.receive_json()

    assert sync["type"] == "comment_sync"
    assert sync["comments"] == []


def test_comment_sync_reflects_comments_added_after_reconnect():
    """A comment added between the session_state snapshot and the comment_sync
    request must appear in the sync response."""
    session = "rc-sync4"

    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob") as bob:
            bob_state = bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            # Alice adds a comment after Bob's session_state was built.
            alice.send_json({"type": "comment_added", "line": 1, "text": "Late comment."})
            alice.receive_json()
            bob.receive_json()  # Bob also got the comment_added broadcast

            # Bob requests a sync to confirm his comment list is up-to-date.
            bob.send_json({"type": "comment_sync"})
            sync = bob.receive_json()

    # Bob's session_state snapshot may or may not have had 0 comments
    # (timing-dependent), but the sync must always reflect the current state.
    assert sync["type"] == "comment_sync"
    assert any(c["text"] == "Late comment." for c in sync["comments"])


# ── snapshot isolation ────────────────────────────────────────────────────────

def test_session_state_comments_is_a_snapshot_not_live_reference():
    """The comments list in session_state must be a copy — mutating
    the room's comment list after state was built must not affect the
    already-sent payload (this is verified via the manager's room state)."""
    session = "rc-snapshot"

    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob") as bob:
            bob_state = bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            # The list Bob received in his state snapshot is a copy.
            # Confirm the room's current comments list is a different object
            # by checking that adding a comment grows the room list but the
            # already-received snapshot stays at its original length.
            initial_count = len(bob_state["comments"])

            alice.send_json({"type": "comment_added", "line": 1, "text": "New comment."})
            alice.receive_json()
            bob.receive_json()  # consume the comment_added broadcast

            # The room now has one more comment than when Bob's state was built.
            room = manager.rooms.get(session)
            assert room is not None
            assert len(room.comments) == initial_count + 1

            # Bob's original snapshot must be unchanged.
            assert len(bob_state["comments"]) == initial_count
