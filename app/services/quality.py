def compute_pose_quality(scores: list[float], valid_frames: int, total_frames: int) -> dict:
    mean_score = sum(scores) / len(scores) if scores else 0.0
    valid_ratio = valid_frames / total_frames if total_frames else 0.0
    return {
        "mean_keypoint_confidence": mean_score,
        "valid_frame_ratio": valid_ratio,
        "occlusion_warning": valid_ratio < 0.8,
    }
