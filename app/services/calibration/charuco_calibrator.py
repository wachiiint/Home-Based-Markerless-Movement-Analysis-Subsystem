"""ChArUco calibration: detection, intrinsic calibration, and per-session pose.

Detection is kept separate from the pose/intrinsic math so the metric math can
be tested with synthetically projected points (no real photo needed).

Units: object points are in millimetres, so ``tvec`` and the floor plane are
metric mm-native.
"""

from datetime import datetime, timezone

import cv2
import numpy as np

from app.models.calibration import (
    CameraCalibration,
    CharucoBoardSpec,
    DeviceIntrinsics,
    FloorPlane,
)
from app.services.calibration.board import build_charuco_board

MIN_POSE_CORNERS = 4


def k_matrix(k4: list[float]) -> np.ndarray:
    fx, fy, cx, cy = k4
    return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float64)


def k_to_list(K: np.ndarray) -> list[float]:
    return [float(K[0, 0]), float(K[1, 1]), float(K[0, 2]), float(K[1, 2])]


def detect_board(image: np.ndarray, board) -> tuple[np.ndarray, np.ndarray, int] | None:
    """Detect the board and return matched (obj_points, img_points, n_corners).

    Returns ``None`` when fewer than ``MIN_POSE_CORNERS`` charuco corners match.
    """
    detector = cv2.aruco.CharucoDetector(board)
    charuco_corners, charuco_ids, _marker_corners, _marker_ids = detector.detectBoard(image)
    if charuco_ids is None or len(charuco_ids) < MIN_POSE_CORNERS:
        return None
    obj_points, img_points = board.matchImagePoints(charuco_corners, charuco_ids)
    if obj_points is None or len(obj_points) < MIN_POSE_CORNERS:
        return None
    return obj_points, img_points, len(charuco_ids)


def calibrate_intrinsics(
    obj_points_list: list[np.ndarray],
    img_points_list: list[np.ndarray],
    image_size: tuple[int, int],
) -> tuple[list[float], list[float], float]:
    """cv2.calibrateCamera over several views. Returns (K4, dist, rms_reproj_px)."""
    rms, K, dist, _rvecs, _tvecs = cv2.calibrateCamera(
        obj_points_list, img_points_list, image_size, None, None
    )
    return k_to_list(K), [float(c) for c in dist.ravel()], float(rms)


def estimate_pose(
    obj_points: np.ndarray,
    img_points: np.ndarray,
    k4: list[float],
    dist: list[float],
) -> tuple[np.ndarray, np.ndarray, FloorPlane, float]:
    """solvePnP the board. Returns (R 3x3, t 3-vec mm, floor_plane, reproj_px)."""
    K = k_matrix(k4)
    dist_arr = np.array(dist, dtype=np.float64)
    ok, rvec, tvec = cv2.solvePnP(obj_points, img_points, K, dist_arr)
    if not ok:
        raise ValueError("solvePnP failed to recover board pose")
    R, _ = cv2.Rodrigues(rvec)
    t = tvec.reshape(3)
    # Board plane (z_board = 0) in camera frame: normal is board's z-axis, and
    # the board origin t lies on it.
    normal = R[:, 2]
    plane = FloorPlane(normal=[float(v) for v in normal], d=float(normal @ t))

    projected, _ = cv2.projectPoints(obj_points, rvec, tvec, K, dist_arr)
    reproj = float(np.sqrt(np.mean((projected.reshape(-1, 2) - img_points.reshape(-1, 2)) ** 2)))
    return R, t, plane, reproj


def calibrate_device_from_images(
    images: list[np.ndarray],
    device_id: str,
    image_size: tuple[int, int],
    spec: CharucoBoardSpec,
    print_scale_factor: float,
    raw_meta: dict | None = None,
    source: str = "unknown",
) -> DeviceIntrinsics:
    """Full intrinsic calibration from several board photos of one device."""
    board = build_charuco_board(spec, print_scale_factor)
    obj_list: list[np.ndarray] = []
    img_list: list[np.ndarray] = []
    for image in images:
        detected = detect_board(image, board)
        if detected is None:
            continue
        obj_points, img_points, _n = detected
        obj_list.append(obj_points)
        img_list.append(img_points)

    if len(obj_list) < 3:
        return DeviceIntrinsics(
            device_id=device_id,
            raw_meta=raw_meta or {},
            image_size=image_size,
            K=[0, 0, 0, 0],
            dist_coeffs=[],
            print_scale_factor=print_scale_factor,
            board_spec_version=spec.version,
            reproj_error_px=0.0,
            source=source,
            calibrated_at=datetime.now(timezone.utc).isoformat(),
            status="failed",
        )

    k4, dist, rms = calibrate_intrinsics(obj_list, img_list, image_size)
    return DeviceIntrinsics(
        device_id=device_id,
        raw_meta=raw_meta or {},
        image_size=image_size,
        K=k4,
        dist_coeffs=dist,
        print_scale_factor=print_scale_factor,
        board_spec_version=spec.version,
        reproj_error_px=rms,
        source=source,
        calibrated_at=datetime.now(timezone.utc).isoformat(),
        status="valid",
    )


def calibrate_session(
    image: np.ndarray,
    intrinsics: DeviceIntrinsics,
    spec: CharucoBoardSpec,
) -> CameraCalibration:
    """Per-session extrinsics/floor-plane from one frame containing the board."""
    if intrinsics.status != "valid":
        return CameraCalibration(
            ok=False, method="charuco", warnings=[f"device intrinsics status={intrinsics.status}"]
        )
    board = build_charuco_board(spec, intrinsics.print_scale_factor)
    detected = detect_board(image, board)
    if detected is None:
        return CameraCalibration(ok=False, method="charuco", warnings=["board not detected in frame"])

    obj_points, img_points, _n = detected
    R, t, plane, reproj = estimate_pose(obj_points, img_points, intrinsics.K, intrinsics.dist_coeffs)
    return CameraCalibration(
        ok=True,
        method="charuco",
        K=intrinsics.K,
        dist_coeffs=intrinsics.dist_coeffs,
        R=[[float(v) for v in row] for row in R],
        t=[float(v) for v in t],
        floor_plane=plane,
        # scale_mm_per_unit is resolved in Phase D once the lifted 3D pose exists.
        scale_mm_per_unit=None,
        scale_source=None,
        reproj_error_px=reproj,
        warnings=[],
    )
