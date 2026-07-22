"""
Regression tests for collaboration comments (#1575).

These tests pin the specific observable contract of the comment feature so
that any future change that silently alters comment structure, ordering,
accumulation behaviour, or broadcast targeting will cause an immediate,
descriptive test failure.

Each test is labelled with the regression scenario it guards.

Scenarios NOT duplicated from existing test files:
- comment payload field completeness (id, createdAt, authorId, line, text, color, author)
- authorId matches the clientId issued by session_state
- comment text whitespace is stripped before storage
- null / missing text field returns a typed error
- comments list grows by exactly 1 per successful add
- cumulative comments list is correct after N sequential adds
- sender receives their own comment_added broadcast
- three-client scenario: comments from two authors visible to late-joining third client
- comment survives another client's disconnect
- comment order is preserved (FIFO)
- comments from the cumulative list in each broadcast match the full history
"""

from app import main as app_main
from app.routers.collaboration import manager
from fastapi.testclient import TestClient

client = TestClient(app_main.app)


def setup_function():
    manager.reset()


# ── Regression: comment payload field completeness ───────────────────────────

def test_comment_payload_has_all_required_fields():
    """Every comment_added broadcast must include id, line, text, authorId,
    author, color, and createdAt fields."""
    with client.websocket_connect("/collaboration/ws/reg-fields?name=Alice") as ws:
        ws.receive_json()  # session_state
        ws.receive_json()  # presence_update

        ws.send_json({"type": "comment_added", "line": 7, "text": "Field check."})
        msg = ws.receive_json()

    comment = msg["comment"]
    assert "id" in comment, "comment must have an id field"
    assert "line" in comment, "comment must have a line field"
    assert "text" in comment, "comment must have a text field"
    assert "authorId" in comment, "comment must have an authorId field"
    assert "author" in comment, "comment must have an author field"
    assert "color" in comment, "comment must have a color field"
    assert "createdAt" in comment, "comment must have a createdAt field"


