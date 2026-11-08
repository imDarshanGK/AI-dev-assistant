"""Characterization tests for how collaboration messages flow through the manager.

These pin the exact payloads and who receives them, so the internals of
handle_message and the per-event handlers can be reshaped without changing the
wire format.
"""

import asyncio
import copy
from datetime import datetime

import pytest
from app.routers.collaboration import COLORS, CollaborationManager


class FakeSocket:
    """Records everything the server sends to one client.

    Messages are copied on send, like serializing them to JSON would, so later
    changes to room state do not rewrite what was already delivered.
    """

    def __init__(self):
        self.sent = []

    async def accept(self):
        return None

    async def send_json(self, message):
        self.sent.append(copy.deepcopy(message))


async def _join(mgr, session_id, name):
    socket = FakeSocket()
    client_id = await mgr.connect(session_id, socket, name)
    return client_id, socket


async def _two_clients(mgr, session_id="room"):
    """Join Alice and Bob, then forget the join traffic."""
    alice_id, alice = await _join(mgr, session_id, "Alice")
    bob_id, bob = await _join(mgr, session_id, "Bob")
    alice.sent.clear()
    bob.sent.clear()
    return alice_id, alice, bob_id, bob


def run(coro):
    return asyncio.run(coro)


# --- code_update ---------------------------------------------------------


def test_code_update_is_broadcast_to_everyone_including_sender():
    async def scenario():
        mgr = CollaborationManager()
        alice_id, alice, bob_id, bob = await _two_clients(mgr)

        await mgr.handle_message(
            "room",
            alice_id,
            {"type": "code_update", "code": "x = 1", "language": "python"},
        )
        return mgr, alice_id, alice, bob

    mgr, alice_id, alice, bob = run(scenario())

    expected = {
        "type": "code_update",
        "code": "x = 1",
        "language": "python",
        "version": 1,
        "senderId": alice_id,
    }
    assert alice.sent == [expected]
    assert bob.sent == [expected]
    room = mgr.rooms["room"]
    assert (room.code, room.language, room.version) == ("x = 1", "python", 1)


def test_code_update_without_language_keeps_the_room_language():
    async def scenario():
        mgr = CollaborationManager()
        alice_id, alice, _, bob = await _two_clients(mgr)

        await mgr.handle_message(
            "room",
            alice_id,
            {"type": "code_update", "code": "a", "language": "python"},
        )
        await mgr.handle_message(
            "room", alice_id, {"type": "code_update", "code": "b", "version": 1}
        )
        return bob

    bob = run(scenario())

    assert [m["version"] for m in bob.sent] == [1, 2]
    assert bob.sent[1]["code"] == "b"
    assert bob.sent[1]["language"] == "python"


@pytest.mark.parametrize("incoming_version", [1, 2, 7])
def test_code_update_at_or_ahead_of_room_version_is_accepted(incoming_version):
    async def scenario():
        mgr = CollaborationManager()
        alice_id, alice, _, bob = await _two_clients(mgr)
        await mgr.handle_message(
            "room", alice_id, {"type": "code_update", "code": "one"}
        )
        bob.sent.clear()

        await mgr.handle_message(
            "room",
            alice_id,
            {"type": "code_update", "code": "two", "version": incoming_version},
        )
        return mgr, bob

    mgr, bob = run(scenario())

    assert bob.sent[0]["type"] == "code_update"
    assert bob.sent[0]["code"] == "two"
    assert mgr.rooms["room"].version == 2


def test_stale_code_update_answers_only_the_sender_with_full_state():
    async def scenario():
        mgr = CollaborationManager()
        alice_id, alice, bob_id, bob = await _two_clients(mgr)
        await mgr.handle_message(
            "room",
            alice_id,
            {"type": "code_update", "code": "x = 1", "language": "python"},
        )
        await mgr.handle_message(
            "room", alice_id, {"type": "comment_added", "text": "hi", "line": 3}
        )
        alice.sent.clear()
        bob.sent.clear()

        await mgr.handle_message(
            "room",
            bob_id,
            {"type": "code_update", "code": "stale", "language": "js", "version": 0},
        )
        return mgr, alice_id, bob_id, alice, bob

    mgr, alice_id, bob_id, alice, bob = run(scenario())

    assert alice.sent == []
    assert len(bob.sent) == 1
    sync = bob.sent[0]
    assert set(sync) == {
        "type",
        "sessionId",
        "clientId",
        "code",
        "language",
        "version",
        "comments",
        "users",
    }
    assert sync["type"] == "sync_required"
    assert sync["sessionId"] == "room"
    assert sync["clientId"] == bob_id
    assert (sync["code"], sync["language"], sync["version"]) == ("x = 1", "python", 1)
    assert [c["text"] for c in sync["comments"]] == ["hi"]
    assert {u["id"] for u in sync["users"]} == {alice_id, bob_id}
    # The stale edit was not applied.
    room = mgr.rooms["room"]
    assert (room.code, room.language, room.version) == ("x = 1", "python", 1)


