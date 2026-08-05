import csv
import io

from app.services.csv_export import assessment_csv, pose2d_csv, pose3d_csv


def _rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


POSE2D = {
    "joint_names": ["nose", "left_knee"],
    "frames": [[[10.5, 20.5], [30.0, 40.0]], None],
    "scores": [[0.9, 0.8], None],
    "source_frame_indices": [0, 3],
    "valid_mask": [True, False],
}

POSE3D = {
    "joint_names": ["pelvis", "r_hip"],
    "frames": [[[0.0, 0.1, 0.2], [1.0, 1.1, 1.2]]],
    "valid_mask": [True],
}


def test_pose2d_header_is_three_columns_per_joint():
    rows = _rows(pose2d_csv(POSE2D))
    assert rows[0] == [
        "frame", "source_frame", "detected",
        "nose_x", "nose_y", "nose_score",
        "left_knee_x", "left_knee_y", "left_knee_score",
    ]


def test_pose2d_one_row_per_frame_with_coordinates():
    rows = _rows(pose2d_csv(POSE2D))
    assert len(rows) == 3  # header + 2 frames
    assert rows[1] == ["0", "0", "1", "10.5", "20.5", "0.9", "30.0", "40.0", "0.8"]


def test_undetected_frame_keeps_its_row_with_empty_cells():
    """Zeros would read as a real position at the origin, so the cells stay blank
    and `detected` carries the fact."""
    rows = _rows(pose2d_csv(POSE2D))
    assert rows[2][:3] == ["1", "3", "0"]
    assert rows[2][3:] == ["", "", "", "", "", ""]


def test_pose3d_is_three_axes_per_joint():
    rows = _rows(pose3d_csv(POSE3D))
    assert rows[0] == ["frame", "valid", "pelvis_x", "pelvis_y", "pelvis_z", "r_hip_x", "r_hip_y", "r_hip_z"]
    assert rows[1] == ["0", "1", "0.0", "0.1", "0.2", "1.0", "1.1", "1.2"]


def test_pose3d_tolerates_a_missing_valid_mask():
    payload = {**POSE3D}
    del payload["valid_mask"]
    rows = _rows(pose3d_csv(payload))
    assert rows[1][1] == "1"


def test_assessment_flattens_to_dotted_metric_paths():
    rows = _rows(assessment_csv({
        "session_id": "s1",
        "clinical_metrics": {"joint_angles": {"left_knee_rom_deg": 84.2}},
        "screening_result": {"flags": ["low_rom"]},
    }))
    assert rows[0] == ["metric", "value"]
    values = dict(rows[1:])
    assert values["session_id"] == "s1"
    assert values["clinical_metrics.joint_angles.left_knee_rom_deg"] == "84.2"
    assert values["screening_result.flags[0]"] == "low_rom"


def test_empty_containers_and_nulls_stay_visible():
    """gait_parameters is empty by design -- dropping the row would hide that."""
    values = dict(_rows(assessment_csv({"gait_parameters": {}, "flags": [], "symmetry": None}))[1:])
    assert values["gait_parameters"] == ""
    assert values["flags"] == ""
    assert values["symmetry"] == ""


def test_line_terminator_is_not_doubled_on_windows():
    assert "\r" not in pose2d_csv(POSE2D)
