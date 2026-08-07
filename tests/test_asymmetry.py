"""Left-against-right across two recordings: the maths, and the refusals."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.analysis.asymmetry import (
    SideRecording,
    compare,
    symmetry_angle_pct,
)

NOW = datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)


def _recording(
    side: str,
    *,
    rom: float = 60.0,
    peak: float = 65.0,
    minimum: float = 5.0,
    patient_id: str = "PT-001",
    task_type: str = "knee_flexion",
    view: str = "lateral",
    recorded_at: datetime | None = NOW,
    analysis_mode: str = "2d",
    sampled_fps: int = 10,
    valid_frame_ratio: float = 0.94,
    guard_warnings: tuple[str, ...] = (),
    smoothness: dict | None = None,
) -> SideRecording:
    return SideRecording(
        session_id=f"rtmpose-{side}",
        side=side,
        patient_id=patient_id,
        task_type=task_type,
        view=view,
        recorded_at=recorded_at,
        analysis_mode=analysis_mode,
        sampled_fps=sampled_fps,
        valid_frame_ratio=valid_frame_ratio,
        guard_warnings=guard_warnings,
        joint_angles={
            f"{side}_knee_rom_deg": rom,
            f"{side}_knee_flexion_max_deg": peak,
            f"{side}_knee_flexion_min_deg": minimum,
        },
        smoothness=smoothness or {"sparc": -2.1, "log_dimensionless_jerk": -8.4, "n_movement_units": 3},
    )


def _row(comparison, key):
    return next(row for row in comparison.metrics if row.spec.key == key)


# -- the index ---------------------------------------------------------------


def test_equal_values_are_perfectly_symmetric():
    assert symmetry_angle_pct(50.0, 50.0) == 0.0


def test_index_is_signed_towards_the_larger_leg_and_bounded():
    assert symmetry_angle_pct(60.0, 40.0) > 0
    assert symmetry_angle_pct(40.0, 60.0) < 0
    # Zifchock's angle cannot leave [-50, 50] however extreme the pair is.
    assert symmetry_angle_pct(1000.0, 0.0) == pytest.approx(50.0)
    assert symmetry_angle_pct(0.0, 1000.0) == pytest.approx(-50.0)


def test_the_index_needs_no_reference_leg():
    """Why this and not a limb symmetry index: LSI divides by a sound limb, and
    in a bilaterally declining population there is no sound limb to divide by.
    The symmetry angle treats the two legs alike -- swapping them only flips the
    sign, so which clip is called "left" cannot change the magnitude."""
    assert symmetry_angle_pct(60.0, 40.0) == pytest.approx(-symmetry_angle_pct(40.0, 60.0))


def test_the_index_is_scale_free_so_the_raw_difference_is_reported_beside_it():
    """A caveat worth pinning down: the index cannot tell a clinically trivial
    difference from a large one, which is why every row also carries its plain
    difference in the metric's own unit."""
    assert symmetry_angle_pct(3.0, 5.0) == pytest.approx(symmetry_angle_pct(30.0, 50.0))
    comparison = compare(_recording("left", rom=3.0), _recording("right", rom=5.0))
    assert _row(comparison, "rom_deg").difference == pytest.approx(-2.0)


def test_two_legs_that_did_not_move_have_no_index():
    assert symmetry_angle_pct(0.0, 0.0) is None


# -- what gets an index ------------------------------------------------------


def test_rom_gets_an_index_but_joint_angles_only_get_a_difference():
    """A joint angle is a position on an arbitrary axis, so a ratio between two
    of them means nothing; ROM is a magnitude with a real zero."""
    comparison = compare(_recording("left", rom=60, peak=65), _recording("right", rom=45, peak=50))
    assert _row(comparison, "rom_deg").symmetry_angle_pct is not None
    assert _row(comparison, "peak_angle_deg").symmetry_angle_pct is None
    assert _row(comparison, "peak_angle_deg").difference == pytest.approx(15.0)


def test_negative_smoothness_measures_get_no_index():
    comparison = compare(_recording("left"), _recording("right"))
    assert _row(comparison, "sparc").symmetry_angle_pct is None
    assert _row(comparison, "ldlj").symmetry_angle_pct is None
    assert _row(comparison, "movement_units").symmetry_angle_pct is not None


def test_difference_is_left_minus_right_and_names_the_larger_leg():
    comparison = compare(_recording("left", rom=60), _recording("right", rom=45))
    row = _row(comparison, "rom_deg")
    assert row.difference == pytest.approx(15.0)
    assert row.larger_side == "left"
    assert row.symmetry_angle_pct > 0


