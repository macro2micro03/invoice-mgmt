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
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")
UPSTAGE_OCR_URL = "https://api.upstage.ai/v1/document-ai/document-parse"
# document-parse는 송장처럼 페이지 레이아웃(표/제목 등)이 있는 문서용이라,
# 나무 책상 위에 놓인 금속 택 하나만 근접 촬영한 사진처럼 "문서 구조"가
# 없는 사진에서는 요소를 하나도 인식하지 못하는 경우가 있다. 이럴 때
# 일반 텍스트 인식용 OCR API를 보조 수단으로 사용한다.
UPSTAGE_TEXT_OCR_URL = "https://api.upstage.ai/v1/document-ai/ocr"
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
