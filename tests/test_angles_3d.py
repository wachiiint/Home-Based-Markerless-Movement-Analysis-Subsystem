import numpy as np
import pytest

from app.schemas.movement import TaskType
from app.services.analysis.kinematics import three_point_angle_3d
from app.services.lifting.angles_3d import angle_series_3d, supports_3d_angle


# ---- 3D three-point angle -------------------------------------------------

def test_three_point_angle_3d_right_angle():
    assert three_point_angle_3d((1, 0, 0), (0, 0, 0), (0, 0, 1)) == pytest.approx(90.0)


def test_three_point_angle_3d_straight():
    assert three_point_angle_3d((-1, 0, 0), (0, 0, 0), (1, 0, 0)) == pytest.approx(180.0)


def test_three_point_angle_3d_still_works_in_2d():
    assert three_point_angle_3d((1, 0), (0, 0), (0, 1)) == pytest.approx(90.0)


def test_three_point_angle_3d_zero_length_ray():
    assert three_point_angle_3d((0, 0, 0), (0, 0, 0), (1, 0, 0)) == 0.0


# ---- task support ---------------------------------------------------------

def test_hip_knee_supported_ankle_not():
    assert supports_3d_angle(TaskType.KNEE_FLEXION)
    assert supports_3d_angle(TaskType.HIP_FLEXION)
    assert not supports_3d_angle(TaskType.ANKLE_DORSIFLEXION)
    assert not supports_3d_angle(TaskType.ANKLE_PLANTARFLEXION)


# ---- angle series on a synthetic skeleton ---------------------------------

def _skeleton_with_knee(angle_points):
    """Build (T,17,3) placing r_hip(1)/r_knee(2)/r_ankle(3) for a known angle."""
    t = len(angle_points)
    kp = np.zeros((t, 17, 3))
    for i, (hip, knee, ankle) in enumerate(angle_points):
        kp[i, 1] = hip
        kp[i, 2] = knee
        kp[i, 3] = ankle
    return kp


def test_angle_series_3d_knee_right_angle():
    # knee at origin, hip up (+y), ankle out (+x) -> 90 degrees
    kp = _skeleton_with_knee([((0, 1, 0), (0, 0, 0), (1, 0, 0))])
    angles = angle_series_3d(kp, TaskType.KNEE_FLEXION, "right")
    assert angles[0] == pytest.approx(90.0)


def test_angle_series_3d_uses_depth():
    # ankle displaced purely in z from a straight leg -> bends out of image plane
    straight = _skeleton_with_knee([((0, 1, 0), (0, 0, 0), (0, -1, 0))])
    bent_in_z = _skeleton_with_knee([((0, 1, 0), (0, 0, 0), (0, 0, 1))])
    assert angle_series_3d(straight, TaskType.KNEE_FLEXION, "right")[0] == pytest.approx(180.0)
    assert angle_series_3d(bent_in_z, TaskType.KNEE_FLEXION, "right")[0] == pytest.approx(90.0)


def test_angle_series_3d_rejects_ankle():
    kp = np.zeros((2, 17, 3))
    with pytest.raises(ValueError):
        angle_series_3d(kp, TaskType.ANKLE_DORSIFLEXION, "right")
