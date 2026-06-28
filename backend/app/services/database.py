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
                result_json TEXT,
                tags        TEXT,
                user_id     TEXT
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
        try:
            await db.execute("ALTER TABLE history ADD COLUMN tags TEXT")
        except Exception:
            pass

        try:
            await db.execute("ALTER TABLE history ADD COLUMN user_id TEXT")
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
        await db.execute("CREATE INDEX IF NOT EXISTS idx_language ON history(language)")

        await db.execute("CREATE INDEX IF NOT EXISTS idx_score ON history(score)")
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_issue_count ON history(issue_count)"
        )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON history(user_id)")

        await db.execute("CREATE INDEX IF NOT EXISTS idx_tags ON history(tags)")
        await db.commit()


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def save_entry(
    code: str,
    language: str,
    score: int | None,
    issue_count: int | None,
    result_json: str | None = None,
    tags: str | None = None,
    user_id: str | None = None,
) -> int:
    code_hash = hash_code(code)
    preview = code.strip()[:120].replace("\n", " ")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
           INSERT INTO history (
                code_hash, language, score, issue_count,
                code_preview, code, result_json, tags, user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                code_hash,
                language,
                score,
                issue_count,
                preview,
                code,
                result_json,
                tags,
                user_id,
            ),
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


async def search_entries(
    q: str = "",
    language: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    tags: str | None = None,
    user_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        query = """
            SELECT id, code_hash, language, score,
                   issue_count, timestamp, code_preview
            FROM history
            WHERE 1=1
        """

        count_query = "SELECT COUNT(*) FROM history WHERE 1=1"

        params = []
        count_params = []

        if tags:
            query += " AND tags LIKE ?"
            count_query += " AND tags LIKE ?"
            params.append(f"%{tags}%")
            count_params.append(f"%{tags}%")

        if user_id:
            query += " AND user_id = ?"
            count_query += " AND user_id = ?"
            params.append(user_id)
            count_params.append(user_id)
        if q:
            query += """
                AND id IN (
                    SELECT rowid FROM fts_history
                    WHERE fts_history MATCH ?
                )
            """
            count_query += """
                AND id IN (
                    SELECT rowid FROM fts_history
                    WHERE fts_history MATCH ?
                )
            """
            params.append(q)
            count_params.append(q)
        if language:
            query += " AND language = ?"
            count_query += " AND language = ?"
            params.append(language)
            count_params.append(language)

        if start_date:
            query += " AND timestamp >= ?"
            count_query += " AND timestamp >= ?"
            params.append(start_date)
            count_params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            count_query += " AND timestamp <= ?"
            params.append(end_date)
            count_params.append(end_date)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

        count_cursor = await db.execute(count_query, count_params)
        total_row = await count_cursor.fetchone()
        total = total_row[0]

        return [dict(row) for row in rows], total


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
            SELECT id, code_hash, language, score, issue_count, timestamp, code_preview, code, result_json, tags, user_id
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
