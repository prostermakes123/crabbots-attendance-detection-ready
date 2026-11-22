"""System, dashboard and demo-data endpoints."""

from __future__ import annotations

import platform
import time
from pathlib import Path

import cv2
import fastapi
import numpy as np
from fastapi import APIRouter, Depends, HTTPException

from .. import __version__
from ..core.config import CONFIG
from ..db import database as db
from ..runtime import get_pipeline, models_present, runtime_info
from ..services import attendance as attendance_service
from ..services import images as image_utils
from ..services import members as members_service
from ..services import sessions as sessions_service
from ..services.gallery import GALLERY
from . import enrollment as enrollment_service
from .deps import pipeline_or_503, require_admin
from ..services.pipeline import RecognitionPipeline

router = APIRouter(prefix="/api", tags=["system"])
STARTED_AT = time.time()

DEMO_DIR = CONFIG.data_dir / "demo_faces"


@router.get("/health")
def health():
    db_ok = True
    db_error = None
    try:
        db.query_one("SELECT 1 AS ok")
    except Exception as exc:  # pragma: no cover
        db_ok = False
        db_error = str(exc)
    info = runtime_info()
    return {
        "status": "ok" if db_ok else "degraded",
        "version": __version__,
        "uptime_seconds": round(time.time() - STARTED_AT, 1),
        "database": {"ok": db_ok, "error": db_error},
        "models": info,
        "gallery": {"members": GALLERY.member_count, "embeddings": GALLERY.embedding_count},
    }


@router.get("/system/info")
def system_info():
    settings = db.get_settings()
    return {
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "fastapi": fastapi.__version__,
        "models": runtime_info(),
        "gallery": {"members": GALLERY.member_count, "embeddings": GALLERY.embedding_count},
        "admin_protected": bool(CONFIG.admin_token),
        "db_path": str(CONFIG.db_path),
        "settings": settings,
        "demo_available": DEMO_DIR.is_dir() and any(DEMO_DIR.glob("*.jpg")),
    }


@router.get("/dashboard")
def dashboard():
    return attendance_service.dashboard_stats()


@router.get("/demo/status")
def demo_status():
    demo_members = db.query_one("SELECT COUNT(*) AS c FROM members WHERE is_demo=1")["c"]
    demo_attendance = db.query_one("SELECT COUNT(*) AS c FROM attendance WHERE is_demo=1")["c"]
    images = sorted(p.name for p in DEMO_DIR.glob("*.jpg")) if DEMO_DIR.is_dir() else []
    return {
        "demo_members": int(demo_members),
        "demo_attendance": int(demo_attendance),
        "demo_images": images,
        "ready": len(images) > 0,
    }


@router.post("/demo/seed", dependencies=[Depends(require_admin)])
def seed_demo(pipeline: RecognitionPipeline = Depends(pipeline_or_503)):
    """Enrol every JPG in data/demo_faces as a clearly-labelled demo member."""
    if not DEMO_DIR.is_dir():
        raise HTTPException(
            status_code=400,
            detail="No demo faces found. Run `python scripts/fetch_demo_faces.py` first.",
        )
    images = sorted(DEMO_DIR.glob("*.jpg")) + sorted(DEMO_DIR.glob("*.png"))
    if not images:
        raise HTTPException(
            status_code=400,
            detail="No demo faces found. Run `python scripts/fetch_demo_faces.py` first.",
        )
    session = sessions_service.create_session("Demo session", is_demo=True)
    created, skipped = [], []
    for path in images:
        name = path.stem.replace("_", " ").strip()
        existing = members_service.name_exists(name)
        if existing:
            skipped.append({"name": name, "reason": "already exists"})
            continue
        try:
            image = image_utils.decode_image_bytes(path.read_bytes(), max_mb=25)
            member = enrollment_service.enroll(
                pipeline, image, name=name, consent=True, is_demo=True,
                force_duplicate_name=True, notes="Public-domain demo portrait",
            )
            created.append({"id": member["id"], "name": member["name"]})
        except enrollment_service.EnrollmentError as exc:
            skipped.append({"name": name, "reason": exc.message})
        except Exception as exc:  # noqa: BLE001
            skipped.append({"name": name, "reason": str(exc)})
    db.audit("demo.seed", "demo", session["id"], "Operator", {"created": created, "skipped": skipped})
    return {"session": session, "created": created, "skipped": skipped}


@router.delete("/demo", dependencies=[Depends(require_admin)])
def purge_demo():
    demo_members = [r["id"] for r in db.query_all("SELECT id FROM members WHERE is_demo=1")]
    with db.transaction() as conn:
        conn.execute("DELETE FROM attendance WHERE is_demo=1")
        conn.execute("DELETE FROM sessions WHERE is_demo=1")
        conn.execute("DELETE FROM members WHERE is_demo=1")
    for member_id in demo_members:
        GALLERY.remove_member(member_id)
        thumb = CONFIG.data_dir / "thumbnails" / f"{member_id}.jpg"
        thumb.unlink(missing_ok=True)
    db.audit("demo.purge", "demo", None, "Operator", {"members": len(demo_members)})
    return {"purged_members": len(demo_members)}
