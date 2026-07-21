"""End-to-end board pipeline over the *real* OpenCV detector.

The other calibration tests feed hand-projected corner points, so they never
exercise ``cv2.aruco`` detection. Here the board is rendered by the same tool an
operator prints, warped into several synthetic camera views, and pushed through
the real detect -> ``calibrateCamera`` -> ``solvePnP`` chain -- the closest we
get to a printed board without physical hardware or ground truth.
"""

import cv2
import numpy as np
import pytest

from app.models.calibration import CharucoBoardSpec
from app.services.calibration.charuco_calibrator import calibrate_device_from_images, calibrate_session
from app.services.calibration.device_store import DeviceStore
from app.tools.calibrate_device import main as calibrate_main
from app.tools.generate_board import board_size_mm, build_board_svg, render_board_image

SPEC = CharucoBoardSpec()
_CAM_W, _CAM_H = 1280, 960
_PPM = 6  # board raster density used to build the views
# One fixed pinhole the synthetic views all share, so ``calibrateCamera`` is
# well-posed (random per-view homographies are not consistent with any single K).
_K_TRUE = np.array([[1400.0, 0, _CAM_W / 2], [0, 1400.0, _CAM_H / 2], [0, 0, 1]], dtype=np.float64)


def _warped_views(n: int) -> list[np.ndarray]:
    """`n` views of the board as seen by ``_K_TRUE`` at varied board poses.

    Each view is the board plane projected through a real pinhole (fixed K,
    varied rotation/distance), so the views are mutually consistent and the
    recovered intrinsics are well-conditioned.
    """
    board = render_board_image(SPEC, px_per_mm=_PPM)
    h, w = board.shape[:2]
    width_mm, height_mm = board_size_mm(SPEC)
    # raster pixel -> board-plane mm, then recentre the board on its own middle
    pix_to_mm = np.array([[1 / _PPM, 0, 0], [0, 1 / _PPM, 0], [0, 0, 1]], dtype=np.float64)
    recentre = np.array([[1, 0, -width_mm / 2], [0, 1, -height_mm / 2], [0, 0, 1]], dtype=np.float64)

    rng = np.random.default_rng(7)
    views = []
    for _ in range(n):
        rvec = rng.uniform(-0.35, 0.35, size=3)
        R, _ = cv2.Rodrigues(rvec)
        z = rng.uniform(750.0, 1050.0)
        t = np.array([0.0, 0.0, z])
        # planar projection: image = K [r1 r2 t] (board-mm) -> homography
        board_to_img = _K_TRUE @ np.column_stack((R[:, 0], R[:, 1], t))
        homography = board_to_img @ recentre @ pix_to_mm
        views.append(cv2.warpPerspective(board, homography, (_CAM_W, _CAM_H), borderValue=255))
    return views


def test_generate_board_svg_is_a4_metric_and_detectable():
    image = render_board_image(SPEC)
    svg = build_board_svg(SPEC, image)
    assert 'width="210.0mm"' in svg and 'height="297.0mm"' in svg
    assert "data:image/png;base64," in svg
    assert board_size_mm(SPEC) == (175.0, 250.0)


def test_full_device_calibration_over_real_detector():
    views = _warped_views(12)
    intrinsics = calibrate_device_from_images(
        views, device_id="rendered", image_size=(_CAM_W, _CAM_H), spec=SPEC, print_scale_factor=1.0,
    )
    assert intrinsics.status == "valid"
    assert intrinsics.reproj_error_px < 1.0
    assert intrinsics.K[0] == pytest.approx(1400.0, rel=0.05)  # fx near the true pinhole
    assert intrinsics.K[1] == pytest.approx(1400.0, rel=0.05)  # fy


def test_session_pose_recovers_from_rendered_view():
    views = _warped_views(12)
    intrinsics = calibrate_device_from_images(
        views, device_id="rendered", image_size=(_CAM_W, _CAM_H), spec=SPEC, print_scale_factor=1.0,
    )
    calibration = calibrate_session(views[0], intrinsics, SPEC)
    assert calibration.ok
    assert calibration.reproj_error_px < 2.0
    assert calibration.floor_plane is not None
    assert np.linalg.norm(calibration.floor_plane.normal) == pytest.approx(1.0, abs=1e-6)


def test_calibrate_device_cli_writes_store(tmp_path):
    image_dir = tmp_path / "shots"
    image_dir.mkdir()
    for i, view in enumerate(_warped_views(10)):
        cv2.imwrite(str(image_dir / f"view_{i:02d}.png"), view)

    rc = calibrate_main([
        "--images", str(image_dir / "*.png"),
        "--make", "TestCam", "--model", "Rendered",
        "--measured-bar-mm", "100", "--data-dir", str(tmp_path / "calib"),
    ])
    assert rc == 0

    store = DeviceStore(tmp_path / "calib")
    data = store._load()
    assert len(data) == 1
    (record,) = data.values()
    assert record["status"] == "valid"
    assert record["print_scale_factor"] == pytest.approx(1.0)
