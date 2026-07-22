import cv2
import numpy as np
import pytest

from app.models.calibration import CharucoBoardSpec, DeviceIntrinsics
from app.services.calibration.board import build_charuco_board, effective_square_length_mm
from app.services.calibration.charuco_calibrator import (
    calibrate_intrinsics,
    detect_board,
    estimate_pose,
)
from app.services.calibration.device_id import derive_device_id
from app.services.calibration.device_store import DeviceStore
from app.services.calibration.print_verify import compute_print_scale

SPEC = CharucoBoardSpec()


# ---- print-verify ---------------------------------------------------------

def test_print_scale_exact():
    factor, warnings = compute_print_scale(100.0)
    assert factor == 1.0
    assert warnings == []


def test_print_scale_corrects_undersized_print():
    # printed bar measured 98mm -> the whole board printed 2% small, so the
    # effective (real, on-paper) lengths must be scaled DOWN by 98/100.
    factor, warnings = compute_print_scale(98.0)
    assert factor == pytest.approx(98 / 100)
    assert warnings == []


def test_print_scale_corrects_oversized_print():
    # printed bar measured 110mm -> printer enlarged 10%, effective lengths
    # must be scaled UP by 110/100.
    factor, warnings = compute_print_scale(110.0)
    assert factor == pytest.approx(110 / 100)


def test_print_scale_warns_on_gross_deviation():
    _factor, warnings = compute_print_scale(80.0)  # fit-to-page shrank it
    assert warnings


def test_effective_square_length_applies_scale():
    assert effective_square_length_mm(SPEC, 98 / 100) == pytest.approx(SPEC.square_length_mm * 98 / 100)


def test_print_scale_direction_recovers_metric_translation():
    """End-to-end guard on the print-scale *direction* via synthetic projection.

    Physically the printer enlarged the board 10% (measured bar = 110 mm), so the
    real on-paper square is ``nominal * 1.1``. We project that physical board from
    a known 2 m distance, then run the analysis path (derive the factor from the
    measured bar, rebuild the board, recover the pose). Only ``factor = 110/100``
    reconstructs the true translation; the reversed ``100/110`` mis-scales it by
    ~17% and this assertion fails.
    """
    measured_bar_mm = 110.0
    true_ratio = measured_bar_mm / 100.0

    physical_board = build_charuco_board(SPEC, print_scale_factor=true_ratio)
    obj_physical = physical_board.getChessboardCorners().reshape(-1, 1, 3).astype(np.float32)
    k4 = [1200.0, 1200.0, 640.0, 360.0]
    rvec = np.array([0.05, -0.03, 0.0])
    tvec = np.array([10.0, -20.0, 2000.0])  # mm
    img = _project(obj_physical, k4, rvec, tvec)

    factor, _ = compute_print_scale(measured_bar_mm)
    analysis_board = build_charuco_board(SPEC, factor)
    obj_analysis = analysis_board.getChessboardCorners().reshape(-1, 1, 3).astype(np.float32)
    _R, t, _plane, reproj = estimate_pose(obj_analysis, img, k4, [0, 0, 0, 0, 0])

    assert t == pytest.approx(tvec, abs=1.0)  # metric translation recovered within 1 mm
    assert reproj < 0.5


# ---- device id ------------------------------------------------------------

def test_device_id_is_deterministic():
    meta = {"make": "Apple", "model": "iPhone 13", "width": 1920, "height": 1080, "orientation": "landscape"}
    assert derive_device_id(meta) == derive_device_id(dict(meta))


def test_device_id_changes_with_resolution():
    base = {"make": "Apple", "model": "iPhone 13", "orientation": "landscape"}
    a, _ = derive_device_id({**base, "width": 1920, "height": 1080})
    b, _ = derive_device_id({**base, "width": 3840, "height": 2160})
    assert a != b


def test_device_id_source_labels():
    _, full = derive_device_id({"make": "Apple", "model": "iPhone", "width": 1920, "height": 1080})
    _, fallback = derive_device_id({"width": 1920, "height": 1080})
    assert full == "full"
    assert fallback == "resolution_only"


# ---- device store ---------------------------------------------------------

def _intrinsics(device_id="dev1", size=(1280, 720)) -> DeviceIntrinsics:
    return DeviceIntrinsics(
        device_id=device_id, image_size=size, K=[1200, 1200, 640, 360], dist_coeffs=[0, 0, 0, 0, 0]
    )


def test_device_store_round_trip(tmp_path):
    store = DeviceStore(tmp_path)
    store.put(_intrinsics())
    got = store.get("dev1", image_size=(1280, 720))
    assert got is not None
    assert got.K == [1200, 1200, 640, 360]
    assert got.status == "valid"


def test_device_store_marks_stale_on_resolution_mismatch(tmp_path):
    store = DeviceStore(tmp_path)
    store.put(_intrinsics(size=(1280, 720)))
    got = store.get("dev1", image_size=(1920, 1080))
    assert got is not None
    assert got.status == "stale"


def test_device_store_missing_returns_none(tmp_path):
    assert DeviceStore(tmp_path).get("nope") is None


# ---- detection on a synthetic board render --------------------------------

def test_detect_board_on_rendered_image():
    board = build_charuco_board(SPEC)
    image = board.generateImage((700, 1000))  # ~ A4 ratio
    detected = detect_board(image, board)
    assert detected is not None
    _obj, _img, n_corners = detected
    # a clean render should recover most interior corners
    assert n_corners >= int(SPEC.expected_charuco_corners * 0.8)


# ---- metric math via synthetic projection (no photo) ----------------------

def _project(obj_mm, k4, rvec, tvec):
    K = np.array([[k4[0], 0, k4[2]], [0, k4[1], k4[3]], [0, 0, 1]], dtype=np.float64)
    img, _ = cv2.projectPoints(obj_mm, rvec, tvec, K, np.zeros(5))
    return img.astype(np.float32)


def test_estimate_pose_recovers_known_translation():
    board = build_charuco_board(SPEC)
    obj = board.getChessboardCorners().reshape(-1, 1, 3).astype(np.float32)
    k4 = [1200.0, 1200.0, 640.0, 360.0]
    rvec = np.array([0.05, -0.03, 0.0])
    tvec = np.array([10.0, -20.0, 2000.0])  # mm, 2 m away
    img = _project(obj, k4, rvec, tvec)

    R, t, plane, reproj = estimate_pose(obj, img, k4, [0, 0, 0, 0, 0])
    assert t == pytest.approx(tvec, abs=1.0)  # within 1 mm
    assert reproj < 0.5
    assert np.linalg.norm(plane.normal) == pytest.approx(1.0, abs=1e-6)


def test_calibrate_intrinsics_recovers_known_K():
    board = build_charuco_board(SPEC)
    obj = board.getChessboardCorners().reshape(-1, 1, 3).astype(np.float32)
    k4 = [1200.0, 1200.0, 640.0, 360.0]
    image_size = (1280, 720)

    rng = np.random.default_rng(0)
    obj_list, img_list = [], []
    for _ in range(15):
        rvec = rng.uniform(-0.4, 0.4, size=3)
        tvec = np.array([rng.uniform(-100, 100), rng.uniform(-100, 100), rng.uniform(1500, 2500)])
        obj_list.append(obj)
        img_list.append(_project(obj, k4, rvec, tvec))

    rec_k4, _dist, rms = calibrate_intrinsics(obj_list, img_list, image_size)
    assert rec_k4[0] == pytest.approx(1200.0, rel=0.05)  # fx
    assert rec_k4[1] == pytest.approx(1200.0, rel=0.05)  # fy
    assert rms < 1.0
