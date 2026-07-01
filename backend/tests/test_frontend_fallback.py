import importlib

import pytest
from fastapi.testclient import TestClient

from app import main as main_module

FAKE_INDEX_HTML = "<html><body>fake spa shell</body></html>"


@pytest.fixture
def frontend_client(tmp_path, monkeypatch):
    """Reload app.main with FRONTEND_DIST pointed at a temp dir containing a fake index.html."""
    fake_dist = tmp_path / "dist"
    fake_dist.mkdir()
    (fake_dist / "index.html").write_text(FAKE_INDEX_HTML, encoding="utf-8")

    monkeypatch.setattr(main_module, "FRONTEND_DIST", fake_dist, raising=False)

    reloaded = importlib.reload(main_module)
    # Force the module's FRONTEND_DIST (recomputed on reload) to the fake dir too,
    # since reload re-executes the module-level Path(...) assignment.
    monkeypatch.setattr(reloaded, "FRONTEND_DIST", fake_dist, raising=False)

    client = TestClient(reloaded.app)
    yield client

    # Reload again afterwards to restore the module to its normal state for other tests.
    importlib.reload(main_module)


def test_unmatched_spa_route_returns_index_html(frontend_client):
    response = frontend_client.get("/search")
    assert response.status_code == 200
    assert FAKE_INDEX_HTML in response.text


def test_unmatched_nested_spa_route_returns_index_html(frontend_client):
    # No route in the app matches this path at all (unlike /invoices/{id}, which
    # is a real, matched API route). This is the "bookmarked deep link to an
    # unknown SPA path" case the fallback exists to handle.
    response = frontend_client.get("/invoices/5/details")
    assert response.status_code == 200
    assert FAKE_INDEX_HTML in response.text


def test_real_api_route_is_not_shadowed(frontend_client):
    response = frontend_client.get("/invoices")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_real_api_route_404_is_not_masked_by_spa_fallback(frontend_client):
    # /invoices/{invoice_id} is a real, matched route. When the invoice doesn't
    # exist it must return its own domain 404 JSON, not the SPA index.html --
    # the fallback must only catch requests that matched NO route at all.
    response = frontend_client.get("/invoices/999999")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_health_route_still_works(frontend_client):
    response = frontend_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
