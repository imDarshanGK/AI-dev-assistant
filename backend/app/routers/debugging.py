"""Debugging router — POST /debugging/"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import Base, get_db
from ..models import Suppression
from ..schemas import CodeRequest, DebuggingResponse
from ..services.code_assistant import detect_language, run_bug_detection

router = APIRouter()

ACTIVE_SUPPRESSION_SCOPES = {"project", "global"}


class SuppressionRequest(BaseModel):
    issue_type: str = Field(
        ..., min_length=1, max_length=200, description="Issue type to suppress"
    )
    line: int | None = Field(
        default=None, gt=0, description="Issue line number if known"
    )
    reason: str = Field(..., min_length=1, description="Reason for the suppression")
    scope: str = Field(default="project", description="Suppression scope")

    @field_validator("issue_type")
    @classmethod
    def validate_issue_type(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("issue_type must not be empty")
        return stripped

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be empty")
        return stripped

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"project", "global"}:
            raise ValueError("scope must be 'project' or 'global'")
        return normalized


def _suppression_matches(issue: dict, suppression: Suppression) -> bool:
    if suppression.scope not in ACTIVE_SUPPRESSION_SCOPES:
        return False
    if issue.get("type") != suppression.issue_type:
        return False
    return suppression.line is None or issue.get("line") == suppression.line


def _filter_suppressed_issues(
    issues: list[dict], suppressions: list[Suppression]
) -> list[dict]:
    if not issues or not suppressions:
        return issues

    return [
        issue
        for issue in issues
        if not any(
            _suppression_matches(issue, suppression) for suppression in suppressions
        )
    ]


@router.post(
    "/",
    response_model=DebuggingResponse,
    summary="Detect bugs and code issues",
    description=(
        "Runs **40+ static-analysis pattern checks** across Python, JavaScript, TypeScript, Java, and C++.\n\n"
        "Each detected issue includes:\n"
        "- The **bug pattern name** (e.g. `ZeroDivisionError`, `bare except`, `innerHTML XSS`)\n"
        "- The **exact line number** where it occurs\n"
        "- A **code snippet** of the offending line\n"
        "- A **concrete fix suggestion**\n"
        "- A **severity level**: `error`, `warning`, or `info`\n\n"
        "When no issues are found, `clean` is `true` and `issues` is an empty list.\n\n"
        "**Rate limited** to 30 requests/minute per IP."
    ),
    responses={
        200: {"description": "Analysis completed successfully."},
        422: {
            "description": "Validation error — `code` is missing, empty, or exceeds 50,000 characters."
        },
        429: {
            "description": "Rate limit exceeded — maximum 30 requests/minute per IP. Check the `Retry-After` header."
        },
        500: {"description": "Internal server error."},
    },
)
async def debug(req: CodeRequest, db: Session = Depends(get_db)):
    Base.metadata.create_all(bind=db.get_bind())

    lang = detect_language(req.code, req.language)
    issues = run_bug_detection(req.code, lang)

    try:
        suppressions = db.execute(select(Suppression)).scalars().all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load suppressions",
        ) from exc

    issues = _filter_suppressed_issues(issues, list(suppressions))
    errors = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warning")
    infos = sum(1 for i in issues if i["severity"] == "info")
    return {
        "issues": issues,
        "summary": (
            f"Found {len(issues)} issue(s): {errors} error(s), {warnings} warning(s), {infos} info."
            if issues
            else "✅ No issues detected!"
        ),
        "clean": len(issues) == 0,
        "error_count": errors,
        "warning_count": warnings,
        "info_count": infos,
        "code": req.code,
    }


@router.post("/suppress", summary="Suppress a debug finding")
async def suppress_issue(req: SuppressionRequest, db: Session = Depends(get_db)):
    Base.metadata.create_all(bind=db.get_bind())

    suppression = Suppression(
        issue_type=req.issue_type,
        line=req.line,
        reason=req.reason,
        scope=req.scope,
    )

    try:
        db.add(suppression)
        db.commit()
        db.refresh(suppression)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not persist suppression",
        ) from exc

    return {
        "success": True,
        "message": "Issue suppressed",
        "issue_type": req.issue_type,
        "line": req.line,
        "scope": req.scope,
    }
