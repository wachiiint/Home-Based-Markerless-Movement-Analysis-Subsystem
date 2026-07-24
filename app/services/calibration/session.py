"""Per-session ChArUco calibration driven frame-by-frame during pass 1.

``observe(frame)`` is called for each sampled frame; it detects the board with a
unit board (layout-only, size-independent), accumulates diagnostics signals, and
keeps the best detection. ``finalize`` looks up the device intrinsics, recovers
the board pose on the best frame, and returns the calibration plus diagnostics.
"""

import numpy as np

from app.models.calibration import BoardDetectionDiagnostics, CameraCalibration, CharucoBoardSpec
from app.services.calibration.board import build_charuco_board
from app.services.calibration.board_diagnostics import (
    BoardObservationStats,
    build_diagnostics,
    frame_blur_score,
    frame_brightness,
)
from app.services.calibration.charuco_calibrator import detect_charuco, pose_from_charuco
from app.services.calibration.device_id import derive_device_id
from app.services.calibration.device_store import DeviceStore

# Above this per-session reprojection error the intrinsics likely no longer match
# the camera (e.g. EIS/zoom changed the focal length) -> flag as unreliable.
MAX_SESSION_REPROJ_PX = 3.0


class SessionCalibrator:
    def __init__(self, device_store: DeviceStore | None, spec: CharucoBoardSpec | None = None) -> None:
        self.device_store = device_store
        self.spec = spec or CharucoBoardSpec()
        self._detect_board = build_charuco_board(self.spec, print_scale_factor=1.0)
        self.stats = BoardObservationStats()
        self._best_corners = None
        self._best_ids = None
        self._best_n = 0

    def observe(self, frame: np.ndarray) -> None:
        corners, ids, n_corners, n_markers = detect_charuco(frame, self._detect_board)
        self.stats.update(n_markers, n_corners, frame_brightness(frame), frame_blur_score(frame))
        if n_corners > self._best_n:
            self._best_n = n_corners
            self._best_corners = corners
            self._best_ids = ids

    def _has_pose_candidate(self) -> bool:
        from app.services.calibration.charuco_calibrator import MIN_POSE_CORNERS

        return self._best_ids is not None and self._best_n >= MIN_POSE_CORNERS

    def finalize(self, device_meta: dict, image_size: tuple[int, int]) -> tuple[CameraCalibration | None, BoardDetectionDiagnostics]:
        detected = self._has_pose_candidate()
        diagnostics = build_diagnostics(self.stats, detected)
        if not detected:
            return None, diagnostics

        if self.device_store is None:
            return (
                CameraCalibration(ok=False, method="charuco", warnings=["no device store configured"]),
                diagnostics,
            )
        device_id, source = derive_device_id(device_meta)
        intrinsics = self.device_store.get(device_id, image_size=image_size)
        if intrinsics is None:
            w, h = image_size
            return CameraCalibration(
                ok=False,
                method="charuco",
                warnings=[
                    f"device not calibrated (device_id={device_id}, source={source}, {w}x{h}); "
                    "calibrate this device at the SAME resolution/orientation as the patient clip"
                ],
            ), diagnostics
        if intrinsics.status != "valid":
            detail = ""
            if intrinsics.status == "stale":
                detail = (
                    f"; calibrated at {intrinsics.image_size[0]}x{intrinsics.image_size[1]} but clip is "
                    f"{image_size[0]}x{image_size[1]} -- recalibrate at the clip resolution"
                )
            return CameraCalibration(ok=False, method="charuco", warnings=[f"intrinsics {intrinsics.status}{detail}"]), diagnostics

        board = build_charuco_board(self.spec, intrinsics.print_scale_factor)
        R, t, plane, reproj = pose_from_charuco(self._best_corners, self._best_ids, board, intrinsics.K, intrinsics.dist_coeffs)

        warnings: list[str] = []
        if source == "resolution_only":
            warnings.append("device_id from resolution only (low confidence)")
        if reproj > MAX_SESSION_REPROJ_PX:
            warnings.append(f"high session reproj {reproj:.2f}px; intrinsics may not match (EIS/zoom?)")

        return (
            CameraCalibration(
                ok=True,
                method="charuco",
                K=intrinsics.K,
                dist_coeffs=intrinsics.dist_coeffs,
                R=[[float(v) for v in row] for row in R],
                t=[float(v) for v in t],
                floor_plane=plane,
                reproj_error_px=reproj,
                warnings=warnings,
            ),
            diagnostics,
        )
