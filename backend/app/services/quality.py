"""Image quality assessment for enrolment and recognition.

These are cheap, explainable heuristics (no extra model): sharpness, exposure,
face size, and landmark-based pose. They gate enrolment so a blurry or tiny
photo cannot poison the gallery.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from .detector import Detection

ALIGN_SIZE = 112


def _laplacian_variance(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _pose_metrics(det: Detection) -> dict[str, float]:
    """Rough yaw/roll from YuNet's 5 landmarks (no 3D model needed)."""
    lm = det.landmarks
    right_eye, left_eye, nose = lm[0], lm[1], lm[2]
    eye_dist = float(np.linalg.norm(left_eye - right_eye)) or 1.0
    eye_mid = (left_eye + right_eye) / 2.0
    yaw_ratio = abs(float(nose[0] - eye_mid[0])) / eye_dist
    dy = float(left_eye[1] - right_eye[1])
    dx = float(left_eye[0] - right_eye[0]) or 1e-6
    roll_deg = abs(float(np.degrees(np.arctan2(dy, dx))))
    if roll_deg > 90:  # landmarks are ordered; keep the acute angle
        roll_deg = 180 - roll_deg
    return {"yaw_ratio": yaw_ratio, "roll_deg": roll_deg, "eye_distance": eye_dist}


def assess_face(
    image_bgr: np.ndarray,
    detection: Detection,
    settings: dict[str, Any],
) -> dict[str, Any]:
    h, w = image_bgr.shape[:2]
    x, y, bw, bh = detection.bbox
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(w, int(x + bw)), min(h, int(y + bh))
    crop = image_bgr[y0:y1, x0:x1]
    if crop.size == 0:
        return {"passed": False, "checks": [], "metrics": {}, "summary": "Face crop is empty."}

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray_aligned = cv2.resize(gray, (ALIGN_SIZE, ALIGN_SIZE), interpolation=cv2.INTER_AREA)
    sharpness = _laplacian_variance(gray_aligned)
    brightness = float(gray.mean())
    face_ratio = float(bw) / float(w)
    pose = _pose_metrics(detection)

    blur_threshold = float(settings.get("enroll_blur_threshold", 45.0))
    min_ratio = float(settings.get("enroll_min_face_ratio", 0.12))
    min_bright = float(settings.get("enroll_min_brightness", 35.0))
    max_bright = float(settings.get("enroll_max_brightness", 232.0))

    checks: list[dict[str, Any]] = []

    def add(check_id: str, label: str, passed: bool, value: str, hint: str, severity: str = "fail") -> None:
        checks.append(
            {
                "id": check_id,
                "label": label,
                "passed": bool(passed),
                "value": value,
                "hint": hint,
                "severity": severity,
            }
        )

    add("sharpness", "Sharpness", sharpness >= blur_threshold,
        f"{sharpness:.0f}", f"Hold still and use a sharper photo (min {blur_threshold:.0f}).")
    add("exposure", "Lighting", min_bright <= brightness <= max_bright,
        f"{brightness:.0f}", "Use even, front-facing light; avoid deep shadow or glare.")
    add("face_size", "Face size", face_ratio >= min_ratio,
        f"{face_ratio * 100:.0f}% of width", f"Move closer: the face should fill at least {min_ratio * 100:.0f}% of the frame.")
    add("resolution", "Face resolution", bw >= 80 and bh >= 80,
        f"{int(bw)}x{int(bh)} px", "Use a higher-resolution photograph.")
    add("pose", "Frontal pose", pose["yaw_ratio"] <= 0.38 and pose["roll_deg"] <= 22,
        f"yaw {pose['yaw_ratio']:.2f}, roll {pose['roll_deg']:.0f}°",
        "Face the camera more directly for enrolment.", severity="warn")

    failed = [c for c in checks if not c["passed"] and c["severity"] == "fail"]
    warned = [c for c in checks if not c["passed"] and c["severity"] == "warn"]
    passed = not failed

    if passed and not warned:
        summary = "Excellent enrolment photo."
    elif passed:
        summary = "Usable photo, but " + ", ".join(c["label"].lower() for c in warned) + " could be better."
    else:
        summary = "Photo rejected: " + "; ".join(c["hint"] for c in failed)

    return {
        "passed": passed,
        "checks": checks,
        "metrics": {
            "sharpness": round(sharpness, 1),
            "brightness": round(brightness, 1),
            "face_ratio": round(face_ratio, 4),
            "face_width": round(float(bw), 1),
            "face_height": round(float(bh), 1),
            "yaw_ratio": round(pose["yaw_ratio"], 3),
            "roll_deg": round(pose["roll_deg"], 1),
        },
        "summary": summary,
        "warnings": [c["id"] for c in warned],
    }
