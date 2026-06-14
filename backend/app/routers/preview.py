from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import re

router = APIRouter(tags=["admin"])

# ── Simple admin auth guard ──────────────────────────────────────────────────
ADMIN_TOKEN = "admin-secret-token"  # In real use, load from env variable


def require_admin(token: str = ""):
    """Check if the request has a valid admin token."""
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin access required.")


# ── Request and response models ───────────────────────────────────────────────
class PreviewRequest(BaseModel):
    template: str                          # e.g. "Analyze {language} code: {code}"
    variables: dict = {}                   # e.g. {"language": "Python", "code": "x=1"}
    mock_response: Optional[bool] = False  # If True, return a fake provider response
    admin_token: str = ""                  # Simple auth token


class PreviewResponse(BaseModel):
    rendered_prompt: str
    mock_provider_response: Optional[str] = None
    variables_found: list
    variables_missing: list


# ── Helper: render template ───────────────────────────────────────────────────
def render_template(template: str, variables: dict) -> tuple[str, list, list]:
    """
    Replace {placeholder} in template with values from variables dict.
    Returns (rendered_text, found_placeholders, missing_placeholders).
    """
    placeholders = re.findall(r"\{(\w+)\}", template)
    found = []
    missing = []
    rendered = template

    for key in placeholders:
        if key in variables:
            rendered = rendered.replace(f"{{{key}}}", str(variables[key]))
            found.append(key)
        else:
            missing.append(key)

    return rendered, found, missing


# ── Preview endpoint ──────────────────────────────────────────────────────────
@router.post("/preview/", response_model=PreviewResponse)
def preview_prompt(request: PreviewRequest):
    """
    Preview how a prompt template renders with given variables.
    Optionally returns a mock provider response.
    Protected by admin token.
    """
    # Check admin auth
    require_admin(request.admin_token)

    # Render the template
    rendered, found, missing = render_template(request.template, request.variables)

    # Optional mock response
    mock_response = None
    if request.mock_response:
        mock_response = (
            f"[MOCK RESPONSE] This is a simulated provider response for the prompt: "
            f'"{rendered[:80]}{"..." if len(rendered) > 80 else ""}"'
        )

    return PreviewResponse(
        rendered_prompt=rendered,
        mock_provider_response=mock_response,
        variables_found=found,
        variables_missing=missing,
    )