def test_arguments_may_be_given_in_either_order():
    forwards = compare(_recording("left", rom=60), _recording("right", rom=45))
    backwards = compare(_recording("right", rom=45), _recording("left", rom=60))
    assert forwards.left.side == backwards.left.side == "left"
    assert _row(forwards, "rom_deg").difference == _row(backwards, "rom_deg").difference


def test_each_recording_contributes_only_its_own_instructed_leg():
    """The whole point of two clips: the contralateral numbers inside a clip are
    a within-clip reference and must not leak into the comparison."""
    left = _recording("left", rom=60)
    left.joint_angles["right_knee_rom_deg"] = 999.0  # the occluded far leg
    comparison = compare(left, _recording("right", rom=45))
    assert _row(comparison, "rom_deg").right == pytest.approx(45.0)


def test_a_metric_present_on_one_side_only_is_still_reported():
    comparison = compare(
        _recording("left"),
        _recording("right", smoothness={"sparc": -2.4}),
    )
    row = _row(comparison, "movement_units")
    assert row.left is not None and row.right is None
    assert row.difference is None


def test_the_unprefixed_single_side_response_shape_still_reads():
    """Fake mode and the original contract shape write ``knee_rom_deg`` with no
    side prefix, where it can only mean the analysed leg."""
    left = _recording("left")
    left.joint_angles.clear()
    left.joint_angles["knee_rom_deg"] = 55.0
    comparison = compare(left, _recording("right", rom=50))
    assert _row(comparison, "rom_deg").left == pytest.approx(55.0)


# -- comparability -----------------------------------------------------------


def _codes(comparison, severity):
    return {check.code for check in comparison.checks if check.severity == severity}


def test_a_comparable_pair_produces_metrics():
    comparison = compare(_recording("left"), _recording("right"))
    assert comparison.comparable
    assert comparison.metrics


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"patient_id": "PT-002"}, "different_patient"),
        ({"task_type": "hip_flexion"}, "different_task"),
        ({"view": "frontal"}, "different_view"),
    ],
)
def test_mismatched_recordings_are_refused_rather_than_reported(kwargs, code):
    comparison = compare(_recording("left"), _recording("right", **kwargs))
    assert not comparison.comparable
    assert code in _codes(comparison, "blocking")
    # A refusal means no numbers at all -- a figure from a mismatched pair would
    # look like an answer.
    assert comparison.metrics == []


def test_two_recordings_of_the_same_leg_are_refused():
    comparison = compare(_recording("left"), _recording("left"))
    assert "not_one_leg_each" in _codes(comparison, "blocking")


def test_an_unknown_task_is_refused():
    comparison = compare(_recording("left", task_type="moon_walk"), _recording("right", task_type="moon_walk"))
    assert "unknown_task" in _codes(comparison, "blocking")


def test_a_long_gap_warns_rather_than_refuses():
    """How many days may separate the two sides is an open clinical question, so
    the default limit prompts a thought instead of enforcing a decision."""
    comparison = compare(
        _recording("left", recorded_at=NOW),
        _recording("right", recorded_at=NOW + timedelta(days=90)),
        max_days_apart=30,
    )
    assert comparison.comparable
    assert "recorded_far_apart" in _codes(comparison, "warning")
    assert comparison.days_apart == pytest.approx(90.0)


def test_a_leg_that_barely_moved_warns_but_still_reports():
    """In this population a leg that barely moves may be the finding rather than
    a spoiled recording, so the numbers stand and the caveat is loud."""
    comparison = compare(
        _recording("left", guard_warnings=("declared_side_barely_moved",)),
        _recording("right"),
    )
    assert comparison.comparable
    assert "side_barely_moved" in _codes(comparison, "warning")
    assert comparison.metrics


def test_recording_conditions_that_degrade_a_comparison_are_warned_about():
    comparison = compare(
        _recording("left", sampled_fps=10, analysis_mode="2d", valid_frame_ratio=0.4),
        _recording("right", sampled_fps=30, analysis_mode="3d"),
    )
    warnings = _codes(comparison, "warning")
    assert {"different_sample_rate", "different_analysis_mode", "low_tracking_coverage"} <= warnings


def test_the_uncheckable_camera_setup_is_stated_not_left_silent():
    """Nothing stored today records where the camera sat, so a clean run must not
    read as a verified one."""
    comparison = compare(_recording("left"), _recording("right"))
    assert "camera_setup_unverified" in _codes(comparison, "warning")


def test_no_verdict_is_produced():
    """There is no test-retest figure yet, so no threshold can separate asymmetry
    from recording noise. The comparison reports and stops."""
    comparison = compare(_recording("left", rom=90), _recording("right", rom=20))
    assert not hasattr(comparison, "verdict")
    assert not any("verdict" in check.code or "abnormal" in check.code for check in comparison.checks)
