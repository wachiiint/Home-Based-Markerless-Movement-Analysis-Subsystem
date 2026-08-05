"""Serialise the raw 2D pose sequence so a run can be saved and re-opened.

Unlike ``pose3d_export``, this is the *input* to every downstream stage rather
than a picture of the output: angles, ROM, smoothness, symmetry, screening and
the 3D lift are all pure functions of this sequence plus the settings recorded
here. So the file is both an inspection artifact and a faithful replay of a run
whose video is gone -- which matters, because the project stores metrics only
and never keeps the video.

Two deliberate choices:

* Undetected frames stay ``null`` instead of being dropped or zero-filled. The
  sequence must remain time-aligned with the sampled frames or the lift and the
  smoothness window would silently shift.
* ``analysis_settings`` travels with the coordinates. The outlier window and
  smoothness metrics are functions of ``frame_sample_fps``, so a file re-read
  under a different ``.env`` would otherwise produce different numbers with
  nothing to show that it had.

Kept out of ``MovementAssessmentResponse`` for the same reason as the 3D payload:
the clinical contract carries no raw coordinates.
"""

import numpy as np

from app.models.keypoints import HALPE26_EDGES, HALPE26_JOINT_NAMES
from app.services.pose.pose_sequence import PoseSequence

SCHEMA_VERSION = 1

_PIXEL_DECIMALS = 2
_SCORE_DECIMALS = 4


def build_pose2d_payload(
    sequence: PoseSequence,
    *,
    sampled_fps: int,
    analyzed_side: str | None,
    task_type: str,
    source_fps: float,
    duration_sec: float,
    analysis_settings: dict,
) -> dict:
    """Skeleton topology + per-frame Halpe26 pixel coordinates and confidences.

    Coordinates are rounded to keep the file manageable: a 120 s clip at 10 fps
    is ~1200 frames x 26 joints x (2 coords + 1 score).
    """
    frames: list[list[list[float]] | None] = []
    scores: list[list[float] | None] = []
    source_indices: list[int] = []
    valid_mask: list[bool] = []

    for pose in sequence.frames:
        source_indices.append(int(pose.source_frame_index))
        valid_mask.append(pose.has_subject)
        if not pose.has_subject:
            frames.append(None)
            scores.append(None)
            continue
        frames.append(np.round(np.asarray(pose.keypoints, dtype=np.float64), _PIXEL_DECIMALS).tolist())
        scores.append(np.round(np.asarray(pose.scores, dtype=np.float64), _SCORE_DECIMALS).tolist())

    return {
        "schema_version": SCHEMA_VERSION,
        "keypoint_format": "halpe26",
        # Pixel coordinates in the source frame, origin top-left. Not metric:
        # scale needs bone length or a calibrated board.
        "coordinate_space": "pixels",
        "num_frames": len(sequence.frames),
        "fps": sampled_fps,
        "source_video": {
            "width": int(sequence.width),
            "height": int(sequence.height),
            "fps": round(float(source_fps), 3),
            "duration_sec": round(float(duration_sec), 3),
        },
        "joint_names": list(HALPE26_JOINT_NAMES),
        "edges": [list(edge) for edge in HALPE26_EDGES],
        "frames": frames,
        "scores": scores,
        # Index into the *original* video, so a saved sequence can still be
        # lined up against the clip it came from.
        "source_frame_indices": source_indices,
        "valid_mask": valid_mask,
        "task_type": task_type,
        "analyzed_side": analyzed_side,
        "analysis_settings": analysis_settings,
    }
