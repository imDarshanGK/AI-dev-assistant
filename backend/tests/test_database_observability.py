"""
Tests for database service observability metrics.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app
from app.services import database

# Set up a temporary database for testing
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
database.DB_PATH = _tmp.name

# Run DB initialization (this will record init_db metrics)
asyncio.run(database.init_db())

client = TestClient(app)


def test_db_observability_metrics_recorded():
    # Ensure metrics are enabled
    os.environ["METRICS_ENABLED"] = "true"

    # Run some operations to trigger metrics logging
    asyncio.run(database.save_entry("print('hello')", "Python", 90, 0))
    asyncio.run(database.get_entries(limit=1))

    # Retrieve metrics from endpoint
    response = client.get("/metrics")
    assert response.status_code == 200
    metrics_text = response.text

    # Verify qyverixai_db_operations_total is present
    assert "qyverixai_db_operations_total" in metrics_text
    assert 'operation="init_db"' in metrics_text
    assert 'operation="save_entry"' in metrics_text
    assert 'operation="get_entries"' in metrics_text
    assert 'status="success"' in metrics_text

    # Verify qyverixai_db_operation_duration_seconds is present
    assert "qyverixai_db_operation_duration_seconds" in metrics_text
    assert 'operation="init_db"' in metrics_text
    assert 'operation="save_entry"' in metrics_text
    assert 'operation="get_entries"' in metrics_text


def test_db_observability_metrics_disabled(monkeypatch):
    # Disable metrics
    monkeypatch.setenv("METRICS_ENABLED", "false")

    # Run operations and ensure they execute cleanly without error
    try:
        row_id = asyncio.run(database.save_entry("print('hello')", "Python", 90, 0))
        assert row_id is not None
    except Exception as e:
        pytest.fail(f"Database operation failed when metrics are disabled: {e}")