# --- cursor_update -------------------------------------------------------


def test_cursor_update_goes_to_everyone_but_the_sender():
    async def scenario():
        mgr = CollaborationManager()
        alice_id, alice, bob_id, bob = await _two_clients(mgr)

        await mgr.handle_message(
            "room",
            bob_id,
            {
                "type": "cursor_update",
                "cursor": {
                    "line": 0,
                    "column": 8,
                    "selectionStart": -4,
                    "selectionEnd": 12,
                },
            },
        )
        return mgr, bob_id, alice, bob

    mgr, bob_id, alice, bob = run(scenario())

    assert bob.sent == []
    assert len(alice.sent) == 1
    update = alice.sent[0]
    assert set(update) == {"type", "user"}
    assert update["type"] == "cursor_update"
    assert set(update["user"]) == {"id", "name", "color", "cursor", "joinedAt"}
    assert update["user"]["id"] == bob_id
    assert update["user"]["name"] == "Bob"
    assert update["user"]["cursor"] == {
        "line": 1,  # clamped up from 0
        "column": 8,
        "selectionStart": 0,  # clamped up from -4
        "selectionEnd": 12,
    }
    assert mgr.rooms["room"].users[bob_id]["cursor"] == update["user"]["cursor"]


def test_cursor_update_is_not_sent_across_rooms():
    async def scenario():
        mgr = CollaborationManager()
        a_id, a = await _join(mgr, "room-a", "Ann")
        _, a2 = await _join(mgr, "room-a", "Al")
        _, other = await _join(mgr, "room-b", "Zed")
        for s in (a, a2, other):
            s.sent.clear()

        await mgr.handle_message(
            "room-a", a_id, {"type": "cursor_update", "cursor": {"line": 2}}
        )
        return a2, other

    a2, other = run(scenario())

    assert len(a2.sent) == 1
    assert other.sent == []


# --- comment_added -------------------------------------------------------


def test_comment_is_broadcast_to_everyone_with_the_full_list():
    async def scenario():
        mgr = CollaborationManager()
        alice_id, alice, bob_id, bob = await _two_clients(mgr)

        await mgr.handle_message(
            "room",
            alice_id,
            {"type": "comment_added", "text": "  check this  ", "line": 4},
        )
        await mgr.handle_message(
            "room", bob_id, {"type": "comment_added", "text": "agreed"}
        )
        return mgr, alice_id, bob_id, alice, bob

    mgr, alice_id, bob_id, alice, bob = run(scenario())

    assert len(alice.sent) == 2
    assert len(bob.sent) == 2
    first = bob.sent[0]
    assert set(first) == {"type", "comment", "comments"}
    assert first["type"] == "comment_added"
    comment = first["comment"]
    assert set(comment) == {
        "id",
        "line",
        "text",
        "authorId",
        "author",
        "color",
        "createdAt",
    }
    assert len(comment["id"]) == 12
    assert comment["line"] == 4
    assert comment["text"] == "check this"  # stripped
    assert comment["authorId"] == alice_id
    assert comment["author"] == "Alice"
    assert comment["color"] == mgr.rooms["room"].users[alice_id]["color"]
    assert datetime.fromisoformat(comment["createdAt"]).tzinfo is not None
    assert first["comments"] == [comment]

    second = alice.sent[1]
    assert second["comment"]["line"] == 1  # default line
    assert second["comment"]["author"] == "Bob"
    assert second["comment"]["authorId"] == bob_id
    assert [c["text"] for c in second["comments"]] == ["check this", "agreed"]
    assert alice.sent == bob.sent


def test_user_colors_cycle_through_the_palette():
    async def scenario():
        mgr = CollaborationManager()
        for index in range(len(COLORS) + 1):
            await _join(mgr, "palette", f"user{index}")
        return mgr

    mgr = run(scenario())

    colors = [u["color"] for u in mgr.rooms["palette"].users.values()]
    assert colors[: len(COLORS)] == COLORS
    assert colors[len(COLORS)] == COLORS[0]


# --- ping, unsupported types, validation, departed clients ---------------


def test_ping_answers_only_the_sender():
    async def scenario():
        mgr = CollaborationManager()
        alice_id, alice, _, bob = await _two_clients(mgr)
        await mgr.handle_message("room", alice_id, {"type": "ping"})
        return alice, bob

    alice, bob = run(scenario())

    assert alice.sent == [{"type": "pong"}]
    assert bob.sent == []


