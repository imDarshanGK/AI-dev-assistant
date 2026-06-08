"""Development-only routes — disabled when ENVIRONMENT=production."""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config import settings
from ..services import email_service

router = APIRouter(prefix="/dev", tags=["Development"])
preview_router = APIRouter(tags=["Development"])


def _ensure_dev_enabled() -> None:
    if settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )


def _preview_index_html(*, base_path: str) -> str:
  """HTML index listing all email preview links."""
  items = "\n".join(
      f'    <li><a href="{base_path}/{name}">{name}</a></li>'
      for name in sorted(email_service.EMAIL_TEMPLATES)
  )
  return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>QyverixAI Email Previews</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      max-width: 480px;
      margin: 48px auto;
      padding: 0 16px;
      color: #1a1b2e;
    }}
    h1 {{ font-size: 1.25rem; color: #7c3aed; }}
    ul {{ line-height: 2; padding-left: 1.25rem; }}
    a {{ color: #7c3aed; }}
  </style>
</head>
<body>
  <h1>QyverixAI Email Previews</h1>
  <p>Select a template to preview in the browser:</p>
  <ul>
{items}
  </ul>
</body>
</html>"""


def _render_email_preview(template: str, *, base_path: str) -> HTMLResponse:
    _ensure_dev_enabled()

    resolved = email_service.resolve_template_name(template)
    if resolved is None:
        available = ", ".join(sorted(email_service.EMAIL_TEMPLATES))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Unknown template '{template}'. "
                f"Available: {available}. "
                f"Open {base_path} for the full list."
            ),
        )

    if resolved != template.strip().lower():
        return RedirectResponse(
            url=f"{base_path}/{resolved}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    html = email_service.render_template(
        resolved,
        email_service.preview_context(resolved),
        inline_styles=False,
    )
    return HTMLResponse(content=html)


@router.get("/email-preview", response_class=HTMLResponse)
def email_preview_dev_index() -> HTMLResponse:
    _ensure_dev_enabled()
    return HTMLResponse(_preview_index_html(base_path="/dev/email-preview"))


@router.get("/email-preview/{template}", response_class=HTMLResponse)
def email_preview_dev(template: str) -> HTMLResponse:
    """Render a transactional email template in the browser for local iteration."""
    return _render_email_preview(template, base_path="/dev/email-preview")


@preview_router.get("/email-preview", response_class=HTMLResponse)
def email_preview_index() -> HTMLResponse:
    _ensure_dev_enabled()
    return HTMLResponse(_preview_index_html(base_path="/email-preview"))


@preview_router.get("/email-preview/{template}", response_class=HTMLResponse)
def email_preview(template: str) -> HTMLResponse:
    """Alias preview route: /email-preview/{template}."""
    return _render_email_preview(template, base_path="/email-preview")
