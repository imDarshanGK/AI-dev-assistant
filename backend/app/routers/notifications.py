"""Notifications router for dynamic email template previews."""

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from ..services.notification_service import NotificationService

router = APIRouter()


@router.get(
    "/preview",
    response_class=HTMLResponse,
    summary="Preview branded HTML email notifications",
)
def preview_notification(
    user_name: str = Query("Kiran", description="Recipient user name"),
    title: str = Query("Anomaly Found in ast_analyzer.py", description="Alert Title"),
    alert_message: str = Query(
        "A critical warning was triggered during analysis: unused import statement at line 14.",
        description="Alert highlighted message",
    ),
    body_text: str = Query(
        "We recommend opening your workspace in QyverixAI and running the automatic clean command to optimize your AST profile.",
        description="Supporting alert details",
    ),
    action_url: str = Query(
        "https://qyverixai.onrender.com/app",
        description="Call to action URL",
    ),
    action_text: str = Query(
        "View Code Insight",
        description="Call to action button text",
    ),
    alert_color: str = Query(
        "#0ea5e9",
        description="Theme highlight color (Hex or CSS color)",
    ),
):
    """HTML preview route for testing and custom-styling the branded notification email templates.

    Renders and displays the HTML directly in the browser.
    """
    service = NotificationService()
    html_content = service.render_generic_alert(
        user_name=user_name,
        title=title,
        alert_message=alert_message,
        body_text=body_text,
        action_url=action_url,
        action_text=action_text,
        alert_color=alert_color,
    )
    return HTMLResponse(content=html_content)
