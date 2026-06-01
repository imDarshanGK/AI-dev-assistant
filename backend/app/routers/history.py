"""
History router — save, retrieve, search and delete analysis history entries.
"""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..services import database

router = APIRouter()


class HistorySaveRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50000)
    language: str
    score: int | None = None
    issue_count: int | None = None


class HistoryEntry(BaseModel):
    id: int
    code_hash: str
    language: str
    score: int | None
    issue_count: int | None
    timestamp: str
    code_preview: str


@router.post("/", response_model=dict, status_code=201)
async def save_history(body: HistorySaveRequest):
    entry_id = await database.save_entry(
        code=body.code,
        language=body.language,
        score=body.score,
        issue_count=body.issue_count,
    )
    return {"id": entry_id, "status": "saved"}


@router.get("/", response_model=list[HistoryEntry])
async def get_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return await database.get_entries(limit=limit, offset=offset)


@router.get("/search", response_model=list[HistoryEntry])
async def search_history(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
):
    return await database.search_entries(q=q, limit=limit)


@router.delete("/{entry_id}", response_model=dict)
async def delete_history(entry_id: int):
    deleted = await database.delete_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="History entry not found.")
    return {"id": entry_id, "status": "deleted"}
