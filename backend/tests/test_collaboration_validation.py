"""Input validation and session lifecycle tests for the collaboration router."""

import asyncio

import pytest
from app import main as app_main
from app.routers import collaboration
from app.routers.collaboration import (
    MAX_CODE_CHARS,
    MAX_COMMENT_CHARS,
    MAX_CURSOR_VALUE,
    MAX_LANGUAGE_CHARS,
    manager,
)
from fastapi.testclient import TestClient

client = TestClient(app_main.app)

WS_URL = "/collaboration/ws/validation-room?name=Alice"


def setup_function():
    manager.reset()


def _join(websocket):
    """Consume the session_state and presence_update sent on join."""
    state = websocket.receive_json()
    websocket.receive_json()
    return state


def _send_and_collect(websocket, payload):
    """Send a payload, then a ping, and return everything before the pong.

    Using the pong as a marker proves the connection is still usable after the
    payload and lets us assert that nothing else was sent back.
    """
    websocket.send_json(payload)
    websocket.send_json({"type": "ping"})
    replies = []
    while True:
        message = websocket.receive_json()
        if message == {"type": "pong"}:
            return replies
        replies.append(message)


def _error(detail):
    return {"type": "error", "detail": detail}


@pytest.mark.parametrize(
    "payload, detail",
    [
        ({"type": "code_update"}, "code is required"),
        ({"type": "code_update", "code": None}, "code must be a string"),
        ({"type": "code_update", "code": 123}, "code must be a string"),
        ({"type": "code_update", "code": ["x"]}, "code must be a string"),
        (
            {"type": "code_update", "code": "x" * (MAX_CODE_CHARS + 1)},
            f"code exceeds {MAX_CODE_CHARS} characters",
        ),
        (
            {"type": "code_update", "code": "x", "version": "abc"},
            "version must be an integer",
        ),
        (
            {"type": "code_update", "code": "x", "version": None},
            "version must be an integer",
        ),
        (
            {"type": "code_update", "code": "x", "version": True},
            "version must be an integer",
        ),
        (
            {"type": "code_update", "code": "x", "version": -1},
            "version must not be negative",
        ),
        (
            {"type": "code_update", "code": "x", "language": 42},
            "language must be a string",
        ),
        (
            {
                "type": "code_update",
                "code": "x",
                "language": "p" * (MAX_LANGUAGE_CHARS + 1),
            },
            f"language exceeds {MAX_LANGUAGE_CHARS} characters",
        ),
    ],
)
def test_invalid_code_update_returns_error_and_keeps_connection(payload, detail):
    with client.websocket_connect(WS_URL) as websocket:
        _join(websocket)

        assert _send_and_collect(websocket, payload) == [_error(detail)]

    assert manager.rooms == {}


def test_invalid_code_update_does_not_change_room_state():
    with client.websocket_connect(WS_URL) as websocket:
        _join(websocket)
        _send_and_collect(
            websocket, {"type": "code_update", "code": "x", "version": "abc"}
        )

        room = manager.rooms["validation-room"]
        assert room.version == 0
        assert room.code == ""


def test_code_update_boundary_values_are_accepted():
    with client.websocket_connect(WS_URL) as websocket:
        _join(websocket)

        replies = _send_and_collect(
            websocket,
            {
                "type": "code_update",
                "code": "x" * MAX_CODE_CHARS,
                "language": "p" * MAX_LANGUAGE_CHARS,
                "version": 0,
            },
        )
        assert [r["type"] for r in replies] == ["code_update"]
        assert len(replies[0]["code"]) == MAX_CODE_CHARS

        # An empty string is a legitimate edit (the user cleared the editor).
        replies = _send_and_collect(
            websocket, {"type": "code_update", "code": "", "version": 1}
        )
        assert [r["type"] for r in replies] == ["code_update"]
        assert replies[0]["code"] == ""


def test_code_update_without_version_or_language_still_works():
    with client.websocket_connect(WS_URL) as websocket:
        _join(websocket)

        replies = _send_and_collect(websocket, {"type": "code_update", "code": "a = 1"})

        assert replies[0]["type"] == "code_update"
        assert replies[0]["version"] == 1
        assert replies[0]["language"] is None


