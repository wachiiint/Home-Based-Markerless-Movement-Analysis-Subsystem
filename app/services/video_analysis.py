from pathlib import Path

import cv2
import numpy as np

from app.core.config import Settings
from app.models.keypoints import leg_indices
from app.models.task_config import TASK_CONFIGS
from app.schemas.movement import TaskType
from app.services.kinematics import three_point_angle, range_of_motion
from app.services.pose_estimator import PoseEstimator
from app.services.response_mapper import build_assessment_response
from app.services.screening import screen_rom
from app.services.smoothing import exponential_moving_average
from app.services.subject_selector import select_main_subject
from app.services.video_io import read_video_metadata


def _angle_for_frame(keypoints, scores, task_type: TaskType, side: str, threshold: float) -> float | None:
    config = TASK_CONFIGS[task_type]
    indices = leg_indices(side)
    required = [indices[config.vertex_joint], indices[config.ray_a_joint], indices[config.ray_b_joint]]
    if any(float(scores[index]) < threshold for index in required):
        return None
    points = [(float(keypoints[index][0]), float(keypoints[index][1])) for index in required]
    return three_point_angle(points[1], points[0], points[2])


def _choose_side(keypoints, scores, task_type: TaskType, threshold: float) -> str | None:
    candidates = []
    for side in ("left", "right"):
        angle = _angle_for_frame(keypoints, scores, task_type, side, threshold)
        if angle is not None:
            indices = leg_indices(side)
            needed = [indices[TASK_CONFIGS[task_type].vertex_joint], indices[TASK_CONFIGS[task_type].ray_a_joint], indices[TASK_CONFIGS[task_type].ray_b_joint]]
            candidates.append((float(np.mean([scores[i] for i in needed])), side))
    return max(candidates)[1] if candidates else None


def analyze_video(input_path: Path, output_path: Path, task_type: TaskType, view: str, settings: Settings, estimator: PoseEstimator) -> object:
    metadata = read_video_metadata(input_path)
    capture = cv2.VideoCapture(str(input_path))
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), settings.frame_sample_fps, (metadata["width"], metadata["height"]))
    if not writer.isOpened():
        capture.release()
        raise ValueError("unable to create annotated video")

    sample_interval = max(1, round(metadata["fps"] / settings.frame_sample_fps))
    angle_samples: list[float] = []
    confidence_samples: list[float] = []
    valid_frames = 0
    processed_frames = 0
    side: str | None = None
    frame_index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index % sample_interval:
                frame_index += 1
                continue
            keypoints, scores = estimator.infer(frame)
            subject = select_main_subject(list(zip(keypoints, scores)))
            annotated = frame.copy()
            if subject is not None:
                subject_keypoints, subject_scores = subject
                from rtmlib import draw_skeleton

                annotated = draw_skeleton(
                    annotated,
                    subject_keypoints[None, :, :],
                    subject_scores[None, :],
                    kpt_thr=settings.min_keypoint_confidence,
                )
                if side is None:
                    side = _choose_side(subject_keypoints, subject_scores, task_type, settings.min_keypoint_confidence)
                if side:
                    angle = _angle_for_frame(subject_keypoints, subject_scores, task_type, side, settings.min_keypoint_confidence)
                    if angle is not None:
                        angle_samples.append(angle)
                        valid_frames += 1
                        confidence_samples.append(float(np.mean(subject_scores)))
            writer.write(annotated)
            processed_frames += 1
            frame_index += 1
    finally:
        capture.release()
        writer.release()

    if not angle_samples:
        raise ValueError("no usable pose found in video")
    smoothed = exponential_moving_average(angle_samples, settings.smoothing_alpha)
    min_angle, max_angle, rom = range_of_motion(smoothed)
    quality_ratio = valid_frames / processed_frames if processed_frames else 0.0
    mean_confidence = float(np.mean(confidence_samples)) if confidence_samples else 0.0
    config = TASK_CONFIGS[task_type]
    risk, confidence, flags = screen_rom(
        rom_deg=rom,
        expected_rom_deg=config.expected_rom_deg,
        borderline_rom_deg=config.borderline_rom_deg,
        valid_frame_ratio=quality_ratio,
        min_valid_frame_ratio=settings.min_valid_frame_ratio,
        mean_keypoint_confidence=mean_confidence,
    )
    return build_assessment_response(
        task_type=task_type,
        view=view,
        duration_sec=metadata["duration_sec"],
        fps=metadata["fps"],
        processed_frames=processed_frames,
        sampled_fps=settings.frame_sample_fps,
        angle_min=min_angle,
        angle_max=max_angle,
        mean_keypoint_confidence=mean_confidence,
        valid_frame_ratio=quality_ratio,
        risk_level=risk,
        confidence_score=confidence,
        flags=flags,
        analyzed_side=side,
    )
