"""Kinematic muscle overlay for the 3D viewer (M-A).

DISPLAY ONLY, and explicitly a *geometry* proxy, not force/activation: a single
camera gives no ground-reaction force, so muscle force cannot be recovered. Two
things are modelled, deliberately decoupled:

* **Shape** -- each muscle is routed as an ordered list of *anchors*, each a
  point a fraction ``t`` along the segment between two H36M17 joints (e.g. 55%
  down the femur). Anchors ride the skeleton, so the drawn path bends with the
  limb. Along-bone placement is the well-observed part of a single-camera lift,
  so the shape is robust; the sideways "belly" bulge the viewer adds is
  illustrative.
* **Colour** -- a per-frame length proxy in ``[0, 1]`` driven by the joint angle
  (``0`` = most shortened, ``1`` = most stretched). Physiological *direction* is
  correct (a knee extensor stretches as the knee flexes).

Anchor placement comes either from a built-in anatomically-approximate table or,
when present, from ``models/gait2392_muscles.json`` extracted from the OpenSim
gait2392 model (see ``app/tools/extract_gait2392_muscles.py``). Either way this
is a length/geometry estimate, **not** a validated gait2392 simulation -- the
single-camera kinematics only reliably observe sagittal hip/knee flexion.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.services.analysis.kinematics import three_point_angle_3d

logger = logging.getLogger(__name__)

_PELVIS = 0
_THORAX = 8
_LEG = {
    "left": {"hip": 4, "knee": 5, "ankle": 6},
    "right": {"hip": 1, "knee": 2, "ankle": 3},
}

_DEFAULT_GAIT2392_PATH = Path(__file__).resolve().parents[3] / "models" / "target" / "gait2392_muscles.json"


def _gait2392_path() -> Path:
    """Where the extracted gait2392 anchor table lives (optional). Read at call
    time so ``GAIT2392_MUSCLES_PATH`` can override it (tests, custom locations)."""
    return Path(os.getenv("GAIT2392_MUSCLES_PATH", str(_DEFAULT_GAIT2392_PATH)))


@dataclass(frozen=True)
class MuscleDef:
    name: str
    joint: str  # "knee" | "hip" -- which joint angle drives the length/colour
    lengthens_on_flexion: bool  # True = stretched as that joint flexes
    # Ordered anchors routing the muscle: (segment start joint, end joint, fraction t in [0,1]).
    anchors: tuple[tuple[str, str, float], ...]
    bulge: float  # signed sideways belly offset for the viewer (+ front / - back); 0 = none


# Anatomically-*approximate* routing for the major flexion/extension muscles.
# Honest label: hand-placed fractions, not measured -- replaced by gait2392 data
# when models/gait2392_muscles.json is present.
_BUILTIN_MUSCLES: tuple[MuscleDef, ...] = (
    MuscleDef("Quadriceps", "knee", True, (("hip", "knee", 0.05), ("hip", "knee", 0.55), ("knee", "ankle", 0.12)), +0.06),
    MuscleDef("Hamstrings", "knee", False, (("pelvis", "hip", 0.5), ("hip", "knee", 0.5), ("knee", "ankle", 0.12)), -0.06),
    MuscleDef("Gastrocnemius", "knee", False, (("hip", "knee", 0.82), ("knee", "ankle", 0.5), ("knee", "ankle", 0.95)), -0.05),
    MuscleDef("Iliopsoas", "hip", False, (("thorax", "pelvis", 0.55), ("pelvis", "hip", 0.6), ("hip", "knee", 0.12)), +0.05),
    MuscleDef("Gluteals", "hip", True, (("pelvis", "hip", 0.2), ("hip", "knee", 0.12)), -0.06),
)


def _index(side: str, name: str) -> int:
    if name == "pelvis":
        return _PELVIS
    if name == "thorax":
        return _THORAX
    return _LEG[side][name]


def _load_gait2392_muscles() -> tuple[MuscleDef, ...] | None:
    """Load anchor defs from the extracted gait2392 table, or None if absent/bad."""
    path = _gait2392_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        muscles = tuple(
            MuscleDef(
                name=m["name"],
                joint=m["joint"],
                lengthens_on_flexion=bool(m["lengthens_on_flexion"]),
                anchors=tuple((a[0], a[1], float(a[2])) for a in m["anchors"]),
                bulge=float(m.get("bulge", 0.05)),
            )
            for m in data["muscles"]
        )
        return muscles or None
    except Exception:
        logger.exception("failed to load gait2392 muscle table %s; using built-in", path)
        return None


def active_muscles() -> tuple[MuscleDef, ...]:
    """gait2392-extracted muscles when available, else the built-in approximation."""
    return _load_gait2392_muscles() or _BUILTIN_MUSCLES


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
    """Per-frame length proxy (pre-normalization): ``180 - angle`` when the muscle
    lengthens on flexion, else the angle itself."""
    raw: list[float] = []
    for frame in keypoints_3d:
        angle = _joint_angle(frame, side, muscle.joint)
        raw.append((180.0 - angle) if muscle.lengthens_on_flexion else angle)
    return raw


def compute_muscle_overlay(keypoints_3d, sides: tuple[str, ...] = ("left", "right")) -> list[dict]:
    """Viewer overlay: one entry per (side, muscle) with skeleton-relative anchors
    (``[jointA, jointB, t]``), a belly ``bulge``, and a per-frame normalized length.

    Returns ``[]`` for an unusable sequence so the viewer simply draws no muscles.
    """
    keypoints_3d = np.asarray(keypoints_3d, dtype=float)
    if keypoints_3d.ndim != 3 or keypoints_3d.shape[1] < 17 or keypoints_3d.shape[0] == 0:
        return []
    overlay: list[dict] = []
    for side in sides:
        for muscle in active_muscles():
            overlay.append(
                {
                    "name": muscle.name,
                    "side": side,
                    "anchors": [[_index(side, a), _index(side, b), round(t, 4)] for a, b, t in muscle.anchors],
                    "bulge": muscle.bulge,
                    "length": _normalize(muscle_length_series(keypoints_3d, side, muscle)),
                }
            )
    return overlay
