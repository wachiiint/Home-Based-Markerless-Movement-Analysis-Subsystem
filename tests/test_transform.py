import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from app.models.calibration import CameraCalibration, FloorPlane
from app.services.calibration.transform import camera_to_floor_6dof


def _calib(R, t):
    return CameraCalibration(
        ok=True, method="charuco", K=[900, 900, 350, 500],
        R=[[float(v) for v in row] for row in R], t=[float(v) for v in t],
        floor_plane=FloorPlane(normal=[0, 0, 1], d=2000),
    )


def test_none_when_no_calibration():
    assert camera_to_floor_6dof(None) is None


def test_none_when_not_ok():
    assert camera_to_floor_6dof(CameraCalibration(ok=False, method="charuco")) is None


def test_maps_board_origin_to_world_origin():
    # board origin sits at t in the camera frame; camera->floor must send it to 0
    R = np.eye(3)
    t = np.array([10.0, -20.0, 2000.0])
    result = camera_to_floor_6dof(_calib(R, t))
    M = np.array(result.matrix)
    x_cam = np.array([t[0], t[1], t[2], 1.0])
    x_world = M @ x_cam
    assert x_world[:3] == pytest.approx([0, 0, 0], abs=1e-6)
    assert M[3].tolist() == [0, 0, 0, 1]


def test_rotation_is_inverse():
    R = Rotation.from_euler("xyz", [20, -15, 30], degrees=True).as_matrix()
    t = np.array([0.0, 0.0, 1500.0])
    result = camera_to_floor_6dof(_calib(R, t))
    # recovered rotation (camera->world) must be R^T
    r_cw = np.array(result.matrix)[:3, :3]
    assert r_cw == pytest.approx(R.T, abs=1e-6)
    assert len(result.rotation_deg) == 3
