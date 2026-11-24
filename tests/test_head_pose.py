import numpy as np

from backend.app.services.head_pose import estimate_head_pose


def test_head_pose_returns_finite_angles_for_valid_five_point_landmarks():
    landmarks = np.array([
        [42.0, 38.0],
        [78.0, 38.0],
        [60.0, 58.0],
        [46.0, 76.0],
        [74.0, 76.0],
    ], dtype=np.float32)

    pose = estimate_head_pose(landmarks, (120, 120))

    assert pose is not None
    assert len(pose) == 3
    assert all(np.isfinite(angle) for angle in pose)
    assert all(-180.0 <= angle <= 180.0 for angle in pose)


def test_head_pose_rejects_invalid_landmarks():
    assert estimate_head_pose(np.zeros((5, 2)), (120, 120)) is None
    assert estimate_head_pose(np.zeros((4, 2)), (120, 120)) is None
    assert estimate_head_pose(np.full((5, 2), np.nan), (120, 120)) is None
