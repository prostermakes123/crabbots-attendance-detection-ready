"""Face detection using YuNet, with an OpenCV Haar fallback for detection-only use.

YuNet is the preferred detector. It returns five landmarks required by SFace
for alignment. When the YuNet ONNX file is not installed, the standalone
detection workflow can still run with OpenCV's bundled frontal-face Haar
cascade. Haar detections intentionally have no landmarks or calibrated score
and must not be passed into the SFace recognition pipeline.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..core.logging import get_logger

log = get_logger("detector")


@dataclass
class Detection:
    bbox: tuple[float, float, float, float]  # x, y, w, h
    landmarks: np.ndarray  # (5, 2) float32; zeros when unavailable
    score: float | None
    landmarks_valid: bool = True

    @property
    def width(self) -> float:
        return self.bbox[2]

    @property
    def height(self) -> float:
        return self.bbox[3]

    def as_yunet_row(self) -> np.ndarray:
        """Return the 15-value row OpenCV SFace expects for alignCrop."""
        if not self.landmarks_valid or self.score is None:
            raise ValueError("This detector did not produce landmarks required for face alignment.")
        x, y, w, h = self.bbox
        row = np.concatenate([[x, y, w, h], self.landmarks.reshape(-1), [self.score]])
        return row.astype(np.float32)

    def scaled(self, factor: float) -> "Detection":
        if not np.isfinite(factor) or factor <= 0:
            raise ValueError("Scale factor must be a positive finite number.")
        x, y, w, h = self.bbox
        return Detection(
            bbox=(x * factor, y * factor, w * factor, h * factor),
            landmarks=self.landmarks * factor,
            score=self.score,
            landmarks_valid=self.landmarks_valid,
        )

    def as_dict(self) -> dict:
        x, y, w, h = self.bbox
        return {
            "bbox": [round(x, 1), round(y, 1), round(w, 1), round(h, 1)],
            "score": round(float(self.score), 4) if self.score is not None else None,
            "landmarks": self.landmarks.round(1).tolist() if self.landmarks_valid else None,
        }


class FaceDetector:
    """Thread-safe face detector. YuNet is preferred; Haar is detection-only fallback."""

    def __init__(
        self,
        model_path: Path,
        score_threshold: float = 0.7,
        *,
        allow_haar_fallback: bool = False,
    ) -> None:
        threshold = float(score_threshold)
        if not np.isfinite(threshold) or not 0.0 < threshold <= 1.0:
            raise ValueError("Face detection score threshold must be in (0, 1].")
        self._lock = threading.Lock()
        self._score_threshold = threshold
        self._detector = None
        self._cascade = None
        self.backend = "yunet"

        path = Path(model_path)
        if path.is_file():
            try:
                self._detector = cv2.FaceDetectorYN.create(
                    str(path), "", (320, 320), self._score_threshold, 0.3, 5000
                )
                log.info("YuNet loaded from %s", path)
                return
            except Exception as exc:
                if not allow_haar_fallback:
                    raise RuntimeError(f"Could not initialize YuNet model at {path}: {exc}") from exc
                log.warning("YuNet initialization failed; using Haar fallback: %s", exc)
        elif not allow_haar_fallback:
            raise FileNotFoundError(
                f"YuNet model not found at {path}. Run: python scripts/download_models.py --detection-only"
            )

        if not allow_haar_fallback:
            raise FileNotFoundError(f"No face detector model available at {path}.")
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(str(cascade_path))
        if cascade.empty():
            raise RuntimeError(
                "YuNet is unavailable and OpenCV's bundled Haar cascade could not be loaded."
            )
        self._cascade = cascade
        self.backend = "haar"
        log.warning("Using OpenCV Haar fallback from %s (frontal-face detection only)", cascade_path)

    @staticmethod
    def _validate_image(image_bgr: np.ndarray) -> np.ndarray:
        if not isinstance(image_bgr, np.ndarray) or image_bgr.size == 0:
            raise ValueError("Input image is empty or is not a NumPy array.")
        if image_bgr.dtype != np.uint8:
            raise ValueError("Input image must use uint8 pixel values.")
        if image_bgr.ndim == 2:
            return cv2.cvtColor(image_bgr, cv2.COLOR_GRAY2BGR)
        if image_bgr.ndim != 3 or image_bgr.shape[2] not in (3, 4):
            raise ValueError("Input image must be grayscale, BGR, or BGRA.")
        if image_bgr.shape[2] == 4:
            return cv2.cvtColor(image_bgr, cv2.COLOR_BGRA2BGR)
        return image_bgr

    def detect(self, image_bgr: np.ndarray, score_threshold: float | None = None) -> list[Detection]:
        image = self._validate_image(image_bgr)
        h, w = image.shape[:2]
        if h < 8 or w < 8:
            return []

        threshold = self._score_threshold if score_threshold is None else float(score_threshold)
        if not np.isfinite(threshold) or not 0.0 < threshold <= 1.0:
            raise ValueError("Face detection score threshold must be in (0, 1].")

        if self.backend == "haar":
            return self._detect_haar(image)
        return self._detect_yunet(image, threshold)

    def detect_resized(
        self,
        image_bgr: np.ndarray,
        max_width: int = 960,
        score_threshold: float | None = None,
    ) -> list[Detection]:
        """Detect on a downscaled copy for speed and map boxes back to source pixels."""
        if isinstance(max_width, bool) or int(max_width) < 8:
            raise ValueError("Maximum processing width must be at least 8 pixels.")
        image = self._validate_image(image_bgr)
        height, width = image.shape[:2]
        if width <= int(max_width):
            return self.detect(image, score_threshold=score_threshold)
        scale = int(max_width) / float(width)
        resized = cv2.resize(
            image,
            (int(max_width), max(1, int(round(height * scale)))),
            interpolation=cv2.INTER_AREA,
        )
        detections = self.detect(resized, score_threshold=score_threshold)
        return [detection.scaled(1.0 / scale) for detection in detections]

    def _run_yunet(self, image: np.ndarray, threshold: float) -> list[Detection]:
        """Run one YuNet pass and return detections in this image's coordinates."""
        h, w = image.shape[:2]
        with self._lock:
            self._detector.setScoreThreshold(threshold)
            self._detector.setInputSize((w, h))
            _, faces = self._detector.detect(image)
        if faces is None:
            return []
        out: list[Detection] = []
        for row in faces:
            if len(row) < 15 or not np.all(np.isfinite(row[:15])):
                continue
            x, y, bw, bh = (float(v) for v in row[:4])
            if bw <= 1 or bh <= 1:
                continue
            landmarks = row[4:14].reshape(5, 2).astype(np.float32)
            out.append(Detection((x, y, bw, bh), landmarks, float(row[14]), True))
        return out

    @staticmethod
    def _suppress_overlaps(
        detections: list[Detection],
        iou_threshold: float = 0.45,
        containment_threshold: float = 0.80,
    ) -> list[Detection]:
        """Remove duplicate boxes, including differently sized boxes around one face.

        IoU handles ordinary overlapping duplicates. Intersection-over-smaller-area
        also catches a tight box nested inside a looser box, a common outcome when
        the original and enlarged YuNet passes see the same face differently.
        Input priority is preserved so original-resolution landmarks win over
        enlarged-pass duplicates for SFace alignment.
        """
        kept: list[Detection] = []
        for candidate in detections:
            x1, y1, w1, h1 = candidate.bbox
            area1 = w1 * h1
            overlaps = False
            for existing in kept:
                x2, y2, w2, h2 = existing.bbox
                area2 = w2 * h2
                ix1, iy1 = max(x1, x2), max(y1, y2)
                ix2, iy2 = min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)
                intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
                union = area1 + area2 - intersection
                smaller_area = min(area1, area2)
                iou = intersection / union if union > 0 else 0.0
                containment = intersection / smaller_area if smaller_area > 0 else 0.0
                if iou >= iou_threshold or containment >= containment_threshold:
                    overlaps = True
                    break
            if not overlaps:
                kept.append(candidate)
        kept.sort(key=lambda det: det.bbox[2] * det.bbox[3], reverse=True)
        return kept

    def _detect_yunet(self, image: np.ndarray, threshold: float) -> list[Detection]:
        """Use a two-scale image pyramid to recover smaller faces without changing thresholds.

        The enlarged pass is capped to avoid excessive memory use on large uploads.
        Its boxes and landmarks are mapped back to the original image before
        overlap suppression, so downstream SFace alignment receives source pixels.
        """
        h, w = image.shape[:2]
        detections = self._run_yunet(image, threshold)

        # The live pipeline commonly supplies 640px-wide frames. A 1.5x pass
        # preserves more facial detail for people farther from the camera.
        if max(h, w) <= 1280:
            scale = 1.5
            enlarged = cv2.resize(
                image,
                (int(round(w * scale)), int(round(h * scale))),
                interpolation=cv2.INTER_CUBIC,
            )
            enlarged_detections = self._run_yunet(enlarged, threshold)
            detections.extend(det.scaled(1.0 / scale) for det in enlarged_detections)

        return self._suppress_overlaps(detections)

    def _detect_haar(self, image: np.ndarray) -> list[Detection]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        with self._lock:
            boxes = self._cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24), flags=cv2.CASCADE_SCALE_IMAGE
            )
        out = [
            Detection(
                bbox=(float(x), float(y), float(bw), float(bh)),
                landmarks=np.zeros((5, 2), dtype=np.float32),
                score=None,
                landmarks_valid=False,
            )
            for x, y, bw, bh in boxes
        ]
        out.sort(key=lambda d: d.bbox[2] * d.bbox[3], reverse=True)
        return out


def annotate_detections(image_bgr: np.ndarray, detections: list[Detection]) -> np.ndarray:
    """Return a copy of the image with detection boxes and optional landmarks."""
    output = image_bgr.copy()
    for index, detection in enumerate(detections, start=1):
        x, y, width, height = (int(round(value)) for value in detection.bbox)
        cv2.rectangle(output, (x, y), (x + width, y + height), (60, 220, 90), 2)
        label = f"Face {index}"
        if detection.score is not None:
            label += f" {detection.score:.2f}"
        text_y = max(22, y - 8)
        cv2.putText(output, label, (x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (60, 220, 90), 2, cv2.LINE_AA)
        if detection.landmarks_valid:
            for px, py in detection.landmarks:
                cv2.circle(output, (int(round(px)), int(round(py))), 2, (0, 200, 255), -1)
    return output