@pytest.mark.parametrize(
    "message, detail",
    [
        (
            {"type": "unknown_event"},
            "Unsupported collaboration message type: unknown_event",
        ),
        ({}, "Unsupported collaboration message type: None"),
        ({"type": None}, "Unsupported collaboration message type: None"),
        ({"type": 7}, "Unsupported collaboration message type: 7"),
        (
            {"type": ["code_update"]},
            "Unsupported collaboration message type: ['code_update']",
        ),
        ({"type": {"a": 1}}, "Unsupported collaboration message type: {'a': 1}"),
        (
            {"type": "Code_Update"},
            "Unsupported collaboration message type: Code_Update",
        ),
        # Server-to-client types are not valid from a client.
        ({"type": "pong"}, "Unsupported collaboration message type: pong"),
        (
            {"type": "presence_update"},
            "Unsupported collaboration message type: presence_update",
        ),
    ],
)
def test_unsupported_message_types_error_only_the_sender(message, detail):
    async def scenario():
        mgr = CollaborationManager()
        alice_id, alice, _, bob = await _two_clients(mgr)
        await mgr.handle_message("room", alice_id, message)
        return mgr, alice, bob

    mgr, alice, bob = run(scenario())

    assert alice.sent == [{"type": "error", "detail": detail}]
    assert bob.sent == []
    assert mgr.rooms["room"].version == 0


@pytest.mark.parametrize(
    "message, detail",
    [
        ({"type": "code_update", "code": 5}, "code must be a string"),
        ({"type": "cursor_update", "cursor": "x"}, "cursor must be an object"),
        ({"type": "comment_added", "text": "   "}, "comment text is required"),
    ],
)
def test_invalid_payload_errors_only_the_sender_and_changes_nothing(message, detail):
    async def scenario():
        mgr = CollaborationManager()
        alice_id, alice, _, bob = await _two_clients(mgr)
        await mgr.handle_message("room", alice_id, message)
        return mgr, alice, bob

    mgr, alice, bob = run(scenario())

    assert alice.sent == [{"type": "error", "detail": detail}]
    assert bob.sent == []
    room = mgr.rooms["room"]
    assert (room.code, room.version, room.comments) == ("", 0, [])


def test_handlers_receive_the_validated_payload_and_invalid_ones_are_skipped(
    monkeypatch,
):
    calls = []

    async def run_scenario():
        mgr = CollaborationManager()
        alice_id, alice, _, _ = await _two_clients(mgr)

        async def record(name, session_id, client_id, data):
            calls.append((name, session_id, client_id, data))

        for name in ("code_update", "cursor_update", "comment_added"):
            monkeypatch.setattr(
                mgr,
                f"_handle_{name}",
                lambda s, c, d, name=name: record(name, s, c, d),
            )

        await mgr.handle_message(
            "room",
            alice_id,
            {"type": "code_update", "code": "c", "extra": "dropped", "version": 2.0},
        )
        await mgr.handle_message(
            "room", alice_id, {"type": "cursor_update", "cursor": {"line": 0}}
        )
        await mgr.handle_message(
            "room", alice_id, {"type": "comment_added", "text": " hi "}
        )
        await mgr.handle_message("room", alice_id, {"type": "code_update"})
        return alice_id

    alice_id = asyncio.run(run_scenario())

    assert calls == [
        (
            "code_update",
            "room",
            alice_id,
            {"code": "c", "language": None, "version": 2},
        ),
        (
            "cursor_update",
            "room",
            alice_id,
            {
                "cursor": {
                    "line": 1,
                    "column": 1,
                    "selectionStart": 0,
                    "selectionEnd": 0,
                }
            },
        ),
        ("comment_added", "room", alice_id, {"text": "hi", "line": 1}),
    ]


def test_messages_from_departed_or_unknown_clients_are_ignored():
    async def scenario():
        mgr = CollaborationManager()
        alice_id, alice, bob_id, bob = await _two_clients(mgr)
        await mgr.disconnect("room", bob_id)
        alice.sent.clear()

        await mgr.handle_message("room", bob_id, {"type": "ping"})
        await mgr.handle_message("room", "nobody", {"type": "code_update", "code": "x"})
        await mgr.handle_message("ghost-room", "nobody", {"type": "ping"})
        return mgr, alice, bob

    mgr, alice, bob = run(scenario())

    assert alice.sent == []
    assert bob.sent == []
    assert "ghost-room" not in mgr.rooms
    assert mgr.rooms["room"].version == 0


def test_errors_use_the_documented_shape_and_skip_clients_without_a_socket():
    async def scenario():
        mgr = CollaborationManager()
        alice_id, alice, _, _ = await _two_clients(mgr)
        room = mgr.rooms["room"]

        await mgr._send_error(room, alice_id, "boom")
        await mgr._send_error(room, "no-such-client", "ignored")
        return alice

    alice = run(scenario())

    assert alice.sent == [{"type": "error", "detail": "boom"}]
