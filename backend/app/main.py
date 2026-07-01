from pathlib import Path

from fastapi import FastAPI
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .database import Base, engine
from .routers import invoices, ocr

Base.metadata.create_all(bind=engine)

app = FastAPI(title="입고자재 송장관리 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ocr.router)
app.include_router(invoices.router)


@app.get("/health")
def health():
    return {"status": "ok"}


app.mount("/storage", StaticFiles(directory=str(config.STORAGE_DIR)), name="storage")

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def _register_frontend(app: FastAPI, frontend_dist: Path) -> None:
    """Mount the built SPA (if present) and register the 404 fallback handler.

    Extracted into a function (rather than inlined at module scope) so tests can
    exercise the mount/fallback behavior against a throwaway FastAPI app and a
    temp directory, without depending on whether frontend/dist actually exists
    on disk in the checkout running the tests.
    """
    if not frontend_dist.exists():
        return

    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    # React Router client-side routes (e.g. /search, /invoices/5) have no matching
    # file on disk, so StaticFiles above 404s on them. Fall back to index.html, but
    # only when NO route matched at all (request.scope["route"] is unset) -- if an
    # API route did match (e.g. GET /invoices/{id} for a missing invoice), its own
    # legitimate 404 must be preserved, not masked by the SPA shell.
    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        route_matched = request.scope.get("route") is not None
        if request.method == "GET" and not route_matched:
            return FileResponse(str(frontend_dist / "index.html"))
        # A real route matched (e.g. GET /invoices/{id} for a missing invoice) --
        # preserve its own 404 response instead of masking it with the SPA shell.
        return await http_exception_handler(request, exc)


_register_frontend(app, FRONTEND_DIST)
