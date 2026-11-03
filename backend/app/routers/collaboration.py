"""Real-time collaboration router for live analysis sessions."""

from __future__ import annotations

import asyncio
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

router = APIRouter()

MAX_CODE_CHARS = 50_000
MAX_COMMENT_CHARS = 1_000
MAX_LANGUAGE_CHARS = 32
MAX_CURSOR_VALUE = 1_000_000

COLORS = [
    "#5b9cf6",
    "#7c3aed",
    "#22d47b",
    "#f5c842",
    "#f5923e",
    "#f25757",
]


class MessageValidationError(ValueError):
    """Raised when a client message has missing or malformed fields."""


def _as_int(value: Any, field_name: str) -> int:
    """Return value as an int, rejecting bools, NaN/inf and non-numbers."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MessageValidationError(f"{field_name} must be an integer")
    if isinstance(value, float) and not math.isfinite(value):
        raise MessageValidationError(f"{field_name} must be an integer")
    number = int(value)
    if abs(number) > MAX_CURSOR_VALUE:
        raise MessageValidationError(f"{field_name} is out of range")
    return number


def _validate_code_update(data: dict[str, Any]) -> dict[str, Any]:
    if "code" not in data:
        raise MessageValidationError("code is required")

    code = data["code"]
    if not isinstance(code, str):
        raise MessageValidationError("code must be a string")
    if len(code) > MAX_CODE_CHARS:
        raise MessageValidationError(f"code exceeds {MAX_CODE_CHARS} characters")

    language = data.get("language")
    if language is not None:
        if not isinstance(language, str):
            raise MessageValidationError("language must be a string")
        if len(language) > MAX_LANGUAGE_CHARS:
            raise MessageValidationError(
                f"language exceeds {MAX_LANGUAGE_CHARS} characters"
            )

    version = _as_int(data.get("version", 0), "version")
    if version < 0:
        raise MessageValidationError("version must not be negative")

    return {"code": code, "language": language, "version": version}


def _validate_cursor_update(data: dict[str, Any]) -> dict[str, Any]:
    raw_cursor = data.get("cursor")
    if not isinstance(raw_cursor, dict):
        raise MessageValidationError("cursor must be an object")

    return {
        "cursor": {
            "line": max(1, _as_int(raw_cursor.get("line", 1), "cursor.line")),
            "column": max(1, _as_int(raw_cursor.get("column", 1), "cursor.column")),
            "selectionStart": max(
                0,
                _as_int(raw_cursor.get("selectionStart", 0), "cursor.selectionStart"),
            ),
            "selectionEnd": max(
                0,
                _as_int(raw_cursor.get("selectionEnd", 0), "cursor.selectionEnd"),
            ),
        }
    }


def _validate_comment_added(data: dict[str, Any]) -> dict[str, Any]:
    raw_text = data.get("text")
    if raw_text is not None and not isinstance(raw_text, str):
        raise MessageValidationError("comment text must be a string")

    text = (raw_text or "").strip()
    if not text:
        raise MessageValidationError("comment text is required")
    if len(text) > MAX_COMMENT_CHARS:
        raise MessageValidationError(f"comment exceeds {MAX_COMMENT_CHARS} characters")

    line = max(1, _as_int(data.get("line", 1), "line"))

    return {"text": text, "line": line}


# Message types that carry fields and need validating before dispatch.
MESSAGE_VALIDATORS = {
    "code_update": _validate_code_update,
    "cursor_update": _validate_cursor_update,
    "comment_added": _validate_comment_added,
}


@dataclass
class CollaborationRoom:
    code: str = ""
    language: str | None = None
    version: int = 0
    comments: list[dict[str, Any]] = field(default_factory=list)
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    sockets: dict[str, WebSocket] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class CollaborationManager:
    def __init__(self) -> None:
        self.rooms: dict[str, CollaborationRoom] = {}

    def reset(self) -> None:
        self.rooms.clear()

    def _get_room(self, session_id: str) -> CollaborationRoom:
        if session_id not in self.rooms:
            self.rooms[session_id] = CollaborationRoom()
        return self.rooms[session_id]

    def _users_payload(self, room: CollaborationRoom) -> list[dict[str, Any]]:
        return list(room.users.values())

    async def _send_error(
        self,
        room: CollaborationRoom,
        client_id: str,
        detail: str,
    ) -> None:
        """Send an error message to a collaboration client if connected."""
        socket = room.sockets.get(client_id)
        if socket is not None:
            await socket.send_json(
                {
                    "type": "error",
                    "detail": detail,
                }
            )

    def _state_payload(
        self,
        session_id: str,
        room: CollaborationRoom,
        client_id: str,
    ) -> dict[str, Any]:
        return {
            "type": "session_state",
            "sessionId": session_id,
            "clientId": client_id,
            "code": room.code,
            "language": room.language,
            "version": room.version,
            "comments": room.comments,
            "users": self._users_payload(room),
        }

    async def _broadcast_presence(
        self, session_id: str, room: CollaborationRoom
    ) -> None:
        users = self._users_payload(room)
        await self.broadcast(
            session_id,
            {"type": "presence_update", "users": users},
        )

    async def connect(
        self,
        session_id: str,
        websocket: WebSocket,
        user_name: str,
    ) -> str:
        await websocket.accept()

        room = self._get_room(session_id)
        client_id = uuid.uuid4().hex[:10]
        safe_name = (user_name or "Anonymous").strip()[:40] or "Anonymous"

        async with room.lock:
            color = COLORS[len(room.users) % len(COLORS)]
            room.sockets[client_id] = websocket
            room.users[client_id] = {
                "id": client_id,
                "name": safe_name,
                "color": color,
                "cursor": None,
                "joinedAt": datetime.now(timezone.utc).isoformat(),
            }
            state = self._state_payload(session_id, room, client_id)

        try:
            await websocket.send_json(state)
            await self._broadcast_presence(session_id, room)
        except BaseException:
            # The join did not finish, so do not leave a half-joined client behind.
            await self.disconnect(session_id, client_id)
            raise
        return client_id

    async def disconnect(self, session_id: str, client_id: str) -> None:
        room = self.rooms.get(session_id)
        if room is None:
            return

        async with room.lock:
            room.sockets.pop(client_id, None)
            room.users.pop(client_id, None)
            should_delete = not room.sockets

        if should_delete:
            self.rooms.pop(session_id, None)
            return

        await self._broadcast_presence(session_id, room)

    async def broadcast(
        self,
        session_id: str,
        message: dict[str, Any],
        exclude: str | None = None,
    ) -> None:
        room = self.rooms.get(session_id)
        if room is None:
            return

        stale_clients: list[str] = []

        for client_id, socket in list(room.sockets.items()):
            if exclude is not None and client_id == exclude:
                continue

            try:
                await socket.send_json(message)
            except RuntimeError:
                stale_clients.append(client_id)

        for client_id in stale_clients:
            await self.disconnect(session_id, client_id)

    async def handle_message(
        self,
        session_id: str,
        client_id: str,
        data: dict[str, Any],
    ) -> None:
        room = self.rooms.get(session_id)
        if room is None or client_id not in room.sockets:
            # The client already left (or was dropped); do not bring the room back.
            return

        message_type = data.get("type")

        if message_type == "ping":
            socket = room.sockets.get(client_id)
            if socket is not None:
                await socket.send_json({"type": "pong"})
            return

        validator = (
            MESSAGE_VALIDATORS.get(message_type)
            if isinstance(message_type, str)
            else None
        )
        if validator is not None:
            try:
                data = validator(data)
            except MessageValidationError as exc:
                await self._send_error(room, client_id, str(exc))
                return

        if message_type == "code_update":
            await self._handle_code_update(session_id, client_id, data)
            return

        if message_type == "cursor_update":
            await self._handle_cursor_update(session_id, client_id, data)
            return

        if message_type == "comment_added":
            await self._handle_comment_added(session_id, client_id, data)
            return

        await self._send_error(
            room,
            client_id,
            f"Unsupported collaboration message type: {message_type}",
        )

    async def _handle_code_update(
        self,
        session_id: str,
        client_id: str,
        data: dict[str, Any],
    ) -> None:
        room = self._get_room(session_id)
        code = data["code"]
        language = data["language"]
        incoming_version = data["version"]

        async with room.lock:
            if incoming_version < room.version:
                state = self._state_payload(session_id, room, client_id)
                state["type"] = "sync_required"
                latest_socket = room.sockets.get(client_id)
            else:
                room.version += 1
                room.code = code
                room.language = language if language is not None else room.language
                payload = {
                    "type": "code_update",
                    "code": room.code,
                    "language": room.language,
                    "version": room.version,
                    "senderId": client_id,
                }
                latest_socket = None
                state = payload

        if latest_socket is not None:
            await latest_socket.send_json(state)
            return

        await self.broadcast(session_id, state)

    async def _handle_cursor_update(
        self,
        session_id: str,
        client_id: str,
        data: dict[str, Any],
    ) -> None:
        room = self._get_room(session_id)
        cursor = data["cursor"]

        async with room.lock:
            user = room.users.get(client_id)
            if user is None:
                return
            user["cursor"] = cursor
            payload = {
                "type": "cursor_update",
                "user": user,
            }

        await self.broadcast(session_id, payload, exclude=client_id)

    async def _handle_comment_added(
        self,
        session_id: str,
        client_id: str,
        data: dict[str, Any],
    ) -> None:
        room = self._get_room(session_id)
        text = data["text"]
        line = data["line"]

        async with room.lock:
            user = room.users.get(client_id, {})
            comment = {
                "id": uuid.uuid4().hex[:12],
                "line": line,
                "text": text,
                "authorId": client_id,
                "author": user.get("name", "Anonymous"),
                "color": user.get("color", COLORS[0]),
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            room.comments.append(comment)
            payload = {
                "type": "comment_added",
                "comment": comment,
                "comments": room.comments,
            }

        await self.broadcast(session_id, payload)


manager = CollaborationManager()


@router.websocket("/ws/{session_id}")
async def collaboration_websocket(
    websocket: WebSocket,
    session_id: str,
    name: str = Query(default="Anonymous", max_length=40),
) -> None:
    client_id = await manager.connect(session_id, websocket, name)

    try:
        while True:
            data = await websocket.receive_json()
            if isinstance(data, dict):
                await manager.handle_message(session_id, client_id, data)
            else:
                await websocket.send_json(
                    {"type": "error", "detail": "message payload must be a JSON object"}
                )
    except WebSocketDisconnect:
        pass
    finally:
        # Always release the client, whatever ended the loop, so a crashed
        # handler cannot leave a dead socket (and its room) behind.
        await manager.disconnect(session_id, client_id)
