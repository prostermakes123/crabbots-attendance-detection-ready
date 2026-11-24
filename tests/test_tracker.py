import numpy as np

from backend.app.services.detector import Detection
from backend.app.services.gallery import MatchResult
from backend.app.services.tracker import MultiFaceTracker, iou


def _detection(x=10.0):
    return Detection((x, 10.0, 80.0, 80.0), np.zeros((5, 2), dtype=np.float32), 0.99)


def _settings():
    return {
        'track_iou_threshold': 0.2,
        'track_max_age_frames': 3,
        'track_min_hits': 2,
        'evidence_window': 5,
        'evidence_consistency': 0.6,
        'recognition_threshold': 0.4,
    }


def test_iou_handles_overlap_and_disjoint_boxes():
    assert iou((0, 0, 10, 10), (5, 5, 10, 10)) == 25 / 175
    assert iou((0, 0, 10, 10), (20, 20, 10, 10)) == 0.0


def test_tracker_accumulates_consistent_identity_evidence():
    tracker = MultiFaceTracker()
    match = MatchResult(True, 'm1', 'Member One', 0.9, 0.1, 0.8, 'accepted')

    first = tracker.update([_detection()], [np.ones(128)], [match], _settings())
    assert first[0].status == 'pending'
    second = tracker.update([_detection(11)], [np.ones(128)], [match], _settings())
    assert second[0].status == 'recognized'
    assert second[0].member_id == 'm1'


def test_tracker_expires_lost_tracks():
    tracker = MultiFaceTracker()
    unknown = MatchResult(False, reason='no_candidates')
    tracker.update([_detection()], [np.ones(128)], [unknown], _settings())
    for _ in range(4):
        tracker.update([], [], [], _settings())
    assert tracker.tracks == {}

def test_tracker_keeps_id_during_fast_non_overlapping_motion():
    tracker = MultiFaceTracker()
    unknown = MatchResult(False, reason='no_candidates')

    first = tracker.update([_detection(10)], [np.ones(128)], [unknown], _settings())
    second = tracker.update([_detection(70)], [np.ones(128)], [unknown], _settings())

    assert first[0].id == second[0].id
    assert second[0].velocity[0] > 0


def test_tracker_uses_motion_prediction_after_a_missed_frame():
    tracker = MultiFaceTracker()
    unknown = MatchResult(False, reason='no_candidates')

    first = tracker.update([_detection(10)], [np.ones(128)], [unknown], _settings())
    tracker.update([_detection(70)], [np.ones(128)], [unknown], _settings())
    tracker.update([], [], [], _settings())
    recovered = tracker.update([_detection(130)], [np.ones(128)], [unknown], _settings())

    assert len(recovered) == 1
    assert recovered[0].id == first[0].id
    assert recovered[0].missed == 0



def test_tracker_preserves_latest_head_pose_for_detection():
    tracker = MultiFaceTracker()
    unknown = MatchResult(False, reason="no_candidates")
    detection = _detection()
    detection.head_pose = (12.0, -4.0, 2.0)

    tracks = tracker.update([detection], [np.ones(128)], [unknown], _settings())

    assert tracks[0].head_pose == (12.0, -4.0, 2.0)
