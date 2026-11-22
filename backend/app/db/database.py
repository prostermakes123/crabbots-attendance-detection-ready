"""SQLite access layer.

One connection per thread (WAL mode) keeps the WebSocket worker and the HTTP
threadpool from stepping on each other, while still allowing simple synchronous
code everywhere.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from ..core.config import CONFIG
from ..core.logging import get_logger

log = get_logger("db")

_local = threading.local()
_SCHEMA_PATH = Path(__file__).with_name("schema.sql")

DEFAULT_SETTINGS: dict[str, Any] = {
    # Recognition
    "recognition_threshold": 0.42,     # cosine similarity required to accept
    "recognition_margin": 0.06,        # top1 - top2 gap required (ambiguity guard)
    "detector_score_threshold": 0.70,
    "min_face_size_px": 48,            # minimum face width at processing resolution
    # Tracking / temporal evidence
    "track_iou_threshold": 0.30,
    "track_max_age_frames": 24,
    "track_min_hits": 3,
    "evidence_window": 12,
    "evidence_consistency": 0.60,      # share of votes the winning identity needs
    # Attendance
    "attendance_cooldown_seconds": 300,
    "attendance_require_session": True,
    # Capture / performance
    "processing_width": 640,
    "target_fps": 8,
    # Enrollment quality gates
    "enroll_min_face_ratio": 0.12,
    "enroll_blur_threshold": 45.0,
    "enroll_min_brightness": 35.0,
    "enroll_max_brightness": 232.0,
    "duplicate_similarity": 0.55,
    "max_upload_mb": 12,
    # Privacy
    "store_thumbnails": True,
    "retain_unknown_events": True,
    "operator_name": "Operator",
}

_SETTING_TYPES = {k: type(v) for k, v in DEFAULT_SETTINGS.items()}


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def get_conn() -> sqlite3.Connection:
    path = str(CONFIG.db_path)
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "path", None) != path:
        conn = _connect(CONFIG.db_path)
        _local.conn = conn
        _local.path = path
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def query_all(sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return list(get_conn().execute(sql, params).fetchall())


def query_one(sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    return get_conn().execute(sql, params).fetchone()


def execute(sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
    conn = get_conn()
    cur = conn.execute(sql, params)
    conn.commit()
    return cur


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def init_db() -> None:
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_conn()
    conn.executescript(schema)
    conn.commit()

    now = utcnow_iso()
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), now),
        )
    conn.commit()
    log.info("database ready at %s", CONFIG.db_path)


def get_settings() -> dict[str, Any]:
    stored = {row["key"]: json.loads(row["value"]) for row in query_all("SELECT key, value FROM settings")}
    merged = dict(DEFAULT_SETTINGS)
    merged.update({k: v for k, v in stored.items() if k in DEFAULT_SETTINGS})
    return merged


def set_settings(updates: dict[str, Any]) -> dict[str, Any]:
    now = utcnow_iso()
    clean: dict[str, Any] = {}
    for key, value in updates.items():
        if key not in DEFAULT_SETTINGS:
            continue
        expected = _SETTING_TYPES[key]
        if expected is bool:
            if not isinstance(value, bool):
                raise ValueError(f"Setting {key} must be a boolean.")
        elif expected is int:
            if isinstance(value, bool):
                raise ValueError(f"Setting {key} must be an integer.")
            value = int(value)
        elif expected is float:
            if isinstance(value, bool):
                raise ValueError(f"Setting {key} must be numeric.")
            value = float(value)
        elif expected is str:
            if not isinstance(value, str):
                raise ValueError(f"Setting {key} must be a string.")
        clean[key] = value
    with transaction() as conn:
        for key, value in clean.items():
            conn.execute(
                """INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (key, json.dumps(value), now),
            )
    return get_settings()


def audit(action: str, entity_type: str, entity_id: str | None, actor: str | None, detail: dict[str, Any] | None = None) -> None:
    execute(
        "INSERT INTO audit_log(timestamp, action, entity_type, entity_id, actor, detail) VALUES (?,?,?,?,?,?)",
        (utcnow_iso(), action, entity_type, entity_id, actor, json.dumps(detail or {})),
    )
