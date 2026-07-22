import logging
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from app.core.config import Settings
from app.models.keypoints import leg_indices
from app.models.task_config import TASK_CONFIGS
from app.schemas.movement import TaskType
from app.services.calibration.device_id import extract_capture_metadata
from app.services.calibration.session import SessionCalibrator
from app.services.calibration.transform import camera_to_floor_6dof
from app.services.analysis.kinematics import three_point_angle, range_of_motion
from app.services.lifting.angles_3d import angle_series_3d, supports_3d_angle
from app.services.lifting.guards import bone_length_consistency
from app.services.lifting.metric_scale import resolve_metric_scale
from app.services.lifting.pipeline import lift_pose_sequence
from app.services.lifting.pose3d_export import build_pose3d_payload
from app.services.pose.pose_estimator import PoseEstimator
from app.services.pose.pose_sequence import FramePose2D, PoseSequence
from app.services.response_mapper import build_assessment_response
from app.services.analysis.screening import screen_rom
from app.services.analysis.smoothing import exponential_moving_average
from app.services.analysis.smoothness import compute_smoothness
from app.services.analysis.symmetry import SideRom, compute_symmetry
from app.services.pose.subject_selector import select_main_subject
from app.services.video_io import read_video_metadata

logger = logging.getLogger(__name__)


def _angle_for_frame(keypoints, scores, task_type: TaskType, side: str, threshold: float) -> float | None:
    config = TASK_CONFIGS[task_type]
    indices = leg_indices(side)
    required = [indices[config.vertex_joint], indices[config.ray_a_joint], indices[config.ray_b_joint]]
    if any(float(scores[index]) < threshold for index in required):
        return None
    points = [(float(keypoints[index][0]), float(keypoints[index][1])) for index in required]
    return three_point_angle(points[1], points[0], points[2])


# Below this, the two legs' motion is treated as a tie and the "primary" side
# (used for 3D + the representative pose-quality reading) is decided by keypoint
# confidence instead of range of motion.
_SIDE_ROM_TIE_DEG = 15.0

_RISK_ORDER = {"low": 0, "moderate": 1, "high": 2}


@dataclass(frozen=True)
class LegAnalysis:
    """Whole-clip 2D analysis for one leg. Both legs are reported to the doctor,
    so this is computed for each side rather than only a chosen one."""

    side: str
    min_angle: float
    max_angle: float
    rom: float
    valid_frames: int
    valid_frame_ratio: float
    mean_confidence: float
    smoothness: dict


def _analyze_leg(sequence: PoseSequence, task_type: TaskType, side: str, settings: Settings, processed_frames: int) -> LegAnalysis | None:
    """Angle/ROM/quality/smoothness for one leg over the whole clip, or None if
    the leg never has all three required joints confidently visible."""
    angles: list[float] = []
    confidences: list[float] = []
    for pose in sequence.frames:
        if not pose.has_subject:
            continue
        angle = _angle_for_frame(pose.keypoints, pose.scores, task_type, side, settings.min_keypoint_confidence)
        if angle is not None:
            angles.append(angle)
            confidences.append(float(np.mean(pose.scores)))
    if not angles:
        return None
    smoothed = exponential_moving_average(angles, settings.smoothing_alpha)
    min_angle, max_angle, rom = range_of_motion(smoothed)
    return LegAnalysis(
        side=side,
        min_angle=min_angle,
        max_angle=max_angle,
        rom=rom,
        valid_frames=len(angles),
        valid_frame_ratio=len(angles) / processed_frames if processed_frames else 0.0,
        mean_confidence=float(np.mean(confidences)),
        smoothness=compute_smoothness(smoothed, settings.frame_sample_fps),
    )


def _analyze_both_legs(sequence: PoseSequence, task_type: TaskType, settings: Settings) -> dict[str, LegAnalysis]:
    """Per-leg analysis for whichever legs are usable (single source of truth for
    the report, side selection, symmetry, and screening)."""
    legs: dict[str, LegAnalysis] = {}
    for side in ("left", "right"):
        leg = _analyze_leg(sequence, task_type, side, settings, sequence.processed_frames)
        if leg is not None:
            legs[side] = leg
    return legs


