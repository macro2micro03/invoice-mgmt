from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)


def test_invoices_passes_when_app_password_unset(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "")
    response = client.get("/invoices")
    assert response.status_code == 200


def test_invoices_rejects_missing_header_when_password_set(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    response = client.get("/invoices")
    assert response.status_code == 401


def test_invoices_rejects_wrong_password(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    response = client.get("/invoices", headers={"X-App-Password": "wrong"})
    assert response.status_code == 401


def test_invoices_accepts_correct_password(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    response = client.get("/invoices", headers={"X-App-Password": "secret123"})
    assert response.status_code == 200


def test_ocr_endpoint_is_protected(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    response = client.post("/ocr", files={"file": ("test.jpg", b"fake", "image/jpeg")})
    assert response.status_code == 401


def test_health_route_is_not_protected(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    response = client.get("/health")
    assert response.status_code == 200


def test_storage_mount_is_not_protected(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    response = client.get("/storage/nonexistent-file.jpg")
    # 파일이 없어 404가 나더라도, 인증 실패(401)가 아니라는 점이 중요하다.
    assert response.status_code == 404
