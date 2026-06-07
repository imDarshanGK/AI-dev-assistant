"""Verify OpenAPI request and response examples are present for analysis endpoints."""

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.main import app as fastapi_app

client = TestClient(fastapi_app)


def test_analysis_endpoints_openapi_examples():
    response = client.get("/openapi.json")
    assert response.status_code == 200

    spec = response.json()
    for path in ["/explanation/", "/debugging/", "/suggestions/", "/analyze/"]:
        assert path in spec["paths"]
        request_body = spec["paths"][path]["post"]["requestBody"]
        examples = request_body["content"]["application/json"].get("examples")
        assert examples and "python_function" in examples

    for path in ["/explanation/", "/debugging/", "/suggestions/", "/analyze/"]:
        response_schema = spec["paths"][path]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert "example" in response_schema
