"""Member lifecycle: enrolment, listing, deletion, thumbnails.

Biometric policy implemented here:
* embeddings are stored as opaque float32 blobs and are never serialised to API
  responses;
* thumbnails are optional (settings.store_thumbnails) and deleted with the member;
* deleting a member cascades to embeddings and can optionally purge attendance.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import numpy as np

from ..core.config import CONFIG
from ..core.logging import get_logger
from ..db import database as db
from .gallery import GALLERY

log = get_logger("members")

THUMB_DIR = CONFIG.data_dir / "thumbnails"


def _row_to_dict(row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def _public(row) -> dict[str, Any]:
    data = _row_to_dict(row)
    data.pop("thumbnail", None)
    data["has_thumbnail"] = bool(row["thumbnail"])
    return data


def list_members(query: str | None = None) -> list[dict[str, Any]]:
    if query:
        rows = db.query_all(
            """SELECT m.*, (SELECT COUNT(*) FROM embeddings e WHERE e.member_id=m.id) AS embedding_count
               FROM members m WHERE m.name LIKE ? ORDER BY m.created_at DESC""",
            (f"%{query}%",),
        )
    else:
        rows = db.query_all(
            """SELECT m.*, (SELECT COUNT(*) FROM embeddings e WHERE e.member_id=m.id) AS embedding_count
               FROM members m ORDER BY m.created_at DESC"""
        )
    return [_public(r) for r in rows]


def get_member(member_id: str) -> dict[str, Any] | None:
    row = db.query_one(
        """SELECT m.*, (SELECT COUNT(*) FROM embeddings e WHERE e.member_id=m.id) AS embedding_count
           FROM members m WHERE m.id=?""",
        (member_id,),
    )
    return _public(row) if row else None


def name_exists(name: str, exclude_id: str | None = None) -> dict[str, Any] | None:
    row = db.query_one(
        "SELECT id, name FROM members WHERE lower(name)=lower(?) AND id IS NOT ?",
        (name.strip(), exclude_id),
    )
    return _row_to_dict(row) if row else None


def save_thumbnail(member_id: str, jpeg_bytes: bytes) -> str | None:
    if not db.get_settings().get("store_thumbnails", True):
        return None
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{member_id}.jpg"
    (THUMB_DIR / filename).write_bytes(jpeg_bytes)
    return filename


def thumbnail_path(member_id: str) -> Path | None:
    row = db.query_one("SELECT thumbnail FROM members WHERE id=?", (member_id,))
    if not row or not row["thumbnail"]:
        return None
    path = THUMB_DIR / row["thumbnail"]
    return path if path.is_file() else None


def create_member(
    name: str,
    vectors: list[np.ndarray],
    consent: bool,
    is_demo: bool = False,
    notes: str | None = None,
    thumbnail_jpeg: bytes | None = None,
    force_duplicate_name: bool = False,
    actor: str | None = None,
) -> dict[str, Any]:
    clean_name = " ".join((name or "").split())
    if len(clean_name) < 2:
        raise ValueError("Name must be at least 2 characters.")
    if len(clean_name) > 80:
        raise ValueError("Name must be 80 characters or fewer.")
    if not consent:
        raise ValueError("Explicit consent is required before storing biometric data.")
    if not vectors:
        raise ValueError("At least one face embedding is required.")

    validated_vectors: list[np.ndarray] = []
    for vector in vectors:
        vec = np.asarray(vector, dtype=np.float32).reshape(-1)
        if vec.size != 128:
            raise ValueError(f"Face embedding must contain 128 values, got {vec.size}.")
        if not np.all(np.isfinite(vec)):
            raise ValueError("Face embedding contains non-finite values.")
        norm = float(np.linalg.norm(vec))
        if norm <= 1e-9:
            raise ValueError("Face embedding has zero magnitude.")
        validated_vectors.append((vec / norm).astype(np.float32))

    if not force_duplicate_name and name_exists(clean_name):
        raise DuplicateNameError(clean_name)

    member_id = f"mem_{uuid.uuid4().hex[:10]}"
    now = db.utcnow_iso()
    store_thumbnail = bool(thumbnail_jpeg and db.get_settings().get("store_thumbnails", True))
    thumb_name = f"{member_id}.jpg" if store_thumbnail else None

    try:
        if store_thumbnail and thumbnail_jpeg:
            THUMB_DIR.mkdir(parents=True, exist_ok=True)
            (THUMB_DIR / thumb_name).write_bytes(thumbnail_jpeg)
        with db.transaction() as conn:
            conn.execute(
                """INSERT INTO members(id, name, created_at, updated_at, consent, consent_at,
                                       is_demo, thumbnail, notes)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (member_id, clean_name, now, now, 1, now, int(is_demo), thumb_name, notes),
            )
            for vec in validated_vectors:
                conn.execute(
                    "INSERT INTO embeddings(member_id, vector, dim, created_at) VALUES (?,?,?,?)",
                    (member_id, vec.tobytes(), int(vec.size), now),
                )
    except Exception:
        if thumb_name:
            (THUMB_DIR / thumb_name).unlink(missing_ok=True)
        raise

    GALLERY.add(member_id, clean_name, validated_vectors)
    db.audit(
        "member.create", "member", member_id, actor,
        {"name": clean_name, "embeddings": len(validated_vectors), "demo": is_demo},
    )
    log.info("member %s enrolled (%d embedding(s))", clean_name, len(validated_vectors))
    return get_member(member_id)  # type: ignore[return-value]


class DuplicateNameError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"A member named '{name}' already exists.")


def delete_member(member_id: str, purge_attendance: bool = False, actor: str | None = None) -> bool:
    member = get_member(member_id)
    if not member:
        return False
    with db.transaction() as conn:
        if purge_attendance:
            conn.execute("DELETE FROM attendance WHERE member_id=?", (member_id,))
        conn.execute("DELETE FROM members WHERE id=?", (member_id,))
    thumb = THUMB_DIR / f"{member_id}.jpg"
    if thumb.is_file():
        try:
            thumb.unlink()
        except OSError:
            pass
    GALLERY.remove_member(member_id)
    db.audit("member.delete", "member", member_id, actor,
             {"name": member["name"], "purged_attendance": purge_attendance})
    log.info("member %s deleted", member["name"])
    return True


def member_vectors(member_id: str) -> list[np.ndarray]:
    rows = db.query_all("SELECT vector, dim FROM embeddings WHERE member_id=?", (member_id,))
    return [np.frombuffer(r["vector"], dtype=np.float32).copy() for r in rows]


def make_thumbnail(image_bgr, detection, size: int = 160) -> bytes:
    """Square JPEG thumbnail cropped around the detected face."""
    import cv2

    h, w = image_bgr.shape[:2]
    x, y, bw, bh = detection.bbox
    cx, cy = x + bw / 2, y + bh / 2
    side = max(bw, bh) * 1.35
    x0 = int(max(0, cx - side / 2))
    y0 = int(max(0, cy - side / 2))
    x1 = int(min(w, cx + side / 2))
    y1 = int(min(h, cy + side / 2))
    crop = image_bgr[y0:y1, x0:x1]
    if crop.size == 0:
        crop = image_bgr
    crop = cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 86])
    if not ok:
        raise ValueError("Could not encode thumbnail")
    return buf.tobytes()
