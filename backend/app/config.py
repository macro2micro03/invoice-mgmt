import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", str(BASE_DIR / "storage")))
PHOTOS_DIR = STORAGE_DIR / "photos"
PDF_DIR = STORAGE_DIR / "pdf"
EXCEL_PATH = STORAGE_DIR / "Master.xlsx"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{(STORAGE_DIR / 'invoices.db').as_posix()}")
UPSTAGE_API_KEY = os.environ.get("UPSTAGE_API_KEY", "")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
UPSTAGE_OCR_URL = "https://api.upstage.ai/v1/document-ai/document-parse"
MAJOR_MATERIALS = {"철근", "철골", "레미콘", "시멘트"}
SUPPORTED_MATERIALS = [
    "철근",
    "철골",
    "레미콘",
    "시멘트",
    "골재",
    "거푸집",
    "단열재",
    "배관",
    "전기자재",
    "마감재",
]

for directory in (PHOTOS_DIR, PDF_DIR):
    directory.mkdir(parents=True, exist_ok=True)