@pytest.mark.parametrize(
    "payload, detail",
    [
        ({"type": "cursor_update"}, "cursor must be an object"),
        ({"type": "cursor_update", "cursor": None}, "cursor must be an object"),
        ({"type": "cursor_update", "cursor": [1, 2]}, "cursor must be an object"),
        ({"type": "cursor_update", "cursor": "3:4"}, "cursor must be an object"),
        (
            {"type": "cursor_update", "cursor": {"line": "x"}},
            "cursor.line must be an integer",
        ),
        (
            {"type": "cursor_update", "cursor": {"line": None}},
            "cursor.line must be an integer",
        ),
        (
            {"type": "cursor_update", "cursor": {"column": True}},
            "cursor.column must be an integer",
        ),
        (
            {"type": "cursor_update", "cursor": {"selectionStart": "0"}},
            "cursor.selectionStart must be an integer",
        ),
        (
            {"type": "cursor_update", "cursor": {"selectionEnd": [0]}},
            "cursor.selectionEnd must be an integer",
        ),
        (
            {"type": "cursor_update", "cursor": {"line": MAX_CURSOR_VALUE + 1}},
            "cursor.line is out of range",
        ),
    ],
)
def test_invalid_cursor_update_returns_error_and_keeps_connection(payload, detail):
    with client.websocket_connect(WS_URL) as websocket:
        _join(websocket)

        assert _send_and_collect(websocket, payload) == [_error(detail)]

        users = manager.rooms["validation-room"].users.values()
        assert all(user["cursor"] is None for user in users)


def test_cursor_update_clamps_low_values_and_defaults_missing_fields():
    with client.websocket_connect(WS_URL) as alice:
        _join(alice)
        with client.websocket_connect(
            "/collaboration/ws/validation-room?name=Bob"
        ) as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            bob.send_json(
                {"type": "cursor_update", "cursor": {"line": 0, "selectionStart": -4}}
            )
            update = alice.receive_json()

            assert update["type"] == "cursor_update"
            assert update["user"]["cursor"] == {
                "line": 1,
                "column": 1,
                "selectionStart": 0,
                "selectionEnd": 0,
            }

            bob.send_json(
                {
                    "type": "cursor_update",
                    "cursor": {"line": MAX_CURSOR_VALUE, "column": 2.0},
                }
            )
            update = alice.receive_json()
            assert update["user"]["cursor"]["line"] == MAX_CURSOR_VALUE
            assert update["user"]["cursor"]["column"] == 2


@pytest.mark.parametrize(
    "payload, detail",
    [
        ({"type": "comment_added"}, "comment text is required"),
        ({"type": "comment_added", "text": None}, "comment text is required"),
        ({"type": "comment_added", "text": ""}, "comment text is required"),
        ({"type": "comment_added", "text": "   \n"}, "comment text is required"),
        ({"type": "comment_added", "text": 5}, "comment text must be a string"),
        ({"type": "comment_added", "text": ["a"]}, "comment text must be a string"),
        ({"type": "comment_added", "text": {"a": 1}}, "comment text must be a string"),
        (
            {"type": "comment_added", "text": "x" * (MAX_COMMENT_CHARS + 1)},
            f"comment exceeds {MAX_COMMENT_CHARS} characters",
        ),
        (
            {"type": "comment_added", "text": "hi", "line": "abc"},
            "line must be an integer",
        ),
        (
            {"type": "comment_added", "text": "hi", "line": None},
            "line must be an integer",
        ),
        (
            {"type": "comment_added", "text": "hi", "line": False},
            "line must be an integer",
        ),
        (
            {"type": "comment_added", "text": "hi", "line": MAX_CURSOR_VALUE + 1},
            "line is out of range",
        ),
    ],
)
def test_invalid_comment_returns_error_and_keeps_connection(payload, detail):
    with client.websocket_connect(WS_URL) as websocket:
        _join(websocket)

        assert _send_and_collect(websocket, payload) == [_error(detail)]

        assert manager.rooms["validation-room"].comments == []


def test_comment_boundary_values_are_accepted():
    with client.websocket_connect(WS_URL) as websocket:
        _join(websocket)

        replies = _send_and_collect(
            websocket,
            {"type": "comment_added", "text": "x" * MAX_COMMENT_CHARS, "line": 0},
        )

        assert [r["type"] for r in replies] == ["comment_added"]
        # Line numbers below 1 are clamped, as before.
        assert replies[0]["comment"]["line"] == 1
        assert len(replies[0]["comment"]["text"]) == MAX_COMMENT_CHARS


