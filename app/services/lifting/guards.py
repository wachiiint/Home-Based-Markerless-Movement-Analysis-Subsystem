"""Silent-wrong guard on the lifted 3D skeleton.

A correct lift keeps each bone (femur/tibia) roughly constant in length over
time. A large coefficient of variation means the 3D is unreliable (e.g. an ONNX
export whose values are wrong despite a valid shape), so the caller degrades to
2D instead of trusting garbage depth.
"""

import numpy as np

# H36M17 bone endpoints
_BONES = {
    "r_femur": (1, 2),
    "r_tibia": (2, 3),
    "l_femur": (4, 5),
    "l_tibia": (5, 6),
}
MAX_BONE_CV = 0.25


def bone_length_consistency(keypoints_3d, valid_mask, max_cv: float = MAX_BONE_CV) -> tuple[bool, float, list[str]]:
    """Return (ok, worst_cv, warnings) from per-bone length variation."""
    kp = np.asarray(keypoints_3d, dtype=np.float64)
    valid = np.asarray(valid_mask, dtype=bool)
    frames = kp[valid] if valid.any() else kp
    if len(frames) < 2:
        return True, 0.0, []

    warnings: list[str] = []
    worst = 0.0
    for name, (a, b) in _BONES.items():
        lengths = np.linalg.norm(frames[:, a] - frames[:, b], axis=1)
        mean = float(lengths.mean())
        if mean < 1e-9:
            continue
        cv = float(lengths.std() / mean)
        worst = max(worst, cv)
        if cv > max_cv:
            warnings.append(f"{name} length varies over time (cv={cv:.2f}); lift may be unreliable")
    return worst <= max_cv, worst, warnings
