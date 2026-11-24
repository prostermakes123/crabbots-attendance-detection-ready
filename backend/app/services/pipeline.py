"""End-to-end recognition pipeline.

    frame -> resize -> detect -> align/embed -> gallery match -> track -> vote
          -> attendance (deduplicated) -> annotated response

The pipeline is deliberately synchronous and stateless apart from the tracker
and gallery it is given, which makes it easy to unit test and to reuse for live
frames, uploaded photos and uploaded videos.
"""

from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from ..core.logging import get_logger
from ..db import database as db
from . import attendance as attendance_service
from . import images as image_utils
from .detector import Detection, FaceDetector
from .gallery import FaceGallery, MatchResult
from .recognizer import FaceRecognizer
from .tracker import MultiFaceTracker, Track

log = get_logger("pipeline")

COLOR_RECOGNIZED = (110, 205, 80)
COLOR_UNKNOWN = (70, 70, 235)
COLOR_PENDING = (60, 190, 235)
COLOR_TEXT = (255, 255, 255)


class RecognitionPipeline:
    def __init__(self, detector: FaceDetector, recognizer: FaceRecognizer, gallery: FaceGallery) -> None:
        self.detector = detector
        self.recognizer = recognizer
        self.gallery = gallery
        self._settings_cache: tuple[float, dict[str, Any]] | None = None
        self._live_recognition_toggle = False

    # -- settings ----------------------------------------------------------
    def settings(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._settings_cache and now - self._settings_cache[0] < 1.0:
            return self._settings_cache[1]
        values = db.get_settings()
        self._settings_cache = (now, values)
        return values

    # -- core --------------------------------------------------------------
    def _detect_and_embed(
        self, image_bgr: np.ndarray, settings: dict[str, Any], *, embed: bool = True,
        multi_scale: bool = True,
    ) -> tuple[list[Detection], list[np.ndarray]]:
        h, w = image_bgr.shape[:2]
        target_w = int(settings.get("processing_width", 800))
        scale = min(1.0, target_w / float(w)) if w else 1.0
        work = image_bgr
        if scale < 0.999:
            work = cv2.resize(image_bgr, (max(1, int(w * scale)), max(1, int(h * scale))),
                              interpolation=cv2.INTER_AREA)
        raw = self.detector.detect(
            work,
            score_threshold=float(settings.get("detector_score_threshold", 0.7)),
            multi_scale=multi_scale,
        )
        min_face = float(settings.get("min_face_size_px", 48))
        kept: list[Detection] = []
        for det in raw:
            if det.bbox[2] < min_face or det.bbox[3] < min_face:
                continue
            kept.append(det.scaled(1.0 / scale) if scale < 0.999 else det)
        if not embed:
            return kept, []
        embeddings: list[np.ndarray] = []
        usable: list[Detection] = []
        for det in kept:
            try:
                embeddings.append(self.recognizer.embed(image_bgr, det))
                usable.append(det)
            except Exception as exc:  # degenerate crop, out-of-bounds landmarks
                log.debug("embedding failed for detection: %s", exc)
        return usable, embeddings

    def _match_all(self, embeddings: list[np.ndarray], settings: dict[str, Any]) -> list[MatchResult]:
        threshold = float(settings.get("recognition_threshold", 0.42))
        margin = float(settings.get("recognition_margin", 0.06))
        return [self.gallery.match(vec, threshold, margin) for vec in embeddings]

    def process_frame(
        self,
        image_bgr: np.ndarray,
        tracker: MultiFaceTracker,
        session_id: str | None,
        source: str | None = None,
        record: bool = True,
        method: str = "live",
    ) -> dict[str, Any]:
        started = time.perf_counter()
        settings = self.settings()
        # Keep detection/tracking responsive every frame, but run the heavier
        # SFace embedding + gallery search every second live frame.
        # New tracks remain pending until the next recognition frame.
        if method == "live":
            self._live_recognition_toggle = not self._live_recognition_toggle
            recognize_this_frame = self._live_recognition_toggle
        else:
            recognize_this_frame = True
        detections, embeddings = self._detect_and_embed(
            image_bgr, settings, embed=recognize_this_frame,
            multi_scale=(method != "live"),
        )
        matches = self._match_all(embeddings, settings) if recognize_this_frame else [None] * len(detections)
        tracks = tracker.update(detections, embeddings, matches, settings)

        events: list[dict[str, Any]] = []
        unknown_events: list[dict[str, Any]] = []

        for track in tracks:
            if track.session_id != session_id:
                track.session_id = session_id
                track.attendance_recorded = False
            if record and track.status == "recognized" and track.member_id and not track.attendance_recorded:
                result = attendance_service.record_attendance(
                    member_id=track.member_id,
                    member_name=track.member_name or "Unknown",
                    confidence=track.confidence,
                    method=method,
                    session_id=session_id,
                    track_id=track.id,
                    source=source,
                )
                track.attendance_recorded = True
                if result["created"]:
                    events.append(result["record"])
            elif record and track.status == "unknown" and not track.unknown_logged:
                attendance_service.record_unknown(session_id, track.id, track.best_similarity, source)
                track.unknown_logged = True
                unknown_events.append({"track_id": track.id, "confidence": round(track.best_similarity, 4)})

        payload = [self._detection_payload(track) for track in tracks if track.missed == 0]
        payload.sort(key=lambda d: (d["status"] != "recognized", -d["confidence"]))
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        return {
            "detections": payload,
            "faces": len(detections),
            "tracks": len(tracks),
            "attendance_created": events,
            "unknown_events": unknown_events,
            "latency_ms": round(elapsed_ms, 1),
            "image_width": int(image_bgr.shape[1]),
            "image_height": int(image_bgr.shape[0]),
            "session_id": session_id,
            "settings": {
                "recognition_threshold": settings["recognition_threshold"],
                "recognition_margin": settings["recognition_margin"],
            },
        }

    @staticmethod
    def _detection_payload(track: Track) -> dict[str, Any]:
        x, y, w, h = track.bbox
        return {
            "track_id": track.id,
            "bbox": [round(x, 1), round(y, 1), round(w, 1), round(h, 1)],
            "status": track.status,
            "member_id": track.member_id,
            "name": track.member_name,
            "confidence": round(float(track.confidence), 4),
            "best_similarity": round(float(track.best_similarity), 4),
            "hits": track.hits,
            "evidence": len(track.evidence),
            "attendance_recorded": track.attendance_recorded,
            "head_pose": [round(v, 1) for v in track.head_pose] if track.head_pose is not None else None,
        }

    # -- single photo ------------------------------------------------------
    def process_photo(
        self,
        image_bgr: np.ndarray,
        session_id: str | None = None,
        record: bool = False,
        source: str | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        settings = self.settings()
        detections, embeddings = self._detect_and_embed(image_bgr, settings)
        matches = self._match_all(embeddings, settings)
        results: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        for det, match in zip(detections, matches):
            item = {
                "bbox": [round(v, 1) for v in det.bbox],
                "detection_score": round(det.score, 4),
                "status": "recognized" if match.accepted else "unknown",
                "member_id": match.member_id if match.accepted else None,
                "name": match.name if match.accepted else None,
                "confidence": round(float(match.similarity), 4),
                "match_reason": match.reason,
            }
            if match.accepted and record and match.member_id:
                result = attendance_service.record_attendance(
                    member_id=match.member_id,
                    member_name=match.name or "Unknown",
                    confidence=match.similarity,
                    method="photo",
                    session_id=session_id,
                    source=source,
                )
                if result["created"]:
                    events.append(result["record"])
                item["attendance"] = result
            results.append(item)
        annotated = self.annotate(image_bgr, results)
        return {
            "detections": results,
            "faces": len(results),
            "multiple_faces": len(results) > 1,
            "attendance_created": events,
            "annotated_image": image_utils.encode_jpeg_base64(annotated),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "image_width": int(image_bgr.shape[1]),
            "image_height": int(image_bgr.shape[0]),
        }

    # -- drawing -----------------------------------------------------------
    def annotate(self, image_bgr: np.ndarray, detections: list[dict[str, Any]]) -> np.ndarray:
        out = image_bgr.copy()
        h, w = out.shape[:2]
        thickness = max(2, int(round(min(w, h) / 320)))
        font_scale = max(0.5, min(1.1, w / 1100))
        for item in detections:
            x, y, bw, bh = item["bbox"]
            status = item.get("status", "unknown")
            color = COLOR_RECOGNIZED if status == "recognized" else COLOR_UNKNOWN
            x0, y0, x1, y1 = int(x), int(y), int(x + bw), int(y + bh)
            cv2.rectangle(out, (x0, y0), (x1, y1), color, thickness)
            if status == "recognized":
                label = f"{item.get('name') or 'Member'} {item.get('confidence', 0) * 100:.0f}%"
            else:
                label = "Unknown person"
            (tw, th), base = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
            ly = max(th + base + 4, y0)
            cv2.rectangle(out, (x0, ly - th - base - 6), (x0 + tw + 10, ly), color, -1)
            cv2.putText(out, label, (x0 + 5, ly - base - 2), cv2.FONT_HERSHEY_SIMPLEX,
                        font_scale, COLOR_TEXT, thickness, cv2.LINE_AA)
        return out

    # -- video -------------------------------------------------------------
    def process_video(
        self,
        path: str,
        session_id: str | None = None,
        record: bool = True,
        source: str | None = None,
        max_seconds: float = 60.0,
    ) -> dict[str, Any]:
        settings = self.settings()
        target_fps = max(1, int(settings.get("target_fps", 8)))
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise ValueError("Could not open the uploaded video.")
        native_fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        if not np.isfinite(native_fps) or native_fps <= 0 or native_fps > 240:
            native_fps = 25.0
        max_seconds = float(max_seconds)
        if not np.isfinite(max_seconds) or max_seconds <= 0:
            cap.release()
            raise ValueError("max_seconds must be a positive finite number.")
        stride = max(1, int(round(native_fps / target_fps)))
        max_frames = max(1, int(native_fps * max_seconds))
        tracker = MultiFaceTracker()
        events: list[dict[str, Any]] = []
        seen: dict[str, dict[str, Any]] = {}
        unknown_tracks: set[int] = set()
        annotated_samples: list[str] = []
        processed = 0
        frame_no = 0
        started = time.perf_counter()
        latencies: list[float] = []
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if frame_no >= max_frames:
                    break
                if frame_no % stride == 0:
                    result = self.process_frame(
                        frame, tracker, session_id, source=source, record=record, method="video"
                    )
                    processed += 1
                    latencies.append(result["latency_ms"])
                    for record_item in result["attendance_created"]:
                        events.append(record_item)
                        seen[record_item["member_id"]] = {
                            "member_id": record_item["member_id"],
                            "name": record_item["member_name"],
                            "confidence": record_item["confidence"],
                            "timestamp": record_item["timestamp"],
                            "track_id": record_item["track_id"],
                        }
                    for unknown in result["unknown_events"]:
                        unknown_tracks.add(unknown["track_id"])
                    if processed % max(1, int(target_fps * 2)) == 0 and len(annotated_samples) < 6:
                        annotated_samples.append(
                            image_utils.encode_jpeg_base64(self.annotate(frame, result["detections"]), quality=72)
                        )
                frame_no += 1
        finally:
            cap.release()

        duration = frame_no / native_fps if native_fps else 0.0
        return {
            "frames_processed": processed,
            "video_frames": frame_no,
            "video_duration_seconds": round(duration, 2),
            "sample_fps": round(processed / duration, 2) if duration > 0 else 0,
            "recognized": list(seen.values()),
            "attendance_created": events,
            "unknown_tracks": len(unknown_tracks),
            "annotated_frames": annotated_samples,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
            "wall_time_seconds": round(time.perf_counter() - started, 2),
        }
