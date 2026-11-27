"""Cross-origin clients must see rate-limit responses and their headers.

The bundled frontend calls the hosted API from another origin when it is opened
from disk. The rate limiter used to sit outside the CORS middleware, so its 429
had no ``Access-Control-Allow-Origin`` header and the browser reported a
network failure, and every preflight request used up one unit of quota.
"""

import pytest
from app import main as app_main
from fastapi.testclient import TestClient

client = TestClient(app_main.app)

ORIGIN = {"Origin": "https://frontend.example"}
PREFLIGHT = {
    **ORIGIN,
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type",
}
BODY = {"code": "x = 1\n", "language": "python"}
RATE_LIMITED_PATHS = ["/explanation/", "/debugging/", "/suggestions/", "/analyze/"]


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    app_main._request_counts.clear()
    yield
    app_main._request_counts.clear()


@pytest.fixture
def limit_of_two(monkeypatch):
    monkeypatch.setattr(app_main, "RATE_LIMIT", 2)


def test_rate_limited_response_carries_cors_headers(limit_of_two):
    for _ in range(2):
        assert client.post("/debugging/", json=BODY, headers=ORIGIN).status_code == 200

    response = client.post("/debugging/", json=BODY, headers=ORIGIN)

    assert response.status_code == 429
    assert response.headers["access-control-allow-origin"] == ORIGIN["Origin"]
    assert response.headers["retry-after"] == "60"
    assert "Rate limit exceeded" in response.json()["detail"]


@pytest.mark.parametrize("path", RATE_LIMITED_PATHS)
def test_preflight_does_not_use_rate_limit_quota(path):
    response = client.options(path, headers=PREFLIGHT)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN["Origin"]
    assert not app_main._request_counts


def test_browser_gets_the_full_quota_despite_preflights(limit_of_two):
    statuses = []
    for _ in range(3):
        client.options("/debugging/", headers=PREFLIGHT)
        statuses.append(
            client.post("/debugging/", json=BODY, headers=ORIGIN).status_code
        )

    assert statuses == [200, 200, 429]


@pytest.mark.parametrize(
    "header",
    [
        "Retry-After",
        "X-Cache",
        "X-Process-Time-Ms",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
    ],
)
def test_custom_response_headers_are_exposed_to_cross_origin_scripts(header):
    response = client.post("/analyze/", json=BODY, headers=ORIGIN)

    assert response.status_code == 200
    exposed = response.headers["access-control-expose-headers"]
    assert header in [name.strip() for name in exposed.split(",")]


def test_same_origin_requests_are_unaffected():
    response = client.post("/debugging/", json=BODY)

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert response.headers["x-ratelimit-limit"] == str(app_main.RATE_LIMIT)
    assert response.headers["x-process-time-ms"]
