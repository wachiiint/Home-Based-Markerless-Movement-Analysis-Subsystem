import numpy as np
import pytest

from app.models.calibration import CameraCalibration, FloorPlane
from app.services.lifting.metric_scale import backproject_to_plane, resolve_metric_scale

K4 = [900.0, 900.0, 350.0, 500.0]
# fronto-parallel floor 2 m away in the camera frame
FLOOR = FloorPlane(normal=[0.0, 0.0, 1.0], d=2000.0)


def _calib(ok=True, floor=FLOOR):
    return CameraCalibration(ok=ok, method="charuco", K=K4, floor_plane=floor)


def test_backproject_hits_known_metric_point():
    # pixel 45px left of centre -> -100mm at z=2000mm (fx=900)
    p = backproject_to_plane((350 - 45, 500), K4, FLOOR)
    assert p == pytest.approx([-100.0, 0.0, 2000.0])


def _frames_feet(lifted_ankle_sep=0.5):
    # ankle pixels 45px either side of centre -> 200mm apart metric
    kp2d = np.zeros((1, 17, 2))
    kp2d[0, 6] = (350 - 45, 500)  # L_ANKLE
    kp2d[0, 3] = (350 + 45, 500)  # R_ANKLE
    kp3d = np.zeros((1, 17, 3))
    kp3d[0, 6] = (0.0, 0.0, 0.0)
    kp3d[0, 3] = (lifted_ankle_sep, 0.0, 0.0)
    return kp2d, kp3d


def test_feet_scale_primary():
    kp2d, kp3d = _frames_feet(lifted_ankle_sep=0.5)  # 200mm / 0.5unit -> 400
    scale, source, warnings = resolve_metric_scale(kp2d, kp3d, [True], _calib())
    assert source == "feet_floor"
    assert scale == pytest.approx(400.0)
    assert warnings == []


def test_height_fallback_when_no_calibration():
    kp2d = np.zeros((1, 17, 2))
    kp3d = np.zeros((1, 17, 3))
    kp3d[0, 10] = (0.0, 1.7, 0.0)  # head, 1.7 units above ankles
    scale, source, _ = resolve_metric_scale(kp2d, kp3d, [True], calibration=None, subject_height_mm=1700)
    assert source == "subject_height"
    assert scale == pytest.approx(1000.0)


def test_cross_check_flags_disagreement():
    kp2d, kp3d = _frames_feet(lifted_ankle_sep=0.5)  # feet -> 400
    kp3d[0, 10] = (0.0, 1.7, 0.0)  # head span 1.7 -> height scale 1700/1.7=1000, disagrees
    scale, source, warnings = resolve_metric_scale(kp2d, kp3d, [True], _calib(), subject_height_mm=1700)
    assert source == "feet_floor"  # feet stays primary
    assert scale == pytest.approx(400.0)
    assert any("scale_uncertain" in w for w in warnings)


def test_cross_check_agrees_no_warning():
    kp2d, kp3d = _frames_feet(lifted_ankle_sep=0.5)  # feet -> 400
    # head span chosen so height scale ~ 400 too: 1700/x=400 -> x=4.25
    kp3d[0, 10] = (0.0, 4.25, 0.0)
    _scale, _source, warnings = resolve_metric_scale(kp2d, kp3d, [True], _calib(), subject_height_mm=1700)
    assert warnings == []


def test_no_source_returns_none():
    kp2d = np.zeros((1, 17, 2))
    kp3d = np.zeros((1, 17, 3))
    scale, source, warnings = resolve_metric_scale(kp2d, kp3d, [True], calibration=None)
    assert scale is None and source is None
    assert warnings
