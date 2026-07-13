from fastapi.testclient import TestClient

from app.main import app


def test_missing_key_rejected(monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "true")
    with TestClient(app) as client:
        response = client.post("/api/movement/assess")
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid service key"}


def test_wrong_key_rejected(monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "true")
    with TestClient(app) as client:
        response = client.post("/api/movement/assess", headers={"X-Internal-Service-Key": "wrong"})
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid service key"}
