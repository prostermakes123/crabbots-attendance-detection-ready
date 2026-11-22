"""Attendance sessions.

A session is one CrabBots meeting/event. Attendance is unique per member per
session, which is the strongest possible duplicate guard, and an additional
time-based cooldown protects against re-admission across sessions.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from ..db import database as db
from ..core.logging import get_logger

log = get_logger("sessions")


def _row_to_dict(row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def get_active_session() -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM sessions WHERE status = 'active' ORDER BY created_at DESC LIMIT 1")
    return _row_to_dict(row) if row else None


def list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    rows = db.query_all(
        """SELECT s.*,
                  (SELECT COUNT(*) FROM attendance a
                    WHERE a.session_id = s.id AND a.status = 'present') AS present_count
           FROM sessions s ORDER BY s.created_at DESC LIMIT ?""",
        (int(limit),),
    )
    return [_row_to_dict(r) for r in rows]


def create_session(name: str | None = None, is_demo: bool = False, start: bool = True) -> dict[str, Any]:
    now = db.utcnow_iso()
    session_id = f"ses_{uuid.uuid4().hex[:12]}"
    label = (name or "").strip() or f"CrabBots session · {datetime.now().strftime('%d %b %Y %H:%M')}"
    with db.transaction() as conn:
        if start:
            conn.execute(
                "UPDATE sessions SET status='ended', ended_at=? WHERE status='active'", (now,)
            )
        conn.execute(
            """INSERT INTO sessions(id, name, status, created_at, started_at, is_demo, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, label, "active" if start else "created", now, now if start else None,
             int(is_demo), None),
        )
    db.audit("session.create", "session", session_id, None, {"name": label, "started": start})
    log.info("session created %s (%s)", session_id, label)
    return get_session(session_id)  # type: ignore[return-value]


def get_session(session_id: str) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
    return _row_to_dict(row) if row else None


def ensure_active_session() -> dict[str, Any]:
    session = get_active_session()
    if session:
        return session
    return create_session()


def start_session(session_id: str) -> dict[str, Any]:
    now = db.utcnow_iso()
    with db.transaction() as conn:
        conn.execute("UPDATE sessions SET status='ended', ended_at=? WHERE status='active'", (now,))
        conn.execute(
            "UPDATE sessions SET status='active', started_at=?, ended_at=NULL WHERE id=?",
            (now, session_id),
        )
    db.audit("session.start", "session", session_id, None, {})
    return get_session(session_id)  # type: ignore[return-value]


def end_session(session_id: str) -> dict[str, Any]:
    now = db.utcnow_iso()
    with db.transaction() as conn:
        conn.execute(
            "UPDATE sessions SET status='ended', ended_at=? WHERE id=? AND status='active'",
            (now, session_id),
        )
    db.audit("session.end", "session", session_id, None, {})
    return get_session(session_id)  # type: ignore[return-value]


def session_counts(session_id: str | None) -> dict[str, int]:
    if not session_id:
        return {"present": 0, "unknown": 0}
    present = db.query_one(
        "SELECT COUNT(*) AS c FROM attendance WHERE session_id=? AND status='present'", (session_id,)
    )["c"]
    unknown = db.query_one(
        "SELECT COUNT(DISTINCT track_id) AS c FROM unknown_events WHERE session_id=?", (session_id,)
    )["c"]
    return {"present": int(present), "unknown": int(unknown or 0)}
