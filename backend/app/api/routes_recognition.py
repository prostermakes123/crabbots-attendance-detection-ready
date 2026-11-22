"""Recognition endpoints for uploaded photos and videos."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..core.config import CONFIG
from ..db import database as db
from ..services import images as image_utils
from ..services import sessions as sessions_service
from ..services.pipeline import RecognitionPipeline
from .deps import pipeline_or_503
from .routes_members import _read_upload

router = APIRouter(prefix="/api/recognize", tags=["recognition"])


@router.post("/photo")
async def recognize_photo(
    file: UploadFile = File(...),
    record: bool = Form(False),
    session_id: str | None = Form(None),
    pipeline: RecognitionPipeline = Depends(pipeline_or_503),
):
    settings = db.get_settings()
    raw = await _read_upload(file, float(settings["max_upload_mb"]))
    try:
        image = image_utils.decode_image_bytes(raw, max_mb=float(settings["max_upload_mb"]))
    except image_utils.ImageValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if record and not session_id:
        session_id = sessions_service.ensure_active_session()["id"]
    return pipeline.process_photo(
        image, session_id=session_id, record=record, source=file.filename or "upload"
    )


@router.post("/video")
async def recognize_video(
    file: UploadFile = File(...),
    record: bool = Form(True),
    session_id: str | None = Form(None),
    pipeline: RecognitionPipeline = Depends(pipeline_or_503),
):
    settings = db.get_settings()
    suffix = Path(file.filename or "clip.mp4").suffix or ".mp4"
    if suffix.lower() not in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
        raise HTTPException(status_code=415, detail="Unsupported video format.")
    tmp_dir = CONFIG.data_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = 200 * 1024 * 1024
    total = 0
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=tmp_dir) as handle:
            tmp_path = handle.name
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(status_code=413, detail="Video exceeds the 200 MB limit.")
                handle.write(chunk)
    except Exception:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
        raise
    try:
        if record and not session_id:
            session_id = sessions_service.ensure_active_session()["id"]
        return pipeline.process_video(
            tmp_path, session_id=session_id, record=record, source=file.filename or "video"
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass
