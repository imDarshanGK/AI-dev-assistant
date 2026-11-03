"""Bad frames, handler crashes, dead sockets and reconnects in collaboration."""

import asyncio
import logging

import pytest
from app import main as app_main
from app.routers.collaboration import (
    INTERNAL_ERROR_DETAIL,
    INVALID_JSON_DETAIL,
    CollaborationManager,
    manager,
)
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient

client = TestClient(app_main.app)

WS_URL = "/collaboration/ws/resilience-room?name=Alice"


def setup_function():
    manager.reset()


def _join(websocket):
    """Consume the session_state and presence_update sent on join."""
    state = websocket.receive_json()
    websocket.receive_json()
    return state


def _assert_still_usable(websocket):
    websocket.send_json({"type": "ping"})
    assert websocket.receive_json() == {"type": "pong"}


class FakeSocket:
    """Minimal stand-in for a WebSocket that can be killed mid-session."""

    def __init__(self, error=None):
        self.error = error
        self.sent = []

    async def accept(self):
        return None

    async def send_json(self, message):
        if self.error is not None:
            raise self.error
        self.sent.append(message)

    def types(self):
        return [m["type"] for m in self.sent]


def test_invalid_json_frame_gets_error_and_keeps_connection():
    with client.websocket_connect(WS_URL) as websocket:
        _join(websocket)

        websocket.send_text("{not json")

        assert websocket.receive_json() == {
            "type": "error",
            "detail": INVALID_JSON_DETAIL,
        }
        _assert_still_usable(websocket)


def test_binary_frame_gets_error_and_keeps_connection():
    with client.websocket_connect(WS_URL) as websocket:
        _join(websocket)

        websocket.send_bytes(b"\x00\x01\x02")

        assert websocket.receive_json() == {
            "type": "error",
            "detail": INVALID_JSON_DETAIL,
        }
        _assert_still_usable(websocket)


def test_bad_frame_does_not_disturb_other_clients():
    with client.websocket_connect(WS_URL) as alice:
        _join(alice)
        with client.websocket_connect(
            "/collaboration/ws/resilience-room?name=Bob"
        ) as bob:
            bob.receive_json()  # session_state
            alice.receive_json()  # presence after Bob joined
            bob.receive_json()  # Bob presence

            bob.send_text("garbage")
            assert bob.receive_json()["detail"] == INVALID_JSON_DETAIL

            # Bob is still in the room and still gets Alice's edits.
            alice.send_json({"type": "code_update", "code": "x = 1", "version": 0})
            assert alice.receive_json()["type"] == "code_update"
            assert bob.receive_json()["code"] == "x = 1"


def test_handler_crash_returns_generic_error_and_logs(monkeypatch, caplog):
    async def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail /srv/app/db.sqlite")

    monkeypatch.setattr(manager, "_handle_cursor_update", boom)

    with caplog.at_level(logging.ERROR, logger="app.routers.collaboration"):
        with client.websocket_connect(WS_URL) as websocket:
            state = _join(websocket)

            websocket.send_json({"type": "cursor_update", "cursor": {"line": 1}})
            reply = websocket.receive_json()

            assert reply == {"type": "error", "detail": INTERNAL_ERROR_DETAIL}
            assert "secret" not in str(reply)
            _assert_still_usable(websocket)

    record = next(r for r in caplog.records if "handler failed" in r.getMessage())
    assert "resilience-room" in record.getMessage()
    assert state["clientId"] in record.getMessage()
    assert record.exc_info is not None  # full traceback stays in the log


def test_handler_crash_does_not_end_the_session(monkeypatch):
    calls = {"n": 0}
    original = manager._handle_comment_added

    async def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("first one fails")
        await original(*args, **kwargs)

    monkeypatch.setattr(manager, "_handle_comment_added", flaky)

    with client.websocket_connect(WS_URL) as websocket:
        _join(websocket)

        websocket.send_json({"type": "comment_added", "text": "one", "line": 1})
        assert websocket.receive_json()["detail"] == INTERNAL_ERROR_DETAIL

        websocket.send_json({"type": "comment_added", "text": "two", "line": 1})
        update = websocket.receive_json()
        assert update["type"] == "comment_added"
        assert update["comment"]["text"] == "two"


