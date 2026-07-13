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


def test_demo_requires_real_inference(monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/api/demo/assess",
            data={"patient_id": "PT-001", "task_type": "knee_flexion", "view": "lateral"},
            files={"file": ("clip.mp4", b"not-empty", "video/mp4")},
        )
    assert response.status_code == 503
