from dataclasses import dataclass

import numpy as np


@dataclass
class FramePose2D:
    """One sampled frame's main-subject 2D pose.

    ``keypoints``/``scores`` are ``None`` when no subject was detected in the
    frame, so the sequence stays time-aligned with the sampled frames (gaps
    included) for later temporal processing such as 2D->3D lifting.
    """

    frame_index: int
    source_frame_index: int
    keypoints: np.ndarray | None  # (26, 2) pixel coordinates
    scores: np.ndarray | None  # (26,) confidences in [0, 1]

    @property
    def has_subject(self) -> bool:
        return self.keypoints is not None and self.scores is not None


@dataclass
class PoseSequence:
    """Full-clip sequence of sampled 2D poses plus frame geometry."""

    frames: list[FramePose2D]
    width: int
    height: int

    @property
    def processed_frames(self) -> int:
        return len(self.frames)
