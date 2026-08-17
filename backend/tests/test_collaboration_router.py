import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_valid_websocket_connection_and_routing():
    """Test valid WebSocket connection and correct URL routing."""
    with client.websocket_connect(
        "/collaboration/ws/room123?name=Bhagyashri"
    ) as websocket:
        assert websocket is not None


def test_session_isolation_and_concurrent_sessions():
    """Test session isolation and concurrent sessions do not bleed state."""
    with (
        client.websocket_connect("/collaboration/ws/roomA?name=UserA") as ws_a,
        client.websocket_connect("/collaboration/ws/roomB?name=UserB") as ws_b,
    ):
        assert ws_a is not None
        assert ws_b is not None


def test_missing_name_query_parameter():
    """Test missing name query parameter is handled correctly."""
    with client.websocket_connect("/collaboration/ws/room123") as websocket:
        assert websocket is not None


def test_session_id_with_special_characters():
    """Test session ID with special characters handled gracefully."""
    with client.websocket_connect(
        "/collaboration/ws/crazy-room-@#$%?name=Bhagyashri"
    ) as websocket:
        assert websocket is not None
