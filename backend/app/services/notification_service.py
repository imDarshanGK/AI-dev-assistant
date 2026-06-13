"""Notification service for compiling and rendering branded HTML email templates."""

from __future__ import annotations
import os
import re
from typing import Any, Dict, Optional

# Attempt to import jinja2; provide a fallback if it is not available.
try:
    import jinja2
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    JINJA_AVAILABLE = True
except ImportError:
    JINJA_AVAILABLE = False


class NotificationService:
    """Service to load, compile, and render HTML email templates."""

    def __init__(self, templates_dir: Optional[str] = None) -> None:
        """Initialize the Notification Service.

        Args:
            templates_dir: Optional custom path to templates folder.
                           Defaults to app/utils/templates/.
        """
        if templates_dir is None:
            # Determine path relative to this file: app/services/ -> app/utils/templates/
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.templates_dir = os.path.abspath(
                os.path.join(current_dir, "..", "utils", "templates")
            )
        else:
            self.templates_dir = templates_dir

        if JINJA_AVAILABLE:
            self.env = Environment(
                loader=FileSystemLoader(self.templates_dir),
                autoescape=select_autoescape(["html", "xml"]),
            )
        else:
            self.env = None

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a specific HTML template with the given context.

        Falls back to basic standard string rendering if Jinja2 is unavailable.
        """
        if JINJA_AVAILABLE and self.env:
            try:
                template = self.env.get_template(template_name)
                return template.render(**context)
            except Exception as exc:
                # Log or raise template loading error
                raise RuntimeError(f"Jinja2 failed to render template {template_name}: {exc}") from exc

        # Fallback implementation (basic HTML loading and placeholder replacement)
        template_path = os.path.join(self.templates_dir, template_name)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template path not found: {template_path}")

        # Read specific template
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()

        # Simple inheritance handler for fallback (if using generic_alert extending base)
        # Note: If Jinja2 is installed via requirements, this fallback is rarely triggered.
        # But we make it robust anyway.
        if "{% extends" in template_content:
            # Find base file name
            base_match = re.search(r'{%\s*extends\s*["\']([^"\']+)["\']\s*%}', template_content)
            if base_match:
                base_name = base_match.group(1)
                base_path = os.path.join(self.templates_dir, base_name)
                if os.path.exists(base_path):
                    with open(base_path, "r", encoding="utf-8") as bf:
                        base_content = bf.read()

                    # Simple mock of block replacement
                    # Extract {% block content %} ... {% endblock %}
                    content_match = re.search(
                        r'{%\s*block\s+content\s*%}(.*?){%\s*endblock\s*%}',
                        template_content,
                        re.DOTALL
                    )
                    action_match = re.search(
                        r'{%\s*block\s+action_button\s*%}(.*?){%\s*endblock\s*%}',
                        template_content,
                        re.DOTALL
                    )

                    rendered_html = base_content
                    if content_match:
                        block_inner = content_match.group(1)
                        rendered_html = re.sub(
                            r'{%\s*block\s+content\s*%}.*?{%\s*endblock\s*%}',
                            block_inner,
                            rendered_html,
                            flags=re.DOTALL
                        )
                    if action_match:
                        action_inner = action_match.group(1)
                        # Handle conditional {% if action_url %} block replacement in fallback
                        if not context.get("action_url"):
                            action_inner = ""
                        rendered_html = re.sub(
                            r'{%\s*block\s+action_button\s*%}.*?{%\s*endblock\s*%}',
                            action_inner,
                            rendered_html,
                            flags=re.DOTALL
                        )

                    template_content = rendered_html

        # Replace double curly braces variables
        # Format: {{ key }} or {{ key | default('val') }}
        for key, value in context.items():
            val_str = str(value) if value is not None else ""
            # Regex to match {{ key }} or {{ key | default(...) }}
            pattern = rf"{{\{{\s*{key}(?:\s*\|\s*default\([^)]*\))?\s*}}\}}"
            template_content = re.sub(pattern, val_str, template_content)

        # Clear out any remaining Jinja brackets to avoid rendering broken symbols
        template_content = re.sub(r"{{\s*[^}]+\s*}}", "", template_content)
        template_content = re.sub(r"{%\s*[^%]+\s*%}", "", template_content)

        return template_content

    def render_generic_alert(
        self,
        user_name: str,
        title: str,
        alert_message: str,
        body_text: str,
        action_url: Optional[str] = None,
        action_text: Optional[str] = None,
        alert_color: Optional[str] = None,
    ) -> str:
        """Helper function to render a branded generic alert email.

        Args:
            user_name: The recipient's name.
            title: The title of the alert.
            alert_message: The core warning or status message.
            body_text: Supporting paragraphs or description text.
            action_url: Optional destination link for CTA button.
            action_text: Optional text for CTA button.
            alert_color: Accent border/button color (e.g. Hex color).
                         Defaults to sky-blue (#0ea5e9).

        Returns:
            Rendered HTML string ready to be sent as an email body.
        """
        context = {
            "user_name": user_name,
            "title": title,
            "alert_message": alert_message,
            "body_text": body_text,
            "action_url": action_url,
            "action_text": action_text or "Take Action",
            "alert_color": alert_color or "#0ea5e9",
        }
        return self.render_template("generic_alert.html", context)
