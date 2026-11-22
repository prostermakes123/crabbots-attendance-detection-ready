from pathlib import Path

import cv2
import numpy as np
import pytest

from backend.app.services.detector import FaceDetector, annotate_detections

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "faces"


def make_haar_detector(tmp_path: Path) -> FaceDetector:
    return FaceDetector(tmp_path / "missing-yunet.onnx", allow_haar_fallback=True)


def test_falls_back_to_bundled_haar_and_detects_fixture_face(tmp_path):
    detector = make_haar_detector(tmp_path)
    image_path = FIXTURES / "Jack_Hathaway.jpg"
    image = cv2.imread(str(image_path))

    detections = detector.detect(image)

    assert detector.backend == "haar"
    assert len(detections) >= 1
    detection = detections[0]
    x, y, width, height = detection.bbox
    assert 0 <= x < image.shape[1]
    assert 0 <= y < image.shape[0]
    assert width > 20 and height > 20
    assert detection.score is None
    assert not detection.landmarks_valid


def test_downscaled_detection_maps_box_back_to_original_coordinates(tmp_path):
    detector = make_haar_detector(tmp_path)
    image = cv2.imread(str(FIXTURES / "Jack_Hathaway.jpg"))

    detections = detector.detect_resized(image, max_width=960)

    # At the reduced resolution the foreground portrait is detected without
    # the small false positive on a suit detail seen at full source size.
    assert len(detections) == 1
    x, y, width, height = detections[0].bbox
    assert x > 500 and y > 200
    assert width > 200 and height > 200


def test_haar_detector_supports_grayscale_and_bgra(tmp_path):
    detector = make_haar_detector(tmp_path)
    image = cv2.imread(str(FIXTURES / "Sophie_Adenot.jpg"))

    assert len(detector.detect(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))) >= 1
    assert len(detector.detect(cv2.cvtColor(image, cv2.COLOR_BGR2BGRA))) >= 1


def test_rejects_bad_threshold(tmp_path):
    detector = make_haar_detector(tmp_path)
    image = cv2.imread(str(FIXTURES / "Jack_Hathaway.jpg"))
    with pytest.raises(ValueError, match="threshold"):
        detector.detect(image, score_threshold=1.5)


def test_rejects_non_uint8_input(tmp_path):
    detector = make_haar_detector(tmp_path)
    with pytest.raises(ValueError, match="uint8"):
        detector.detect(np.zeros((100, 100, 3), dtype=np.float32))


def test_haar_detections_cannot_be_used_for_sface_alignment(tmp_path):
    detector = make_haar_detector(tmp_path)
    image = cv2.imread(str(FIXTURES / "Jack_Hathaway.jpg"))
    detection = detector.detect(image)[0]
    with pytest.raises(ValueError, match="landmarks"):
        detection.as_yunet_row()


def test_annotation_returns_new_image(tmp_path):
    detector = make_haar_detector(tmp_path)
    image = cv2.imread(str(FIXTURES / "Jack_Hathaway.jpg"))
    detections = detector.detect(image)
    annotated = annotate_detections(image, detections)

    assert annotated.shape == image.shape
    assert annotated.dtype == np.uint8
    assert not np.shares_memory(annotated, image)
