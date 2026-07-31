from fastapi.testclient import TestClient
from app.main import app

def test_docker_generator_fallback():
    with TestClient(app) as client:
        payload = {
            "project_structure": "app/\n  main.py\nrequirements.txt",
            "detected_files": ["main.py", "requirements.txt"],
            "target_language": "python",
            "db_dependency": "postgresql"
        }
        response = client.post("/api/generate-docker", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "dockerfile" in data
        assert "docker_compose" in data
        assert "explanation" in data
        assert "python:3.11-slim" in data["dockerfile"]
        assert "postgres:15-alpine" in data["docker_compose"]
