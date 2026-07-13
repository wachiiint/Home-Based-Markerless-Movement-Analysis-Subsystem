"""Resolve the metric scale of the lifted (unit-less) 3D skeleton.

Primary: back-project both ankle pixels onto the calibrated floor plane to get a
metric ankle-to-ankle distance, and compare it to the same distance in the
lifted skeleton. Fallback: scale so the head-to-ankle span matches a
patient-entered height. If both are available they are cross-checked and a
disagreement raises a ``scale_uncertain`` guard warning.
"""

import numpy as np

from app.models.calibration import CameraCalibration
from app.services.calibration.charuco_calibrator import k_matrix

R_ANKLE, L_ANKLE, HEAD = 3, 6, 10  # H36M17 indices
CROSS_CHECK_TOL = 0.15


def backproject_to_plane(pixel, k4, floor_plane) -> np.ndarray | None:
    """Camera-frame point (mm) where the pixel's ray meets the floor plane."""
    k_inv = np.linalg.inv(k_matrix(k4))
    direction = k_inv @ np.array([pixel[0], pixel[1], 1.0])
    normal = np.array(floor_plane.normal, dtype=np.float64)
    denom = float(normal @ direction)
    if abs(denom) < 1e-9:
        return None
    return (floor_plane.d / denom) * direction


def _feet_scale_frame(kp2d, kp3d, k4, floor_plane) -> float | None:
    left = backproject_to_plane(kp2d[L_ANKLE], k4, floor_plane)
    right = backproject_to_plane(kp2d[R_ANKLE], k4, floor_plane)
    if left is None or right is None:
        return None
    metric = float(np.linalg.norm(left - right))
    lifted = float(np.linalg.norm(np.asarray(kp3d[L_ANKLE]) - np.asarray(kp3d[R_ANKLE])))
    if lifted < 1e-9:
        return None
    return metric / lifted


def _height_scale_frame(kp3d, subject_height_mm) -> float | None:
    mid_ankle = (np.asarray(kp3d[L_ANKLE]) + np.asarray(kp3d[R_ANKLE])) / 2
    span = float(np.linalg.norm(np.asarray(kp3d[HEAD]) - mid_ankle))
    if span < 1e-9:
        return None
    return subject_height_mm / span


def _median_valid(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None and np.isfinite(v)]
    return float(np.median(clean)) if clean else None


def resolve_metric_scale(
    keypoints_2d_h36m,
    keypoints_3d,
    valid_mask,
    calibration: CameraCalibration | None,
    subject_height_mm: float | None = None,
    cross_check_tol: float = CROSS_CHECK_TOL,
) -> tuple[float | None, str | None, list[str]]:
    """Return (scale_mm_per_unit, scale_source, warnings)."""
    warnings: list[str] = []
    frames = range(len(keypoints_3d))
    valid = [bool(v) for v in valid_mask]

    feet_scale = None
    if calibration is not None and calibration.ok and calibration.K and calibration.floor_plane:
        feet_scale = _median_valid([
            _feet_scale_frame(keypoints_2d_h36m[i], keypoints_3d[i], calibration.K, calibration.floor_plane)
            for i in frames if valid[i]
        ])

    height_scale = None
    if subject_height_mm and subject_height_mm > 0:
        height_scale = _median_valid([
            _height_scale_frame(keypoints_3d[i], subject_height_mm) for i in frames if valid[i]
        ])

    if feet_scale is not None and height_scale is not None:
        rel_diff = abs(feet_scale - height_scale) / feet_scale
        if rel_diff > cross_check_tol:
            warnings.append(
                f"scale_uncertain: feet-floor ({feet_scale:.1f}) and height "
                f"({height_scale:.1f}) mm/unit differ by {rel_diff:.0%}"
            )
        return feet_scale, "feet_floor", warnings
    if feet_scale is not None:
        return feet_scale, "feet_floor", warnings
    if height_scale is not None:
        return height_scale, "subject_height", warnings
    return None, None, ["no metric scale source (no floor calibration or height)"]
