# Requirements Document

## Introduction

The presence sync subsystem in QyverixAI handles real-time collaborative editing over WebSocket connections. Currently, the `CollaborationManager` and its `CollaborationRoom` objects process connection lifecycle events, code updates, cursor movements, and comments with no structured logging, metrics, or error-visibility hooks. This feature adds observability to the presence sync flow — structured logs at key lifecycle points, Prometheus counters/gauges for WebSocket and collaboration events, and consistent error-event visibility — without altering any existing collaboration behaviour.

## Glossary

- **Collaboration_Router**: The FastAPI `APIRouter` defined in `routers/collaboration.py` that handles the `/ws/{session_id}` WebSocket endpoint.
- **Collaboration_Manager**: The `CollaborationManager` class that manages rooms, connections, message dispatch, and broadcasts.
- **Presence_Sync**: The process of tracking and broadcasting connected-user state (join, leave, cursor position) across all participants in a collaboration room.
- **Observability_Layer**: The set of structured log statements, Prometheus metrics counters/gauges, and error-visibility hooks added by this feature.
- **collaboration_logger**: The Python logger instance named `app.routers.collaboration` used exclusively by the Collaboration_Router and Collaboration_Manager.
- **Prometheus_Registry**: The `prometheus_client` default registry already used in `observability.py`.
- **Session**: A named collaboration room identified by a `session_id` string.
- **Client**: A single WebSocket connection within a Session, identified by a `client_id` string.

---

## Requirements

### Requirement 1: Structured Connection Lifecycle Logging

**User Story:** As an operator, I want structured log entries for every WebSocket connection and disconnection event, so that I can trace collaboration sessions and diagnose connectivity problems.

#### Acceptance Criteria

1. WHEN a Client connects to a Session, THE collaboration_logger SHALL emit an INFO-level log entry containing the `session_id`, `client_id`, and the current connected-user count for that Session.
2. WHEN a Client disconnects from a Session, THE collaboration_logger SHALL emit an INFO-level log entry containing the `session_id`, `client_id`, a disconnect reason field (either `"websocket_disconnect"` or `"stale_socket"`), and the remaining connected-user count for that Session.
3. WHEN a Session is destroyed because its last Client disconnects, THE collaboration_logger SHALL emit an INFO-level log entry containing the `session_id` and the reason `"session_closed"`.
4. THE collaboration_logger SHALL use the key-value format `key=value` consistently in all log messages to support log-aggregation queries.

### Requirement 2: Structured Message-Event Logging

**User Story:** As an operator, I want structured log entries for each collaboration message type handled, so that I can understand activity patterns and identify unusual message rates.

#### Acceptance Criteria

1. WHEN a `code_update` message is processed successfully, THE collaboration_logger SHALL emit a DEBUG-level log entry containing the `session_id`, `client_id`, the new `version`, and the code length in characters.
2. WHEN a `cursor_update` message is processed successfully, THE collaboration_logger SHALL emit a DEBUG-level log entry containing the `session_id`, `client_id`, and the cursor `line` and `column` values.
3. WHEN a `comment_added` message is processed successfully, THE collaboration_logger SHALL emit an INFO-level log entry containing the `session_id`, `client_id`, the `comment_id`, and the `line` number.
4. WHEN a message of an unsupported type is received, THE collaboration_logger SHALL emit a WARNING-level log entry containing the `session_id`, `client_id`, and the unrecognised `message_type`.

### Requirement 3: Structured Error-Event Logging

**User Story:** As an operator, I want structured log entries for validation failures and protocol errors within the presence sync flow, so that I can detect abuse, misconfigured clients, or bugs without relying solely on HTTP-level error signals.

#### Acceptance Criteria

1. WHEN a `code_update` message is rejected because the code field is not a string, THE collaboration_logger SHALL emit a WARNING-level log entry containing the `session_id`, `client_id`, and `reason="invalid_code_type"`.
2. WHEN a `code_update` message is rejected because the code length exceeds `MAX_CODE_CHARS`, THE collaboration_logger SHALL emit a WARNING-level log entry containing the `session_id`, `client_id`, `reason="code_too_long"`, and the received length.
3. WHEN a `comment_added` message is rejected because the comment text is empty, THE collaboration_logger SHALL emit a WARNING-level log entry containing the `session_id`, `client_id`, and `reason="empty_comment_text"`.
4. WHEN a `comment_added` message is rejected because the comment text exceeds `MAX_COMMENT_CHARS`, THE collaboration_logger SHALL emit a WARNING-level log entry containing the `session_id`, `client_id`, `reason="comment_too_long"`, and the received length.
5. WHEN a stale socket is detected during broadcast, THE collaboration_logger SHALL emit a WARNING-level log entry containing the `session_id`, `client_id`, and `reason="stale_socket"`.
6. IF a `sync_required` response is sent to a Client because its `incoming_version` is behind the room `version`, THEN THE collaboration_logger SHALL emit a DEBUG-level log entry containing the `session_id`, `client_id`, `incoming_version`, and the current room `version`.
7. IF a WebSocket message payload is not a JSON object, THEN THE collaboration_logger SHALL emit a WARNING-level log entry containing the `session_id`, `client_id`, and `reason="non_object_payload"`.

### Requirement 4: Prometheus WebSocket Connection Metrics

**User Story:** As an operator, I want Prometheus gauges and counters that track active WebSocket connections and total connection lifecycle events, so that I can alert on abnormal connection counts and visualise collaboration traffic.

