"""Data models for camera calibration (Phase B).

Two lifetimes are modelled separately:

- ``DeviceIntrinsics``: computed once per physical device (camera + resolution)
  and persisted. Holds ``K`` and distortion; tied to a specific ``image_size``.
- ``CameraCalibration``: computed per session from one video; holds the board
  pose (world/floor frame) and reprojection error.

All lengths are in millimetres so metric quantities come out mm-native.
"""

from pydantic import BaseModel, Field


class CharucoBoardSpec(BaseModel):
    """Physical spec of the printed ChArUco board on A4. Single source of truth."""

    version: str = "a4-charuco-v1"
    dictionary: str = "DICT_5X5_100"
    squares_x: int = 7
    squares_y: int = 10
    square_length_mm: float = 25.0
    marker_length_mm: float = 18.0

    @property
    def expected_charuco_corners(self) -> int:
        """Interior chessboard corners the detector can return at most."""
        return (self.squares_x - 1) * (self.squares_y - 1)


class DeviceIntrinsics(BaseModel):
    """Per-device intrinsics, persisted. ``K`` is valid only for ``image_size``."""

    device_id: str
    raw_meta: dict = Field(default_factory=dict)  # make, model, resolution, orientation
    image_size: tuple[int, int]  # (width, height) K is tied to this
    K: list[float]  # [fx, fy, cx, cy]
    dist_coeffs: list[float]
    print_scale_factor: float = 1.0
    board_spec_version: str = "a4-charuco-v1"
    reproj_error_px: float = 0.0
    source: str = "unknown"  # how device_id metadata was obtained
    calibrated_at: str = ""  # ISO-8601
    status: str = "valid"  # valid | stale | failed


class FloorPlane(BaseModel):
    """Plane in the camera coordinate frame: normal . X = d (mm)."""

    normal: list[float]  # unit normal [x, y, z]
    d: float


class BoardDetectionDiagnostics(BaseModel):
    """Why the ChArUco board was (not) found, so a clinician can decide whether
    to ask the patient to re-record. Advisory only -- the system never
    auto-rejects (V1 is decision-support, not diagnosis)."""

    detected: bool
    frames_checked: int = 0
    frames_with_any_marker: int = 0
    max_corners_found: int = 0
    brightness_mean: float = 0.0
    blur_score: float = 0.0
    likely_causes: list[str] = Field(default_factory=list)
    recommendation: str = "ok"  # ok | retake | usable_2d
    message: str = ""


class CameraCalibration(BaseModel):
    """Per-session calibration output. All strategies return this shape."""

    ok: bool
    method: str  # charuco | blank_a4 | assumed_fov
    K: list[float] | None = None  # [fx, fy, cx, cy]
    dist_coeffs: list[float] | None = None
    R: list[list[float]] | None = None  # board(world) -> camera rotation, 3x3
    t: list[float] | None = None  # board origin in camera frame (mm)
    floor_plane: FloorPlane | None = None
    scale_mm_per_unit: float | None = None  # filled in Phase D with the lifted pose
    scale_source: str | None = None
    reproj_error_px: float | None = None
    frames_used: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
