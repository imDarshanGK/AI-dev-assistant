"""
SQLite database service using aiosqlite for persistent history storage.
Full-text search is powered by SQLite FTS5.
"""

from __future__ import annotations
import hashlib
import os
import aiosqlite

DB_PATH = os.getenv("HISTORY_DB_PATH", "history.db")


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                code_hash   TEXT NOT NULL,
                language    TEXT NOT NULL,
                score       INTEGER,
                issue_count INTEGER,
                timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
                code_preview TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_history
            USING fts5(code_preview, content=history, content_rowid=id)
        """)
        columns = await db.execute("PRAGMA table_info(history)")
        column_names = {row[1] for row in await columns.fetchall()}
        if "user_id" not in column_names:
            await db.execute("ALTER TABLE history ADD COLUMN user_id INTEGER")
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON history(timestamp DESC)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_user_timestamp "
            "ON history(user_id, timestamp DESC)"
        )
        await db.commit()


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def save_entry(
    user_id: int,
    code: str,
    language: str,
    score: int | None,
    issue_count: int | None,
) -> int:
    code_hash = hash_code(code)
    preview = code.strip()[:120].replace("\n", " ")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO history (
                user_id, code_hash, language, score, issue_count, code_preview
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, code_hash, language, score, issue_count, preview),
        )
        row_id = cursor.lastrowid
        await db.execute(
            "INSERT INTO fts_history(rowid, code_preview) VALUES (?, ?)",
            (row_id, preview),
        )
        await db.commit()
        return row_id


async def get_entries(user_id: int, limit: int = 20, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, code_hash, language, score, issue_count, timestamp, code_preview
            FROM history
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def search_entries(user_id: int, q: str, limit: int = 20) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT h.id, h.code_hash, h.language, h.score,
                   h.issue_count, h.timestamp, h.code_preview
            FROM history h
            WHERE h.user_id = ?
              AND h.id IN (
                SELECT rowid FROM fts_history WHERE fts_history MATCH ?
            )
            ORDER BY h.timestamp DESC
            LIMIT ?
            """,
            (user_id, q, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def delete_entry(entry_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM history WHERE id = ? AND user_id = ?", (entry_id, user_id)
        )
        if cursor.rowcount > 0:
            await db.execute(
                "DELETE FROM fts_history WHERE rowid = ?", (entry_id,)
            )
        await db.commit()
        return cursor.rowcount > 0
