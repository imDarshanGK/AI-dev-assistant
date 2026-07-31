from __future__ import annotations

import asyncio
import tempfile

import pytest
from app.services import database


# Use a temporary db so tests never modify the application's real db.
@pytest.fixture
def temp_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    old_path = database.DB_PATH
    database.DB_PATH = tmp.name

    asyncio.run(database.init_db())

    yield

    database.DB_PATH = old_path


# Verify that hashing is deterministic and input-dependent.
def test_hash_code_is_deterministic():
    hash1 = database.hash_code("print('hello')")
    hash2 = database.hash_code("print('hello')")
    hash3 = database.hash_code("print('bye')")

    assert hash1 == hash2
    assert hash1 != hash3


# Verify that a saved entry can be retrieved unchanged.
def test_save_and_get_entry(temp_db):
    row_id = asyncio.run(
        database.save_entry(
            code="print('hello')",
            language="Python",
            score=95,
            issue_count=1,
        )
    )

    entry = asyncio.run(database.get_entry(row_id))

    assert entry is not None
    assert entry["language"] == "Python"
    assert entry["score"] == 95
    assert entry["issue_count"] == 1
    assert entry["code"] == "print('hello')"


# Verify that the entry count reflects successful inserts.
def test_count_entries(temp_db):
    assert asyncio.run(database.count_entries()) == 0

    asyncio.run(
        database.save_entry(
            code="print('one')",
            language="Python",
            score=100,
            issue_count=0,
        )
    )

    asyncio.run(
        database.save_entry(
            code="print('two')",
            language="Python",
            score=90,
            issue_count=1,
        )
    )

    assert asyncio.run(database.count_entries()) == 2


# Verify that deleting an entry removes it from the database.
def test_delete_entry(temp_db):
    row_id = asyncio.run(
        database.save_entry(
            code="print('hello')",
            language="Python",
            score=95,
            issue_count=1,
        )
    )

    assert asyncio.run(database.count_entries()) == 1

    deleted = asyncio.run(database.delete_entry(row_id))

    assert deleted is True
    assert asyncio.run(database.count_entries()) == 0
    assert asyncio.run(database.get_entry(row_id)) is None


# Verify that all entries can be cleared in a single operation.
def test_clear_entries(temp_db):
    asyncio.run(
        database.save_entry(
            code="print('one')",
            language="Python",
            score=100,
            issue_count=0,
        )
    )

    asyncio.run(
        database.save_entry(
            code="print('two')",
            language="Python",
            score=90,
            issue_count=1,
        )
    )

    assert asyncio.run(database.count_entries()) == 2

    deleted_count = asyncio.run(database.clear_entries())

    assert deleted_count == 2
    assert asyncio.run(database.count_entries()) == 0


# Verify that full-text search returns matching entries.
def test_search_entries(temp_db):
    asyncio.run(
        database.save_entry(
            code="print('hello world')",
            language="Python",
            score=95,
            issue_count=1,
        )
    )

    results = asyncio.run(database.search_entries("hello"))

    assert len(results) == 1

    assert results[0]["language"] == "Python"
    assert "hello world" in results[0]["code_preview"]


# Verify that entries are returned in the default descending order.
def test_get_entries_default_order(temp_db):
    asyncio.run(
        database.save_entry(
            code="print('first')",
            language="Python",
            score=80,
            issue_count=2,
        )
    )

    asyncio.run(
        database.save_entry(
            code="print('second')",
            language="Python",
            score=90,
            issue_count=1,
        )
    )

    entries = asyncio.run(database.get_entries())

    assert len(entries) == 2
    assert entries[0]["code_preview"] == "print('second')"
    assert entries[1]["code_preview"] == "print('first')"


# Verify that an invalid sort column safely falls back to the default.
def test_invalid_sort_by_fallback(temp_db):
    asyncio.run(
        database.save_entry(
            code="print('hello')",
            language="Python",
            score=95,
            issue_count=1,
        )
    )

    entries = asyncio.run(database.get_entries(sort_by="definitely_not_a_column"))

    assert len(entries) == 1
    assert entries[0]["language"] == "Python"


# Verify that an invalid sort order safely falls back to the default.
def test_invalid_order_fallback(temp_db):
    asyncio.run(
        database.save_entry(
            code="print('hello')",
            language="Python",
            score=95,
            issue_count=1,
        )
    )

    entries = asyncio.run(database.get_entries(order="banana"))

    assert len(entries) == 1
    assert entries[0]["language"] == "Python"
