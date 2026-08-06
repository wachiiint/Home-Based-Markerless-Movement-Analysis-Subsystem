from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


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
