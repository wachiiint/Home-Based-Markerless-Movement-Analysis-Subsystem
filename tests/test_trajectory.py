"""The angle trajectory: the per-frame series behind the graph.

The point of keeping it is that the graph and the summary numbers come from the
same smoothed values, and that frames the tracker could not read stay visible as
gaps instead of being drawn through.
"""

import csv
import io

import numpy as np

from app.core.config import Settings
from app.models import keypoints as kp
from app.models.task_config import TASK_CONFIGS
from app.schemas.movement import TaskType
from app.services.csv_export import assessment_csv, trajectory_csv
from app.services.pose.pose_sequence import FramePose2D, PoseSequence
from app.services.video_analysis import _analyze_both_legs, _build_trajectory

SETTINGS = Settings()
TASK = TaskType.KNEE_FLEXION


def _rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


def _pose(knee_offset: float) -> np.ndarray:
    """Both knees bent by the same offset, so either leg is analysable."""
    points = np.zeros((26, 2))
    points[kp.LEFT_HIP] = (470, 500)
    points[kp.RIGHT_HIP] = (530, 500)
    points[kp.LEFT_KNEE] = (470, 700)
    points[kp.RIGHT_KNEE] = (530, 700)
    points[kp.LEFT_ANKLE] = (470 + knee_offset, 900)
    points[kp.RIGHT_ANKLE] = (530 + knee_offset, 900)
    return points


def _sequence(offsets, blank_frames=()) -> PoseSequence:
    frames = []
    for index, offset in enumerate(offsets):
        if index in blank_frames:
            frames.append(FramePose2D(index, index, None, None))
            continue
        frames.append(FramePose2D(index, index, _pose(offset), np.full(26, 0.9)))
    return PoseSequence(frames=frames, width=1000, height=1000)


def test_series_has_one_entry_per_sampled_frame():
    sequence = _sequence([0, 40, 80, 120, 160, 200])
    legs = _analyze_both_legs(sequence, TASK, SETTINGS)
    for leg in legs.values():
        assert len(leg.series) == sequence.processed_frames


def test_undetected_frames_keep_their_slot_as_null():
    """A gap is the honest picture -- interpolating would invent movement."""
    legs = _analyze_both_legs(_sequence([0, 40, 80, 120, 160, 200], blank_frames={2, 3}), TASK, SETTINGS)
    series = legs["left"].series
    assert series[2] is None and series[3] is None
    assert series[0] is not None and series[4] is not None


def test_series_extremes_agree_with_the_reported_rom():
    """The graph and the numbers are read from the same smoothed values."""
    legs = _analyze_both_legs(_sequence([0, 40, 80, 120, 160, 200]), TASK, SETTINGS)
    leg = legs["left"]
    values = [v for v in leg.series if v is not None]
    assert min(values) == round(leg.min_angle, 2)
    assert max(values) == round(leg.max_angle, 2)


def test_time_axis_uses_the_sampled_rate():
    legs = _analyze_both_legs(_sequence([0, 40, 80, 120]), TASK, SETTINGS)
    trajectory = _build_trajectory(legs, TASK, 4, sampled_fps=10)
    assert trajectory.time_sec == [0.0, 0.1, 0.2, 0.3]


def test_trajectory_names_the_joint_without_a_side_prefix():
    legs = _analyze_both_legs(_sequence([0, 40, 80, 120]), TASK, SETTINGS)
    trajectory = _build_trajectory(legs, TASK, 4, sampled_fps=10)
    assert trajectory.joint == "knee_flexion_deg"
    assert TASK_CONFIGS[TASK].max_key.startswith("knee_flexion")


def test_a_leg_that_was_never_usable_is_absent_rather_than_all_nulls():
    legs = _analyze_both_legs(_sequence([0, 40, 80, 120]), TASK, SETTINGS)
    del legs["right"]
    trajectory = _build_trajectory(legs, TASK, 4, sampled_fps=10)
    assert trajectory.right_angle_deg is None
    assert trajectory.left_angle_deg is not None


ASSESSMENT = {
    "session_id": "rtmpose-1",
    "clinical_metrics": {"joint_angles": {"left_knee_rom_deg": 42.0}},
    "trajectory": {
        "joint": "knee_flexion_deg",
        "time_sec": [0.0, 0.1, 0.2],
        "left_angle_deg": [170.0, None, 150.5],
        "right_angle_deg": None,
    },
}


def test_trajectory_csv_is_one_row_per_frame_per_present_leg():
    rows = _rows(trajectory_csv(ASSESSMENT))
    assert rows[0] == ["frame", "time_sec", "left_knee_flexion_deg"]
    assert rows[1] == ["0", "0.0", "170.0"]
    assert len(rows) == 4  # header + 3 frames


def test_untracked_frame_keeps_its_row_with_an_empty_cell():
    rows = _rows(trajectory_csv(ASSESSMENT))
    assert rows[2] == ["1", "0.1", ""]


def test_trajectory_csv_tolerates_a_response_without_one():
    rows = _rows(trajectory_csv({"session_id": "rtmpose-1"}))
    assert rows == [["frame", "time_sec"]]


def test_metrics_csv_leaves_the_trajectory_out():
    """Flattened, it would bury the metrics under hundreds of indexed rows."""
    text = assessment_csv(ASSESSMENT)
    assert "trajectory" not in text
    assert "clinical_metrics.joint_angles.left_knee_rom_deg" in text
