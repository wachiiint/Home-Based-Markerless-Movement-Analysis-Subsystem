from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.calibration import BoardDetectionDiagnostics


class VideoMetadata(BaseModel):
    duration_sec: float
    fps: float
    view: str
    task_type: str
    processed_frames: int
    sampled_fps: int
    # The leg the patient was instructed to move, echoed back from the request.
    # The other leg's metrics are still reported, as a contralateral reference.
    analyzed_side: str | None = None


class PoseQuality(BaseModel):
    mean_keypoint_confidence: float = Field(ge=0, le=1)
    valid_frame_ratio: float = Field(ge=0, le=1)
    occlusion_warning: bool


class ClinicalMetrics(BaseModel):
    joint_angles: dict[str, float]
    joint_angles_3d: dict[str, float] = Field(default_factory=dict)
    scale_mm_per_unit: float | None = None
    scale_source: str | None = None
    gait_parameters: dict = Field(default_factory=dict)
    compensation: dict = Field(default_factory=dict)
    smoothness: dict = Field(default_factory=dict)
    symmetry_index_score: float | None = None
    pose_quality: PoseQuality


class AngleTrajectory(BaseModel):
    """The smoothed 2D joint angle through time -- the movement itself, rather
    than only its extremes.

    One entry per **sampled** frame, so the two legs and the time axis stay
    aligned. A frame whose joints were not confidently visible keeps its slot
    with ``null``: a gap in the graph is the honest picture, an interpolated
    value would invent movement that was never seen.
    """

    # Angle name without the side prefix, e.g. "estimated_knee_angle_deg".
    joint: str
    time_sec: list[float]
    left_angle_deg: list[float | None] | None = None
    right_angle_deg: list[float | None] | None = None


class ScreeningResult(BaseModel):
    risk_level: Literal["low", "moderate", "high"]
    confidence_score: float = Field(ge=0, le=1)
    flags: list[str]


class TransformationMatrix6DoF(BaseModel):
    frame: str = "camera_to_floor"
    matrix: list[list[float]]  # 4x4 homogeneous
    translation_mm: list[float]  # [x, y, z]
    rotation_deg: list[float]  # euler xyz


class MovementAssessmentResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str
    video_metadata: VideoMetadata
    clinical_metrics: ClinicalMetrics
    screening_result: ScreeningResult
    # Kept beside the summary metrics rather than inside them: it is the raw
    # movement for plotting, not a clinical figure. None when no angle series
    # was produced (the fake-mode response).
    trajectory: AngleTrajectory | None = None
    transformation_matrix_6dof: TransformationMatrix6DoF | None = None
    analysis_mode: Literal["2d", "3d"] = "2d"
    board_diagnostics: BoardDetectionDiagnostics | None = None
    guard_warnings: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    device: Literal["cuda:0", "cpu"]
    model_backend: str
    model_loaded: bool


class DemoAssessmentResponse(BaseModel):
    assessment: MovementAssessmentResponse
    annotated_video_url: str
    # Download targets for the export row. The JSON form of each artifact is the
    # complete one; the CSV is a flat spreadsheet view that drops the skeleton
    # topology and the replay settings. Nulls mean that run produced no 3D/2D.
    assessment_url: str
    assessment_csv_url: str
    # The angle graph as a spreadsheet: one row per sampled frame. Null when the
    # run produced no trajectory.
    trajectory_csv_url: str | None = None
    # pose_3d_url is also what the 3D viewer fetches to render.
    pose_3d_url: str | None = None
    pose_3d_csv_url: str | None = None
    pose_2d_url: str | None = None
    pose_2d_csv_url: str | None = None
    expires_at: str