def _select_analyzed_side(legs: dict[str, LegAnalysis]) -> str | None:
    """Pick the *primary* leg: the exercised one (larger ROM), confidence breaking
    ties. Both legs are reported regardless; this only drives the single-leg 3D
    lift and the representative pose-quality reading.
    """
    if not legs:
        return None
    if len(legs) == 1:
        return next(iter(legs))
    left, right = legs["left"], legs["right"]
    if abs(left.rom - right.rom) >= _SIDE_ROM_TIE_DEG:
        return "left" if left.rom > right.rom else "right"
    return "left" if left.mean_confidence >= right.mean_confidence else "right"


def _screen_both_legs(legs: dict[str, LegAnalysis], task_type: TaskType, settings: Settings) -> tuple[str, float, list[str]]:
    """Screen each leg; the top-line risk is the worse side. Flags are tagged by
    side so the headline has a visible reason (e.g. ``right: rom_below_borderline``)."""
    config = TASK_CONFIGS[task_type]
    risk, confidence, flags = "low", 1.0, []
    for side in ("left", "right"):
        leg = legs.get(side)
        if leg is None:
            continue
        leg_risk, leg_conf, leg_flags = screen_rom(
            rom_deg=leg.rom,
            expected_rom_deg=config.expected_rom_deg,
            borderline_rom_deg=config.borderline_rom_deg,
            valid_frame_ratio=leg.valid_frame_ratio,
            min_valid_frame_ratio=settings.min_valid_frame_ratio,
            mean_keypoint_confidence=leg.mean_confidence,
        )
        flags.extend(f"{side}: {flag}" for flag in leg_flags)
        if leg.rom < config.borderline_rom_deg:
            flags.append(f"{side}: rom_below_borderline")
        elif leg.rom < config.expected_rom_deg:
            flags.append(f"{side}: rom_below_expected")
        if _RISK_ORDER[leg_risk] > _RISK_ORDER[risk]:
            risk, confidence = leg_risk, leg_conf
        elif risk == "low" and leg_risk == "low":
            # both low so far -> keep the least confident reading as the headline
            confidence = min(confidence, leg_conf)
    return risk, confidence, flags


def _collect_pose_sequence(input_path: Path, output_path: Path, metadata: dict, settings: Settings, estimator: PoseEstimator, frame_observer=None) -> PoseSequence:
    """Pass 1: run 2D inference over sampled frames, write the annotated video,
    and collect the main-subject 2D pose per frame into a ``PoseSequence``.

    ``frame_observer`` (optional) is called with each sampled BGR frame before
    annotation -- used by the session calibrator to detect the ChArUco board.
    """
    capture = cv2.VideoCapture(str(input_path))
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), settings.frame_sample_fps, (metadata["width"], metadata["height"]))
    if not writer.isOpened():
        capture.release()
        raise ValueError("unable to create annotated video")

    sample_interval = max(1, round(metadata["fps"] / settings.frame_sample_fps))
    frames: list[FramePose2D] = []
    frame_index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index % sample_interval:
                frame_index += 1
                continue
            if frame_observer is not None:
                frame_observer(frame)
            keypoints, scores = estimator.infer(frame)
            subject = select_main_subject(list(zip(keypoints, scores)))
            annotated = frame.copy()
            subject_keypoints = subject_scores = None
            if subject is not None:
                subject_keypoints, subject_scores = subject
                from rtmlib import draw_skeleton

                annotated = draw_skeleton(
                    annotated,
                    subject_keypoints[None, :, :],
                    subject_scores[None, :],
                    kpt_thr=settings.min_keypoint_confidence,
                )
            writer.write(annotated)
            frames.append(
                FramePose2D(
                    frame_index=len(frames),
                    source_frame_index=frame_index,
                    keypoints=subject_keypoints,
                    scores=subject_scores,
                )
            )
            frame_index += 1
    finally:
        capture.release()
        writer.release()

    return PoseSequence(frames=frames, width=metadata["width"], height=metadata["height"])


