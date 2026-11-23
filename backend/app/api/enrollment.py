"""Enrolment workflow: validate -> detect -> quality gate -> duplicate gate -> save."""

from __future__ import annotations

import base64
from typing import Any

import cv2
import numpy as np

from ..db import database as db
from ..services import images as image_utils
from ..services import members as members_service
from ..services.quality import assess_face
from ..services.pipeline import RecognitionPipeline


class EnrollmentError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _preview(image: np.ndarray, detections: list[dict[str, Any]], pipeline: RecognitionPipeline) -> str:
    annotated = pipeline.annotate(image, detections)
    preview = image_utils.resize_max_width(annotated, 720)
    return image_utils.encode_jpeg_base64(preview, quality=80)


def analyze(pipeline: RecognitionPipeline, image: np.ndarray) -> dict[str, Any]:
    """Analyse an enrolment photo without persisting anything."""
    settings = pipeline.settings()
    detections, embeddings = pipeline._detect_and_embed(image, settings)  # noqa: SLF001 - same package

    if not detections:
        raise EnrollmentError(
            "no_face",
            "No face was detected. Use a clear, well-lit, front-facing photograph.",
            details={"preview_image": _preview(image, [], pipeline)},
        )
    if len(detections) > 1:
        boxes = [
            {"bbox": [round(v, 1) for v in d.bbox], "score": round(d.score, 3)} for d in detections
        ]
        raise EnrollmentError(
            "multiple_faces",
            f"{len(detections)} faces were detected. Enrolment photos must contain exactly one person.",
            details={
                "faces": boxes,
                "preview_image": _preview(
                    image,
                    [{"bbox": b["bbox"], "status": "unknown"} for b in boxes],
                    pipeline,
                ),
            },
        )

    detection = detections[0]
    quality = assess_face(image, detection, settings)
    if not quality["passed"]:
        raise EnrollmentError(
            "low_quality",
            quality["summary"],
            details={
                "quality": quality,
                "preview_image": _preview(
                    image,
                    [{"bbox": [round(v, 1) for v in detection.bbox], "status": "unknown"}],
                    pipeline,
                ),
            },
        )

    embedding = embeddings[0]
    dup_threshold = float(settings.get("duplicate_similarity", 0.55))
    candidate = pipeline.gallery.match(embedding, threshold=dup_threshold, margin=0.0)
    duplicate = None
    if candidate.similarity >= dup_threshold and candidate.member_id:
        duplicate = {
            "member_id": candidate.member_id,
            "name": candidate.name,
            "similarity": round(float(candidate.similarity), 4),
        }

    thumbnail = members_service.make_thumbnail(image, detection)
    return {
        "ok": True,
        "face_count": 1,
        "detection": detection.as_dict(),
        "quality": quality,
        "duplicate": duplicate,
        "preview_image": _preview(
            image,
            [{"bbox": [round(v, 1) for v in detection.bbox], "status": "recognized", "name": "Enrolment photo", "confidence": 1.0}],
            pipeline,
        ),
        "thumbnail": "data:image/jpeg;base64," + base64.b64encode(thumbnail).decode("ascii"),
        "thresholds": {
            "duplicate_similarity": dup_threshold,
            "recognition_threshold": settings["recognition_threshold"],
        },
    }


def enroll(
    pipeline: RecognitionPipeline,
    image: np.ndarray,
    name: str,
    consent: bool,
    additional_images: list[np.ndarray] | None = None,
    is_demo: bool = False,
    force_duplicate: bool = False,
    force_duplicate_name: bool = False,
    notes: str | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    """Enroll one person using a primary image plus optional camera-angle captures."""
    images = [image, *(additional_images or [])]
    if len(images) > 6:
        raise EnrollmentError("too_many_images", "Use at most six face images per member.")

    settings = pipeline.settings()
    reports = [analyze(pipeline, candidate) for candidate in images]
    duplicates = [report["duplicate"] for report in reports if report["duplicate"]]
    if duplicates and not force_duplicate:
        dup = max(duplicates, key=lambda item: item["similarity"])
        raise EnrollmentError(
            "duplicate_face",
            f"This face already looks like {dup['name']} ({dup['similarity'] * 100:.0f}% similar). "
            "Confirm only if it is a different person.",
            status_code=409,
            details={"duplicate": dup},
        )

    vectors: list[np.ndarray] = []
    primary_detection = None
    for candidate in images:
        detections, embeddings = pipeline._detect_and_embed(candidate, settings)  # noqa: SLF001
        if len(detections) != 1 or len(embeddings) != 1:
            raise EnrollmentError("invalid_scan", "Each enrollment image must contain exactly one clear face.")
        if primary_detection is None:
            primary_detection = detections[0]
        vectors.append(embeddings[0])

    thumbnail = members_service.make_thumbnail(image, primary_detection)
    try:
        member = members_service.create_member(
            name=name,
            vectors=vectors,
            consent=consent,
            is_demo=is_demo,
            notes=notes,
            thumbnail_jpeg=thumbnail,
            force_duplicate_name=force_duplicate_name,
            actor=actor,
        )
    except members_service.DuplicateNameError as exc:
        raise EnrollmentError(
            "duplicate_name",
            str(exc),
            status_code=409,
            details={"name": exc.name},
        ) from exc
    except ValueError as exc:
        raise EnrollmentError("invalid_input", str(exc), status_code=400) from exc

    member["preview_image"] = reports[0]["preview_image"]
    member["quality"] = reports[0]["quality"]
    member["enrollment_images"] = len(images)
    return member
