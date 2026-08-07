"""Turn two stored sessions into an asymmetry comparison.

The seam between the store and the pure comparison in
``analysis/asymmetry.py``: it reads the two ``assessment.json`` files, narrows
each to the leg that recording was instructed to move, and dresses the result in
the response schema. No arithmetic happens here.

Reading the stored assessment rather than the index row is deliberate. The index
carries only ROM, which is enough to *find* a candidate pair but not enough to
compare one -- peak angle and the smoothness measures live in the full record.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from app.schemas.response import (
    AsymmetryComparisonResponse,
    AsymmetryMetric,
    ComparabilityCheck,
    ComparedSession,
    MovementAssessmentResponse,
)
from app.services.analysis.asymmetry import Comparison, SideRecording, compare
from app.services.session_store import SessionStore

logger = logging.getLogger(__name__)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        logger.warning("unparseable recorded_at %r", value)
        return None


def load_side_recording(store: SessionStore, session_id: str) -> SideRecording | None:
    """One stored session as a comparison input, or None when it is not there.

    A session whose response never named a side cannot take part: without
    ``analyzed_side`` there is no way to know which leg its numbers belong to, and
    guessing would be the one mistake this whole design exists to avoid.
    """
    record = store.get(session_id)
    directory: Path | None = store.directory_of(record) if record is not None else store.resolve(session_id)
    if directory is None or not directory.is_dir():
        return None
    assessment_path = directory / "assessment.json"
    if not assessment_path.exists():
        return None
    assessment = MovementAssessmentResponse.model_validate_json(
        assessment_path.read_text(encoding="utf-8")
    )

    side = assessment.video_metadata.analyzed_side
    if side not in ("left", "right"):
        return None

    metrics = assessment.clinical_metrics
    record = record or {}
    return SideRecording(
        session_id=assessment.session_id,
        side=side,
        patient_id=record.get("patient_id") or "",
        task_type=assessment.video_metadata.task_type,
        view=assessment.video_metadata.view,
        recorded_at=_parse_time(record.get("recorded_at")),
        analysis_mode=assessment.analysis_mode,
        sampled_fps=assessment.video_metadata.sampled_fps,
        valid_frame_ratio=metrics.pose_quality.valid_frame_ratio,
        guard_warnings=tuple(assessment.guard_warnings),
        joint_angles=dict(metrics.joint_angles or {}),
        joint_angles_3d=dict(metrics.joint_angles_3d or {}),
        # Only this recording's instructed leg. The other leg's smoothness is in
        # the stored record and stays there: it is a within-clip reference, not
        # an input to a between-clip comparison.
        smoothness=dict((metrics.smoothness or {}).get(side) or {}),
    )


def _as_compared_session(recording: SideRecording) -> ComparedSession:
    return ComparedSession(
        session_id=recording.session_id,
        side=recording.side,
        patient_id=recording.patient_id,
        task_type=recording.task_type,
        view=recording.view,
        recorded_at=recording.recorded_at.isoformat() if recording.recorded_at else None,
        analysis_mode=recording.analysis_mode,
        valid_frame_ratio=recording.valid_frame_ratio,
        guard_warnings=list(recording.guard_warnings),
    )


def to_response(comparison: Comparison) -> AsymmetryComparisonResponse:
    return AsymmetryComparisonResponse(
        comparable=comparison.comparable,
        left=_as_compared_session(comparison.left),
        right=_as_compared_session(comparison.right),
        days_apart=comparison.days_apart,
        checks=[
            ComparabilityCheck(code=check.code, severity=check.severity, message=check.message)
            for check in comparison.checks
        ],
        metrics=[
            AsymmetryMetric(
                key=row.spec.key,
                label=row.spec.label,
                unit=row.spec.unit,
                left=row.left,
                right=row.right,
                difference=row.difference,
                symmetry_angle_pct=row.symmetry_angle_pct,
                larger_side=row.larger_side,
            )
            for row in comparison.metrics
        ],
    )


def compare_sessions(
    store: SessionStore, first_id: str, second_id: str, *, max_days_apart: int = 30
) -> AsymmetryComparisonResponse | None:
    """Compare two stored sessions. None when either cannot be loaded."""
    first = load_side_recording(store, first_id)
    second = load_side_recording(store, second_id)
    if first is None or second is None:
        return None
    return to_response(compare(first, second, max_days_apart=max_days_apart))
