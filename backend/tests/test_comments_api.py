from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_comment():
    response = client.post(
        "/share/test-share/findings/fnd_123/comments",
        json={
            "text": "Investigating this issue",
            "author": "tester",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["share_id"] == "test-share"
    assert data["finding_id"] == "fnd_123"
    assert data["text"] == "Investigating this issue"


def test_fetch_comments():
    client.post(
        "/share/test-share/findings/fnd_001/comments",
        json={
            "text": "Comment A",
            "author": "tester",
        },
    )

    response = client.get(
        "/share/test-share/comments"
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) >= 1