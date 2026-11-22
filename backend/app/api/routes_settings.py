"""Settings API with range validation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.config import CONFIG
from ..db import database as db
from .deps import require_admin

router = APIRouter(prefix="/api/settings", tags=["settings"])

BOUNDS: dict[str, tuple[float, float]] = {
    "recognition_threshold": (0.10, 0.95),
    "recognition_margin": (0.0, 0.50),
    "detector_score_threshold": (0.30, 0.95),
    "min_face_size_px": (20, 400),
    "track_iou_threshold": (0.05, 0.90),
    "track_max_age_frames": (1, 120),
    "track_min_hits": (1, 30),
    "evidence_window": (1, 60),
    "evidence_consistency": (0.30, 1.0),
    "attendance_cooldown_seconds": (0, 86400),
    "processing_width": (320, 1920),
    "target_fps": (1, 30),
    "enroll_min_face_ratio": (0.03, 0.90),
    "enroll_blur_threshold": (0, 500),
    "enroll_min_brightness": (0, 255),
    "enroll_max_brightness": (0, 255),
    "duplicate_similarity": (0.20, 0.95),
    "max_upload_mb": (1, 50),
}

BOOLEAN_KEYS = {"attendance_require_session", "store_thumbnails", "retain_unknown_events"}
STRING_KEYS = {"operator_name"}


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


@router.get("")
def get_settings():
    values = db.get_settings()
    return {
        "values": values,
        "defaults": db.DEFAULT_SETTINGS,
        "bounds": BOUNDS,
        "admin_protected": bool(CONFIG.admin_token),
        "boolean_keys": sorted(BOOLEAN_KEYS),
        "string_keys": sorted(STRING_KEYS),
    }


@router.put("", dependencies=[Depends(require_admin)])
def update_settings(payload: SettingsUpdate):
    clean: dict[str, Any] = {}
    allowed = BOOLEAN_KEYS | STRING_KEYS | set(BOUNDS)
    unknown = sorted(set(payload.values) - allowed)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown setting(s): {', '.join(unknown)}")
    for key, value in payload.values.items():
        if key in BOOLEAN_KEYS:
            clean[key] = bool(value)
            continue
        if key in STRING_KEYS:
            if not isinstance(value, str) or len(value) > 80:
                raise HTTPException(status_code=400, detail=f"{key} must be a string of at most 80 characters.")
            clean[key] = value.strip() or "Operator"
            continue
        if key in BOUNDS:
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{key} must be numeric.") from None
            low, high = BOUNDS[key]
            if not low <= number <= high:
                raise HTTPException(
                    status_code=400, detail=f"{key} must be between {low} and {high}."
                )
            clean[key] = number

    merged = {**db.get_settings(), **clean}
    if merged["recognition_threshold"] + merged["recognition_margin"] > 1.0:
        raise HTTPException(status_code=400, detail="Threshold + margin cannot exceed 1.0.")
    if merged["enroll_min_brightness"] > merged["enroll_max_brightness"]:
        raise HTTPException(status_code=400, detail="Minimum brightness cannot exceed maximum brightness.")

    try:
        updated = db.set_settings(clean)
    except (TypeError, ValueError, OverflowError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.audit("settings.update", "settings", None, updated.get("operator_name"), {"changed": clean})
    return {"values": updated, "changed": clean}


@router.post("/reset", dependencies=[Depends(require_admin)])
def reset_settings():
    updated = db.set_settings(dict(db.DEFAULT_SETTINGS))
    db.audit("settings.reset", "settings", None, updated.get("operator_name"), {})
    return {"values": updated}
