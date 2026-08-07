from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.schemas.movement import TaskType
from app.services.response_mapper import build_fake_response
from app.services.session_store import SessionStore


def test_demo_page_is_available(monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "RTMPose Movement Lab" in response.text


def test_demo_page_offers_every_export_as_csv(monkeypatch):
    """The panel is the reading surface, so it links CSV only. The JSON record
    is still served, but by URL in the response rather than by a button."""
    monkeypatch.setenv("FAKE_MODE", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/")
    for artifact in ("assessment", "pose2d", "pose3d"):
        assert f'id="export-{artifact}-csv"' in response.text
        assert f'id="export-{artifact}"' not in response.text


def test_calibration_lives_on_its_own_page(monkeypatch):
    """Calibration is a once-per-device chore, so it is off the analysis page."""
    monkeypatch.setenv("FAKE_MODE", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        analysis = client.get("/")
        calibrate = client.get("/calibrate")
    assert 'id="calibrate-form"' not in analysis.text
    assert 'href="/calibrate"' in analysis.text
    assert calibrate.status_code == 200
    assert 'id="calibrate-form"' in calibrate.text


def test_pose2d_download_404s_for_unknown_session(monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/api/demo/results/no-such-session/pose2d.json")
    assert response.status_code == 404


def test_page_offers_the_stored_session_history(monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/")
    assert 'id="history-list"' in response.text


def _seed(tmp_path, patient_id="PT-001", side="left"):
    store = SessionStore(tmp_path)
    return store.save(
        patient_id=patient_id,
        assessment=build_fake_response(TaskType.KNEE_FLEXION, "lateral", side, 10),
    )


def test_history_lists_stored_sessions_and_filters_by_patient(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_MODE", "true")
    monkeypatch.setenv("SESSION_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    mine = _seed(tmp_path, "PT-001")
    _seed(tmp_path, "PT-002")

    with TestClient(app) as client:
        everyone = client.get("/api/demo/sessions").json()["sessions"]
        scoped = client.get("/api/demo/sessions", params={"patient_id": "PT-001"}).json()["sessions"]

    assert len(everyone) == 2
    assert [row["session_id"] for row in scoped] == [mine["session_id"]]


def test_a_stored_session_reopens_in_the_shape_of_a_fresh_one(monkeypatch, tmp_path):
    """The browser renders a reopened session through the same path as a new one,
    so the payload has to match."""
    monkeypatch.setenv("FAKE_MODE", "true")
    monkeypatch.setenv("SESSION_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    row = _seed(tmp_path)

    with TestClient(app) as client:
        response = client.get(f"/api/demo/sessions/{row['session_id']}")
        assessment = client.get(f"/api/demo/results/{row['session_id']}/assessment.json")

    payload = response.json()
    assert response.status_code == 200
    assert payload["assessment"]["session_id"] == row["session_id"]
    assert payload["patient_id"] == "PT-001"
    # Nothing was analysed here, so there is no render and no 3D to point at.
    assert payload["annotated_video_url"] is None
    assert payload["pose_3d_url"] is None
    # Stored results do not expire under the default settings.
    assert payload["expires_at"] is None
    assert assessment.status_code == 200


def test_unknown_session_404s(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_MODE", "true")
    monkeypatch.setenv("SESSION_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/api/demo/sessions/no-such-session")
    assert response.status_code == 404


def test_comparison_lives_on_its_own_page(monkeypatch):
    """Asymmetry reads two stored sessions rather than producing one, so it is off
    the analysis page -- like calibration."""
    monkeypatch.setenv("FAKE_MODE", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        analysis = client.get("/")
        compare = client.get("/compare")
    assert 'href="/compare"' in analysis.text
    assert compare.status_code == 200
    assert 'id="asymmetry-metrics"' in compare.text


def test_comparison_page_carries_the_graph_and_the_3d_viewer(monkeypatch):
    """Both legs on one graph, and one recording at a time in the viewer -- the
    two clips have their own camera and scale, so overlaying the skeletons would
    show a difference between setups and invite it to be read as asymmetry."""
    monkeypatch.setenv("FAKE_MODE", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        page = client.get("/compare")
    assert 'id="trajectory-chart"' in page.text
    assert 'id="viewer-canvas"' in page.text
    for side in ("left", "right"):
        assert f'id="viewer-side-{side}"' in page.text


def test_both_pages_draw_their_graph_with_the_same_module(monkeypatch):
    """The chart was extracted so the two pages cannot drift into two different
    readings of the same series."""
    monkeypatch.setenv("FAKE_MODE", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        analysis_js = client.get("/static/app.js").text
        compare_js = client.get("/static/compare.js").text
        chart_js = client.get("/static/anglechart.js")
    assert chart_js.status_code == 200
    for source in (analysis_js, compare_js):
        assert "/static/anglechart.js" in source


def test_compare_reports_the_difference_between_two_stored_sessions(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_MODE", "true")
    monkeypatch.setenv("SESSION_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    left = _seed(tmp_path, "PT-001", side="left")
    right = _seed(tmp_path, "PT-001", side="right")

    with TestClient(app) as client:
        response = client.get("/api/demo/compare", params={"left": left["session_id"], "right": right["session_id"]})

    payload = response.json()
    assert response.status_code == 200
    assert payload["comparable"] is True
    assert payload["left"]["side"] == "left" and payload["right"]["side"] == "right"
    rom = next(row for row in payload["metrics"] if row["key"] == "rom_deg")
    assert rom["left"] is not None and rom["right"] is not None
    # No pass/fail is offered, by design -- there is no validated threshold yet.
    assert "verdict" not in payload and "risk_level" not in payload


def test_compare_refuses_two_patients_and_says_why(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_MODE", "true")
    monkeypatch.setenv("SESSION_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    mine = _seed(tmp_path, "PT-001", side="left")
    theirs = _seed(tmp_path, "PT-002", side="right")

    with TestClient(app) as client:
        response = client.get("/api/demo/compare", params={"left": mine["session_id"], "right": theirs["session_id"]})

    payload = response.json()
    # Not an error: "these cannot be compared, and here is the reason" is the
    # useful answer, and the page renders it.
    assert response.status_code == 200
    assert payload["comparable"] is False
    assert payload["metrics"] == []
    assert "different_patient" in {check["code"] for check in payload["checks"]}


def test_compare_404s_on_a_missing_session(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_MODE", "true")
    monkeypatch.setenv("SESSION_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    row = _seed(tmp_path, "PT-001", side="left")
    with TestClient(app) as client:
        response = client.get("/api/demo/compare", params={"left": row["session_id"], "right": "no-such-session"})
    assert response.status_code == 404


def test_compare_rejects_a_session_against_itself(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_MODE", "true")
    monkeypatch.setenv("SESSION_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    row = _seed(tmp_path, "PT-001", side="left")
    with TestClient(app) as client:
        response = client.get("/api/demo/compare", params={"left": row["session_id"], "right": row["session_id"]})
    assert response.status_code == 400


def test_demo_requires_real_inference(monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/api/demo/assess",
            data={"patient_id": "PT-001", "task_type": "knee_flexion", "view": "lateral", "side": "left"},
            files={"file": ("clip.mp4", b"not-empty", "video/mp4")},
        )
    assert response.status_code == 503
