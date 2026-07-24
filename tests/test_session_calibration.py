import numpy as np

from app.models.calibration import CharucoBoardSpec, DeviceIntrinsics
from app.services.calibration.board import build_charuco_board
from app.services.calibration.device_id import derive_device_id
from app.services.calibration.device_store import DeviceStore
from app.services.calibration.session import SessionCalibrator

SPEC = CharucoBoardSpec()
IMG_W, IMG_H = 700, 1000
META = {"make": "acme", "model": "phone", "width": IMG_W, "height": IMG_H, "orientation": "portrait"}


def _board_image():
    board = build_charuco_board(SPEC)
    return board.generateImage((IMG_W, IMG_H), marginSize=30)


def _store_with_intrinsics(tmp_path) -> DeviceStore:
    store = DeviceStore(tmp_path)
    device_id, _ = derive_device_id(META)
    store.put(
        DeviceIntrinsics(
            device_id=device_id,
            image_size=(IMG_W, IMG_H),
            K=[900.0, 900.0, IMG_W / 2, IMG_H / 2],
            dist_coeffs=[0, 0, 0, 0, 0],
        )
    )
    return store


def test_session_calibrates_with_board_and_intrinsics(tmp_path):
    store = _store_with_intrinsics(tmp_path)
    calib = SessionCalibrator(store, SPEC)
    image = _board_image()
    for _ in range(3):
        calib.observe(image)
    calibration, diag = calib.finalize(META, (IMG_W, IMG_H))

    assert diag.detected
    assert calibration is not None and calibration.ok
    assert calibration.floor_plane is not None
    assert calibration.reproj_error_px is not None and calibration.reproj_error_px < 3.0


def test_session_board_detected_but_device_not_calibrated(tmp_path):
    calib = SessionCalibrator(DeviceStore(tmp_path), SPEC)  # empty store
    image = _board_image()
    for _ in range(3):
        calib.observe(image)
    calibration, diag = calib.finalize(META, (IMG_W, IMG_H))

    assert diag.detected  # board was fine...
    assert calibration is not None and not calibration.ok  # ...but no intrinsics
    assert any("device not calibrated" in w for w in calibration.warnings)


def test_session_board_absent(tmp_path):
    calib = SessionCalibrator(_store_with_intrinsics(tmp_path), SPEC)
    # a lit, textured room (noise) with no board -> not dark, not blurry
    rng = np.random.default_rng(0)
    scene = rng.integers(60, 200, size=(IMG_H, IMG_W, 3), dtype=np.uint8)
    for _ in range(4):
        calib.observe(scene)
    calibration, diag = calib.finalize(META, (IMG_W, IMG_H))

    assert not diag.detected
    assert calibration is None
    assert "board_absent" in diag.likely_causes


def test_session_stale_intrinsics_on_resolution_mismatch(tmp_path):
    store = _store_with_intrinsics(tmp_path)  # calibrated at 700x1000
    calib = SessionCalibrator(store, SPEC)
    image = _board_image()
    for _ in range(3):
        calib.observe(image)
    # finalize with a different resolution -> intrinsics marked stale
    calibration, diag = calib.finalize(META, (1920, 1080))
    assert calibration is not None and not calibration.ok
    assert any("stale" in w for w in calibration.warnings)
