"""Left-against-right asymmetry, computed across **two** recordings.

This is the replacement footing for the single-clip symmetry in ``symmetry.py``.
The problem with reading both legs off one clip is physical, not statistical: in a
lateral view the far leg is occluded and foreshortened, so its numbers are not on
the same footing as the near leg's. Dividing one by the other measures distance
from the camera as much as it measures the patient.

The fix is one clip per leg, each filmed with that leg facing the camera. Each
recording contributes **only the leg it was instructed to move** -- the leg that
was screened, the leg the response's ``analyzed_side`` names. The contralateral
numbers inside each clip stay what they always were: a reference and a recording
check, never half of an asymmetry index.

Two recordings buy comparability problems that one clip did not have, so nothing
is compared until the pair passes :func:`check_comparability`. A blocking check
means no numbers at all -- a mismatched pair should refuse, not report.

**No thresholds here, and none coming until there is evidence.** Saying "15%
apart is abnormal" requires knowing what two recordings of the *same* leg
disagree by; without that test-retest figure a threshold cannot separate
asymmetry from recording noise. This module reports the difference and says how
it was measured. The judgement is not ours to make yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import atan2, degrees

from app.models.task_config import TASK_CONFIGS
from app.schemas.movement import TaskType

# Below this, a clip's instructed leg was tracked too rarely for its summary
# numbers to carry a comparison. Matches the default MIN_VALID_FRAME_RATIO.
MIN_VALID_FRAME_RATIO = 0.6

SIDES = ("left", "right")


@dataclass(frozen=True)
class SideRecording:
    """One stored analysis, reduced to the leg it was instructed to move.

    Built from a stored session by the service layer; this module never reads a
    file or a response model.
    """

    session_id: str
    side: str
    patient_id: str
    task_type: str
    view: str
    recorded_at: datetime | None
    analysis_mode: str
    sampled_fps: int
    valid_frame_ratio: float
    guard_warnings: tuple[str, ...] = ()
    # Whole ``clinical_metrics`` sub-dicts, side prefixes intact.
    joint_angles: dict[str, float] = field(default_factory=dict)
    joint_angles_3d: dict[str, float] = field(default_factory=dict)
    # Already narrowed to this recording's instructed side.
    smoothness: dict[str, float] = field(default_factory=dict)

    def angle(self, key: str, *, three_d: bool = False) -> float | None:
        """One side-prefixed metric for *this* recording's instructed leg.

        Falls back to the bare key: the single-side response form (fake mode, and
        the original contract shape) writes ``knee_rom_deg`` rather than
        ``left_knee_rom_deg``, and there it can only mean the analysed side.
        """
        source = self.joint_angles_3d if three_d else self.joint_angles
        value = source.get(f"{self.side}_{key}")
        if value is None:
            value = source.get(key)
        return None if value is None else float(value)


@dataclass(frozen=True)
class Check:
    """One comparability finding.

    ``blocking`` means the pair is not two views of the same question and no
    number is produced. ``warning`` means the comparison stands but the reader
    needs to know something about it.
    """

    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    unit: str
    # A ratio index needs a positive magnitude with a meaningful zero. ROM has
    # one; a joint *angle* does not (it is a position on an arbitrary axis, and
    # can sit near or below zero), and SPARC/LDLJ are negative by construction.
    # Those get the plain difference, which is the honest thing to report.
    magnitude: bool


@dataclass(frozen=True)
class MetricComparison:
    spec: MetricSpec
    left: float | None
    right: float | None
    difference: float | None
    symmetry_angle_pct: float | None
    larger_side: str | None


@dataclass(frozen=True)
class Comparison:
    left: SideRecording
    right: SideRecording
    checks: list[Check]
    metrics: list[MetricComparison]
    days_apart: float | None

    @property
    def comparable(self) -> bool:
        return not any(check.severity == "blocking" for check in self.checks)


def symmetry_angle_pct(left: float, right: float) -> float | None:
    """Zifchock symmetry angle (2008), as a percentage, signed so that positive
    means the left value is the larger one.

    Chosen because **neither leg is a valid reference here**. The familiar limb
    symmetry index, ``involved / uninvolved * 100``, assumes a sound limb to
    divide by; that assumption comes from unilateral injury work (ACL, one-sided
    arthroplasty) and does not survive the move to sarcopenia, where decline is
    bilateral. Dividing by an also-impaired leg produces a healthy-looking 100%,
    and the ratio has no bound as the denominator shrinks. The symmetry angle
    needs no such choice: it is the angle between the point ``(left, right)`` and
    the line of equality, so it treats the two legs alike by construction and
    stays inside [-50, +50] whatever the magnitudes.

    ``atan2`` rather than a division keeps a zero left value finite. Both values
    at zero is the one case with no answer: there is no asymmetry to speak of
    between two legs that did not move.

    Note what this does *not* fix. Like any scale-free index it says nothing
    about whether a difference matters -- 3 deg against 5 deg and 30 deg against
    50 deg score identically. That is why every row is reported with its plain
    difference in degrees beside the index, and why neither carries a threshold.
    """
    if left < 0 or right < 0:
        return None
    if left <= 0 and right <= 0:
        return None
    theta = degrees(atan2(right, left))
    return round((45.0 - theta) / 90.0 * 100.0, 2)


def _metric_specs(task_type: TaskType) -> list[tuple[MetricSpec, str, bool]]:
    """(spec, joint_angles key, is_3d) for one task.

    The joint name comes from the task config rather than a hardcoded list, so a
    hip clip is labelled hip and an ankle clip ankle without a second table to
    keep in sync.
    """
    config = TASK_CONFIGS[task_type]
    joint = config.rom_key.replace("_rom_deg", "")
    return [
        (MetricSpec("rom_deg", f"{joint.capitalize()} ROM", "°", True), config.rom_key, False),
        (MetricSpec("rom_deg_3d", f"{joint.capitalize()} ROM (3D)", "°", True), config.rom_key + "_3d", True),
        (MetricSpec("peak_angle_deg", f"Peak {joint} angle", "°", False), config.max_key, False),
        (MetricSpec("min_angle_deg", f"Minimum {joint} angle", "°", False), config.min_key, False),
    ]


# Smoothness lives in its own per-side block rather than in joint_angles.
_SMOOTHNESS_SPECS = [
    (MetricSpec("sparc", "Smoothness (SPARC)", "", False), "sparc"),
    (MetricSpec("ldlj", "Smoothness (LDLJ)", "", False), "log_dimensionless_jerk"),
    (MetricSpec("movement_units", "Movement units", "", True), "n_movement_units"),
]


def _compare_metric(spec: MetricSpec, left: float | None, right: float | None) -> MetricComparison | None:
    """One row, or None when neither recording produced the metric.

    A metric present on one side only is still reported: "the left clip has this
    and the right does not" is information, and blanking the row would hide it.
    """
    if left is None and right is None:
        return None
    difference = None if (left is None or right is None) else round(left - right, 3)
    index = (
        symmetry_angle_pct(left, right)
        if spec.magnitude and left is not None and right is not None
        else None
    )
    larger = None
    if difference is not None and difference != 0:
        larger = "left" if difference > 0 else "right"
    return MetricComparison(spec=spec, left=left, right=right, difference=difference, symmetry_angle_pct=index, larger_side=larger)


def check_comparability(left: SideRecording, right: SideRecording, max_days_apart: int) -> tuple[list[Check], float | None]:
    """What stands between these two recordings and a fair comparison.

    The blocking rules are the ones where the pair is not answering one question:
    a different patient, a different movement, a different camera view, or two
    recordings of the same leg. Everything else is a warning, because it degrades
    a comparison rather than invalidating it -- and because a guard that refuses
    too readily gets worked around.

    The time limit is a warning for a specific reason: how far apart two sides may
    be recorded is a clinical judgement nobody has made yet (see the open question
    in docs2/04-planning.md). Blocking on an unconfirmed default would enforce a
    decision we have not taken.
    """
    checks: list[Check] = []

    if left.patient_id != right.patient_id:
        checks.append(Check("different_patient", "blocking", f"These recordings belong to different patients ({left.patient_id} and {right.patient_id})."))
    if left.task_type != right.task_type:
        checks.append(Check("different_task", "blocking", f"Different movements ({left.task_type} and {right.task_type}) — there is no shared quantity to compare."))
    if left.view != right.view:
        checks.append(Check("different_view", "blocking", f"Filmed from different views ({left.view} and {right.view}); the same joint projects differently in each."))
    if {left.side, right.side} != set(SIDES):
        checks.append(Check("not_one_leg_each", "blocking", f"Asymmetry needs one left-leg and one right-leg recording; got {left.side} and {right.side}."))

    # A task this build does not know has no metric keys to read, so the pair
    # cannot be compared even when both recordings agree on it.
    known_tasks = {task.value for task in TaskType}
    unknown = {r.task_type for r in (left, right)} - known_tasks
    if unknown:
        checks.append(Check("unknown_task", "blocking", f"Unrecognised movement task ({', '.join(sorted(unknown))}); this build has no metric definition for it."))

    days_apart = None
    if left.recorded_at is not None and right.recorded_at is not None:
        days_apart = round(abs((left.recorded_at - right.recorded_at).total_seconds()) / 86400.0, 2)
        if days_apart > max_days_apart:
            checks.append(Check("recorded_far_apart", "warning", f"Recorded {days_apart:g} days apart (limit {max_days_apart}). The patient may have changed between them, so a difference is not necessarily asymmetry."))

    if left.sampled_fps != right.sampled_fps:
        checks.append(Check("different_sample_rate", "warning", f"Sampled at different rates ({left.sampled_fps} and {right.sampled_fps} fps). Smoothness measures depend on the sample rate; the range of motion does not."))
    if left.analysis_mode != right.analysis_mode:
        checks.append(Check("different_analysis_mode", "warning", f"One recording was analysed in {left.analysis_mode.upper()} and the other in {right.analysis_mode.upper()}."))

    for recording in (left, right):
        if recording.valid_frame_ratio < MIN_VALID_FRAME_RATIO:
            checks.append(Check("low_tracking_coverage", "warning", f"The {recording.side} recording tracked the leg in only {recording.valid_frame_ratio:.0%} of frames."))
        if "declared_side_barely_moved" in recording.guard_warnings:
            # Deliberately not blocking: in this population a leg that barely
            # moves may be the finding rather than a spoiled recording. Flag it
            # loudly and let the clinician decide which it is.
            checks.append(Check("side_barely_moved", "warning", f"The {recording.side} leg barely moved in its clip — the difference below may be a failed attempt rather than asymmetry."))
        if "declared_side_did_not_move_most" in recording.guard_warnings:
            checks.append(Check("possible_wrong_side", "warning", f"In the {recording.side} recording the other leg moved more, so the wrong leg may have been filmed or selected."))
        if any(w.startswith("heavy_tracking_noise") for w in recording.guard_warnings):
            checks.append(Check("heavy_tracking_noise", "warning", f"Tracking was unstable in the {recording.side} recording; its angles were repaired before these numbers were read."))

    # The camera has to sit at the same distance and height for two clips to be
    # comparable, and nothing stored today records where it sat. Say so rather
    # than let the absence of a complaint read as a clean bill of health.
    checks.append(Check("camera_setup_unverified", "warning", "Camera distance, height and angle are not recorded, so the service cannot verify the two clips were filmed the same way. That is the reader's check to make."))

    return checks, days_apart


def compare(first: SideRecording, second: SideRecording, *, max_days_apart: int = 30) -> Comparison:
    """Compare two recordings, one per leg.

    Arguments are accepted in either order and returned left-first, so the caller
    does not have to know which session held which leg. When the sides are not one
    of each, the given order is kept -- there is no left to put first.
    """
    if second.side == "left" and first.side != "left":
        first, second = second, first
    checks, days_apart = check_comparability(first, second, max_days_apart)

    metrics: list[MetricComparison] = []
    if not any(check.severity == "blocking" for check in checks):
        task_type = TaskType(first.task_type)
        for spec, key, three_d in _metric_specs(task_type):
            row = _compare_metric(spec, first.angle(key, three_d=three_d), second.angle(key, three_d=three_d))
            if row is not None:
                metrics.append(row)
        for spec, key in _SMOOTHNESS_SPECS:
            left_value = first.smoothness.get(key)
            right_value = second.smoothness.get(key)
            row = _compare_metric(
                spec,
                None if left_value is None else float(left_value),
                None if right_value is None else float(right_value),
            )
            if row is not None:
                metrics.append(row)

    return Comparison(left=first, right=second, checks=checks, metrics=metrics, days_apart=days_apart)
