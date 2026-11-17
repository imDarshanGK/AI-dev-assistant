"""Request-ID propagation through the logging middleware, without external services."""

import asyncio
import logging
from uuid import UUID

import httpx
import pytest
from app.middleware import logger, request_id_and_logging_middleware
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


@pytest.fixture
def logging_app() -> FastAPI:
    """Exercise the real middleware on an isolated ASGI app."""
    app = FastAPI()
    app.middleware("http")(request_id_and_logging_middleware)

    @app.get("/logged/{status_code}")
    async def logged_response(status_code: int, request: Request) -> JSONResponse:
        # Allow overlapping requests to reach their handlers before either returns.
        await asyncio.sleep(0)
        return JSONResponse(
            {"request_id": request.state.request_id}, status_code=status_code
        )

    return app


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [200, 422])
async def test_request_id_matches_state_header_and_logs(
    logging_app: FastAPI, caplog: pytest.LogCaptureFixture, status_code: int
) -> None:
    """Successful and error responses keep one ID from start to finish."""
    path = f"/logged/{status_code}"
    with caplog.at_level(logging.INFO, logger=logger.name):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=logging_app), base_url="http://test"
        ) as client:
            response = await client.get(path)

    assert response.status_code == status_code
    request_id = response.headers["X-Request-ID"]
    assert UUID(request_id).version == 4
    assert response.json()["request_id"] == request_id
    messages = [
        record.getMessage() for record in caplog.records if record.name == logger.name
    ]
    assert len(messages) == 2
    assert messages[0].startswith("request_started ")
    assert messages[1].startswith("request_finished ")
    for message in messages:
        assert f"request_id={request_id} " in message
        assert f"method=GET path={path}" in message
    assert f"status={status_code} " in messages[1]


@pytest.mark.asyncio
async def test_overlapping_requests_keep_distinct_correlated_ids(
    logging_app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    """Two overlapping requests must not reuse or exchange their log context."""
    with caplog.at_level(logging.INFO, logger=logger.name):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=logging_app), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(
                client.get("/logged/200"), client.get("/logged/200")
            )

    request_ids = {response.headers["X-Request-ID"] for response in responses}
    assert len(request_ids) == 2
    for response in responses:
        assert response.status_code == 200
        request_id = response.headers["X-Request-ID"]
        assert UUID(request_id).version == 4
        assert response.json()["request_id"] == request_id
        messages = [
            record.getMessage()
            for record in caplog.records
            if record.name == logger.name
            and f"request_id={request_id} " in record.getMessage()
        ]
        assert len(messages) == 2
        assert messages[0].startswith("request_started ")
        assert messages[1].startswith("request_finished ")
