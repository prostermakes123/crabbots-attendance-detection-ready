"""Standalone face-detection endpoints (no identity recognition required)."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, UploadFile

from ..core.config import CONFIG
from ..db import database as db
from ..runtime import ModelNotReady, get_detector
from ..services import images as image_utils
from ..services.detector import annotate_detections
from .routes_members import _read_upload

router = APIRouter(prefix="/api/detection", tags=["face detection"])


@router.get("/status")
def detection_status():
    try:
        detector = get_detector()
    except ModelNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "ready": True,
        "backend": detector.backend,
        "landmarks_available": detector.backend == "yunet",
        "model_file_present": CONFIG.yunet_path.is_file(),
        "note": (
            "YuNet provides bounding boxes, five landmarks, and a detection score."
            if detector.backend == "yunet"
            else "Haar fallback provides frontal-face boxes only; it is not suitable for SFace alignment."
        ),
    }


@router.post("/photo")
async def detect_photo(file: UploadFile):
    """Detect faces in an uploaded photo and return boxes plus an annotated preview."""
    settings = db.get_settings()
    raw = await _read_upload(file, float(settings["max_upload_mb"]))
    try:
        image = image_utils.decode_image_bytes(raw, max_mb=float(settings["max_upload_mb"]))
    except image_utils.ImageValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        detector = get_detector()
    except ModelNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    started = time.perf_counter()
    detections = detector.detect_resized(
        image, max_width=int(settings.get("processing_width", 640))
    )
    annotated = annotate_detections(image, detections)
    preview = image_utils.resize_max_width(annotated, 1280)
    return {
        "backend": detector.backend,
        "face_count": len(detections),
        "image_width": int(image.shape[1]),
        "image_height": int(image.shape[0]),
        "latency_ms": round((time.perf_counter() - started) * 1000.0, 2),
        "detections": [d.as_dict() for d in detections],
        "annotated_image": image_utils.encode_jpeg_base64(preview, quality=85),
    }
