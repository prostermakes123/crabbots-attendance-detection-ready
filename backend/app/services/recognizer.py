"""Face embedding extraction (OpenCV SFace, Apache-2.0).

SFace is a MobileFaceNet trained with a sigmoid-constrained hypersphere loss.
It produces 128-D embeddings and ships with OpenCV's alignment helper, so the
whole pipeline (detect -> align -> embed -> cosine) stays inside OpenCV and
ONNX Runtime: no compilation, no GPU requirement.
"""

from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np

from ..core.logging import get_logger
from .detector import Detection

log = get_logger("recognizer")

EMBEDDING_DIM = 128


class FaceRecognizer:
    def __init__(self, model_path: Path) -> None:
        if not Path(model_path).is_file():
            raise FileNotFoundError(
                f"SFace model not found at {model_path}. Run: python scripts/download_models.py"
            )
        self._lock = threading.Lock()
        self._recognizer = cv2.FaceRecognizerSF.create(str(model_path), "")
        log.info("SFace loaded from %s", model_path)

    def align(self, image_bgr: np.ndarray, detection: Detection) -> np.ndarray:
        with self._lock:
            return self._recognizer.alignCrop(image_bgr, detection.as_yunet_row())

    def embed(self, image_bgr: np.ndarray, detection: Detection) -> np.ndarray:
        """Return an L2-normalised float32 embedding of shape (128,)."""
        with self._lock:
            aligned = self._recognizer.alignCrop(image_bgr, detection.as_yunet_row())
            raw = self._recognizer.feature(aligned)
        vector = np.asarray(raw, dtype=np.float32).reshape(-1)
        if vector.size != EMBEDDING_DIM:
            raise ValueError(f"Unexpected embedding dimension: expected {EMBEDDING_DIM}, got {vector.size}.")
        if not np.all(np.isfinite(vector)):
            raise ValueError("Embedding contains non-finite values.")
        norm = float(np.linalg.norm(vector))
        if not np.isfinite(norm) or norm < 1e-9:
            raise ValueError("Degenerate embedding (zero or non-finite norm)")
        return vector / norm

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity for L2-normalised vectors (dot product)."""
        return float(np.dot(a, b))


def cosine_matrix(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Similarities between one normalised query and a (N, D) normalised matrix."""
    if matrix.size == 0:
        return np.zeros((0,), dtype=np.float32)
    return matrix @ query
