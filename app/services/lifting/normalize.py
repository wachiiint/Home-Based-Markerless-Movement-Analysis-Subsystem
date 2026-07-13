"""Screen-coordinate normalization for 2D->3D lifting.

MotionBERT / VideoPose3D expect 2D keypoints normalized by the image width so x
falls in [-1, 1] and y keeps the aspect ratio. This is the standard
``normalize_screen_coordinates`` transform:

    x' = x / w * 2 - 1
    y' = y / w * 2 - h / w
"""

import numpy as np


def normalize_screen_coordinates(keypoints: np.ndarray, width: int, height: int) -> np.ndarray:
    """Normalize pixel coordinates. ``keypoints``: (..., 2). Returns same shape."""
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    keypoints = np.asarray(keypoints, dtype=np.float64)
    out = keypoints.copy()
    out[..., 0] = keypoints[..., 0] / width * 2 - 1
    out[..., 1] = keypoints[..., 1] / width * 2 - height / width
    return out


def denormalize_screen_coordinates(keypoints: np.ndarray, width: int, height: int) -> np.ndarray:
    """Inverse of :func:`normalize_screen_coordinates`."""
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    keypoints = np.asarray(keypoints, dtype=np.float64)
    out = keypoints.copy()
    out[..., 0] = (keypoints[..., 0] + 1) * width / 2
    out[..., 1] = (keypoints[..., 1] + height / width) * width / 2
    return out
