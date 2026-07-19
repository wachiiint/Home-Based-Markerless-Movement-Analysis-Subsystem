from uuid import uuid4

from app.models.calibration import BoardDetectionDiagnostics
from app.models.task_config import TASK_CONFIGS
from app.schemas.movement import TaskType
from app.schemas.response import (
    ClinicalMetrics,
    MovementAssessmentResponse,
    PoseQuality,
    ScreeningResult,
    TransformationMatrix6DoF,
    VideoMetadata,
)


def build_assessment_response(
    *,
    task_type: TaskType,
    view: str,
    duration_sec: float,
    fps: float,
    processed_frames: int,
    sampled_fps: int,
    angle_min: float,
    angle_max: float,
    mean_keypoint_confidence: float,
    valid_frame_ratio: float,
    risk_level: str,
    confidence_score: float,
    flags: list[str],
    analyzed_side: str | None = None,
    analysis_mode: str = "2d",
    joint_angles_3d: dict[str, float] | None = None,
    scale_mm_per_unit: float | None = None,
    scale_source: str | None = None,
    transformation_6dof: TransformationMatrix6DoF | None = None,
    board_diagnostics: BoardDetectionDiagnostics | None = None,
    guard_warnings: list[str] | None = None,
) -> MovementAssessmentResponse:
    config = TASK_CONFIGS[task_type]
    rom = round(angle_max - angle_min, 2)
    joint_angles = {
        config.max_key: round(angle_max, 2),
        config.min_key: round(angle_min, 2),
        config.rom_key: rom,
    }

    return MovementAssessmentResponse(
        session_id=f"rtmpose-{uuid4()}",
        video_metadata=VideoMetadata(
            duration_sec=round(duration_sec, 2),
            fps=round(fps, 2),
            view=view,
            task_type=task_type.value,
            processed_frames=processed_frames,
            sampled_fps=sampled_fps,
            analyzed_side=analyzed_side,
        ),
        clinical_metrics=ClinicalMetrics(
            joint_angles=joint_angles,
            joint_angles_3d=joint_angles_3d or {},
            scale_mm_per_unit=scale_mm_per_unit,
            scale_source=scale_source,
            gait_parameters={},
            compensation={},
            smoothness={},
            symmetry_index_score=None,
            pose_quality=PoseQuality(
                mean_keypoint_confidence=mean_keypoint_confidence,
                valid_frame_ratio=valid_frame_ratio,
                occlusion_warning=valid_frame_ratio < 0.8, #TODO: Questionable ?
            ),
        ),
        screening_result=ScreeningResult(
            risk_level=risk_level,  # type: ignore[arg-type]
            confidence_score=confidence_score,
            flags=flags,
        ),
        transformation_matrix_6dof=transformation_6dof,
        analysis_mode=analysis_mode,  # type: ignore[arg-type]
        board_diagnostics=board_diagnostics,
        guard_warnings=guard_warnings or [],
    )


def build_fake_response(task_type: TaskType, view: str, sampled_fps: int) -> MovementAssessmentResponse:
    return build_assessment_response(
        task_type=task_type,
        view=view,
        duration_sec=12.4,
        fps=30,
        processed_frames=124,
        sampled_fps=sampled_fps,
        angle_min=4.2,
        angle_max=61.4,
        mean_keypoint_confidence=0.88,
        valid_frame_ratio=0.94,
        risk_level="low",
        confidence_score=0.82,
        flags=[],
        analyzed_side="left",
    )
