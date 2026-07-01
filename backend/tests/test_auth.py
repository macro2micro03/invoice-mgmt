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
    # 인증 실패(401)만 아니면 됨 — 파일이 없으면 404, SPA 폴백이 있으면 200 모두 허용
    assert response.status_code != 401


def test_invoices_rejects_similarly_named_wrong_header(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    # 헤더 이름이 정확히 "X-App-Password"가 아니면(끝의 "ord"가 빠진 오타 등)
    # 값이 맞아도 인증되지 않아야 한다. 이는 프런트/백엔드 간 헤더 이름 계약을 고정한다.
    response = client.get("/invoices", headers={"X-App-Passwd": "secret123"})
    assert response.status_code == 401