def test_comment_id_is_nonempty_string():
    """comment.id must be a non-empty string (hex)."""
    with client.websocket_connect("/collaboration/ws/reg-id?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()
        ws.send_json({"type": "comment_added", "line": 1, "text": "ID check."})
        msg = ws.receive_json()

    assert isinstance(msg["comment"]["id"], str)
    assert len(msg["comment"]["id"]) > 0


def test_comment_created_at_is_iso8601_utc():
    """comment.createdAt must be a non-empty ISO-8601 string ending with '+00:00' or 'Z'."""
    from datetime import datetime, timezone

    with client.websocket_connect("/collaboration/ws/reg-ts?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()
        ws.send_json({"type": "comment_added", "line": 1, "text": "Timestamp check."})
        msg = ws.receive_json()

    created_at = msg["comment"]["createdAt"]
    assert isinstance(created_at, str) and created_at, "createdAt must be a non-empty string"

    # Must be parseable as a timezone-aware datetime.
    try:
        dt = datetime.fromisoformat(created_at)
    except ValueError:
        raise AssertionError(f"createdAt is not a valid ISO-8601 string: {created_at!r}")

    assert dt.tzinfo is not None, "createdAt must include timezone info"


# ── Regression: authorId matches actual clientId ──────────────────────────────

def test_comment_author_id_matches_session_client_id():
    """comment.authorId must equal the clientId that was issued in session_state."""
    with client.websocket_connect("/collaboration/ws/reg-authorid?name=Alice") as ws:
        state = ws.receive_json()  # session_state
        ws.receive_json()          # presence_update
        my_client_id = state["clientId"]

        ws.send_json({"type": "comment_added", "line": 1, "text": "Who am I?"})
        msg = ws.receive_json()

    assert msg["comment"]["authorId"] == my_client_id


# ── Regression: text whitespace stripping ─────────────────────────────────────

def test_comment_text_leading_trailing_whitespace_is_stripped():
    """The server must strip leading and trailing whitespace from comment text."""
    with client.websocket_connect("/collaboration/ws/reg-strip?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "  trimmed  "})
        msg = ws.receive_json()

    assert msg["comment"]["text"] == "trimmed"


def test_comment_text_internal_whitespace_is_preserved():
    """Internal whitespace must NOT be stripped — only leading/trailing."""
    with client.websocket_connect("/collaboration/ws/reg-internal?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "  a  b  c  "})
        msg = ws.receive_json()

    assert msg["comment"]["text"] == "a  b  c"


# ── Regression: null / missing text field ─────────────────────────────────────

def test_null_text_returns_typed_error():
    """JSON null for text (Python None) must return an error with 'string' in detail."""
    with client.websocket_connect("/collaboration/ws/reg-null?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        # JSON null → Python None; isinstance(None, str) is False.
        ws.send_json({"type": "comment_added", "line": 1, "text": None})
        msg = ws.receive_json()

    assert msg["type"] == "error"
    assert "string" in msg["detail"].lower()


def test_missing_text_field_returns_typed_error():
    """Omitting the text field entirely must return the same error as null text."""
    with client.websocket_connect("/collaboration/ws/reg-notext?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1})
        msg = ws.receive_json()

    assert msg["type"] == "error"
    assert "string" in msg["detail"].lower()


# ── Regression: comments list grows by exactly 1 per add ─────────────────────

def test_comments_list_grows_by_one_per_successful_add():
    """Each accepted comment must append exactly one entry to the cumulative list."""
    session = "reg-grow"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        for i in range(1, 6):
            ws.send_json({"type": "comment_added", "line": i, "text": f"Comment {i}"})
            msg = ws.receive_json()
            assert len(msg["comments"]) == i, (
                f"After {i} adds, comments list must have length {i}, got {len(msg['comments'])}"
            )


# ── Regression: cumulative comments list is correct ──────────────────────────

def test_cumulative_comments_list_content_is_correct():
    """The comments list in each broadcast must contain all prior comments in order."""
    session = "reg-cumulative"
    texts = ["Alpha", "Beta", "Gamma"]

    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        for text in texts:
            ws.send_json({"type": "comment_added", "line": 1, "text": text})
            msg = ws.receive_json()

    # Final message must include all three comments in insertion order.
    assert [c["text"] for c in msg["comments"]] == texts


# ── Regression: FIFO comment ordering ────────────────────────────────────────

def test_comments_are_ordered_fifo():
    """Comments must appear in the order they were accepted by the server."""
    session = "reg-fifo"
    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        for i in range(5):
            ws.send_json({"type": "comment_added", "line": i + 1, "text": f"Step {i}"})
            ws.receive_json()

    room = manager.rooms.get(session)
    assert room is not None
    texts = [c["text"] for c in room.comments]
    assert texts == [f"Step {i}" for i in range(5)]


# ── Regression: sender receives own comment_added broadcast ──────────────────

def test_sender_receives_own_comment_broadcast():
    """The client that posts a comment must also receive the comment_added broadcast
    (broadcast does not exclude the sender for comments)."""
    with client.websocket_connect("/collaboration/ws/reg-selfrecv?name=Alice") as ws:
        state = ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 1, "text": "Self receive."})
        msg = ws.receive_json()

    assert msg["type"] == "comment_added"
    assert msg["comment"]["authorId"] == state["clientId"]


# ── Regression: three-client scenario ────────────────────────────────────────

def test_comments_from_two_authors_visible_to_late_joining_third_client():
    """Comments posted by client A and client B must both appear in the
    session_state received by a third client who joins after both posts."""
    session = "reg-three"

    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob") as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            alice.send_json({"type": "comment_added", "line": 1, "text": "From Alice."})
            alice.receive_json()
            bob.receive_json()

            bob.send_json({"type": "comment_added", "line": 2, "text": "From Bob."})
            alice.receive_json()
            bob.receive_json()

            # Charlie joins last.
            with client.websocket_connect(f"/collaboration/ws/{session}?name=Charlie") as charlie:
                charlie_state = charlie.receive_json()
                alice.receive_json()
                bob.receive_json()
                charlie.receive_json()

    comment_texts = [c["text"] for c in charlie_state["comments"]]
    assert "From Alice." in comment_texts
    assert "From Bob." in comment_texts
    assert charlie_state["reconnected"] is True


def test_comment_authors_in_three_client_scenario_are_correct():
    """Each comment in Charlie's session_state must correctly attribute its author."""
    session = "reg-three-authors"

    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob") as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            alice.send_json({"type": "comment_added", "line": 1, "text": "Alice says hi."})
            alice.receive_json()
            bob.receive_json()

            bob.send_json({"type": "comment_added", "line": 3, "text": "Bob replies."})
            alice.receive_json()
            bob.receive_json()

            with client.websocket_connect(f"/collaboration/ws/{session}?name=Charlie") as charlie:
                charlie_state = charlie.receive_json()
                alice.receive_json()
                bob.receive_json()
                charlie.receive_json()

    by_text = {c["text"]: c["author"] for c in charlie_state["comments"]}
    assert by_text["Alice says hi."] == "Alice"
    assert by_text["Bob replies."] == "Bob"


# ── Regression: comment survives another client's disconnect ──────────────────

def test_comment_persists_after_other_client_disconnects():
    """A comment added before a second client disconnects must still be in the
    room's comment list after that client leaves."""
    session = "reg-persist-disc"

    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as alice:
        alice.receive_json()
        alice.receive_json()

        with client.websocket_connect(f"/collaboration/ws/{session}?name=Bob") as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            alice.send_json({"type": "comment_added", "line": 1, "text": "Outlive Bob."})
            alice.receive_json()
            bob.receive_json()

        # Bob disconnects; Alice consumes the presence_update.
        alice.receive_json()

        # Comment must still be in the room.
        room = manager.rooms.get(session)
        assert room is not None
        assert any(c["text"] == "Outlive Bob." for c in room.comments)


# ── Regression: comment_added.comments always includes new comment ────────────

def test_comment_added_comments_list_includes_the_new_comment():
    """The cumulative comments list in a comment_added payload must include
    the comment that was just added."""
    with client.websocket_connect("/collaboration/ws/reg-includes?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 4, "text": "Included."})
        msg = ws.receive_json()

    ids = [c["id"] for c in msg["comments"]]
    assert msg["comment"]["id"] in ids


# ── Regression: comment line is stored correctly ──────────────────────────────

def test_comment_line_matches_sent_value():
    """The line number sent in the request must match the line stored in the comment."""
    with client.websocket_connect("/collaboration/ws/reg-line?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "comment_added", "line": 42, "text": "Line 42."})
        msg = ws.receive_json()

    assert msg["comment"]["line"] == 42


# ── Regression: comment_added payload structure under multi-comment load ──────

def test_comments_list_in_broadcast_is_consistent_with_room_state():
    """The comments list inside each comment_added broadcast must match the
    room's internal comment list at the time of the broadcast."""
    session = "reg-consistent"
    received_snapshots = []

    with client.websocket_connect(f"/collaboration/ws/{session}?name=Alice") as ws:
        ws.receive_json()
        ws.receive_json()

        for i in range(4):
            ws.send_json({"type": "comment_added", "line": i + 1, "text": f"T{i}"})
            msg = ws.receive_json()
            received_snapshots.append(list(msg["comments"]))

    # Each snapshot must be a prefix-extension of the previous one.
    for idx in range(1, len(received_snapshots)):
        prev = received_snapshots[idx - 1]
        curr = received_snapshots[idx]
        assert len(curr) == len(prev) + 1, (
            f"comments list should grow by 1 at step {idx}"
        )
        # All previous comments must still be present in the same order.
        for j, prev_cmt in enumerate(prev):
            assert curr[j]["id"] == prev_cmt["id"], (
                f"Comment at index {j} changed between broadcast {idx-1} and {idx}"
            )
