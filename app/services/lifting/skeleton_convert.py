"""Convert Halpe26 2D keypoints to the H36M 17-joint skeleton.

MotionBERT (and most 2D->3D lifters) are trained on the Human3.6M 17-joint
layout, so the RTMPose Halpe26 output must be remapped first. Halpe26 already
contains a pelvis (19) and neck (18), so all H36M joints map directly except
the mid-spine (H36M 7), which is synthesised as the pelvis-neck midpoint.

H36M17 joint order (MotionBERT / VideoPose3D convention):
    0 Pelvis  1 RHip  2 RKnee  3 RAnkle  4 LHip  5 LKnee  6 LAnkle
    7 Spine   8 Thorax  9 Neck/Nose  10 Head
    11 LShoulder 12 LElbow 13 LWrist  14 RShoulder 15 RElbow 16 RWrist
"""

import numpy as np

from app.models import keypoints as kp

H36M_JOINT_NAMES = [
    "pelvis", "r_hip", "r_knee", "r_ankle", "l_hip", "l_knee", "l_ankle",
    "spine", "thorax", "neck_nose", "head",
    "l_shoulder", "l_elbow", "l_wrist", "r_shoulder", "r_elbow", "r_wrist",
]
NUM_H36M_JOINTS = 17

# H36M joint index -> Halpe26 index (direct copies). Index 7 (spine) is
# synthesised separately and is intentionally absent here.
_DIRECT_MAP: dict[int, int] = {
    0: kp.HIP,            # pelvis (root)
    1: kp.RIGHT_HIP,
    2: kp.RIGHT_KNEE,
    3: kp.RIGHT_ANKLE,
    4: kp.LEFT_HIP,
    5: kp.LEFT_KNEE,
    6: kp.LEFT_ANKLE,
    8: kp.NECK,           # thorax
    9: kp.NOSE,           # neck/nose
    10: kp.HEAD,
    11: kp.LEFT_SHOULDER,
    12: kp.LEFT_ELBOW,
    13: kp.LEFT_WRIST,
    14: kp.RIGHT_SHOULDER,
    15: kp.RIGHT_ELBOW,
    16: kp.RIGHT_WRIST,
}
_SPINE_PARENTS = (kp.HIP, kp.NECK)  # midpoint -> H36M spine (7)


def halpe26_to_h36m17(keypoints: np.ndarray, scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Remap a sequence of Halpe26 poses to H36M17.

    ``keypoints``: (T, 26, 2), ``scores``: (T, 26).
    Returns ``(kp17 (T, 17, 2), sc17 (T, 17))``. The synthesised spine takes
    the mean position and the min confidence of its two parents.
    """
    keypoints = np.asarray(keypoints, dtype=np.float64)
    scores = np.asarray(scores, dtype=np.float64)
    if keypoints.ndim != 3 or keypoints.shape[1:] != (26, 2):
        raise ValueError(f"expected keypoints (T, 26, 2), got {keypoints.shape}")

    t = keypoints.shape[0]
    kp17 = np.zeros((t, NUM_H36M_JOINTS, 2), dtype=np.float64)
    sc17 = np.zeros((t, NUM_H36M_JOINTS), dtype=np.float64)

    for h36m_idx, halpe_idx in _DIRECT_MAP.items():
        kp17[:, h36m_idx] = keypoints[:, halpe_idx]
        sc17[:, h36m_idx] = scores[:, halpe_idx]

    a, b = _SPINE_PARENTS
    kp17[:, 7] = (keypoints[:, a] + keypoints[:, b]) / 2.0
    sc17[:, 7] = np.minimum(scores[:, a], scores[:, b])

    return kp17, sc17
