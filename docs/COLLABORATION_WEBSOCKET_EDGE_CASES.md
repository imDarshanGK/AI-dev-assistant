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
  - *Behavior:* Falls through all `if message_type ==` branches in `handle_message()`. The server responds with: `{"type": "error", "detail": "Unsupported collaboration message type: <type>"}`. The connection is kept open. A missing `type`, or one that is not a string (for example a list), gets the same response.
  - *Client guidance:* Only send types listed in the [Message Types](#message-types) table above.

- **Non-dict payload (e.g. a JSON array or string)**
  - *Behavior:* The route's `while True` loop checks `if isinstance(data, dict)`. If not, the server responds with: `{"type": "error", "detail": "message payload must be a JSON object"}`. The connection is kept open.

- **Code field is exactly at the character limit vs. one over**
  - *Behavior:* `MAX_CODE_CHARS = 50_000`. A payload with exactly 50,000 characters is accepted. A payload with 50,001 characters is rejected with: `{"type": "error", "detail": "code exceeds 50000 characters"}`.

- **Code field is missing or not a string**
  - *Behavior:* `code` is required in a `code_update`. If it is missing the server responds with `{"type": "error", "detail": "code is required"}`; if it is not a `str` (e.g. a number or array) the response is `{"type": "error", "detail": "code must be a string"}`. An empty string is valid.

- **Bad `version` or `language` on a code update**
  - *Behavior:* `version` is optional (defaults to `0`) but must be a non-negative integer, otherwise the server responds with `"version must be an integer"` or `"version must not be negative"`. `language` is optional but must be a string of at most `MAX_LANGUAGE_CHARS = 32` characters. The room is not touched and the connection is kept open.

- **Empty comment text (after stripping whitespace)**
  - *Behavior:* The text is stripped. If it is missing, `null` or empty after stripping, the server responds with: `{"type": "error", "detail": "comment text is required"}`. Whitespace-only comments are also rejected. A text value that is not a string gets `"comment text must be a string"`.

- **Comment text exactly at the character limit vs. one over**
  - *Behavior:* `MAX_COMMENT_CHARS = 1_000`. A comment of exactly 1,000 characters is accepted. A comment of 1,001 characters is rejected with: `{"type": "error", "detail": "comment exceeds 1000 characters"}`.

- **Cursor update with a non-dict cursor value**
  - *Behavior:* The `cursor` field must be an object. Otherwise the server responds with `{"type": "error", "detail": "cursor must be an object"}` and nothing is broadcast. A cursor field (`line`, `column`, `selectionStart`, `selectionEnd`) that is not a number gets `"cursor.<field> must be an integer"`, and one with an absolute value above `MAX_CURSOR_VALUE = 1_000_000` gets `"cursor.<field> is out of range"`. The same rules apply to the `line` of a comment.

---

### Concurrency & State Edge Cases

- **Stale code update (version conflict)**
  - *Behavior:* Every `code_update` must include the client's current `version` integer. If `incoming_version < room.version`, the update is **rejected without applying**. The server responds with a `sync_required` message containing the full current state (`code`, `version`, `comments`, `users`).
  - *Client guidance:* On receiving `sync_required`, the client must discard its pending local change and re-apply it on top of the received state.

- **Broadcast to a client that has already disconnected (stale socket)**
  - *Behavior:* `broadcast()` catches `RuntimeError` when `socket.send_json()` fails on a dead connection. The stale `client_id` is batched into `stale_clients` and `disconnect()` is called for each one *after* the broadcast loop completes. This prevents mid-loop mutation of the sockets dictionary.
  - *Lifecycle:* A message that arrives from a client that is no longer in the room (for example one that `broadcast()` already dropped) is ignored, and it does not recreate the removed room. In the route, `disconnect()` always runs in a `finally` block, so an unexpected error in the receive loop cannot leave a dead socket registered. If sending the initial `session_state` fails, the half-joined client is removed again.

- **Cursor update for a `client_id` not in `room.users`**
  - *Behavior:* `handle_message()` ignores messages from clients that are not registered in the room, and `_handle_cursor_update()` still checks `if user is None: return`. The update is silently ignored and not broadcast.

---

### Security & Validation Edge Cases

- **`session_id` with special characters**
  - *Behavior:* The route parameter `session_id: str` has no regex or length constraint. Any URL-safe string is accepted as a session identifier.
  - ⚠️ **Known gap:** There is no validation preventing extremely long `session_id` values or path traversal attempts. Consider adding a `Path(..., max_length=128, regex="^[a-zA-Z0-9_-]+$")` constraint.

- **Cursor values that are negative or zero**
  - *Behavior:* Coordinates are sanitised on arrival:
    - `line` and `column` → `max(1, int(value))` — clamped to a minimum of 1
    - `selectionStart` and `selectionEnd` → `max(0, int(value))` — clamped to a minimum of 0
  - Negative or zero numeric inputs are silently clamped; no error is returned to the sender. Non-numeric values are rejected, see above.

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
| `code` is missing | `"code is required"` |
| `code` is not a string | `"code must be a string"` |
| `code` exceeds limit | `"code exceeds 50000 characters"` |
| `version` is not an integer | `"version must be an integer"` |
| `version` is negative | `"version must not be negative"` |
| `language` is not a string | `"language must be a string"` |
| `language` exceeds limit | `"language exceeds 32 characters"` |
| `cursor` is not an object | `"cursor must be an object"` |
| Cursor field or comment `line` is not a number | `"cursor.<field> must be an integer"` / `"line must be an integer"` |
| Cursor field or comment `line` is huge | `"cursor.<field> is out of range"` / `"line is out of range"` |
| Comment text is empty | `"comment text is required"` |
| Comment text is not a string | `"comment text must be a string"` |
| Comment exceeds limit | `"comment exceeds 1000 characters"` |

---

## Known Limitations

| Limitation | Detail |
|---|---|
| **No state persistence** | All room state lives in process memory. A server restart or last-user-disconnect wipes all code and comments with no recovery path. |
| **No authentication** | Any client that knows a `session_id` can join. There is no token or permission check on the WebSocket handshake. |
| **No `session_id` validation** | The session identifier has no length or character-set constraints at the route level. |
| **Single-process only** | The `CollaborationManager` is an in-process dictionary. Running multiple server workers (e.g. with Gunicorn) will produce isolated rooms per worker, breaking multi-user sync. |
