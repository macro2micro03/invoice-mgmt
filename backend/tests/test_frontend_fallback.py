import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.main import _register_frontend

FAKE_INDEX_HTML = "<html><body>fake spa shell</body></html>"


@pytest.fixture
def frontend_client(tmp_path):
    """Build a throwaway FastAPI app with _register_frontend pointed at a temp
    dist dir containing a fake index.html, plus a couple of stand-in routes to
    exercise the matched-vs-unmatched route distinction.

    This avoids importlib.reload()/monkeypatch trickery on the real app.main
    module -- reloading the module re-executes its module-level
    `FRONTEND_DIST = Path(...)` assignment, which overwrites any monkeypatched
    value before the mount/handler registration runs, so the previous version
    of this fixture was silently testing against whatever frontend/dist
    happens to really exist on disk, not the fake one.
    """
    fake_dist = tmp_path / "dist"
    fake_dist.mkdir()
    (fake_dist / "index.html").write_text(FAKE_INDEX_HTML, encoding="utf-8")

    test_app = FastAPI()

    @test_app.get("/health")
    def health():
        return {"status": "ok"}

    @test_app.get("/invoices")
    def list_invoices():
        return []

    @test_app.get("/invoices/{invoice_id}")
    def get_invoice(invoice_id: int):
        # A real, matched route whose own 404 must NOT be masked by the SPA fallback.
        raise HTTPException(status_code=404, detail="invoice not found")

    _register_frontend(test_app, fake_dist)

    return TestClient(test_app)


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


def test_register_frontend_is_noop_when_dist_missing(tmp_path):
    missing_dist = tmp_path / "does-not-exist"
    test_app = FastAPI()

    @test_app.get("/health")
    def health():
        return {"status": "ok"}

    _register_frontend(test_app, missing_dist)

    client = TestClient(test_app)
    # No frontend mounted and no custom 404 handler registered, so an unmatched
    # route falls through to FastAPI's default JSON 404 rather than index.html.
    response = client.get("/search")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
