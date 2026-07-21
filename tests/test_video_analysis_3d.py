import numpy as np

from app.core.config import Settings
from app.models.calibration import BoardDetectionDiagnostics, CameraCalibration, FloorPlane
from app.schemas.movement import TaskType
from app.services.lifting.lifter import StubLifter
from app.services.pose.pose_sequence import FramePose2D, PoseSequence
from app.services.video_analysis import _augment_with_3d, _select_analyzed_side

SETTINGS = Settings()


def _base_pose():
    kp = np.zeros((26, 2))
    coords = {
        0: (500, 100), 5: (460, 200), 6: (540, 200), 7: (440, 300), 8: (560, 300),
        9: (430, 400), 10: (570, 400), 11: (470, 500), 12: (530, 500),
        13: (470, 700), 14: (530, 700), 15: (470, 900), 16: (530, 900),
        17: (500, 80), 18: (500, 190), 19: (500, 500),
        20: (470, 950), 21: (530, 950), 22: (475, 950), 23: (535, 950),
        24: (470, 940), 25: (530, 940),
    }
    for i, (x, y) in coords.items():
        kp[i] = (x, y)
    return kp


def _rigid_sequence(t=6):
    base = _base_pose()
    frames = []
    for i in range(t):
        kp = base + np.array([i * 2.0, 0.0])  # rigid translation -> bones constant
        frames.append(FramePose2D(i, i, kp, np.full(26, 0.9)))
    return PoseSequence(frames=frames, width=1000, height=1000)


class _FakeCalibrator:
    def __init__(self, calibration, diagnostics):
        self._c, self._d = calibration, diagnostics

    def finalize(self, device_meta, image_size):
        return self._c, self._d


def _ok_calibration():
    return CameraCalibration(
        ok=True, method="charuco", K=[900, 900, 500, 500],
        R=[[1, 0, 0], [0, 1, 0], [0, 0, 1]], t=[0, 0, 2000],
        floor_plane=FloorPlane(normal=[0, 0, 1], d=2000),
    )


def _diag(detected):
    return BoardDetectionDiagnostics(detected=detected)


def _one_leg_moving_sequence(moving="right", t=8):
    """Sequence where one knee sweeps a wide arc and the other stays straight.

    The stationary leg is given *higher* keypoint confidence on the first frame,
    reproducing the condition under which the old first-frame lock picked the
    wrong (non-exercising) leg.
    """
    import math

    from app.models import keypoints as kp

    hip_i, knee_i, ankle_i = (
        (kp.RIGHT_HIP, kp.RIGHT_KNEE, kp.RIGHT_ANKLE) if moving == "right"
        else (kp.LEFT_HIP, kp.LEFT_KNEE, kp.LEFT_ANKLE)
    )
    still = (
        (kp.LEFT_HIP, kp.LEFT_KNEE, kp.LEFT_ANKLE) if moving == "right"
        else (kp.RIGHT_HIP, kp.RIGHT_KNEE, kp.RIGHT_ANKLE)
    )
    frames = []
    for i in range(t):
        points = np.zeros((26, 2))
        scores = np.full(26, 0.9)
        # stationary leg: hip-knee-ankle collinear -> constant 180deg knee angle
        points[still[0]], points[still[1]], points[still[2]] = (460, 500), (460, 700), (460, 900)
        # moving leg: ankle sweeps, driving a wide knee ROM
        theta = math.radians(180 - i * 15)
        points[hip_i], points[knee_i] = (540, 500), (540, 700)
        points[ankle_i] = (540 + math.sin(theta) * 200, 700 + math.cos(theta) * 200)
        if i == 0:
            # bias the FIRST frame toward the stationary leg on confidence
            for j in still:
                scores[j] = 0.99
            for j in (hip_i, knee_i, ankle_i):
                scores[j] = 0.80
        frames.append(FramePose2D(i, i, points, scores))
    return PoseSequence(frames=frames, width=1000, height=1000)


def test_select_side_picks_moving_leg_over_first_frame_confidence():
    seq = _one_leg_moving_sequence(moving="right")
    assert _select_analyzed_side(seq, TaskType.KNEE_EXTENSION, SETTINGS.min_keypoint_confidence) == "right"


def test_select_side_symmetric_left():
    seq = _one_leg_moving_sequence(moving="left")
    assert _select_analyzed_side(seq, TaskType.KNEE_EXTENSION, SETTINGS.min_keypoint_confidence) == "left"


def test_no_lifter_stays_2d():
    result = _augment_with_3d(_rigid_sequence(), TaskType.KNEE_FLEXION, "right", SETTINGS, None, None, {}, None)
    assert result.analysis_mode == "2d"
    assert result.board_diagnostics is None


def test_board_absent_reports_diagnostics_and_2d():
    calib = _FakeCalibrator(None, _diag(detected=False))
    result = _augment_with_3d(_rigid_sequence(), TaskType.KNEE_FLEXION, "right", SETTINGS, StubLifter(), calib, {}, None)
    assert result.analysis_mode == "2d"
    assert result.board_diagnostics is not None and not result.board_diagnostics.detected
    assert result.transformation_6dof is None


def test_calibrated_knee_produces_3d():
    calib = _FakeCalibrator(_ok_calibration(), _diag(detected=True))
    result = _augment_with_3d(_rigid_sequence(), TaskType.KNEE_FLEXION, "right", SETTINGS, StubLifter(), calib, {}, None)
    assert result.analysis_mode == "3d"
    assert "knee_rom_deg_3d" in result.joint_angles_3d
    assert result.transformation_6dof is not None


def test_calibrated_ankle_stays_2d_but_keeps_6dof():
    calib = _FakeCalibrator(_ok_calibration(), _diag(detected=True))
    result = _augment_with_3d(_rigid_sequence(), TaskType.ANKLE_DORSIFLEXION, "right", SETTINGS, StubLifter(), calib, {}, None)
    assert result.analysis_mode == "2d"  # H36M17 has no toe
    assert result.transformation_6dof is not None  # calibration still yields the transform
