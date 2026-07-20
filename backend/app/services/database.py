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
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                code_hash   TEXT NOT NULL,
                language    TEXT NOT NULL,
                score       INTEGER,
                issue_count INTEGER,
                timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
                code_preview TEXT NOT NULL,
                code        TEXT,
                result_json TEXT
            )
        """
        )
        try:
            await db.execute("ALTER TABLE history ADD COLUMN code TEXT")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE history ADD COLUMN result_json TEXT")
        except Exception:
            pass
        await db.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_history
            USING fts5(code_preview, content=history, content_rowid=id)
        """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON history(timestamp DESC)"
        )
        await db.commit()


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def save_entry(
    code: str,
    language: str,
    score: int | None,
    issue_count: int | None,
    result_json: str | None = None,
) -> int:
    code_hash = hash_code(code)
    preview = code.strip()[:120].replace("\n", " ")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO history (code_hash, language, score, issue_count, code_preview, code, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (code_hash, language, score, issue_count, preview, code, result_json),
        )
        row_id = cursor.lastrowid
        await db.execute(
            "INSERT INTO fts_history(rowid, code_preview) VALUES (?, ?)",
            (row_id, preview),
        )
        await db.commit()
        return row_id


async def count_entries() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM history")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_entries(
    limit: int = 20, offset: int = 0, sort_by: str = "timestamp", order: str = "desc"
) -> list[dict]:
    allowed_sort_columns = {"timestamp", "score", "issue_count", "id"}
    allowed_orders = {"asc", "desc"}
    if sort_by not in allowed_sort_columns:
        sort_by = "timestamp"
    if order.lower() not in allowed_orders:
        order = "desc"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = f"""
            SELECT id, code_hash, language, score, issue_count, timestamp, code_preview
            FROM history
            ORDER BY {sort_by} {order}, id DESC
            LIMIT ? OFFSET ?
        """

        cursor = await db.execute(query, (limit, offset))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def search_entries(q: str, limit: int = 20) -> list[dict]:
    q = q[:200]
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT h.id, h.code_hash, h.language, h.score,
                   h.issue_count, h.timestamp, h.code_preview
            FROM history h
            WHERE h.id IN (
                SELECT rowid FROM fts_history WHERE fts_history MATCH ?
            )
            ORDER BY h.timestamp DESC
            LIMIT ?
            """,
            (q, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def delete_entry(entry_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM history WHERE id = ?", (entry_id,))
        await db.execute("DELETE FROM fts_history WHERE rowid = ?", (entry_id,))
        await db.commit()
        return cursor.rowcount > 0


async def get_entry(entry_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, code_hash, language, score, issue_count, timestamp, code_preview, code, result_json
            FROM history
            WHERE id = ?
            """,
            (entry_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def clear_entries() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM history")
        await db.execute("DELETE FROM fts_history")
        await db.commit()
        return cursor.rowcount
