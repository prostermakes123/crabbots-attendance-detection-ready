"""Process-wide singletons and lazy model loading.

Models are loaded lazily so that tests which only exercise the database or API
validation do not need the ONNX weights on disk. If a request needs the
pipeline and the weights are missing, the API returns a 503 with the exact
command to fix it.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from .core.config import CONFIG
from .core.logging import get_logger
from .db import database as db
from .services.detector import FaceDetector
from .services.gallery import GALLERY
from .services.pipeline import RecognitionPipeline
from .services.recognizer import FaceRecognizer

log = get_logger("runtime")


class ModelNotReady(RuntimeError):
    pass


@dataclass
class Runtime:
    pipeline: RecognitionPipeline | None = None
    load_error: str | None = None


_state = Runtime()
_lock = threading.Lock()
_detector_only: FaceDetector | None = None
_detector_lock = threading.Lock()


def models_present() -> bool:
    return CONFIG.yunet_path.is_file() and CONFIG.sface_path.is_file()


def get_pipeline() -> RecognitionPipeline:
    if _state.pipeline is not None:
        return _state.pipeline
    with _lock:
        if _state.pipeline is not None:
            return _state.pipeline
        if not models_present():
            raise ModelNotReady(
                "Face models are not installed. Run `python scripts/download_models.py` "
                "and restart the server."
            )
        settings = db.get_settings()
        try:
            detector = FaceDetector(
                CONFIG.yunet_path,
                float(settings["detector_score_threshold"]),
                allow_haar_fallback=False,
            )
            recognizer = FaceRecognizer(CONFIG.sface_path)
        except Exception as exc:  # pragma: no cover - depends on local install
            _state.load_error = str(exc)
            log.exception("failed to load models")
            raise ModelNotReady(f"Could not load face models: {exc}") from exc
        GALLERY.load_from_db()
        _state.pipeline = RecognitionPipeline(detector, recognizer, GALLERY)
        _state.load_error = None
        log.info("recognition pipeline ready")
        return _state.pipeline


def get_detector() -> FaceDetector:
    """Return a detector without requiring the separate SFace recognition model.

    YuNet is preferred. If its ONNX file is not installed, OpenCV's bundled
    Haar cascade provides a lower-capability frontal-face detection fallback.
    """
    global _detector_only
    if _detector_only is not None:
        return _detector_only
    with _detector_lock:
        if _detector_only is not None:
            return _detector_only
        settings = db.get_settings()
        try:
            _detector_only = FaceDetector(
                CONFIG.yunet_path,
                float(settings["detector_score_threshold"]),
                allow_haar_fallback=True,
            )
        except Exception as exc:  # pragma: no cover - depends on local OpenCV install
            log.exception("failed to load standalone face detector")
            raise ModelNotReady(f"Could not initialize face detector: {exc}") from exc
        return _detector_only


def reset_runtime() -> None:
    """Test helper: drop cached models so the next request rebuilds them."""
    global _state, _detector_only
    with _lock:
        _state = Runtime()
    with _detector_lock:
        _detector_only = None


def runtime_info() -> dict:
    return {
        "models_present": models_present(),
        "detection_model_present": CONFIG.yunet_path.is_file(),
        "detection_backend": _detector_only.backend if _detector_only is not None else None,
        "pipeline_ready": _state.pipeline is not None,
        "load_error": _state.load_error,
        "yunet": CONFIG.yunet_path.name,
        "sface": CONFIG.sface_path.name,
    }
