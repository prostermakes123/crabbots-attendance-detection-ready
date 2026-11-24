import numpy as np

from backend.app.services.gallery import FaceGallery
from backend.app.services.pipeline import RecognitionPipeline
from backend.app.services.tracker import MultiFaceTracker, Track


class EmptyDetector:
    def detect(self, *_args, **_kwargs):
        return []


class EmptyRecognizer:
    pass


class FixedTracker:
    def __init__(self, status):
        self.status = status

    def update(self, *_args, **_kwargs):
        track = Track(id=1, bbox=(0, 0, 20, 20), created_frame=1, last_frame=1)
        track.status = self.status
        track.member_id = 'member-1' if self.status == 'recognized' else None
        track.member_name = 'Member One' if self.status == 'recognized' else None
        track.confidence = 0.9
        track.best_similarity = 0.9
        return [track]


def test_record_false_does_not_write_attendance_or_unknown_events(monkeypatch):
    import backend.app.services.pipeline as pipeline_module

    writes = {'attendance': 0, 'unknown': 0}
    monkeypatch.setattr(pipeline_module.attendance_service, 'record_attendance', lambda **_kw: writes.__setitem__('attendance', writes['attendance'] + 1) or {'created': True, 'record': {}})
    monkeypatch.setattr(pipeline_module.attendance_service, 'record_unknown', lambda *_a, **_kw: writes.__setitem__('unknown', writes['unknown'] + 1))

    pipeline = RecognitionPipeline(EmptyDetector(), EmptyRecognizer(), FaceGallery())
    monkeypatch.setattr(pipeline, 'settings', lambda: {
        'processing_width': 640,
        'detector_score_threshold': 0.7,
        'min_face_size_px': 20,
        'recognition_threshold': 0.4,
        'recognition_margin': 0.05,
    })
    image = np.zeros((64, 64, 3), dtype=np.uint8)

    pipeline.process_frame(image, FixedTracker('recognized'), 'session-1', record=False)
    pipeline.process_frame(image, FixedTracker('unknown'), 'session-1', record=False)

    assert writes == {'attendance': 0, 'unknown': 0}

def test_pipeline_keeps_more_detail_for_small_faces():
    from backend.app.services.detector import Detection

    class CapturingDetector:
        def __init__(self):
            self.shape = None
            self.threshold = None

        def detect(self, image, score_threshold=None):
            self.shape = image.shape
            self.threshold = score_threshold
            return [Detection(
                (100.0, 80.0, 40.0, 40.0),
                np.zeros((5, 2), dtype=np.float32),
                0.8,
            )]

    class CapturingRecognizer:
        def __init__(self):
            self.source_shape = None
            self.bbox = None

        def embed(self, image, detection):
            self.source_shape = image.shape
            self.bbox = detection.bbox
            return np.ones(128, dtype=np.float32)

    detector = CapturingDetector()
    recognizer = CapturingRecognizer()
    pipeline = RecognitionPipeline(detector, recognizer, FaceGallery())
    settings = {
        "processing_width": 800,
        "detector_score_threshold": 0.65,
        "min_face_size_px": 32,
    }
    image = np.zeros((900, 1600, 3), dtype=np.uint8)

    detections, embeddings = pipeline._detect_and_embed(image, settings)

    assert detector.shape[:2] == (450, 800)
    assert detector.threshold == 0.65
    assert recognizer.source_shape == image.shape
    assert detections[0].bbox == (200.0, 160.0, 80.0, 80.0)
    assert len(embeddings) == 1