def test_dead_sender_socket_ends_loop_and_cleans_room(monkeypatch):
    """If even the error reply cannot be sent, the client is released."""

    async def boom(*args, **kwargs):
        raise RuntimeError("handler failed")

    monkeypatch.setattr(manager, "_handle_cursor_update", boom)

    real_send_json = WebSocket.send_json

    async def send_json_failing_on_errors(self, data, mode="text"):
        if isinstance(data, dict) and data.get("type") == "error":
            raise OSError("peer is gone")
        await real_send_json(self, data, mode)

    monkeypatch.setattr(WebSocket, "send_json", send_json_failing_on_errors)

    with client.websocket_connect(WS_URL) as websocket:
        _join(websocket)
        websocket.send_json({"type": "cursor_update", "cursor": {"line": 1}})
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_json()

    assert manager.rooms == {}


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("Cannot call send once a close message has been sent"),
        OSError("broken pipe"),
        ConnectionResetError("reset by peer"),
        WebSocketDisconnect(1006),
    ],
    ids=["RuntimeError", "OSError", "ConnectionResetError", "WebSocketDisconnect"],
)
def test_broadcast_drops_dead_socket_whatever_the_error(error, caplog):
    async def scenario():
        mgr = CollaborationManager()
        alive_a, dead, alive_b = FakeSocket(), FakeSocket(), FakeSocket()
        ids = [
            await mgr.connect("room-x", alive_a, "A"),
            await mgr.connect("room-x", dead, "Dead"),
            await mgr.connect("room-x", alive_b, "B"),
        ]
        for socket in (alive_a, dead, alive_b):
            socket.sent.clear()

        dead.error = error
        await mgr.broadcast("room-x", {"type": "code_update", "code": "hi"})
        return mgr, ids, alive_a, alive_b

    with caplog.at_level(logging.WARNING, logger="app.routers.collaboration"):
        mgr, ids, alive_a, alive_b = asyncio.run(scenario())

    room = mgr.rooms["room-x"]
    assert set(room.sockets) == {ids[0], ids[2]}
    assert set(room.users) == {ids[0], ids[2]}

    # Both survivors got the message, then a presence update without the ghost.
    for socket in (alive_a, alive_b):
        assert socket.sent[0] == {"type": "code_update", "code": "hi"}
        assert socket.sent[-1]["type"] == "presence_update"
        assert {u["name"] for u in socket.sent[-1]["users"]} == {"A", "B"}

    warning = next(r for r in caplog.records if "dropping dead" in r.getMessage())
    assert "room-x" in warning.getMessage()
    assert ids[1] in warning.getMessage()


def test_broadcast_to_only_dead_sockets_removes_the_room():
    async def scenario():
        mgr = CollaborationManager()
        only = FakeSocket()
        await mgr.connect("lonely", only, "Solo")
        only.error = OSError("gone")
        await mgr.broadcast("lonely", {"type": "code_update"})
        return mgr

    mgr = asyncio.run(scenario())

    assert "lonely" not in mgr.rooms


def test_reconnect_with_same_name_drops_the_ghost_entry():
    """A half-open old socket must not break or linger after a reconnect."""

    async def scenario():
        mgr = CollaborationManager()
        old = FakeSocket()
        old_id = await mgr.connect("rejoin", old, "Alice")
        old.error = OSError("connection reset")  # the tab died, no close frame

        new = FakeSocket()
        new_id = await mgr.connect("rejoin", new, "Alice")
        return mgr, old_id, new_id, new

    mgr, old_id, new_id, new = asyncio.run(scenario())

    room = mgr.rooms["rejoin"]
    assert new_id != old_id
    assert list(room.users) == [new_id]
    assert list(room.sockets) == [new_id]
    assert new.types()[0] == "session_state"
    assert new.sent[-1]["type"] == "presence_update"
    assert [u["name"] for u in new.sent[-1]["users"]] == ["Alice"]


def test_reconnect_over_live_socket_keeps_both_until_one_dies():
    """Same name is not treated as the same person while both sockets are up."""
    with client.websocket_connect("/collaboration/ws/rejoin-live?name=Sam") as first:
        _join(first)
        with client.websocket_connect(
            "/collaboration/ws/rejoin-live?name=Sam"
        ) as second:
            second.receive_json()
            presence = first.receive_json()
            assert [u["name"] for u in presence["users"]] == ["Sam", "Sam"]

        # Second one left, first gets the shrunken presence and keeps working.
        assert [u["name"] for u in first.receive_json()["users"]] == ["Sam"]
        _assert_still_usable(first)