@dataclass
class _ThreeDResult:
    analysis_mode: str = "2d"
    joint_angles_3d: dict = field(default_factory=dict)
    scale_mm_per_unit: float | None = None
    scale_source: str | None = None
    transformation_6dof: object | None = None
    board_diagnostics: object | None = None
    guard_warnings: list = field(default_factory=list)
    pose_3d: dict | None = None


def _augment_with_3d(
    sequence, task_type, side, settings, lifter, calibrator, device_meta, subject_height_mm, want_pose_3d=False, report_sides=None
) -> _ThreeDResult:
    """Best-effort 3D. Never raises: any failure returns a 2D result so the
    endpoint always responds (falls back to the 2D analysis).

    Two separable outputs come from one lift:

    * ``pose_3d`` -- root-relative coordinates for the demo viewer. Needs only
      the lifter, no board, and is produced solely when ``want_pose_3d`` is set
      (it is display-only, so the clinical endpoint does not pay for the lift).
    * metric 3D (``joint_angles_3d``, scale, 6DoF) -- additionally requires a
      calibrated board and a task whose angle is defined in 3D.
    """
    result = _ThreeDResult()
    if lifter is None:
        return result
    try:
        calibration = None
        if calibrator is not None:
            calibration, diagnostics = calibrator.finalize(device_meta, (sequence.width, sequence.height))
            result.board_diagnostics = diagnostics
            result.transformation_6dof = camera_to_floor_6dof(calibration)
            if calibration is not None:
                result.guard_warnings += list(calibration.warnings)

        metric_possible = (
            calibration is not None
            and calibration.ok
            and supports_3d_angle(task_type)  # calibrated but e.g. ankle -> angles stay 2D
            and side is not None
        )
        if not (want_pose_3d or metric_possible):
            return result

        lifted = lift_pose_sequence(sequence, lifter)
        lift_ok, _cv, bone_warnings = bone_length_consistency(lifted.keypoints_3d, lifted.valid_mask)
        result.guard_warnings += bone_warnings

        if metric_possible and lift_ok:
            # Report both legs (side-prefixed), mirroring the 2D joint_angles.
            config = TASK_CONFIGS[task_type]
            joint_angles_3d: dict[str, float] = {}
            for leg_side in (report_sides or ["left", "right"]):
                angles = angle_series_3d(lifted.keypoints_3d, task_type, leg_side)
                smoothed = exponential_moving_average(angles, settings.smoothing_alpha)
                min_a, max_a, rom = range_of_motion(smoothed)
                joint_angles_3d[f"{leg_side}_{config.max_key}_3d"] = round(max_a, 2)
                joint_angles_3d[f"{leg_side}_{config.min_key}_3d"] = round(min_a, 2)
                joint_angles_3d[f"{leg_side}_{config.rom_key}_3d"] = rom
            result.joint_angles_3d = joint_angles_3d
            scale, scale_source, scale_warnings = resolve_metric_scale(
                lifted.keypoints_2d_h36m, lifted.keypoints_3d, lifted.valid_mask, calibration, subject_height_mm,
            )
            result.scale_mm_per_unit = scale
            result.scale_source = scale_source
            result.guard_warnings += scale_warnings
            result.analysis_mode = "3d"

        if want_pose_3d:
            # Shown even when the guard rejects the lift, flagged so the viewer
            # can warn: it is a picture, not a clinical number.
            result.pose_3d = build_pose3d_payload(
                lifted,
                sampled_fps=settings.frame_sample_fps,
                analyzed_side=side,
                lift_reliable=lift_ok,
                lift_warnings=bone_warnings,
                analysis_mode=result.analysis_mode,
            )
    except Exception:
        logger.exception("3D augmentation failed; using 2D result")
        result.analysis_mode = "2d"
        result.guard_warnings.append("3d augmentation failed; see logs")
    return result


