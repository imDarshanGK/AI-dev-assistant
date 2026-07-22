"""Real-time collaboration router for live analysis sessions."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from ..observability import (
    record_collab_connect,
    record_collab_disconnect,
    record_collab_error,
    record_collab_message,
)

router = APIRouter()

logger = logging.getLogger(__name__)

MAX_CODE_CHARS = 50_000
MAX_COMMENT_CHARS = 1_000
MAX_SESSION_ID_CHARS = 128

COLORS = [
    "#5b9cf6",
    "#7c3aed",
    "#22d47b",
    "#f5c842",
    "#f5923e",
    "#f25757",
]


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

    def _get_room_if_exists(self, session_id: str) -> CollaborationRoom | None:
        """Return the room only if it already exists, without creating a phantom room."""
        return self.rooms.get(session_id)

    def _users_payload(self, room: CollaborationRoom) -> list[dict[str, Any]]:
        return list(room.users.values())

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
            users = self._users_payload(room)

        logger.info(
            "client_connected session_id=%s client_id=%s active_users=%d",
            session_id,
            client_id,
            len(users),
        )
        record_collab_connect(session_id)

        await websocket.send_json(state)
        await self.broadcast(
            session_id,
            {"type": "presence_update", "users": users},
        )
        return client_id

    async def disconnect(self, session_id: str, client_id: str) -> None:
        room = self.rooms.get(session_id)
        if room is None:
            return

        async with room.lock:
            room.sockets.pop(client_id, None)
            room.users.pop(client_id, None)
            users = self._users_payload(room)
            should_delete = not room.sockets

        logger.info(
            "client_disconnected session_id=%s client_id=%s remaining_users=%d",
            session_id,
            client_id,
            len(users),
        )
        record_collab_disconnect(session_id)

        if should_delete:
            self.rooms.pop(session_id, None)
            logger.info("session_closed session_id=%s reason=last_client_left", session_id)
            return

        await self.broadcast(
            session_id,
            {"type": "presence_update", "users": users},
        )

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
            except Exception:
                # Any send failure (RuntimeError from a closed socket,
                # WebSocketDisconnect, etc.) marks the client as stale so it
                # is cleaned up without crashing the rest of the broadcast.
                logger.warning(
                    "stale_socket_detected session_id=%s client_id=%s",
                    session_id,
                    client_id,
                )
                record_collab_error(session_id, "stale_socket")
                stale_clients.append(client_id)

        for client_id in stale_clients:
            await self.disconnect(session_id, client_id)

    async def handle_message(
        self,
        session_id: str,
        client_id: str,
        data: dict[str, Any],
    ) -> None:
        # Guard: if the room was already destroyed (e.g. last client left
        # concurrently), do not silently recreate a phantom room.
        room = self._get_room_if_exists(session_id)
        if room is None:
            logger.warning(
                "message_for_missing_room session_id=%s client_id=%s",
                session_id,
                client_id,
            )
            return

        message_type = data.get("type")

        if message_type == "ping":
            socket = room.sockets.get(client_id)
            if socket is not None:
                await socket.send_json({"type": "pong"})
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

        logger.warning(
            "unsupported_message_type session_id=%s client_id=%s message_type=%s",
            session_id,
            client_id,
            message_type,
        )
        record_collab_error(session_id, "unsupported_message_type")
        socket = room.sockets.get(client_id)
        if socket is not None:
            await socket.send_json(
                {
                    "type": "error",
                    "detail": f"Unsupported collaboration message type: {message_type}",
                }
            )

    async def _handle_code_update(
        self,
        session_id: str,
        client_id: str,
        data: dict[str, Any],
    ) -> None:
        room = self._get_room_if_exists(session_id)
        if room is None:
            return

        socket = room.sockets.get(client_id)
        code = data.get("code", "")
        language = data.get("language")

        # Safely coerce version — reject non-numeric values rather than crash.
        raw_version = data.get("version", 0)
        try:
            incoming_version = int(raw_version)
        except (TypeError, ValueError):
            logger.warning(
                "invalid_version_field session_id=%s client_id=%s reason=non_integer_version",
                session_id,
                client_id,
            )
            record_collab_error(session_id, "non_integer_version")
            if socket is not None:
                await socket.send_json(
                    {"type": "error", "detail": "version must be an integer"}
                )
            return

        if not isinstance(code, str):
            logger.warning(
                "code_update_rejected session_id=%s client_id=%s reason=invalid_code_type",
                session_id,
                client_id,
            )
            record_collab_error(session_id, "invalid_code_type")
            if socket is not None:
                await socket.send_json(
                    {"type": "error", "detail": "code must be a string"}
                )
            return

        if len(code) > MAX_CODE_CHARS:
            logger.warning(
                "code_update_rejected session_id=%s client_id=%s reason=code_too_long length=%d",
                session_id,
                client_id,
                len(code),
            )
            record_collab_error(session_id, "code_too_long")
            if socket is not None:
                await socket.send_json(
                    {
                        "type": "error",
                        "detail": f"code exceeds {MAX_CODE_CHARS} characters",
                    }
                )
            return

        async with room.lock:
            if incoming_version < room.version:
                state = self._state_payload(session_id, room, client_id)
                state["type"] = "sync_required"
                latest_socket = room.sockets.get(client_id)
                logger.debug(
                    "sync_required session_id=%s client_id=%s incoming_version=%d room_version=%d",
                    session_id,
                    client_id,
                    incoming_version,
                    room.version,
                )
            else:
                room.version += 1
                room.code = code
                room.language = language if isinstance(language, str) else room.language
                payload = {
                    "type": "code_update",
                    "code": room.code,
                    "language": room.language,
                    "version": room.version,
                    "senderId": client_id,
                }
                latest_socket = None
                state = payload
                logger.debug(
                    "code_update session_id=%s client_id=%s version=%d code_length=%d",
                    session_id,
                    client_id,
                    room.version,
                    len(code),
                )
                record_collab_message(session_id, "code_update")

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
        room = self._get_room_if_exists(session_id)
        if room is None:
            return

        raw_cursor = data.get("cursor")

        if not isinstance(raw_cursor, dict):
            return

        # Safely coerce cursor fields — non-integer values must not crash.
        try:
            cursor = {
                "line": max(1, int(raw_cursor.get("line", 1))),
                "column": max(1, int(raw_cursor.get("column", 1))),
                "selectionStart": max(0, int(raw_cursor.get("selectionStart", 0))),
                "selectionEnd": max(0, int(raw_cursor.get("selectionEnd", 0))),
            }
        except (TypeError, ValueError):
            logger.warning(
                "cursor_update_rejected session_id=%s client_id=%s reason=non_integer_cursor_field",
                session_id,
                client_id,
            )
            record_collab_error(session_id, "non_integer_cursor_field")
            socket = room.sockets.get(client_id)
            if socket is not None:
                await socket.send_json(
                    {"type": "error", "detail": "cursor fields must be integers"}
                )
            return

        async with room.lock:
            user = room.users.get(client_id)
            if user is None:
                return
            user["cursor"] = cursor
            payload = {
                "type": "cursor_update",
                "user": user,
            }
            logger.debug(
                "cursor_update session_id=%s client_id=%s line=%d column=%d",
                session_id,
                client_id,
                cursor["line"],
                cursor["column"],
            )
            record_collab_message(session_id, "cursor_update")

        await self.broadcast(session_id, payload, exclude=client_id)

    async def _handle_comment_added(
        self,
        session_id: str,
        client_id: str,
        data: dict[str, Any],
    ) -> None:
        room = self._get_room_if_exists(session_id)
        if room is None:
            return

        text = str(data.get("text", "")).strip()

        # Safely coerce line number.
        raw_line = data.get("line", 1)
        try:
            line = max(1, int(raw_line))
        except (TypeError, ValueError):
            line = 1

        socket = room.sockets.get(client_id)

        if not text:
            logger.warning(
                "comment_rejected session_id=%s client_id=%s reason=empty_comment_text",
                session_id,
                client_id,
            )
            record_collab_error(session_id, "empty_comment_text")
            if socket is not None:
                await socket.send_json(
                    {"type": "error", "detail": "comment text is required"}
                )
            return

        if len(text) > MAX_COMMENT_CHARS:
            logger.warning(
                "comment_rejected session_id=%s client_id=%s reason=comment_too_long length=%d",
                session_id,
                client_id,
                len(text),
            )
            record_collab_error(session_id, "comment_too_long")
            if socket is not None:
                await socket.send_json(
                    {
                        "type": "error",
                        "detail": f"comment exceeds {MAX_COMMENT_CHARS} characters",
                    }
                )
            return

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
            logger.info(
                "comment_added session_id=%s client_id=%s comment_id=%s line=%d",
                session_id,
                client_id,
                comment["id"],
                line,
            )
            record_collab_message(session_id, "comment_added")

        await self.broadcast(session_id, payload)


manager = CollaborationManager()


@router.websocket("/ws/{session_id}")
async def collaboration_websocket(
    websocket: WebSocket,
    session_id: str,
    name: str = Query(default="Anonymous", max_length=40),
) -> None:
    # Validate session_id before accepting the connection.
    if not session_id or not session_id.strip() or len(session_id) > MAX_SESSION_ID_CHARS:
        await websocket.close(code=1008, reason="invalid session_id")
        return

    client_id = await manager.connect(session_id, websocket, name)

    try:
        while True:
            try:
                data = await websocket.receive_json()
            except ValueError:
                # Malformed JSON from the client — send an error and keep the
                # connection alive rather than crashing the handler loop.
                logger.warning(
                    "non_json_message session_id=%s client_id=%s reason=malformed_json",
                    session_id,
                    client_id,
                )
                record_collab_error(session_id, "malformed_json")
                try:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "detail": "message must be valid JSON",
                        }
                    )
                except Exception:
                    pass
                continue

            if isinstance(data, dict):
                await manager.handle_message(session_id, client_id, data)
            else:
                logger.warning(
                    "non_object_payload session_id=%s client_id=%s reason=non_object_payload",
                    session_id,
                    client_id,
                )
                record_collab_error(session_id, "non_object_payload")
                await websocket.send_json(
                    {"type": "error", "detail": "message payload must be a JSON object"}
                )
    except WebSocketDisconnect:
        await manager.disconnect(session_id, client_id)
