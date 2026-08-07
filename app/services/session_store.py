"""Local, on-disk store for completed analyses.

Results used to be written to a temp folder and deleted an hour later, which made
every run disposable: there was nothing to open again, and nothing for a later
recording to be compared against. They now land under ``data/sessions``, keyed by
patient, and stay there.

Layout::

    data/sessions/
        index.jsonl                            one line per stored session
        PT-001/
            20260807-142530-rtmpose-<uuid>/
                assessment.json                the complete response
                annotated.mp4                  optional -- see KEEP_ANNOTATED_VIDEO
                pose2d.json                    optional -- when the run produced it
                pose3d.json                    optional -- when the lift succeeded

**The directory is the record.** ``index.jsonl`` is a rebuildable summary of it,
so listing a patient's history costs one file read rather than opening every
assessment. It is append-only and deliberately flat: when the SQLite layer of P2
arrives, these rows are what it reads in.

Two things are deliberately *not* stored. The uploaded clip is deleted with the
working directory as soon as the analysis is done -- only the annotated render can
be kept, and only when configured to. And nothing here computes a comparison
between sessions: this stores, it does not judge. Progress and symmetry verdicts
are P4's separate query endpoints, over exactly these rows.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.response import MovementAssessmentResponse

logger = logging.getLogger(__name__)

INDEX_NAME = "index.jsonl"

# Patient ids and session ids reach us from a form field, so they become path
# segments only after everything outside this set is replaced.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


def _safe_segment(value: str, fallback: str) -> str:
    cleaned = _UNSAFE.sub("-", (value or "").strip())[:64].strip("-.")
    return cleaned or fallback


def _summarize(
    assessment: MovementAssessmentResponse,
    *,
    patient_id: str,
    recorded_at: datetime,
    directory: str,
    expires_at: str | None,
    has_annotated_video: bool,
    has_pose_2d: bool,
    has_pose_3d: bool,
) -> dict:
    """The one index row for a session: enough to draw a history list and to
    decide which two sessions are worth comparing, without opening the full
    assessment. Anything richer is a read of ``assessment.json``."""
    metrics = assessment.clinical_metrics
    rom_deg: dict[str, float] = {}
    for key, value in (metrics.joint_angles or {}).items():
        if not key.endswith("_rom_deg"):
            continue
        for side in ("left", "right"):
            if key.startswith(f"{side}_"):
                rom_deg[side] = value
    return {
        "session_id": assessment.session_id,
        "patient_id": patient_id,
        "recorded_at": recorded_at.isoformat(),
        "task_type": assessment.video_metadata.task_type,
        "view": assessment.video_metadata.view,
        # The leg the patient was instructed to move -- the only one screened.
        "side": assessment.video_metadata.analyzed_side,
        "analysis_mode": assessment.analysis_mode,
        "risk_level": assessment.screening_result.risk_level,
        "confidence_score": assessment.screening_result.confidence_score,
        "rom_deg": rom_deg,
        "valid_frame_ratio": metrics.pose_quality.valid_frame_ratio,
        "guard_warnings": list(assessment.guard_warnings),
        # Relative to the store root, so the whole folder can be moved or copied
        # to another machine without rewriting the index.
        "directory": directory,
        "expires_at": expires_at,
        "has_annotated_video": has_annotated_video,
        "has_pose_2d": has_pose_2d,
        "has_pose_3d": has_pose_3d,
    }


class SessionStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, dict] = {}
        self._load_index()

    @property
    def index_path(self) -> Path:
        return self.root / INDEX_NAME

    # -- reading ----------------------------------------------------------

    def _load_index(self) -> None:
        """Read the index into memory once at startup.

        A row that will not parse is skipped rather than fatal: the file is
        append-only, so the plausible corruption is a half-written last line, and
        losing one history entry is not a reason to refuse to start. The session's
        own directory is still on disk and still reachable by id.
        """
        if not self.index_path.exists():
            return
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                session_id = row["session_id"]
            except (json.JSONDecodeError, KeyError, TypeError):
                logger.warning("skipping unreadable row in %s", self.index_path)
                continue
            # Append-only means a re-saved session appears twice; the later row wins.
            self._index[session_id] = row
        logger.info("session store: %d session(s) under %s", len(self._index), self.root)

    def get(self, session_id: str) -> dict | None:
        return self._index.get(session_id)

    def directory_of(self, record: dict) -> Path:
        return self.root / record["directory"]

    def resolve(self, session_id: str) -> Path | None:
        """Locate a session's directory, falling back to a scan of the store.

        The index is the fast path. The scan covers the case where the index was
        lost or truncated but the session's own folder survived -- the folder is
        the record, so a readable result should not become unreachable because a
        summary file did.
        """
        record = self._index.get(session_id)
        if record is not None:
            directory = self.directory_of(record)
            if directory.is_dir():
                return directory
        safe_id = _safe_segment(session_id, "")
        if not safe_id:
            return None
        for candidate in sorted(self.root.glob(f"*/*-{safe_id}")):
            if candidate.is_dir():
                return candidate
        return None

    def list(self, patient_id: str | None = None, limit: int = 50) -> list[dict]:
        """Stored sessions, newest first, optionally for one patient."""
        rows = [
            row for row in self._index.values()
            if patient_id is None or row.get("patient_id") == patient_id
        ]
        rows.sort(key=lambda row: row.get("recorded_at") or "", reverse=True)
        return rows[:limit] if limit > 0 else rows

<<<<<<< HEAD
    def patients(self) -> list[str]:
        """Every patient named in the store, sorted.

        A row is skipped rather than trusted: the index is append-only and rows
        written by an older build (or hand-edited) can carry a missing, null or
        non-string id, and one of those must not take the history list down.
        """
        names = {row.get("patient_id") for row in self._index.values()}
        return sorted(name for name in names if isinstance(name, str) and name)
=======
    def patients(self) -> "list[str]":
        return sorted({row.get("patient_id", "") for row in self._index.values()} - {""})
>>>>>>> 268305e (Merge friend's work with scope-update docs; fix session_store import crash)

    # -- writing ----------------------------------------------------------

    def save(
        self,
        *,
        patient_id: str,
        assessment: MovementAssessmentResponse,
        annotated_video: Path | None = None,
        pose_2d: dict | None = None,
        pose_3d: dict | None = None,
        keep_annotated_video: bool = True,
        expires_at: str | None = None,
        recorded_at: datetime | None = None,
    ) -> dict:
        """Write one completed analysis to disk and return its index row.

        ``annotated_video`` is **moved**, not copied: it lives in the working
        directory that the caller is about to delete.
        """
        recorded_at = recorded_at or datetime.now(timezone.utc)
        patient_segment = _safe_segment(patient_id, "unknown-patient")
        # Timestamp first so the folders sort chronologically in a file browser;
        # the session id makes the name unique within one second.
        name = f"{recorded_at.strftime('%Y%m%d-%H%M%S')}-{_safe_segment(assessment.session_id, 'session')}"
        relative = f"{patient_segment}/{name}"
        directory = self.root / patient_segment / name
        directory.mkdir(parents=True, exist_ok=True)

        directory.joinpath("assessment.json").write_text(
            assessment.model_dump_json(indent=2), encoding="utf-8"
        )
        if pose_3d is not None:
            directory.joinpath("pose3d.json").write_text(json.dumps(pose_3d), encoding="utf-8")
        if pose_2d is not None:
            directory.joinpath("pose2d.json").write_text(json.dumps(pose_2d), encoding="utf-8")

        stored_video = False
        if keep_annotated_video and annotated_video is not None and annotated_video.exists():
            shutil.move(str(annotated_video), str(directory / "annotated.mp4"))
            stored_video = True

        row = _summarize(
            assessment,
            patient_id=patient_id,
            recorded_at=recorded_at,
            directory=relative,
            expires_at=expires_at,
            has_annotated_video=stored_video,
            has_pose_2d=pose_2d is not None,
            has_pose_3d=pose_3d is not None,
        )
        self._index[row["session_id"]] = row
        with self.index_path.open("a", encoding="utf-8") as index:
            index.write(json.dumps(row) + "\n")
        return row

    def purge_expired(self, now: datetime | None = None) -> int:
        """Delete sessions whose TTL has passed. A row with ``expires_at`` of
        ``None`` -- the default while this is a proof of concept -- never expires."""
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        expired = []
        for session_id, row in self._index.items():
            expires_at = row.get("expires_at")
            if not expires_at:
                continue
            try:
                deadline = datetime.fromisoformat(expires_at)
            except (TypeError, ValueError):
                continue
            if deadline.tzinfo is None:
                # We always write an aware timestamp, but a row from another
                # writer may be naive, and comparing the two raises. UTC is the
                # only reading consistent with what this store produces.
                deadline = deadline.replace(tzinfo=timezone.utc)
            if deadline <= now:
                expired.append(session_id)
        if not expired:
            return 0
        for session_id in expired:
            shutil.rmtree(self.directory_of(self._index.pop(session_id)), ignore_errors=True)
        self._rewrite_index()
        return len(expired)

    def _rewrite_index(self) -> None:
        """Compact the append-only index after a deletion.

        Written to a sibling file and swapped in, so a crash mid-write leaves the
        previous index intact rather than a truncated one.
        """
        temporary = self.index_path.with_suffix(".jsonl.tmp")
        temporary.write_text(
            "".join(json.dumps(row) + "\n" for row in self._index.values()), encoding="utf-8"
        )
        temporary.replace(self.index_path)
