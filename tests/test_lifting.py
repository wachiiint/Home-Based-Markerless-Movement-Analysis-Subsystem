import numpy as np
import pytest

from app.models import keypoints as kp
from app.services.lifting.lifter import StubLifter
from app.services.lifting.normalize import (
    denormalize_screen_coordinates,
    normalize_screen_coordinates,
)
from app.services.lifting.pipeline import lift_pose_sequence, sequence_to_arrays
from app.services.lifting.skeleton_convert import (
    NUM_H36M_JOINTS,
    halpe26_to_h36m17,
)
from app.services.pose_sequence import FramePose2D, PoseSequence


def _fake_halpe(t=4):
    rng = np.random.default_rng(0)
    return rng.uniform(0, 1000, size=(t, 26, 2)), rng.uniform(0.5, 1.0, size=(t, 26))


# ---- skeleton conversion --------------------------------------------------

def test_convert_shape():
    keypoints, scores = _fake_halpe()
    kp17, sc17 = halpe26_to_h36m17(keypoints, scores)
    assert kp17.shape == (4, NUM_H36M_JOINTS, 2)
    assert sc17.shape == (4, NUM_H36M_JOINTS)


def test_convert_direct_joints_map_correctly():
    keypoints, scores = _fake_halpe()
    kp17, _ = halpe26_to_h36m17(keypoints, scores)
    # H36M pelvis(0) <- Halpe hip(19); H36M r_knee(2) <- Halpe right_knee(14)
    assert np.allclose(kp17[:, 0], keypoints[:, kp.HIP])
    assert np.allclose(kp17[:, 2], keypoints[:, kp.RIGHT_KNEE])
    assert np.allclose(kp17[:, 6], keypoints[:, kp.LEFT_ANKLE])
    assert np.allclose(kp17[:, 10], keypoints[:, kp.HEAD])


def test_convert_spine_is_hip_neck_midpoint():
    keypoints, scores = _fake_halpe()
    kp17, sc17 = halpe26_to_h36m17(keypoints, scores)
    expected = (keypoints[:, kp.HIP] + keypoints[:, kp.NECK]) / 2
    assert np.allclose(kp17[:, 7], expected)
    assert np.allclose(sc17[:, 7], np.minimum(scores[:, kp.HIP], scores[:, kp.NECK]))


def test_convert_rejects_wrong_shape():
    with pytest.raises(ValueError):
        halpe26_to_h36m17(np.zeros((4, 17, 2)), np.zeros((4, 17)))


# ---- normalization --------------------------------------------------------

def test_normalize_round_trip():
    pts = np.array([[[0.0, 0.0], [1280.0, 720.0], [640.0, 360.0]]])
    norm = normalize_screen_coordinates(pts, 1280, 720)
    back = denormalize_screen_coordinates(norm, 1280, 720)
    assert np.allclose(back, pts)


def test_normalize_x_range():
    pts = np.array([[[0.0, 0.0], [1280.0, 0.0]]])
    norm = normalize_screen_coordinates(pts, 1280, 720)
    assert norm[0, 0, 0] == pytest.approx(-1.0)
    assert norm[0, 1, 0] == pytest.approx(1.0)


# ---- pipeline (Phase A sequence -> 3D via stub) ---------------------------

def _sequence(t=5, gap_at=None):
    frames = []
    rng = np.random.default_rng(1)
    for i in range(t):
        if gap_at is not None and i in gap_at:
            frames.append(FramePose2D(i, i, None, None))
        else:
            frames.append(
                FramePose2D(i, i, rng.uniform(0, 1000, (26, 2)), rng.uniform(0.5, 1.0, (26)))
            )
    return PoseSequence(frames=frames, width=1280, height=720)


def test_sequence_to_arrays_fills_gaps():
    seq = _sequence(t=5, gap_at={2})
    keypoints, scores, valid = sequence_to_arrays(seq)
    assert keypoints.shape == (5, 26, 2)
    assert valid.tolist() == [True, True, False, True, True]
    # gap frame filled by a nearest valid frame (not left as zeros)
    assert not np.allclose(keypoints[2], 0)


def test_lift_pipeline_end_to_end_with_stub():
    seq = _sequence(t=6, gap_at={4})
    lifted = lift_pose_sequence(seq, StubLifter())
    assert lifted.keypoints_3d.shape == (6, 17, 3)
    assert lifted.valid_mask.tolist() == [True, True, True, True, False, True]
    # stub keeps z=0
    assert np.allclose(lifted.keypoints_3d[..., 2], 0)


def test_lift_pipeline_all_missing_raises():
    seq = _sequence(t=3, gap_at={0, 1, 2})
    with pytest.raises(ValueError):
        lift_pose_sequence(seq, StubLifter())
