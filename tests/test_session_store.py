"""The local store that lets a result outlive the run that produced it.

Covers the working path (save, list, reopen), the failure paths that matter for a
store meant to survive restarts (lost index, unreadable row), and the one privacy
promise the store makes: the uploaded clip never enters it.
"""

import json
from datetime import datetime, timedelta, timezone

from app.schemas.movement import TaskType
from app.services.response_mapper import build_fake_response
from app.services.session_store import SessionStore


def _assessment(side: str = "left", rom: float | None = None):
    response = build_fake_response(TaskType.KNEE_FLEXION, "lateral", side, 10)
    # build_fake_response emits unprefixed single-side keys; the real analyzer
    # emits side-prefixed ones, which is what the index summarises.
    response.clinical_metrics.joint_angles = {
        "left_knee_rom_deg": rom if rom is not None else 57.2,
        "right_knee_rom_deg": 12.0,
    }
    return response


def test_save_writes_the_assessment_and_indexes_it(tmp_path):
    store = SessionStore(tmp_path)
    assessment = _assessment()

    row = store.save(patient_id="PT-001", assessment=assessment, pose_2d={"frames": []})

    directory = store.directory_of(row)
    assert directory.is_dir()
    stored = json.loads(directory.joinpath("assessment.json").read_text(encoding="utf-8"))
    assert stored["session_id"] == assessment.session_id
    assert directory.joinpath("pose2d.json").exists()
    assert not directory.joinpath("pose3d.json").exists()
    assert row["patient_id"] == "PT-001"
    assert row["rom_deg"] == {"left": 57.2, "right": 12.0}
    assert row["has_pose_2d"] is True
    assert row["has_pose_3d"] is False


def test_annotated_video_is_moved_in_and_can_be_left_out(tmp_path):
    """The render is moved, not copied: it lives in a working directory the
    caller deletes straight after."""
    store = SessionStore(tmp_path)

    source = tmp_path / "work" / "annotated.mp4"
    source.parent.mkdir()
    source.write_bytes(b"video")
    kept = store.save(patient_id="PT-001", assessment=_assessment(), annotated_video=source)
    assert store.directory_of(kept).joinpath("annotated.mp4").read_bytes() == b"video"
    assert not source.exists()
    assert kept["has_annotated_video"] is True

    other = tmp_path / "work" / "annotated2.mp4"
    other.write_bytes(b"video")
    dropped = store.save(
        patient_id="PT-001", assessment=_assessment(), annotated_video=other,
        keep_annotated_video=False,
    )
    assert not store.directory_of(dropped).joinpath("annotated.mp4").exists()
    assert dropped["has_annotated_video"] is False
    # Left where it was, for the caller's cleanup to take with the uploaded clip.
    assert other.exists()


def test_history_survives_a_restart(tmp_path):
    """The whole point of the store: a new process finds what the old one wrote."""
    first = SessionStore(tmp_path)
    row = first.save(patient_id="PT-001", assessment=_assessment())

    reopened = SessionStore(tmp_path)
    assert reopened.get(row["session_id"]) is not None
    assert reopened.resolve(row["session_id"]) == first.directory_of(row)


def test_sessions_are_listed_newest_first_and_filtered_by_patient(tmp_path):
    store = SessionStore(tmp_path)
    base = datetime(2026, 8, 7, 9, 0, tzinfo=timezone.utc)
    older = store.save(patient_id="PT-001", assessment=_assessment(), recorded_at=base)
    newer = store.save(
        patient_id="PT-001", assessment=_assessment(), recorded_at=base + timedelta(hours=2)
    )
    other = store.save(
        patient_id="PT-002", assessment=_assessment(), recorded_at=base + timedelta(hours=1)
    )

    everyone = [row["session_id"] for row in store.list()]
    assert everyone == [newer["session_id"], other["session_id"], older["session_id"]]
    assert [row["session_id"] for row in store.list("PT-001")] == [
        newer["session_id"], older["session_id"]
    ]
    assert store.patients() == ["PT-001", "PT-002"]


def test_a_session_is_reachable_after_the_index_is_lost(tmp_path):
    """The directory is the record. Losing the summary file must not make a
    stored result unreachable."""
    store = SessionStore(tmp_path)
    row = store.save(patient_id="PT-001", assessment=_assessment())
    directory = store.directory_of(row)

    store.index_path.unlink()
    rebuilt = SessionStore(tmp_path)
    assert rebuilt.get(row["session_id"]) is None  # no summary to list
    assert rebuilt.resolve(row["session_id"]) == directory  # but still openable


def test_a_truncated_index_row_costs_one_entry_not_the_startup(tmp_path):
    store = SessionStore(tmp_path)
    good = store.save(patient_id="PT-001", assessment=_assessment())
    with store.index_path.open("a", encoding="utf-8") as index:
        index.write('{"session_id": "half-writ')

    rebuilt = SessionStore(tmp_path)
    assert [row["session_id"] for row in rebuilt.list()] == [good["session_id"]]


def test_stored_sessions_do_not_expire_by_default(tmp_path):
    store = SessionStore(tmp_path)
    row = store.save(patient_id="PT-001", assessment=_assessment())

    assert row["expires_at"] is None
    assert store.purge_expired(datetime.now(timezone.utc) + timedelta(days=365)) == 0
    assert store.get(row["session_id"]) is not None


def test_purge_removes_expired_sessions_and_compacts_the_index(tmp_path):
    """The TTL is off by default but still honoured, so the old behaviour is a
    setting rather than a deleted code path."""
    store = SessionStore(tmp_path)
    now = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    expiring = store.save(
        patient_id="PT-001", assessment=_assessment(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
    )
    kept = store.save(patient_id="PT-001", assessment=_assessment())
    directory = store.directory_of(expiring)

    assert store.purge_expired(now + timedelta(hours=2)) == 1
    assert not directory.exists()
    assert store.get(expiring["session_id"]) is None
    assert store.get(kept["session_id"]) is not None
    rows = [json.loads(line) for line in store.index_path.read_text(encoding="utf-8").splitlines()]
    assert [row["session_id"] for row in rows] == [kept["session_id"]]


def test_patient_id_cannot_escape_the_store_root(tmp_path):
    """The id is a form field, so it becomes a path segment only after cleaning."""
    store = SessionStore(tmp_path)
    row = store.save(patient_id="../../etc", assessment=_assessment())

    directory = store.directory_of(row)
    assert tmp_path in directory.parents
    assert ".." not in row["directory"]