#### Acceptance Criteria

1. THE Observability_Layer SHALL define a Prometheus Gauge named `qyverixai_collaboration_active_connections` with label `session_id` that reflects the number of Clients currently connected to each Session.
2. WHEN a Client connects to a Session, THE Observability_Layer SHALL increment the `qyverixai_collaboration_active_connections` gauge for that `session_id` by 1.
3. WHEN a Client disconnects from a Session, THE Observability_Layer SHALL decrement the `qyverixai_collaboration_active_connections` gauge for that `session_id` by 1.
4. THE Observability_Layer SHALL define a Prometheus Counter named `qyverixai_collaboration_connections_total` with label `session_id` that counts the total number of Client connections accepted since process start.
5. WHEN a Client connects to a Session, THE Observability_Layer SHALL increment the `qyverixai_collaboration_connections_total` counter for that `session_id` by 1.

### Requirement 5: Prometheus Message-Event Metrics

**User Story:** As an operator, I want Prometheus counters for each collaboration message type, so that I can build dashboards showing real-time edit activity, cursor movement frequency, and comment creation rates.

#### Acceptance Criteria

1. THE Observability_Layer SHALL define a Prometheus Counter named `qyverixai_collaboration_messages_total` with labels `session_id` and `message_type` that counts every successfully processed collaboration message.
2. WHEN a `code_update` message is processed successfully, THE Observability_Layer SHALL increment the `qyverixai_collaboration_messages_total` counter with `message_type="code_update"` for the corresponding `session_id`.
3. WHEN a `cursor_update` message is processed successfully, THE Observability_Layer SHALL increment the `qyverixai_collaboration_messages_total` counter with `message_type="cursor_update"` for the corresponding `session_id`.
4. WHEN a `comment_added` message is processed successfully, THE Observability_Layer SHALL increment the `qyverixai_collaboration_messages_total` counter with `message_type="comment_added"` for the corresponding `session_id`.

### Requirement 6: Prometheus Error and Validation Metrics

**User Story:** As an operator, I want a Prometheus counter for collaboration validation and protocol errors, so that I can alert on sustained error rates that may indicate a broken client or attempted abuse.

#### Acceptance Criteria

1. THE Observability_Layer SHALL define a Prometheus Counter named `qyverixai_collaboration_errors_total` with labels `session_id` and `error_reason` that counts every validation rejection or protocol error in the presence sync flow.
2. WHEN a `code_update` message is rejected for any validation reason, THE Observability_Layer SHALL increment the `qyverixai_collaboration_errors_total` counter with the corresponding `error_reason` label.
3. WHEN a `comment_added` message is rejected for any validation reason, THE Observability_Layer SHALL increment the `qyverixai_collaboration_errors_total` counter with the corresponding `error_reason` label.
4. WHEN a stale socket is detected during broadcast, THE Observability_Layer SHALL increment the `qyverixai_collaboration_errors_total` counter with `error_reason="stale_socket"` for the corresponding `session_id`.
5. WHEN an unsupported message type is received, THE Observability_Layer SHALL increment the `qyverixai_collaboration_errors_total` counter with `error_reason="unsupported_message_type"` for the corresponding `session_id`.

### Requirement 7: Metrics Registration in Existing Prometheus Registry

**User Story:** As an operator, I want the collaboration metrics to appear on the existing `/metrics` scrape endpoint, so that I can use a single Prometheus target for the entire application.

#### Acceptance Criteria

1. THE Observability_Layer SHALL register all collaboration Prometheus metrics (`qyverixai_collaboration_active_connections`, `qyverixai_collaboration_connections_total`, `qyverixai_collaboration_messages_total`, `qyverixai_collaboration_errors_total`) in the same `prometheus_client` default registry used by the existing metrics in `observability.py`.
2. WHILE the `METRICS_ENABLED` environment variable is set to `false`, THE Observability_Layer SHALL skip all Prometheus counter and gauge updates for collaboration events.
3. THE Observability_Layer SHALL define collaboration metrics in `observability.py` alongside the existing HTTP metrics, following the established naming and label-cardinality conventions.

### Requirement 8: No Regression in Collaboration Behaviour

**User Story:** As a developer, I want the observability additions to be strictly additive, so that all existing collaboration features — code sync, cursor sharing, comments, and session management — continue to work without modification.

#### Acceptance Criteria

1. THE Collaboration_Manager SHALL preserve all existing session state transitions (connect, broadcast, disconnect, room cleanup) after the Observability_Layer is integrated.
2. WHEN observability instrumentation raises an unexpected exception, THE Collaboration_Manager SHALL log the exception at ERROR level and continue normal operation without propagating the error to the Client.
3. THE Collaboration_Router SHALL not alter the structure or content of any WebSocket message sent to Clients as a result of adding observability.

### Requirement 9: Logger Registration

**User Story:** As an operator, I want the collaboration logger to participate in the existing per-component log-level override system, so that I can control its verbosity via the `LOG_LEVEL_COLLABORATION` environment variable without changing code.

#### Acceptance Criteria

1. THE Observability_Layer SHALL add a `"collaboration"` entry to the `COMPONENT_LOGGER_MAP` in `logging_config.py` mapped to the logger name `"app.routers.collaboration"`.
2. WHEN the `LOG_LEVEL_COLLABORATION` environment variable is set, THE Observability_Layer SHALL apply the specified log level to the `app.routers.collaboration` logger at startup.
