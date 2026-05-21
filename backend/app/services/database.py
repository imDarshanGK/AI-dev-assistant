"""
SQLite database service using aiosqlite for persistent history storage.
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
                code_hash   TEXT NOT NULL,
                language    TEXT NOT NULL,
                score       INTEGER,
                issue_count INTEGER,
                timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
                code_preview TEXT NOT NULL
            )
        """)
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
) -> int:
    code_hash = hash_code(code)
    preview = code.strip()[:120].replace("\n", " ")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO history (code_hash, language, score, issue_count, code_preview)
            VALUES (?, ?, ?, ?, ?)
            """,
            (code_hash, language, score, issue_count, preview),
        )
        await db.commit()
        return cursor.lastrowid


async def get_entries(limit: int = 20, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, code_hash, language, score, issue_count, timestamp, code_preview
            FROM history
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def search_entries(q: str, limit: int = 20) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, code_hash, language, score, issue_count, timestamp, code_preview
            FROM history
            WHERE code_preview LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (f"%{q}%", limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def delete_entry(entry_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM history WHERE id = ?", (entry_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
