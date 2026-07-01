"""API router for finding comments."""

from fastapi import APIRouter, HTTPException

from app.schemas import (
    CommentCreate,
    CommentResponse,
)
from app.services.database import (
    save_comment,
    get_comments,
)

router = APIRouter(
    prefix="/share",
    tags=["Comments"],
)


@router.post(
    "/{share_id}/findings/{finding_id}/comments",
    response_model=CommentResponse,
)
async def add_comment(
    share_id: str,
    finding_id: str,
    comment: CommentCreate,
):
    try:
        record = await save_comment(
            share_id=share_id,
            finding_id=finding_id,
            text=comment.text,
            author=comment.author,
            parent_id=comment.parent_id,
        )

        return record

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to save comment",
        )


@router.get(
    "/{share_id}/comments",
    response_model=list[CommentResponse],
)
async def fetch_comments(
    share_id: str,
):
    try:
        return await get_comments(share_id)

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch comments",
        )
