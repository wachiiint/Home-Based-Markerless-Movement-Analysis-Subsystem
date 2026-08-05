import numpy as np

from app.models.keypoints import HALPE26_EDGES, HALPE26_JOINT_NAMES
from app.services.pose.pose2d_export import build_pose2d_payload
from app.services.pose.pose_sequence import FramePose2D, PoseSequence

SETTINGS_SNAPSHOT = {"frame_sample_fps": 10, "smoothing_alpha": 0.4}


def _sequence_with_gap():
    """Three sampled frames where the middle one had no detected subject."""
    kp = np.arange(52, dtype=np.float64).reshape(26, 2)
    return PoseSequence(
        frames=[
            FramePose2D(0, 0, kp, np.full(26, 0.9)),
            FramePose2D(1, 3, None, None),
            FramePose2D(2, 6, kp + 1.0, np.full(26, 0.8)),
        ],
        width=1920,
        height=1080,
    )


def _payload(sequence=None):
    return build_pose2d_payload(
        sequence if sequence is not None else _sequence_with_gap(),
        sampled_fps=10,
        analyzed_side="left",
        task_type="knee_flexion",
        source_fps=30.0,
        duration_sec=1.0,
        analysis_settings=SETTINGS_SNAPSHOT,
    )


def test_payload_carries_skeleton_topology():
    payload = _payload()
    assert payload["keypoint_format"] == "halpe26"
    assert payload["joint_names"] == HALPE26_JOINT_NAMES
    assert len(payload["joint_names"]) == 26
    # Edges are what makes the export drawable as bones rather than a dot cloud.
    assert payload["edges"] == [list(edge) for edge in HALPE26_EDGES]


def test_edges_reference_valid_joints():
    for a, b in HALPE26_EDGES:
        assert 0 <= a < 26 and 0 <= b < 26
        assert a != b


def test_undetected_frames_stay_aligned_as_nulls():
    """Dropping the gap would shift every later frame in time, silently changing
    the smoothness window and the lift."""
    payload = _payload()
    assert payload["num_frames"] == 3
    assert payload["frames"][1] is None
    assert payload["scores"][1] is None
    assert payload["valid_mask"] == [True, False, True]
    # Original video positions are preserved, not the sampled indices.
    assert payload["source_frame_indices"] == [0, 3, 6]


def test_detected_frames_carry_coordinates_and_scores():
    payload = _payload()
    assert np.shape(payload["frames"][0]) == (26, 2)
    assert len(payload["scores"][0]) == 26
    assert payload["frames"][0][1] == [2.0, 3.0]
    assert payload["scores"][2][0] == 0.8


def test_replay_settings_and_source_geometry_are_recorded():
    payload = _payload()
    assert payload["analysis_settings"] == SETTINGS_SNAPSHOT
    assert payload["source_video"] == {"width": 1920, "height": 1080, "fps": 30.0, "duration_sec": 1.0}
    assert payload["fps"] == 10
    assert payload["analyzed_side"] == "left"
    assert payload["task_type"] == "knee_flexion"


def test_payload_is_json_serialisable():
    """numpy floats would survive dataclass access but break json.dumps in main."""
    import json

    json.dumps(_payload())


def test_sequence_with_no_detections_still_exports():
    sequence = PoseSequence(frames=[FramePose2D(0, 0, None, None)], width=640, height=480)
    payload = _payload(sequence)
    assert payload["valid_mask"] == [False]
    assert payload["frames"] == [None]
