"""Run the CrabBots face detector on a still image or webcam.

Examples:
  python scripts/detect_faces.py --image tests/fixtures/faces/Jack_Hathaway.jpg
  python scripts/detect_faces.py --image photo.jpg --output data/annotated.jpg
  python scripts/detect_faces.py --camera 0 --seconds 20 --output data/camera-test.mp4

YuNet is used when its ONNX weights are installed. Otherwise the command uses
OpenCV's bundled Haar cascade as a detection-only fallback. Haar has no facial
landmarks and is not used for SFace identity recognition.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.config import CONFIG  # noqa: E402
from backend.app.services.detector import FaceDetector, annotate_detections  # noqa: E402


def _detector(threshold: float) -> FaceDetector:
    return FaceDetector(CONFIG.yunet_path, threshold, allow_haar_fallback=True)


def run_image(
    detector: FaceDetector, image_path: Path, output_path: Path | None, processing_width: int
) -> int:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"Could not read image: {image_path}")
    started = time.perf_counter()
    detections = detector.detect_resized(image, max_width=processing_width)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    print(json.dumps({
        "image": str(image_path),
        "backend": detector.backend,
        "face_count": len(detections),
        "latency_ms": round(elapsed_ms, 2),
        "detections": [d.as_dict() for d in detections],
    }, indent=2))
    annotated = annotate_detections(image, detections)
    destination = output_path or (ROOT / "data" / "face-detection-result.jpg")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destination), annotated):
        raise SystemExit(f"Could not write annotated image: {destination}")
    print(f"Annotated image saved to: {destination}")
    return len(detections)


def run_camera(
    detector: FaceDetector,
    camera_index: int,
    duration_seconds: float,
    output_path: Path,
    display: bool,
    processing_width: int,
) -> int:
    capture = cv2.VideoCapture(camera_index)
    if not capture.isOpened():
        raise SystemExit(
            f"Could not open camera {camera_index}. Check camera permissions or try --camera 1."
        )

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if not 1 <= fps <= 120:
        fps = 20.0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        capture.release()
        raise SystemExit(f"Could not create output video: {output_path}")

    started = time.monotonic()
    frame_count = 0
    total_faces = 0
    max_faces = 0
    try:
        while time.monotonic() - started < duration_seconds:
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            detections = detector.detect_resized(frame, max_width=processing_width)
            annotated = annotate_detections(frame, detections)
            writer.write(annotated)
            frame_count += 1
            total_faces += len(detections)
            max_faces = max(max_faces, len(detections))
            if display:
                try:
                    cv2.imshow("CrabBots - Face Detection (press Q to stop)", annotated)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                except cv2.error as exc:
                    raise SystemExit(
                        "Live display is unavailable in this OpenCV build. "
                        "Run without --display and inspect the saved MP4, or install "
                        "opencv-python (not opencv-python-headless)."
                    ) from exc
    finally:
        capture.release()
        writer.release()
        if display:
            cv2.destroyAllWindows()

    elapsed = max(time.monotonic() - started, 1e-6)
    print(json.dumps({
        "camera": camera_index,
        "backend": detector.backend,
        "frames_processed": frame_count,
        "elapsed_seconds": round(elapsed, 2),
        "processing_fps": round(frame_count / elapsed, 2),
        "total_face_detections": total_faces,
        "max_faces_in_frame": max_faces,
        "output_video": str(output_path),
    }, indent=2))
    return total_faces


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect faces using YuNet (or Haar fallback).")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path, help="Path to an image to analyse")
    source.add_argument("--camera", type=int, help="Webcam device index, usually 0")
    parser.add_argument("--output", type=Path, help="Annotated image/video output path")
    parser.add_argument("--seconds", type=float, default=20.0, help="Camera capture duration (default: 20)")
    parser.add_argument("--threshold", type=float, default=0.7, help="YuNet score threshold in (0, 1]")
    parser.add_argument("--processing-width", type=int, default=960, help="Downscale wider frames to this width (default: 960)")
    parser.add_argument("--display", action="store_true", help="Show a live preview; requires GUI-enabled OpenCV")
    args = parser.parse_args()

    if not 0.0 < args.threshold <= 1.0:
        parser.error("--threshold must be in (0, 1].")
    if args.processing_width < 8:
        parser.error("--processing-width must be at least 8.")
    if args.camera is not None and args.seconds <= 0:
        parser.error("--seconds must be positive.")
    if args.display and args.camera is None:
        parser.error("--display can only be used with --camera.")

    detector = _detector(args.threshold)
    print(f"Face detector backend: {detector.backend}")
    if detector.backend == "haar":
        print("Note: YuNet weights are not installed; using frontal-face Haar fallback.")
        print("For YuNet, run: python scripts/download_models.py --detection-only")

    if args.image:
        run_image(detector, args.image, args.output, args.processing_width)
    else:
        output = args.output or (ROOT / "data" / "face-detection-camera.mp4")
        run_camera(detector, args.camera, args.seconds, output, args.display, args.processing_width)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
