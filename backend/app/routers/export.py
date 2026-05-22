from __future__ import annotations

import csv
import json
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, HTTPException, Response
from ..schemas import ExportRequest

router = APIRouter()


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _build_csv(data: list[dict]) -> str:
    if not data:
        return ""

    columns = sorted({key for item in data if isinstance(item, dict) for key in item.keys()})
    output = StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(columns)
    for item in data:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="CSV export requires an array of objects")
        writer.writerow([_csv_value(item.get(col)) for col in columns])
    return output.getvalue()


def _build_filename(kind: str, fmt: str) -> str:
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return f"qyverixai-{kind}-{now}.{fmt}"


@router.post("/history/{fmt}")
def export_history(fmt: str, payload: ExportRequest) -> Response:
    if fmt not in ("json", "csv"):
        raise HTTPException(status_code=400, detail="Unsupported export format")

    filename = _build_filename("history", fmt)
    if fmt == "json":
        body = json.dumps(payload.data, indent=2, ensure_ascii=False)
        return Response(
            body,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    body = _build_csv(payload.data)
    return Response(
        body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/favorites/{fmt}")
def export_favorites(fmt: str, payload: ExportRequest) -> Response:
    if fmt not in ("json", "csv"):
        raise HTTPException(status_code=400, detail="Unsupported export format")

    filename = _build_filename("favorites", fmt)
    if fmt == "json":
        body = json.dumps(payload.data, indent=2, ensure_ascii=False)
        return Response(
            body,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    body = _build_csv(payload.data)
    return Response(
        body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
