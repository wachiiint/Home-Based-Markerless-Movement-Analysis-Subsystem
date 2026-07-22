"""Kinematic muscle-length proxies for the 3D viewer overlay (M-A).

DISPLAY ONLY, and explicitly a *geometry* proxy, not a force/activation one: a
single camera gives no ground-reaction force, so muscle force cannot be
recovered. What this computes is muscle *length* driven by joint angle -- a
muscle that spans a flexing joint lengthens or shortens as that joint moves.
Each muscle's length is min-max normalized to ``[0, 1]`` over the clip
(``0`` = most shortened, ``1`` = most lengthened / stretched) purely so the
viewer can colour it. It is never a clinical number and stays out of
``MovementAssessmentResponse`` -- it rides only in the demo ``pose_3d`` payload.

The driving angles come from the H36M17 skeleton (see ``skeleton_convert``):
knee = angle(hip, knee, ankle); hip = angle(thorax, hip, knee). Ankle muscles
are driven by the knee angle as a proxy because H36M17 has no toe joint.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.services.analysis.kinematics import three_point_angle_3d

_PELVIS = 0
_THORAX = 8
_LEG = {
    "left": {"hip": 4, "knee": 5, "ankle": 6},
    "right": {"hip": 1, "knee": 2, "ankle": 3},
}


@dataclass(frozen=True)
class MuscleDef:
    name: str
    joint: str  # "knee" | "hip" -- which joint angle drives the length
    lengthens_on_flexion: bool  # True = stretched as the joint flexes (antagonist)
    path: tuple[str, ...]  # leg-joint names the muscle is drawn along
    offset: int  # +1 anterior / -1 posterior -- only to fan the tubes apart visually


# A small, readable set of the major lower-limb muscles relevant to the flexion/
# extension tasks. Physiological length *direction* is correct (a knee extensor
# stretches as the knee flexes); the drawn geometry is illustrative.
_MUSCLES: tuple[MuscleDef, ...] = (
    MuscleDef("Quadriceps", "knee", lengthens_on_flexion=True, path=("hip", "knee"), offset=+1),
    MuscleDef("Hamstrings", "knee", lengthens_on_flexion=False, path=("hip", "knee"), offset=-1),
    MuscleDef("Gastrocnemius", "knee", lengthens_on_flexion=False, path=("knee", "ankle"), offset=-1),
    MuscleDef("Iliopsoas", "hip", lengthens_on_flexion=False, path=("pelvis", "knee"), offset=+1),
    MuscleDef("Gluteals", "hip", lengthens_on_flexion=True, path=("pelvis", "knee"), offset=-1),
)


def _index(side: str, name: str) -> int:
    if name == "pelvis":
        return _PELVIS
    if name == "thorax":
        return _THORAX
    return _LEG[side][name]


def _joint_angle(frame: np.ndarray, side: str, joint: str) -> float:
    leg = _LEG[side]
    if joint == "knee":
        return three_point_angle_3d(frame[leg["hip"]], frame[leg["knee"]], frame[leg["ankle"]])
    return three_point_angle_3d(frame[_THORAX], frame[leg["hip"]], frame[leg["knee"]])


def _normalize(values: list[float]) -> list[float]:
    """Min-max to [0, 1]; a static (flat) series maps to a neutral 0.5."""
    arr = np.asarray(values, dtype=float)
    lo, hi = float(arr.min()), float(arr.max())
    if hi - lo < 1e-6:
        return [0.5] * arr.size
    return [round(float(v), 4) for v in (arr - lo) / (hi - lo)]


def muscle_length_series(keypoints_3d: np.ndarray, side: str, muscle: MuscleDef) -> list[float]:
    """Per-frame length proxy for one muscle (pre-normalization).

    Length increases with the flexion of the driven joint for an antagonist
    (``lengthens_on_flexion``) and decreases for the agonist. Flexion is
    ``180 - angle``, so raw length is ``180 - angle`` when it lengthens on
    flexion, else the angle itself.
    """
    raw: list[float] = []
    for frame in keypoints_3d:
        angle = _joint_angle(frame, side, muscle.joint)
        raw.append((180.0 - angle) if muscle.lengthens_on_flexion else angle)
    return raw


def compute_muscle_overlay(keypoints_3d, sides: tuple[str, ...] = ("left", "right")) -> list[dict]:
    """Viewer overlay: one entry per (side, muscle) with the joints to draw it
    along and a per-frame normalized length in ``[0, 1]``.

    Returns ``[]`` for an unusable sequence so the viewer simply draws no muscles.
    """
    keypoints_3d = np.asarray(keypoints_3d, dtype=float)
    if keypoints_3d.ndim != 3 or keypoints_3d.shape[1] < 17 or keypoints_3d.shape[0] == 0:
        return []
    overlay: list[dict] = []
    for side in sides:
        for muscle in _MUSCLES:
            overlay.append(
                {
                    "name": muscle.name,
                    "side": side,
                    "joints": [_index(side, name) for name in muscle.path],
                    "offset": muscle.offset,
                    "length": _normalize(muscle_length_series(keypoints_3d, side, muscle)),
                }
            )
    return overlay
