"""2D normalization for MotionBERT lifting.

MotionBERT is trained with the *subject's bounding box* mapped to [-1, 1] --
not the image (``lib/utils/utils_data.py``: ``crop_scale`` / ``crop_scale_3d``).
Crucially ``crop_scale_3d`` divides z by that same bounding-box scale, so the
predicted depth is expressed in bounding-box units.

Normalizing by the image instead (VideoPose3D's convention) makes the subject
smaller than anything the model saw in training and the predicted depth comes
out compressed several-fold -- measured at ~3x on a subject filling 37% of the
frame. It only looks correct when the subject happens to fill the frame, which
is why upstream wild-inference demos appear fine.
"""

import numpy as np


def crop_scale(keypoints: np.ndarray, scores: np.ndarray, ratio: float = 1.0) -> np.ndarray:
    """Map the subject's bounding box to [-1, 1], as MotionBERT was trained.

    ``keypoints``: (T, J, 2) pixels, ``scores``: (T, J). Returns (T, J, 2).
    The longer side of the box spans the full range; the shorter side keeps its
    aspect ratio. Joints with a zero score are zeroed, matching upstream.
    """
    keypoints = np.asarray(keypoints, dtype=np.float64)
    scores = np.asarray(scores, dtype=np.float64)
    if keypoints.ndim != 3 or keypoints.shape[-1] != 2:
        raise ValueError(f"expected keypoints (T, J, 2), got {keypoints.shape}")
    if scores.shape != keypoints.shape[:2]:
        raise ValueError(f"scores {scores.shape} do not match keypoints {keypoints.shape[:2]}")

    valid = scores > 0
    if not valid.any():
        raise ValueError("no valid keypoints to normalize")

    xs_valid = keypoints[..., 0][valid]
    ys_valid = keypoints[..., 1][valid]
    xmin, xmax = xs_valid.min(), xs_valid.max()
    ymin, ymax = ys_valid.min(), ys_valid.max()

    scale = max(xmax - xmin, ymax - ymin) * ratio
    if scale <= 0:
        raise ValueError("subject bounding box has zero size")

    x_offset = (xmin + xmax - scale) / 2.0
    y_offset = (ymin + ymax - scale) / 2.0

    out = (keypoints - np.array([x_offset, y_offset])) / scale
    out = (out - 0.5) * 2.0
    out = np.clip(out, -1.0, 1.0)
    out[~valid] = 0.0
    return out
