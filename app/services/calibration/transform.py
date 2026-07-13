"""Build the camera->floor 6DoF transform from a ChArUco calibration.

The calibration stores the board(world)->camera pose (R, t): X_cam = R X_board + t.
The clinically useful transform is its inverse, camera->floor, which places the
camera in the floor frame and is the anchor for later CT registration.
"""

import numpy as np
from scipy.spatial.transform import Rotation

from app.models.calibration import CameraCalibration
from app.schemas.response import TransformationMatrix6DoF


def camera_to_floor_6dof(calibration: CameraCalibration | None) -> TransformationMatrix6DoF | None:
    if calibration is None or not calibration.ok or calibration.R is None or calibration.t is None:
        return None
    R = np.array(calibration.R, dtype=np.float64)
    t = np.array(calibration.t, dtype=np.float64)

    r_cw = R.T  # camera->world rotation
    t_cw = -r_cw @ t  # camera origin in the floor frame (mm)

    matrix = np.eye(4)
    matrix[:3, :3] = r_cw
    matrix[:3, 3] = t_cw
    euler = Rotation.from_matrix(r_cw).as_euler("xyz", degrees=True)

    return TransformationMatrix6DoF(
        frame="camera_to_floor",
        matrix=matrix.tolist(),
        translation_mm=[float(v) for v in t_cw],
        rotation_deg=[float(v) for v in euler],
    )