def test_comment_text_is_stripped_and_line_defaults_to_one():
    with client.websocket_connect(WS_URL) as websocket:
        _join(websocket)

        replies = _send_and_collect(
            websocket, {"type": "comment_added", "text": "  looks fine  "}
        )

        assert replies[0]["comment"]["text"] == "looks fine"
        assert replies[0]["comment"]["line"] == 1


@pytest.mark.parametrize(
    "payload, detail",
    [
        ({}, "Unsupported collaboration message type: None"),
        ({"type": None}, "Unsupported collaboration message type: None"),
        (
            {"type": ["code_update"]},
            "Unsupported collaboration message type: ['code_update']",
        ),
        ({"type": {"a": 1}}, "Unsupported collaboration message type: {'a': 1}"),
        ({"type": 7}, "Unsupported collaboration message type: 7"),
    ],
)
def test_missing_or_non_string_type_gets_error_not_crash(payload, detail):
    with client.websocket_connect(WS_URL) as websocket:
        _join(websocket)

        assert _send_and_collect(websocket, payload) == [_error(detail)]


@pytest.mark.parametrize("payload", [[], "code_update", 42, None, True])
def test_non_object_payload_is_rejected_and_connection_stays_open(payload):
    with client.websocket_connect(WS_URL) as websocket:
        _join(websocket)

        assert _send_and_collect(websocket, payload) == [
            _error("message payload must be a JSON object")
        ]


def test_invalid_message_only_reaches_the_sender():
    with client.websocket_connect(WS_URL) as alice:
        _join(alice)
        with client.websocket_connect(
            "/collaboration/ws/validation-room?name=Bob"
        ) as bob:
            bob.receive_json()
            alice.receive_json()
            bob.receive_json()

            assert _send_and_collect(bob, {"type": "code_update", "code": 1}) == [
                _error("code must be a string")
            ]

            # Alice saw nothing from Bob's bad message, only her own ping/pong.
            alice.send_json({"type": "ping"})
            assert alice.receive_json() == {"type": "pong"}


# --- session lifecycle ---------------------------------------------------


class _FakeSocket:
    def __init__(self, fail_on_send=False):
        self.sent = []
        self.accepted = False
        self.fail_on_send = fail_on_send

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        if self.fail_on_send:
            raise RuntimeError("socket closed")
        self.sent.append(message)


def test_message_from_departed_client_does_not_recreate_room():
    async def scenario():
        socket = _FakeSocket()
        client_id = await manager.connect("gone-room", socket, "Alice")
        await manager.disconnect("gone-room", client_id)
        assert "gone-room" not in manager.rooms

        await manager.handle_message(
            "gone-room", client_id, {"type": "code_update", "code": "x"}
        )
        await manager.handle_message("gone-room", client_id, {"type": "ping"})

    asyncio.run(scenario())

    assert "gone-room" not in manager.rooms


def test_message_from_departed_client_is_ignored_in_a_live_room():
    async def scenario():
        alice_socket, bob_socket = _FakeSocket(), _FakeSocket()
        alice = await manager.connect("shared-room", alice_socket, "Alice")
        bob = await manager.connect("shared-room", bob_socket, "Bob")
        await manager.disconnect("shared-room", bob)
        alice_socket.sent.clear()

        await manager.handle_message(
            "shared-room", bob, {"type": "code_update", "code": "stale", "version": 0}
        )
        await manager.handle_message(
            "shared-room", bob, {"type": "comment_added", "text": "late"}
        )
        return alice

    asyncio.run(scenario())

    room = manager.rooms["shared-room"]
    assert room.code == ""
    assert room.version == 0
    assert room.comments == []


def test_failed_join_does_not_leave_a_half_joined_client():
    async def scenario():
        with pytest.raises(RuntimeError):
            await manager.connect("flaky-room", _FakeSocket(fail_on_send=True), "Alice")

    asyncio.run(scenario())

    assert "flaky-room" not in manager.rooms


def test_unexpected_loop_error_still_cleans_up_the_client():
    class ExplodingSocket(_FakeSocket):
        async def receive_json(self):
            raise RuntimeError("unexpected failure")

    async def scenario():
        socket = ExplodingSocket()
        try:
            await collaboration.collaboration_websocket(socket, "crash-room", "Alice")
        except RuntimeError:
            pass

    asyncio.run(scenario())

    assert "crash-room" not in manager.rooms
