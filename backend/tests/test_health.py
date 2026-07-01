from fastapi.testclient import TestClient
from app.main import app
from app import config

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_url_uses_forward_slashes():
    assert "\\" not in config.DATABASE_URL
