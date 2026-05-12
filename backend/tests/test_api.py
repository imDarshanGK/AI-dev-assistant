import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app 

client = TestClient(app)

def test_explanation_endpoint_mocked():
    # Target the function inside the router file
    target = "app.routers.explanation.explain_code"
    
    mock_payload = {"code": "print('hello')", "language": "python"}
    
    # MATCHING THE SCHEMA: summary instead of explanation, key_points instead of observations
    mock_response = {
        "language": "python",
        "summary": "This is a mock summary of the code.",
        "key_points": ["Uses a print function", "Valid Python syntax"],
        "complexity": "Beginner"
    }

    with patch(target) as mocked_service:
        mocked_service.return_value = mock_response
        
        response = client.post("/explanation/", json=mock_payload)
        
        # Validation
        assert response.status_code == 200
        assert response.json()["summary"] == "This is a mock summary of the code."
        assert "key_points" in response.json()
        mocked_service.assert_called_once()