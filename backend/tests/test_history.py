"""
Tests for the /history/ endpoints.
"""
import sys, os, tempfile, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services import database

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
database.DB_PATH = _tmp.name

asyncio.run(database.init_db())

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=True)


def test_save_history():
    r = client.post("/history/", json={
        "code": "print('hello')",
        "language": "Python",
        "score": 85,
        "issue_count": 1,
    })
    assert r.status_code == 201
    d = r.json()
    assert d["status"] == "saved"
    assert "id" in d


def test_get_history():
    client.post("/history/", json={"code": "x = 1", "language": "Python", "score": 90, "issue_count": 0})
    r = client.get("/history/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) > 0


def test_get_history_pagination():
    r = client.get("/history/?limit=1&offset=0")
    assert r.status_code == 200
    assert len(r.json()) <= 1


def test_search_history():
    client.post("/history/", json={"code": "def my_unique_function(): pass", "language": "Python"})
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
    client.post("/history/", json={"code": "let x = 1;", "language": "JavaScript", "score": 70, "issue_count": 2})
    r = client.get("/history/")
    assert r.status_code == 200
    entry = r.json()[0]
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
