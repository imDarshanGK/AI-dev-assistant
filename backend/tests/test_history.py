"""
Tests for the /history/ endpoints.
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app
from app.services import database
from fastapi.testclient import TestClient

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
database.DB_PATH = _tmp.name

asyncio.run(database.init_db())

client = TestClient(app, raise_server_exceptions=True)


def test_save_history():
    r = client.post(
        "/history/",
        json={
            "code": "print('hello')",
            "language": "Python",
            "score": 85,
            "issue_count": 1,
        },
    )
    assert r.status_code == 201
    d = r.json()
    assert d["status"] == "saved"
    assert "id" in d


def test_get_history():
    client.post(
        "/history/",
        json={"code": "x = 1", "language": "Python", "score": 90, "issue_count": 0},
    )
    r = client.get("/history/")
    assert r.status_code == 200
    res = r.json()
    assert "items" in res
    assert "meta" in res
    assert isinstance(res["items"], list)
    assert len(res["items"]) > 0
    assert res["meta"]["total"] >= 1


def test_get_history_pagination():
    r = client.get("/history/?limit=1&offset=0")
    assert r.status_code == 200
    res = r.json()
    assert "items" in res
    assert len(res["items"]) <= 1
    assert res["meta"]["limit"] == 1
    assert res["meta"]["offset"] == 0


def test_get_history_sorting():

    client.post(
        "/history/",
        json={"code": "low score", "language": "Python", "score": 10, "issue_count": 5},
    )
    client.post(
        "/history/",
        json={
            "code": "high score",
            "language": "Python",
            "score": 99,
            "issue_count": 1,
        },
    )

    r = client.get("/history/?sort_by=score&order=desc")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 2
    assert items[0]["score"] >= items[1]["score"]

    r = client.get("/history/?sort_by=score&order=asc")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["score"] <= items[1]["score"]


def test_search_history():
    client.post(
        "/history/",
        json={"code": "def my_unique_function(): pass", "language": "Python"},
    )
    r = client.get("/history/search?q=my_unique_function")
    assert r.status_code == 200
    results = r.json()
    assert any("my_unique_function" in e["code_preview"] for e in results)


def test_delete_history():
    r = client.post("/history/", json={"code": "to be deleted", "language": "Python"})
    entry_id = r.json()["id"]
    r = client.delete(f"/history/{entry_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"


def test_delete_nonexistent():
    r = client.delete("/history/999999")
    assert r.status_code == 404


def test_history_entry_fields():
    client.post(
        "/history/",
        json={
            "code": "let x = 1;",
            "language": "JavaScript",
            "score": 70,
            "issue_count": 2,
        },
    )
    r = client.get("/history/")
    assert r.status_code == 200
    entry = r.json()["items"][0]
    assert "id" in entry
    assert "code_hash" in entry
    assert "language" in entry
    assert "score" in entry
    assert "issue_count" in entry
    assert "timestamp" in entry
    assert "code_preview" in entry


def test_search_no_results():
    r = client.get("/history/search?q=xyznotfoundever")
    assert r.status_code == 200
    assert r.json() == []


def test_search_history_max_length():
    r = client.get("/history/search?q=" + ("x" * 201))
    assert r.status_code == 422


def test_history_detail():
    save_r = client.post(
        "/history/",
        json={
            "code": "print('hello world')",
            "language": "Python",
            "score": 95,
            "issue_count": 0,
            "result_json": '{"status": "ok"}',
        },
    )
    assert save_r.status_code == 201
    entry_id = save_r.json()["id"]

    r = client.get(f"/history/{entry_id}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["id"] == entry_id
    assert detail["code"] == "print('hello world')"
    assert detail["result_json"] == '{"status": "ok"}'


def test_history_detail_not_found():
    r = client.get("/history/999999")
    assert r.status_code == 404


def test_clear_all_history():
    client.post("/history/", json={"code": "dummy", "language": "Python"})

    r = client.delete("/history/")
    assert r.status_code == 200
    assert r.json() == {"status": "cleared"}

    get_r = client.get("/history/")
    assert get_r.json()["meta"]["total"] == 0
