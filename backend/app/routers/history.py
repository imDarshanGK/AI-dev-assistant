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
    result_json: str | None = None


class HistoryEntry(BaseModel):
    id: int
    code_hash: str
    language: str
    score: int | None
    issue_count: int | None
    timestamp: str
    code_preview: str


class HistoryDetailResponse(BaseModel):
    id: int
    code_hash: str
    language: str
    score: int | None
    issue_count: int | None
    timestamp: str
    code_preview: str
    code: str | None
    result_json: str | None


class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int
    sort_by: str
    order: str


class HistoryResponse(BaseModel):
    items: list[HistoryEntry]
    meta: PaginationMeta


@router.post("/", response_model=dict, status_code=201)
async def save_history(body: HistorySaveRequest):
    entry_id = await database.save_entry(
        code=body.code,
        language=body.language,
        score=body.score,
        issue_count=body.issue_count,
        result_json=body.result_json,
    )
    return {"id": entry_id, "status": "saved"}


@router.get("/search", response_model=list[HistoryEntry])
async def search_history(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=100),
):
    return await database.search_entries(q=q, limit=limit)


@router.get("/", response_model=HistoryResponse)
async def get_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("timestamp", pattern="^(timestamp|score|issue_count|id)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    total = await database.count_entries()
    items = await database.get_entries(
        limit=limit, offset=offset, sort_by=sort_by, order=order
    )
    return {
        "items": items,
        "meta": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
            "order": order,
        },
    }


@router.get("/{entry_id}", response_model=HistoryDetailResponse)
async def get_history_entry(entry_id: int):
    entry = await database.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found.")
    return entry


@router.delete("/", response_model=dict)
async def clear_history():
    await database.clear_entries()
    return {"status": "cleared"}


@router.delete("/{entry_id}", response_model=dict)
async def delete_history(entry_id: int):
    deleted = await database.delete_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="History entry not found.")
    return {"id": entry_id, "status": "deleted"}
