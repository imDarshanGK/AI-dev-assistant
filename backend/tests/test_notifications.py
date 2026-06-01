from fastapi.testclient import TestClient
from app.main import app
from app.services.notification_service import NotificationService

client = TestClient(app)


def test_notification_service_rendering():
    service = NotificationService()
    html = service.render_generic_alert(
        user_name="Alice",
        title="Test Alert Title",
        alert_message="Alert main message",
        body_text="Alert secondary body text",
        action_url="https://example.com/action",
        action_text="Click Me",
        alert_color="#ff5555",
    )
    # Check that critical context was rendered
    assert "Alice" in html
    assert "Test Alert Title" in html
    assert "Alert main message" in html
    assert "Alert secondary body text" in html
    assert "https://example.com/action" in html
    assert "Click Me" in html
    assert "#ff5555" in html
    assert "QyverixAI" in html


def test_preview_endpoint():
    response = client.get("/notifications/preview")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    
    html = response.text
    # Default query values should be in the html
    assert "Kiran" in html
    assert "Anomaly Found in ast_analyzer.py" in html
    assert "unused import statement" in html
