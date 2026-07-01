from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