@dataclass
class VideoAnalysis:
    """Analysis output. ``pose_3d`` is the demo viewer's display payload and is
    deliberately kept beside the response rather than inside it, so the clinical
    contract carries no raw coordinates."""

    response: object
    pose_3d: dict | None = None


def analyze_video(input_path: Path, output_path: Path, task_type: TaskType, view: str, settings: Settings, estimator: PoseEstimator, lifter=None, device_store=None, subject_height_mm: float | None = None, want_pose_3d: bool = False, device_make: str = "", device_model: str = "") -> VideoAnalysis:
    metadata = read_video_metadata(input_path)
    calibrator = SessionCalibrator(device_store) if (lifter is not None and device_store is not None) else None
    observer = calibrator.observe if calibrator is not None else None
    sequence = _collect_pose_sequence(input_path, output_path, metadata, settings, estimator, frame_observer=observer)

    processed_frames = sequence.processed_frames
    config = TASK_CONFIGS[task_type]

    # Analyze BOTH legs and report each to the doctor -- no single-leg selection.
    # A "primary" side is still chosen (larger ROM = the exercised leg) only to
    # drive the single-leg 3D lift and the representative pose-quality reading.
    legs = _analyze_both_legs(sequence, task_type, settings)
    if not legs:
        raise ValueError("no usable pose found in video")
    side = _select_analyzed_side(legs)
    analyzed_side = "both" if len(legs) == 2 else side

    joint_angles: dict[str, float] = {}
    smoothness: dict[str, dict] = {}
    for leg_side, leg in legs.items():
        joint_angles[f"{leg_side}_{config.max_key}"] = round(leg.max_angle, 2)
        joint_angles[f"{leg_side}_{config.min_key}"] = round(leg.min_angle, 2)
        joint_angles[f"{leg_side}_{config.rom_key}"] = leg.rom
        if leg.smoothness:
            smoothness[leg_side] = leg.smoothness

    symmetry_score = compute_symmetry(
        {s: SideRom(rom_deg=leg.rom, mean_confidence=leg.mean_confidence, valid_frames=leg.valid_frames) for s, leg in legs.items()},
        config.borderline_rom_deg,
    )
    risk, confidence, flags = _screen_both_legs(legs, task_type, settings)

    # pose_quality reports the exercised (primary) leg -- the rep the clinician cares about.
    primary = legs[side]

    device_meta = extract_capture_metadata(input_path)
    # MP4 upload strips EXIF make/model, so the video-derived id degrades to
    # "resolution_only" and never matches a device calibrated with --make/--model.
    # Let the caller (request form) supply them so both sides derive the same id.
    if device_make:
        device_meta["make"] = device_make
    if device_model:
        device_meta["model"] = device_model
    three_d = _augment_with_3d(
        sequence, task_type, side, settings, lifter, calibrator, device_meta, subject_height_mm, want_pose_3d,
        report_sides=list(legs.keys()),
    )

    response = build_assessment_response(
        task_type=task_type,
        view=view,
        duration_sec=metadata["duration_sec"],
        fps=metadata["fps"],
        processed_frames=processed_frames,
        sampled_fps=settings.frame_sample_fps,
        angle_min=primary.min_angle,
        angle_max=primary.max_angle,
        mean_keypoint_confidence=primary.mean_confidence,
        valid_frame_ratio=primary.valid_frame_ratio,
        risk_level=risk,
        confidence_score=confidence,
        flags=flags,
        analyzed_side=analyzed_side,
        joint_angles_override=joint_angles,
        analysis_mode=three_d.analysis_mode,
        joint_angles_3d=three_d.joint_angles_3d,
        scale_mm_per_unit=three_d.scale_mm_per_unit,
        scale_source=three_d.scale_source,
        transformation_6dof=three_d.transformation_6dof,
        board_diagnostics=three_d.board_diagnostics,
        guard_warnings=three_d.guard_warnings,
        smoothness=smoothness,
        symmetry_index_score=symmetry_score,
    )
    return VideoAnalysis(response=response, pose_3d=three_d.pose_3d)
