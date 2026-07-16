"""Serialise a lifted 3D sequence into the payload the demo viewer renders.

This is a *display* artifact, not a clinical one: the coordinates are
root-relative and unitless (metric scale needs a calibrated board), so the
payload carries ``lift_reliable`` and the guard warnings to let the UI say so.
Kept out of ``MovementAssessmentResponse`` on purpose -- the clinical contract
stays lean and the coords are served as a separate demo-only file.
"""

import numpy as np

from app.services.lifting.pipeline import Lifted3DSequence
from app.services.lifting.skeleton_convert import H36M_EDGES, H36M_JOINT_NAMES

_COORD_DECIMALS = 4


def build_pose3d_payload(
    lifted: Lifted3DSequence,
    *,
    sampled_fps: int,
    analyzed_side: str | None,
    lift_reliable: bool,
    lift_warnings: list[str],
    analysis_mode: str,
) -> dict:
    """Viewer payload: skeleton topology + per-frame 3D coordinates.

    Coordinates are rounded to keep the file small (a 120s clip is ~1200
    frames x 17 joints x 3 axes).
    """
    keypoints = np.asarray(lifted.keypoints_3d, dtype=np.float64)
    frames = np.round(keypoints, _COORD_DECIMALS).tolist()
    return {
        "num_frames": int(keypoints.shape[0]),
        "fps": sampled_fps,
        "joint_names": list(H36M_JOINT_NAMES),
        "edges": [list(edge) for edge in H36M_EDGES],
        "frames": frames,
        "valid_mask": [bool(v) for v in np.asarray(lifted.valid_mask).tolist()],
        "analyzed_side": analyzed_side,
        "analysis_mode": analysis_mode,
        "lift_reliable": bool(lift_reliable),
        "lift_warnings": list(lift_warnings),
    }
