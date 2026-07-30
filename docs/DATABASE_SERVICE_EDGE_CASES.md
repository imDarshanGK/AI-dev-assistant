# Database Service — Edge Case Reference

This document describes the behaviour of the SQLite database service under uncommon or boundary conditions. It is intended for contributors extending the persistence layer and for developers integrating with the history APIs.

**Source:** `backend/app/services/database.py`

---

## Overview

The database service uses **SQLite** through **aiosqlite** for persistent history storage. Full-text search is implemented using **SQLite FTS5**.

By default, the database file is stored as:

```text
history.db
```

The location can be overridden using the `HISTORY_DB_PATH` environment variable. If it is not set, the service defaults to `history.db`.

---

## Initialization Edge Cases

### Database file does not exist

- **Behavior:** SQLite automatically creates the database file when the service connects for the first time.
- **Result:** No manual database creation step is required.

---

### Database already initialized

- **Behavior:** Initialization is safe to run multiple times.
- Tables, indexes, and the FTS virtual table use `IF NOT EXISTS`, preventing duplicate creation.

---

### Older database schema

- **Behavior:** During startup, the service attempts to add newly introduced columns (`code` and `result_json`).
- Existing databases continue working without requiring users to recreate the database.
- Errors caused by adding an already existing column are ignored, allowing backward-compatible initialization.

---

## Query Edge Cases

### Invalid sort column

- **Behavior:** Unsupported `sort_by` values automatically fall back to:

```text
timestamp
```

This prevents invalid SQL ordering.

---

### Invalid sort order

- **Behavior:** Any value other than `asc` or `desc` defaults to:

```text
desc
```

---

### Empty database

- **Behavior:**
  - `count_entries()` returns `0`
  - `get_entries()` returns an empty list
  - `search_entries()` returns an empty list

No exception is raised.

---

## Search Edge Cases

### Very long search query

- **Behavior:** Search queries are truncated to the first **200 characters** before executing the SQLite FTS5 search.

---

### No matching records

- **Behavior:** An empty list is returned.

---

## Entry Operations

### Requested entry does not exist

- **Behavior:** `get_entry()` returns `None`.

---

### Delete non-existent entry

- **Behavior:** `delete_entry()` returns `False`, indicating that no matching record was removed.

---

### Clearing an empty database

- **Behavior:** The operation succeeds without raising an exception and returns zero deleted rows.

---

## Metrics Edge Cases

### Metrics disabled

- **Behavior:** Database operations continue normally.
- Performance metrics are skipped without affecting database functionality.

---

### Database operation failure

- **Behavior:** Any exception raised during a database operation is re-raised to the caller.
- When metrics are enabled, the failed operation is still recorded with a failure status before the exception is propagated.

---

## Known Limitations

| Limitation | Detail |
|------------|--------|
| SQLite only | The implementation currently targets SQLite and is not database-agnostic. |
| FTS dependency | Full-text search relies on SQLite FTS5 support. |
| No retry logic | Failed database operations are propagated immediately without automatic retries. |
| No connection pooling | Each operation creates its own SQLite connection using `aiosqlite.connect()`. |
| Per-operation connections | A fresh database connection is opened for every operation rather than maintaining a shared connection pool. |