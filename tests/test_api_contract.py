from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_fake_mode_contract(monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/api/movement/assess",
            headers={"X-Internal-Service-Key": "dev-local-analysis-key"},
            data={"patient_id": "PT-001", "task_type": "knee_flexion", "view": "lateral"},
            files={"file": ("clip.mp4", b"not-empty", "video/mp4")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert {"session_id", "video_metadata", "clinical_metrics", "screening_result", "transformation_matrix_6dof"} <= set(payload)
    assert isinstance(payload["clinical_metrics"], dict)
    assert isinstance(payload["screening_result"], dict)
    assert payload["screening_result"]["risk_level"] in {"low", "moderate", "high"}
    assert 0 <= payload["screening_result"]["confidence_score"] <= 1
    assert 0 <= payload["clinical_metrics"]["pose_quality"]["mean_keypoint_confidence"] <= 1


def test_unknown_task_type_is_400(monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/api/movement/assess",
            headers={"X-Internal-Service-Key": "dev-local-analysis-key"},
            data={"patient_id": "PT-001", "task_type": "bad_task", "view": "lateral"},
            files={"file": ("clip.mp4", b"not-empty", "video/mp4")},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "unknown task_type"}


def test_broken_file_is_422(monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/api/movement/assess",
            headers={"X-Internal-Service-Key": "dev-local-analysis-key"},
            data={"patient_id": "PT-001", "task_type": "knee_flexion", "view": "lateral"},
            files={"file": ("clip.mp4", b"", "video/mp4")},
        )

    assert response.status_code == 422
    assert response.json() == {"detail": "unreadable video"}
