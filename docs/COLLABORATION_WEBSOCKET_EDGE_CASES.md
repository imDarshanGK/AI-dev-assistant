# Collaboration WebSocket — Edge Case Reference

This document maps every known edge case in the real-time collaboration WebSocket to the exact code that handles it. It is intended for client implementors and contributors extending the feature.

**Route:** `WS /collaboration/ws/{session_id}?name=<display_name>`  
**Source:** [`backend/app/routers/collaboration.py`](../backend/app/routers/collaboration.py)

---

## Protocol

The real-time collaboration module uses WebSockets to connect multiple clients to a single session identified by the `session_id` URL parameter. A global `CollaborationManager` instance controls `CollaborationRoom` objects representing individual sessions.

Each message sent over the socket must be a **JSON object** (`{}`). JSON arrays or primitives are rejected. On connection, the server immediately sends a `session_state` welcome packet containing the current code, version number, comments, and active users.

---

## Message Types

| Type | Direction | Description |
|---|---|---|
| `session_state` | Server → Client | Sent on connect. Full snapshot of current room state. |
| `presence_update` | Server → All | Broadcast when any user joins or leaves. |
| `ping` | Client → Server | Keepalive heartbeat. |
| `pong` | Server → Client | Response to `ping`. |
| `code_update` | Client → Server | Submit a code change with a version number. |
| `code_update` | Server → All | Broadcast confirmed code change to all clients. |
| `sync_required` | Server → Client | Sent when an incoming `code_update` is stale (version conflict). |
| `cursor_update` | Client → Server | Submit cursor/selection position. |
| `cursor_update` | Server → Others | Broadcast cursor position to all clients **except** the sender. |
| `comment_added` | Client → Server | Submit a new comment on a line. |
| `comment_added` | Server → All | Broadcast the new comment and full comment list to all clients. |
| `error` | Server → Client | Sent when the server rejects a message. See [Error Responses](#error-responses-reference). |

---

## Edge Cases by Category

### Connection & Presence Edge Cases

- **Two users join simultaneously**
  - *Behavior:* Protected by `async with room.lock` inside `connect()`. The per-room asyncio lock serialises connection handling, ensuring color assignment and presence list updates are race-condition-free.
  - *Note:* The lock is **per-room**, not global. Concurrent connections to *different* sessions do not block each other.

- **User joins with an empty or whitespace-only name**
  - *Behavior:* The `name` query parameter is sanitised as `safe_name = (user_name or "Anonymous").strip()[:40] or "Anonymous"`. An empty string, whitespace-only string, or missing parameter all resolve to `"Anonymous"`. Names are also hard-capped at 40 characters.

- **User joins a session that does not exist yet**
  - *Behavior:* Rooms are lazily created. `_get_room(session_id)` allocates a fresh `CollaborationRoom` on first access. There is no separate "create session" step.

- **Last user disconnects**
  - *Behavior:* `disconnect()` checks `should_delete = not room.sockets` after removing the client. If the room is now empty, the entire `CollaborationRoom` object is deleted from memory.
  - ⚠️ **All session state (code, version, comments) is ephemeral and in-memory only.** When all users leave, the state is permanently lost. There is no persistence layer.

---

### Message & Protocol Edge Cases

- **Unknown `type` field sent**
  - *Behavior:* Falls through all `if message_type ==` branches in `handle_message()`. The server responds with: `{"type": "error", "detail": "Unsupported collaboration message type: <type>"}`. The connection is kept open.
  - *Client guidance:* Only send types listed in the [Message Types](#message-types) table above.

- **Non-dict payload (e.g. a JSON array or string)**
  - *Behavior:* The route's `while True` loop checks `if isinstance(data, dict)`. If not, the server responds with: `{"type": "error", "detail": "message payload must be a JSON object"}`. The connection is kept open.

- **Code field is exactly at the character limit vs. one over**
  - *Behavior:* `MAX_CODE_CHARS = 50_000`. A payload with exactly 50,000 characters is accepted. A payload with 50,001 characters is rejected with: `{"type": "error", "detail": "code exceeds 50000 characters"}`.

- **Code field is not a string**
  - *Behavior:* If the `code` value in a `code_update` is not a `str` (e.g. a number or array), the server responds with: `{"type": "error", "detail": "code must be a string"}`.

- **Empty comment text (after stripping whitespace)**
  - *Behavior:* `text = str(data.get("text", "")).strip()`. If the result is an empty string, the server responds with: `{"type": "error", "detail": "comment text is required"}`. Whitespace-only comments are also rejected.

- **Comment text exactly at the character limit vs. one over**
  - *Behavior:* `MAX_COMMENT_CHARS = 1_000`. A comment of exactly 1,000 characters is accepted. A comment of 1,001 characters is rejected with: `{"type": "error", "detail": "comment exceeds 1000 characters"}`.

- **Cursor update with a non-dict cursor value**
  - *Behavior:* `_handle_cursor_update()` checks `if not isinstance(raw_cursor, dict): return`. The update is **silently dropped** — no error is sent back to the client.
  - *Note:* This silent failure can mask client-side bugs. Monitor for missing cursor broadcasts as a symptom.

---

### Concurrency & State Edge Cases

- **Stale code update (version conflict)**
  - *Behavior:* Every `code_update` must include the client's current `version` integer. If `incoming_version < room.version`, the update is **rejected without applying**. The server responds with a `sync_required` message containing the full current state (`code`, `version`, `comments`, `users`).
  - *Client guidance:* On receiving `sync_required`, the client must discard its pending local change and re-apply it on top of the received state.

- **Broadcast to a client that has already disconnected (stale socket)**
  - *Behavior:* `broadcast()` catches `RuntimeError` when `socket.send_json()` fails on a dead connection. The stale `client_id` is batched into `stale_clients` and `disconnect()` is called for each one *after* the broadcast loop completes. This prevents mid-loop mutation of the sockets dictionary.

- **Cursor update for a `client_id` not in `room.users`**
  - *Behavior:* `_handle_cursor_update()` checks `if user is None: return` after looking up the client in `room.users`. The update is silently ignored and not broadcast.

---

### Security & Validation Edge Cases

- **`session_id` with special characters**
  - *Behavior:* The route parameter `session_id: str` has no regex or length constraint. Any URL-safe string is accepted as a session identifier.
  - ⚠️ **Known gap:** There is no validation preventing extremely long `session_id` values or path traversal attempts. Consider adding a `Path(..., max_length=128, regex="^[a-zA-Z0-9_-]+$")` constraint.

- **Cursor values that are negative or zero**
  - *Behavior:* Coordinates are sanitised on arrival:
    - `line` and `column` → `max(1, int(value))` — clamped to a minimum of 1
    - `selectionStart` and `selectionEnd` → `max(0, int(value))` — clamped to a minimum of 0
  - Negative or zero inputs are silently clamped; no error is returned to the sender.

---

## Error Responses Reference

All error messages from the server share the same structure:

```json
{"type": "error", "detail": "<reason>"}
```

| Trigger | `detail` value |
|---|---|
| Non-dict JSON payload | `"message payload must be a JSON object"` |
| Unrecognised message type | `"Unsupported collaboration message type: {type}"` |
| `code` is not a string | `"code must be a string"` |
| `code` exceeds limit | `"code exceeds 50000 characters"` |
| Comment text is empty | `"comment text is required"` |
| Comment exceeds limit | `"comment exceeds 1000 characters"` |

---

## Known Limitations

| Limitation | Detail |
|---|---|
| **No state persistence** | All room state lives in process memory. A server restart or last-user-disconnect wipes all code and comments with no recovery path. |
| **No authentication** | Any client that knows a `session_id` can join. There is no token or permission check on the WebSocket handshake. |
| **No `session_id` validation** | The session identifier has no length or character-set constraints at the route level. |
| **Silent cursor failures** | Invalid cursor payloads fail silently, which can disguise client-side bugs. |
| **Single-process only** | The `CollaborationManager` is an in-process dictionary. Running multiple server workers (e.g. with Gunicorn) will produce isolated rooms per worker, breaking multi-user sync. |
