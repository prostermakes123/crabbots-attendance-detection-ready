"""Attendance engine: deduplication, cooldown, audit trail."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..core.logging import get_logger
from ..db import database as db
from . import sessions as sessions_service
from .gallery import GALLERY

log = get_logger("attendance")


def _parse(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def _row_to_dict(row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def record_attendance(
    member_id: str,
    member_name: str,
    confidence: float,
    method: str,
    session_id: str | None = None,
    track_id: int | None = None,
    source: str | None = None,
    is_demo: bool = False,
    actor: str | None = None,
) -> dict[str, Any]:
    """Record attendance once. Returns {created, reason, record}."""
    settings = db.get_settings()

    if session_id:
        existing = sessions_service.get_session(session_id)
        if not existing or existing["status"] != "active":
            session_id = None
    if not session_id:
        session = sessions_service.get_active_session()
        if session is None and settings.get("attendance_require_session", True):
            session = sessions_service.ensure_active_session()
        session_id = session["id"] if session else None

    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat(timespec="milliseconds")

    # Cross-session cooldown: stops a person being re-added moments after a
    # previous session ended, or by a second camera.
    cooldown = int(settings.get("attendance_cooldown_seconds", 300))
    if cooldown > 0:
        last = db.query_one(
            """SELECT timestamp FROM attendance
               WHERE member_id=? AND status='present' ORDER BY timestamp DESC LIMIT 1""",
            (member_id,),
        )
        if last:
            elapsed = (now_dt - _parse(last["timestamp"])).total_seconds()
            if elapsed < cooldown:
                return {
                    "created": False,
                    "reason": "cooldown",
                    "retry_after_seconds": int(cooldown - elapsed),
                    "record": None,
                }

    record_id = f"att_{uuid.uuid4().hex[:12]}"
    try:
        with db.transaction() as conn:
            conn.execute(
                """INSERT INTO attendance
                   (id, member_id, member_name, session_id, timestamp, confidence, method,
                    track_id, source, status, is_demo)
                   VALUES (?,?,?,?,?,?,?,?,?,'present',?)""",
                (record_id, member_id, member_name, session_id, now, float(confidence), method,
                 track_id, source, int(is_demo)),
            )
    except sqlite3.IntegrityError:
        # Unique (session_id, member_id) guard: already present in this session.
        return {"created": False, "reason": "already_in_session", "record": None}

    db.audit("attendance.record", "attendance", record_id, actor,
             {"member_id": member_id, "method": method, "confidence": round(float(confidence), 4)})
    log.info("attendance %s -> %s (%s, %.3f)", record_id, member_name, method, confidence)
    return {"created": True, "reason": "created", "record": get_attendance(record_id)}


def get_attendance(record_id: str) -> dict[str, Any] | None:
    row = db.query_one(
        """SELECT a.*, s.name AS session_name FROM attendance a
           LEFT JOIN sessions s ON s.id = a.session_id WHERE a.id=?""",
        (record_id,),
    )
    return _row_to_dict(row) if row else None


def list_attendance(
    session_id: str | None = None,
    member_id: str | None = None,
    query: str | None = None,
    status: str | None = "present",
    limit: int = 200,
    offset: int = 0,
    date: str | None = None,
) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []
    if session_id:
        where.append("a.session_id = ?")
        params.append(session_id)
    if member_id:
        where.append("a.member_id = ?")
        params.append(member_id)
    if status:
        where.append("a.status = ?")
        params.append(status)
    if query:
        where.append("(a.member_name LIKE ? OR a.source LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])
    if date:
        where.append("substr(a.timestamp, 1, 10) = ?")
        params.append(date)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    total = db.query_one(f"SELECT COUNT(*) AS c FROM attendance a {clause}", tuple(params))["c"]
    rows = db.query_all(
        f"""SELECT a.*, s.name AS session_name FROM attendance a
            LEFT JOIN sessions s ON s.id = a.session_id
            {clause} ORDER BY a.timestamp DESC LIMIT ? OFFSET ?""",
        tuple(params) + (int(limit), int(offset)),
    )
    return {"total": int(total), "items": [_row_to_dict(r) for r in rows]}


def remove_attendance(record_id: str, reason: str, operator: str) -> dict[str, Any] | None:
    now = db.utcnow_iso()
    with db.transaction() as conn:
        conn.execute(
            """UPDATE attendance SET status='removed', removed_at=?, removed_reason=?, removed_by=?
               WHERE id=? AND status='present'""",
            (now, reason, operator, record_id),
        )
    db.audit("attendance.remove", "attendance", record_id, operator, {"reason": reason})
    return get_attendance(record_id)


def record_unknown(
    session_id: str | None,
    track_id: int | None,
    confidence: float,
    source: str | None = None,
) -> None:
    if not db.get_settings().get("retain_unknown_events", True):
        return
    db.execute(
        """INSERT INTO unknown_events(session_id, timestamp, track_id, confidence, source)
           VALUES (?,?,?,?,?)""",
        (session_id, db.utcnow_iso(), track_id, float(confidence), source),
    )


def dashboard_stats() -> dict[str, Any]:
    settings = db.get_settings()
    active = sessions_service.get_active_session()
    members = db.query_one("SELECT COUNT(*) AS c FROM members")["c"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    present_today = db.query_one(
        "SELECT COUNT(DISTINCT member_id) AS c FROM attendance WHERE status='present' AND substr(timestamp,1,10)=?",
        (today,),
    )["c"]
    attendance_today = db.query_one(
        "SELECT COUNT(*) AS c FROM attendance WHERE status='present' AND substr(timestamp,1,10)=?",
        (today,),
    )["c"]
    unknown_today = db.query_one(
        "SELECT COUNT(*) AS c FROM unknown_events WHERE substr(timestamp,1,10)=?", (today,)
    )["c"]
    session_present = 0
    if active:
        session_present = db.query_one(
            "SELECT COUNT(*) AS c FROM attendance WHERE session_id=? AND status='present'", (active["id"],)
        )["c"]
    recent = db.query_all(
        """SELECT a.id, a.member_id, a.member_name, a.timestamp, a.confidence, a.method,
                  a.session_id, a.status, s.name AS session_name
           FROM attendance a LEFT JOIN sessions s ON s.id=a.session_id
           WHERE a.status='present' ORDER BY a.timestamp DESC LIMIT 8"""
    )
    recent_unknown = db.query_all(
        "SELECT * FROM unknown_events ORDER BY timestamp DESC LIMIT 5"
    )
    return {
        "members": int(members),
        "present_today": int(present_today),
        "attendance_today": int(attendance_today),
        "unknown_today": int(unknown_today),
        "session_present": int(session_present),
        "active_session": active,
        "recent": [_row_to_dict(r) for r in recent],
        "recent_unknown": [_row_to_dict(r) for r in recent_unknown],
        "gallery_members": GALLERY.member_count,
        "thresholds": {
            "recognition_threshold": settings["recognition_threshold"],
            "recognition_margin": settings["recognition_margin"],
        },
    }


def export_rows(session_id: str | None = None) -> list[dict[str, Any]]:
    where = "WHERE a.status='present'"
    params: tuple[Any, ...] = ()
    if session_id:
        where += " AND a.session_id=?"
        params = (session_id,)
    rows = db.query_all(
        f"""SELECT a.timestamp, a.member_name, a.confidence, a.method, a.track_id,
                   a.source, s.name AS session_name, a.id
            FROM attendance a LEFT JOIN sessions s ON s.id=a.session_id
            {where} ORDER BY a.timestamp ASC""",
        params,
    )
    return [_row_to_dict(r) for r in rows]
