"""Attendance history, manual corrections and CSV export."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..db import database as db
from ..services import attendance as attendance_service

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


class RemovalRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=300)
    operator: str | None = Field(default=None, max_length=80)


@router.get("")
def list_attendance(
    session_id: str | None = None,
    member_id: str | None = None,
    q: str | None = Query(default=None, max_length=80),
    status: str | None = "present",
    date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = 200,
    offset: int = 0,
):
    return attendance_service.list_attendance(
        session_id=session_id,
        member_id=member_id,
        query=q,
        status=status,
        limit=min(max(limit, 1), 1000),
        offset=max(offset, 0),
        date=date,
    )


@router.delete("/{record_id}")
def remove_attendance(record_id: str, payload: RemovalRequest):
    record = attendance_service.get_attendance(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found.")
    if record["status"] == "removed":
        raise HTTPException(status_code=409, detail="Record is already removed.")
    settings = db.get_settings()
    operator = (payload.operator or settings.get("operator_name") or "Operator").strip()
    return attendance_service.remove_attendance(record_id, payload.reason, operator)


@router.get("/export.csv")
def export_csv(session_id: str | None = None):
    rows = attendance_service.export_rows(session_id=session_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["record_id", "timestamp_utc", "member_name", "confidence", "method", "track_id", "source", "session"]
    )
    for row in rows:
        writer.writerow(
            [
                row["id"],
                row["timestamp"],
                row["member_name"],
                f"{row['confidence']:.4f}",
                row["method"],
                row["track_id"] if row["track_id"] is not None else "",
                row["source"] or "",
                row["session_name"] or "",
            ]
        )
    filename = f"crabbots_attendance_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/audit")
def audit_trail(limit: int = 100):
    rows = db.query_all(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (min(max(limit, 1), 500),)
    )
    return {"items": [{k: row[k] for k in row.keys()} for row in rows]}
