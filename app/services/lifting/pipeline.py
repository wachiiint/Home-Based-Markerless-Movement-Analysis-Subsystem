"""Bridge the Phase A PoseSequence to a lifted 3D sequence.

Steps: gather 2D arrays (filling gaps), Halpe26->H36M17, normalize, then lift.
Kept standalone (does not touch analyze_video); Phase D wires it in.
"""

from dataclasses import dataclass

import numpy as np

from app.services.lifting.lifter import Lifter
from app.services.lifting.normalize import normalize_screen_coordinates
from app.services.lifting.skeleton_convert import halpe26_to_h36m17
from app.services.pose_sequence import PoseSequence


@dataclass
class Lifted3DSequence:
    keypoints_3d: np.ndarray  # (T, 17, 3) root-relative
    valid_mask: np.ndarray  # (T,) bool: frame had a real detection
    width: int
    height: int


def sequence_to_arrays(sequence: PoseSequence) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Dense (T, 26, 2)/(T, 26) arrays + (T,) validity mask.

    Missing frames (no subject) are filled by nearest-valid hold so the lifter
    receives a continuous sequence; the mask records which frames were real.
    """
    t = sequence.processed_frames
    keypoints = np.zeros((t, 26, 2), dtype=np.float64)
    scores = np.zeros((t, 26), dtype=np.float64)
    valid = np.zeros(t, dtype=bool)
    for i, frame in enumerate(sequence.frames):
        if frame.has_subject:
            keypoints[i] = frame.keypoints
            scores[i] = frame.scores
            valid[i] = True

    if valid.any():
        valid_idx = np.where(valid)[0]
        for i in range(t):
            if not valid[i]:
                nearest = valid_idx[np.argmin(np.abs(valid_idx - i))]
                keypoints[i] = keypoints[nearest]
                scores[i] = scores[nearest]
    return keypoints, scores, valid


def lift_pose_sequence(sequence: PoseSequence, lifter: Lifter) -> Lifted3DSequence:
    keypoints, scores, valid = sequence_to_arrays(sequence)
    if not valid.any():
        raise ValueError("no usable pose found in sequence")

    kp17, sc17 = halpe26_to_h36m17(keypoints, scores)
    normalized = normalize_screen_coordinates(kp17, sequence.width, sequence.height)
    keypoints_3d = lifter.lift(normalized, sc17)

    keypoints_3d = np.asarray(keypoints_3d, dtype=np.float64)
    if keypoints_3d.shape != (sequence.processed_frames, 17, 3):
        raise ValueError(
            f"lifter returned {keypoints_3d.shape}, expected {(sequence.processed_frames, 17, 3)}"
        )
    return Lifted3DSequence(
        keypoints_3d=keypoints_3d, valid_mask=valid, width=sequence.width, height=sequence.height
    )
