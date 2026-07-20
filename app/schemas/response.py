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
    # Lazily fetched by the 3D viewer; null when the lifter is off/unavailable.
    pose_3d_url: str | None = None
    expires_at: str
