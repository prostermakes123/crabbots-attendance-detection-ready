"""Lightweight 3D-assisted head-pose estimation from YuNet's five landmarks.

Angles are diagnostic estimates, not a reconstructed face or a recognition score.
"""
from __future__ import annotations

import cv2
import numpy as np


# Approximate generic 3D face reference points in YuNet order:
# left eye, right eye, nose tip, left mouth corner, right mouth corner.
_FACE_MODEL = np.array([
    (-30.0,  30.0,  30.0),
    ( 30.0,  30.0,  30.0),
    (  0.0,   0.0,   0.0),
    (-25.0, -30.0, 25.0),
    ( 25.0, -30.0,  25.0),
], dtype=np.float64)


def estimate_head_pose(landmarks: np.ndarray, image_size: tuple[int, int]) -> tuple[float, float, float] | None:
    """Return yaw, pitch, roll in degrees, or None when geometry is unreliable."""
    points = np.asarray(landmarks, dtype=np.float64)
    width, height = image_size
    if points.shape != (5, 2) or width < 8 or height < 8 or not np.all(np.isfinite(points)):
        return None
    if np.ptp(points[:, 0]) < 3 or np.ptp(points[:, 1]) < 3:
        return None

    model = _FACE_MODEL.copy()
    # The two mouth corners are vertically below the nose.
    model[3, 1] = -30.0
    focal = float(max(width, height))
    camera = np.array([[focal, 0.0, width / 2.0],
                       [0.0, focal, height / 2.0],
                       [0.0, 0.0, 1.0]], dtype=np.float64)
    distortion = np.zeros((4, 1), dtype=np.float64)
    try:
        ok, rotation, _translation = cv2.solvePnP(
            model, points, camera, distortion, flags=cv2.SOLVEPNP_ITERATIVE
        )
        if not ok:
            return None
        matrix, _ = cv2.Rodrigues(rotation)
        sy = float(np.hypot(matrix[0, 0], matrix[1, 0]))
        if sy < 1e-6:
            pitch = np.degrees(np.arctan2(-matrix[1, 2], matrix[1, 1]))
            yaw = np.degrees(np.arctan2(-matrix[2, 0], sy))
            roll = 0.0
        else:
            pitch = np.degrees(np.arctan2(matrix[2, 1], matrix[2, 2]))
            yaw = np.degrees(np.arctan2(-matrix[2, 0], sy))
            roll = np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0]))
        angles = tuple(float(np.clip(v, -180.0, 180.0)) for v in (yaw, pitch, roll))
        return angles if np.all(np.isfinite(angles)) else None
    except (cv2.error, ValueError, np.linalg.LinAlgError):
        return None
