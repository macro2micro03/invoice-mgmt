# AI 기반 건설자재 입고관리 시스템 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 모바일 웹(PWA)에서 송장을 촬영하면 OCR로 표준 필드를 추출하고, 사용자가 수정 후 저장하면 DB/사진/Master.xlsx/주요자재 PDF가 자동 생성되는 시스템을 만든다.

**Architecture:** React+Vite PWA 프론트엔드가 사용자 PC/홈서버에서 구동되는 FastAPI 백엔드에 LAN으로 접속한다. 백엔드는 SQLite에 저장하고, Upstage Document AI로 OCR을 수행하며, openpyxl/reportlab으로 엑셀·PDF를 파생 생성한다. 로그인 없음, LAN 내부 접속만 허용.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, openpyxl, reportlab, requests, React, Vite, vite-plugin-pwa, react-router-dom, pytest, httpx.

## Global Constraints

- 표준 데이터 필드(고정): `material_type, vendor, delivery_date, vehicle_no, invoice_no, item_name, spec, unit, quantity, weight, note` — 모든 DB/엑셀/PDF/API가 이 필드명을 그대로 사용한다.
- 로그인 기능 없음 (MVP 범위 밖). 인증 관련 코드/미들웨어를 추가하지 않는다.
- **저장 우선순위 원칙**: DB 저장이 성공하면 그 건은 "저장 완료"로 취급한다. 사진 저장/엑셀 append/PDF 생성이 실패해도 예외를 사용자에게 전파하지 않고 서버 로그로만 남긴다 (`print`/`logging`으로 충분, 재시도 로직은 MVP 범위 밖).
- OCR 실패(네트워크 오류/타임아웃 포함)는 절대 요청을 막지 않는다 — 항상 빈 필드를 반환하고 사용자가 수동 입력하게 한다.
- "주요자재" 판정은 `app/config.py`의 `MAJOR_MATERIALS` 집합 하나로만 관리한다 (`{"철근", "철골", "레미콘", "시멘트"}`).
- 모든 파일 경로는 `STORAGE_DIR` 하위 상대경로로 DB에 저장한다 (절대경로 저장 금지 — 서버를 옮겨도 깨지지 않도록).
- 백엔드 테스트는 `backend/` 디렉터리에서 `pytest tests/ -v`로 실행한다.

---

### Task 1: 백엔드 프로젝트 스캐폴드 + 헬스체크

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_health.py`

**Interfaces:**
- Consumes: 없음 (최초 태스크)
- Produces: `app.config` 모듈 (`STORAGE_DIR`, `PHOTOS_DIR`, `EXCEL_PATH`, `PDF_DIR`, `DATABASE_URL`, `UPSTAGE_API_KEY`, `UPSTAGE_OCR_URL`, `MAJOR_MATERIALS`), `app.main.app` (FastAPI 인스턴스)

- [ ] **Step 1: 디렉터리와 requirements.txt 작성**

`backend/requirements.txt`:
```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
pydantic==2.9.2
openpyxl==3.1.5
reportlab==4.2.2
requests==2.32.3
python-multipart==0.0.9
pytest==8.3.3
httpx==0.27.2
```

- [ ] **Step 2: `app/__init__.py` 생성 (빈 파일)**

```python
```

- [ ] **Step 3: `app/config.py` 작성**

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", str(BASE_DIR / "storage")))
PHOTOS_DIR = STORAGE_DIR / "photos"
PDF_DIR = STORAGE_DIR / "pdf"
EXCEL_PATH = STORAGE_DIR / "Master.xlsx"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{STORAGE_DIR / 'invoices.db'}")
UPSTAGE_API_KEY = os.environ.get("UPSTAGE_API_KEY", "")
UPSTAGE_OCR_URL = "https://api.upstage.ai/v1/document-ai/document-parse"
MAJOR_MATERIALS = {"철근", "철골", "레미콘", "시멘트"}

for directory in (PHOTOS_DIR, PDF_DIR):
    directory.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: `app/main.py` 작성 (헬스체크만)**

```python
from fastapi import FastAPI

app = FastAPI(title="입고자재 송장관리 API")


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: `tests/__init__.py` 생성 (빈 파일)**

```python
```

- [ ] **Step 6: 실패하는 테스트 작성 — `tests/test_health.py`**

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 7: 테스트 실행해서 통과 확인**

Run (backend 디렉터리 안에서): `pytest tests/test_health.py -v`
Expected: `test_health_returns_ok PASSED` (Step 4에서 이미 구현했으므로 바로 통과해야 함)

- [ ] **Step 8: 커밋**

```bash
git add backend/requirements.txt backend/app/__init__.py backend/app/config.py backend/app/main.py backend/tests/__init__.py backend/tests/test_health.py
git commit -m "chore: backend 스캐폴드 및 헬스체크 추가"
```

---

### Task 2: DB 모델 / 스키마 / CRUD

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/models.py`
- Create: `backend/app/schemas.py`
- Create: `backend/app/crud.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_crud.py`

**Interfaces:**
- Consumes: `app.config.DATABASE_URL`
- Produces:
  - `app.database.Base`, `app.database.engine`, `app.database.SessionLocal`, `app.database.get_db()`
  - `app.models.Invoice` (컬럼: `id, material_type, vendor, delivery_date, vehicle_no, invoice_no, item_name, spec, unit, quantity, weight, note, photo_path, created_at, updated_at`)
  - `app.schemas.InvoiceCreate`, `app.schemas.InvoiceUpdate`, `app.schemas.InvoiceOut`
  - `app.crud.create_invoice(db, data: InvoiceCreate, photo_path=None) -> Invoice`
  - `app.crud.get_invoice(db, invoice_id: int) -> Invoice | None`
  - `app.crud.list_invoices(db, vendor=None, material_type=None, invoice_no=None, delivery_date=None) -> list[Invoice]`
  - `app.crud.update_invoice(db, invoice_id: int, data: InvoiceUpdate) -> Invoice | None`
  - `tests/conftest.py`의 `db_session` fixture (테스트 전용 SQLite, 매 테스트마다 초기화)

- [ ] **Step 1: `app/database.py` 작성**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from . import config

engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: `app/models.py` 작성**

```python
from sqlalchemy import Column, Integer, String, Float, Date, DateTime
from sqlalchemy.sql import func

from .database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    material_type = Column(String, nullable=False, index=True)
    vendor = Column(String, nullable=True, index=True)
    delivery_date = Column(Date, nullable=True, index=True)
    vehicle_no = Column(String, nullable=True)
    invoice_no = Column(String, nullable=True, index=True)
    item_name = Column(String, nullable=True)
    spec = Column(String, nullable=True)
    unit = Column(String, nullable=True)
    quantity = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)
    note = Column(String, nullable=True)
    photo_path = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 3: `app/schemas.py` 작성**

```python
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class InvoiceBase(BaseModel):
    material_type: str
    vendor: Optional[str] = None
    delivery_date: Optional[date] = None
    vehicle_no: Optional[str] = None
    invoice_no: Optional[str] = None
    item_name: Optional[str] = None
    spec: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = None
    weight: Optional[float] = None
    note: Optional[str] = None


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(InvoiceBase):
    pass


class InvoiceOut(InvoiceBase):
    id: int
    photo_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 4: `tests/conftest.py` 작성 (테스트용 격리 스토리지/DB)**

```python
import os
import tempfile

TEST_STORAGE_DIR = tempfile.mkdtemp(prefix="invoice_test_")
os.environ["STORAGE_DIR"] = TEST_STORAGE_DIR
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_STORAGE_DIR}/test.db"

import pytest  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 5: 실패하는 테스트 작성 — `tests/test_crud.py`**

```python
from datetime import date

from app import crud, schemas


def make_invoice_data(**overrides):
    base = dict(
        material_type="철근",
        vendor="대한제강",
        delivery_date=date(2026, 7, 1),
        vehicle_no="12가3456",
        invoice_no="INV-001",
        item_name="철근 D10",
        spec="D10",
        unit="TON",
        quantity=10.5,
        weight=10500,
        note="비고 없음",
    )
    base.update(overrides)
    return schemas.InvoiceCreate(**base)


def test_create_and_get_invoice(db_session):
    created = crud.create_invoice(db_session, make_invoice_data(), photo_path="photos/1.jpg")
    assert created.id is not None
    fetched = crud.get_invoice(db_session, created.id)
    assert fetched.vendor == "대한제강"
    assert fetched.photo_path == "photos/1.jpg"


def test_get_invoice_missing_returns_none(db_session):
    assert crud.get_invoice(db_session, 999999) is None


def test_list_invoices_filter_by_vendor(db_session):
    crud.create_invoice(db_session, make_invoice_data(vendor="A업체"))
    crud.create_invoice(db_session, make_invoice_data(vendor="B업체"))
    results = crud.list_invoices(db_session, vendor="A업체")
    assert len(results) == 1
    assert results[0].vendor == "A업체"


def test_update_invoice(db_session):
    created = crud.create_invoice(db_session, make_invoice_data())
    update_data = schemas.InvoiceUpdate(**{**make_invoice_data().model_dump(), "vendor": "수정된업체"})
    updated = crud.update_invoice(db_session, created.id, update_data)
    assert updated.vendor == "수정된업체"


def test_update_invoice_missing_returns_none(db_session):
    update_data = make_invoice_data()
    assert crud.update_invoice(db_session, 999999, schemas.InvoiceUpdate(**update_data.model_dump())) is None
```

- [ ] **Step 6: 테스트 실행해서 실패 확인**

Run: `pytest tests/test_crud.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.crud'`

- [ ] **Step 7: `app/crud.py` 구현**

```python
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from . import models, schemas


def create_invoice(db: Session, data: schemas.InvoiceCreate, photo_path: Optional[str] = None) -> models.Invoice:
    invoice = models.Invoice(**data.model_dump(), photo_path=photo_path)
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def get_invoice(db: Session, invoice_id: int) -> Optional[models.Invoice]:
    return db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()


def list_invoices(
    db: Session,
    vendor: Optional[str] = None,
    material_type: Optional[str] = None,
    invoice_no: Optional[str] = None,
    delivery_date: Optional[date] = None,
) -> list[models.Invoice]:
    query = db.query(models.Invoice)
    if vendor:
        query = query.filter(models.Invoice.vendor == vendor)
    if material_type:
        query = query.filter(models.Invoice.material_type == material_type)
    if invoice_no:
        query = query.filter(models.Invoice.invoice_no == invoice_no)
    if delivery_date:
        query = query.filter(models.Invoice.delivery_date == delivery_date)
    return query.order_by(models.Invoice.id.desc()).all()


def update_invoice(db: Session, invoice_id: int, data: schemas.InvoiceUpdate) -> Optional[models.Invoice]:
    invoice = get_invoice(db, invoice_id)
    if invoice is None:
        return None
    for key, value in data.model_dump().items():
        setattr(invoice, key, value)
    db.commit()
    db.refresh(invoice)
    return invoice
```

- [ ] **Step 8: 테스트 실행해서 통과 확인**

Run: `pytest tests/test_crud.py -v`
Expected: 5개 테스트 모두 PASSED

- [ ] **Step 9: 커밋**

```bash
git add backend/app/database.py backend/app/models.py backend/app/schemas.py backend/app/crud.py backend/tests/conftest.py backend/tests/test_crud.py
git commit -m "feat: Invoice 모델/스키마/CRUD 추가"
```

---

### Task 3: OCR 정규화 및 Upstage 연동

**Files:**
- Create: `backend/app/ocr.py`
- Create: `backend/tests/test_ocr.py`

**Interfaces:**
- Consumes: `app.config.UPSTAGE_API_KEY`, `app.config.UPSTAGE_OCR_URL`
- Produces:
  - `app.ocr.STANDARD_FIELDS` (list, `schemas.InvoiceBase`와 동일한 11개 필드명)
  - `app.ocr.call_upstage_ocr(image_bytes: bytes, filename: str = "invoice.jpg") -> dict`
  - `app.ocr.extract_text(raw_response: dict) -> str`
  - `app.ocr.normalize_fields(raw_text: str) -> dict[str, str]` (모든 필드가 항상 존재, 못 찾으면 빈 문자열)

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_ocr.py`**

```python
from app import ocr


def test_extract_text_from_flat_text_response():
    raw = {"text": "거래처: 대한제강"}
    assert ocr.extract_text(raw) == "거래처: 대한제강"


def test_extract_text_from_elements_response():
    raw = {"elements": [{"content": {"text": "line1"}}, {"content": {"text": "line2"}}]}
    assert ocr.extract_text(raw) == "line1\nline2"


def test_normalize_fields_extracts_labeled_values():
    text = (
        "거래처: 대한제강\n"
        "납품일: 2026-07-01\n"
        "차량번호: 12가3456\n"
        "송장번호: INV-001\n"
        "품명: 철근 D10\n"
        "규격: D10\n"
        "단위: TON\n"
        "수량: 10.5\n"
    )
    fields = ocr.normalize_fields(text)
    assert fields["vendor"] == "대한제강"
    assert fields["delivery_date"] == "2026-07-01"
    assert fields["vehicle_no"] == "12가3456"
    assert fields["invoice_no"] == "INV-001"
    assert fields["item_name"] == "철근 D10"
    assert fields["unit"] == "TON"


def test_normalize_fields_missing_label_returns_empty_strings():
    fields = ocr.normalize_fields("아무 관련 없는 텍스트")
    for field in ocr.STANDARD_FIELDS:
        assert fields[field] == ""


def test_call_upstage_ocr_sends_auth_header(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"text": "ok"}

    def fake_post(url, headers=None, files=None, timeout=None):
        captured["headers"] = headers
        captured["url"] = url
        return FakeResponse()

    monkeypatch.setattr(ocr, "requests", type("R", (), {"post": staticmethod(fake_post)}))
    monkeypatch.setattr(ocr.config, "UPSTAGE_API_KEY", "test-key")

    result = ocr.call_upstage_ocr(b"fake-bytes")
    assert result == {"text": "ok"}
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_call_upstage_ocr_raises_without_api_key(monkeypatch):
    monkeypatch.setattr(ocr.config, "UPSTAGE_API_KEY", "")
    try:
        ocr.call_upstage_ocr(b"fake-bytes")
        assert False, "should have raised"
    except RuntimeError:
        pass
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `pytest tests/test_ocr.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ocr'`

- [ ] **Step 3: `app/ocr.py` 구현**

```python
import re

import requests

from . import config

FIELD_LABELS = {
    "material_type": ["자재종류", "자재명"],
    "vendor": ["거래처", "공급자", "상호"],
    "delivery_date": ["납품일", "일자", "날짜"],
    "vehicle_no": ["차량번호", "차량"],
    "invoice_no": ["송장번호", "거래명세서번호", "명세서번호"],
    "item_name": ["품명"],
    "spec": ["규격"],
    "unit": ["단위"],
    "quantity": ["수량"],
    "weight": ["중량"],
    "note": ["비고"],
}

STANDARD_FIELDS = list(FIELD_LABELS.keys())


def call_upstage_ocr(image_bytes: bytes, filename: str = "invoice.jpg") -> dict:
    if not config.UPSTAGE_API_KEY:
        raise RuntimeError("UPSTAGE_API_KEY가 설정되지 않았습니다")
    response = requests.post(
        config.UPSTAGE_OCR_URL,
        headers={"Authorization": f"Bearer {config.UPSTAGE_API_KEY}"},
        files={"document": (filename, image_bytes)},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def extract_text(raw_response: dict) -> str:
    text = raw_response.get("text", "")
    if text:
        return text
    elements = raw_response.get("elements", [])
    lines = []
    for element in elements:
        content = element.get("content", {})
        if isinstance(content, dict) and content.get("text"):
            lines.append(content["text"])
    return "\n".join(lines)


def normalize_fields(raw_text: str) -> dict:
    result = {field: "" for field in STANDARD_FIELDS}
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    for line in lines:
        for field, labels in FIELD_LABELS.items():
            if result[field]:
                continue
            for label in labels:
                if label not in line:
                    continue
                match = re.search(rf"{label}\s*[:：]?\s*(.+)", line)
                if match:
                    value = match.group(1).strip()
                    if value and value != label:
                        result[field] = value
                        break
    return result
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `pytest tests/test_ocr.py -v`
Expected: 6개 테스트 모두 PASSED

- [ ] **Step 5: 커밋**

```bash
git add backend/app/ocr.py backend/tests/test_ocr.py
git commit -m "feat: OCR 응답 정규화 및 Upstage 클라이언트 추가"
```

---

### Task 4: 사진 저장

**Files:**
- Create: `backend/app/photos.py`
- Create: `backend/tests/test_photos.py`

**Interfaces:**
- Consumes: `app.config.PHOTOS_DIR`, `app.config.STORAGE_DIR`
- Produces: `app.photos.save_photo(image_bytes: bytes, original_filename: str) -> str` (STORAGE_DIR 기준 상대경로 반환)

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_photos.py`**

```python
from app import config, photos


def test_save_photo_writes_file_and_returns_relative_path():
    rel_path = photos.save_photo(b"fake-bytes", "invoice.jpg")
    full_path = config.STORAGE_DIR / rel_path
    assert full_path.exists()
    assert full_path.read_bytes() == b"fake-bytes"
    assert rel_path.startswith("photos")


def test_save_photo_preserves_extension():
    rel_path = photos.save_photo(b"data", "scan.png")
    assert rel_path.endswith(".png")


def test_save_photo_defaults_to_jpg_when_no_extension():
    rel_path = photos.save_photo(b"data", "noext")
    assert rel_path.endswith(".jpg")
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `pytest tests/test_photos.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.photos'`

- [ ] **Step 3: `app/photos.py` 구현**

```python
import uuid
from pathlib import Path

from . import config


def save_photo(image_bytes: bytes, original_filename: str) -> str:
    ext = Path(original_filename).suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = config.PHOTOS_DIR / filename
    dest.write_bytes(image_bytes)
    return str(dest.relative_to(config.STORAGE_DIR)).replace("\\", "/")
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `pytest tests/test_photos.py -v`
Expected: 3개 테스트 모두 PASSED

- [ ] **Step 5: 커밋**

```bash
git add backend/app/photos.py backend/tests/test_photos.py
git commit -m "feat: 원본 사진 저장 유틸 추가"
```

---

### Task 5: Master.xlsx 자동 작성

**Files:**
- Create: `backend/app/excel.py`
- Create: `backend/tests/test_excel.py`

**Interfaces:**
- Consumes: `app.config.EXCEL_PATH`, `app.models.Invoice`
- Produces: `app.excel.append_invoice(invoice: models.Invoice) -> None` (자재종류별 시트에 행 추가, 시트 없으면 헤더와 함께 생성)

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_excel.py`**

```python
from datetime import date

from openpyxl import load_workbook

from app import config, excel, models


def make_invoice(**overrides):
    defaults = dict(
        id=1,
        material_type="철근",
        vendor="대한제강",
        delivery_date=date(2026, 7, 1),
        vehicle_no="12가3456",
        invoice_no="INV-001",
        item_name="철근 D10",
        spec="D10",
        unit="TON",
        quantity=10.5,
        weight=10500,
        note="",
    )
    defaults.update(overrides)
    return models.Invoice(**defaults)


def test_append_invoice_creates_sheet_with_header_and_row():
    if config.EXCEL_PATH.exists():
        config.EXCEL_PATH.unlink()
    excel.append_invoice(make_invoice())
    workbook = load_workbook(config.EXCEL_PATH)
    assert "철근" in workbook.sheetnames
    sheet = workbook["철근"]
    assert sheet.cell(row=1, column=1).value == "id"
    assert sheet.cell(row=2, column=2).value == "대한제강"


def test_append_invoice_appends_to_existing_sheet():
    if config.EXCEL_PATH.exists():
        config.EXCEL_PATH.unlink()
    excel.append_invoice(make_invoice(id=1))
    excel.append_invoice(make_invoice(id=2, vendor="B업체"))
    workbook = load_workbook(config.EXCEL_PATH)
    sheet = workbook["철근"]
    assert sheet.max_row == 3
    assert sheet.cell(row=3, column=2).value == "B업체"


def test_append_invoice_separates_sheets_by_material_type():
    if config.EXCEL_PATH.exists():
        config.EXCEL_PATH.unlink()
    excel.append_invoice(make_invoice(id=1, material_type="철근"))
    excel.append_invoice(make_invoice(id=2, material_type="시멘트"))
    workbook = load_workbook(config.EXCEL_PATH)
    assert set(workbook.sheetnames) == {"철근", "시멘트"}
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `pytest tests/test_excel.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.excel'`

- [ ] **Step 3: `app/excel.py` 구현**

```python
from openpyxl import Workbook, load_workbook

from . import config, models

HEADERS = ["id", "거래처", "납품일", "차량번호", "송장번호", "품명", "규격", "단위", "수량", "중량", "비고"]


def append_invoice(invoice: models.Invoice) -> None:
    if config.EXCEL_PATH.exists():
        workbook = load_workbook(config.EXCEL_PATH)
    else:
        workbook = Workbook()
        workbook.remove(workbook.active)

    sheet_name = (invoice.material_type or "미분류")[:31]
    if sheet_name not in workbook.sheetnames:
        sheet = workbook.create_sheet(sheet_name)
        sheet.append(HEADERS)
    else:
        sheet = workbook[sheet_name]

    sheet.append([
        invoice.id,
        invoice.vendor,
        invoice.delivery_date.isoformat() if invoice.delivery_date else "",
        invoice.vehicle_no,
        invoice.invoice_no,
        invoice.item_name,
        invoice.spec,
        invoice.unit,
        invoice.quantity,
        invoice.weight,
        invoice.note,
    ])
    workbook.save(config.EXCEL_PATH)
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `pytest tests/test_excel.py -v`
Expected: 3개 테스트 모두 PASSED

- [ ] **Step 5: 커밋**

```bash
git add backend/app/excel.py backend/tests/test_excel.py
git commit -m "feat: Master.xlsx 자재별 시트 append 추가"
```

---

### Task 6: 주요자재 PDF 생성

**Files:**
- Create: `backend/app/pdf.py`
- Create: `backend/tests/test_pdf.py`

**Interfaces:**
- Consumes: `app.config.PDF_DIR`, `app.config.MAJOR_MATERIALS`, `app.models.Invoice`
- Produces:
  - `app.pdf.is_major_material(material_type: str) -> bool`
  - `app.pdf.generate_pdf(invoice: models.Invoice) -> str` (STORAGE_DIR 기준 상대경로 반환)

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_pdf.py`**

```python
from datetime import date

from app import config, models, pdf


def make_invoice(**overrides):
    defaults = dict(
        id=1,
        material_type="철근",
        vendor="대한제강",
        delivery_date=date(2026, 7, 1),
        vehicle_no="12가3456",
        invoice_no="INV-001",
        item_name="철근 D10",
        spec="D10",
        unit="TON",
        quantity=10.5,
        weight=10500,
        note="",
    )
    defaults.update(overrides)
    return models.Invoice(**defaults)


def test_is_major_material_true_for_configured_types():
    assert pdf.is_major_material("철근") is True
    assert pdf.is_major_material("레미콘") is True


def test_is_major_material_false_for_others():
    assert pdf.is_major_material("마감재") is False


def test_generate_pdf_creates_nonempty_file():
    rel_path = pdf.generate_pdf(make_invoice())
    full_path = config.STORAGE_DIR / rel_path
    assert full_path.exists()
    assert full_path.stat().st_size > 0
    assert rel_path.startswith("pdf")
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `pytest tests/test_pdf.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pdf'`

- [ ] **Step 3: `app/pdf.py` 구현**

한글 출력을 위해 reportlab에 내장된 CID 폰트(`HYSMyeongJo-Medium`)를 등록해서 사용한다 (별도 폰트 파일 설치 불필요).

```python
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from . import config, models

pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
FONT_NAME = "HYSMyeongJo-Medium"

FIELD_LABELS = [
    ("거래처", "vendor"),
    ("납품일", "delivery_date"),
    ("차량번호", "vehicle_no"),
    ("송장번호", "invoice_no"),
    ("품명", "item_name"),
    ("규격", "spec"),
    ("단위", "unit"),
    ("수량", "quantity"),
    ("중량", "weight"),
    ("비고", "note"),
]


def is_major_material(material_type: str) -> bool:
    return material_type in config.MAJOR_MATERIALS


def generate_pdf(invoice: models.Invoice) -> str:
    filename = f"invoice_{invoice.id}.pdf"
    dest = config.PDF_DIR / filename
    pdf_canvas = canvas.Canvas(str(dest), pagesize=A4)
    pdf_canvas.setFont(FONT_NAME, 14)
    pdf_canvas.drawString(50, 800, f"주요자재 입고서류 - {invoice.material_type}")
    pdf_canvas.setFont(FONT_NAME, 11)
    y = 760
    for label, attr in FIELD_LABELS:
        value = getattr(invoice, attr)
        pdf_canvas.drawString(50, y, f"{label}: {value if value is not None else ''}")
        y -= 24
    pdf_canvas.save()
    return str(dest.relative_to(config.STORAGE_DIR)).replace("\\", "/")
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `pytest tests/test_pdf.py -v`
Expected: 3개 테스트 모두 PASSED

- [ ] **Step 5: 커밋**

```bash
git add backend/app/pdf.py backend/tests/test_pdf.py
git commit -m "feat: 주요자재 PDF 생성 추가"
```

---

### Task 7: API 라우터 연결 (OCR + Invoices) 및 정적 파일 서빙

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/ocr.py`
- Create: `backend/app/routers/invoices.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_ocr_endpoint.py`
- Create: `backend/tests/test_invoices_api.py`

**Interfaces:**
- Consumes: Task 2~6에서 만든 `crud`, `schemas`, `ocr`, `photos`, `excel`, `pdf`, `database.get_db`
- Produces:
  - `POST /ocr` (multipart, field `file`) → `dict` (11개 표준 필드)
  - `POST /invoices` (multipart form 필드 + 선택적 `photo` 파일) → `InvoiceOut`
  - `GET /invoices?vendor=&material_type=&invoice_no=&delivery_date=` → `list[InvoiceOut]`
  - `GET /invoices/{id}` → `InvoiceOut` (404 시 에러)
  - `PUT /invoices/{id}` (JSON body) → `InvoiceOut` (404 시 에러)
  - `GET /storage/...` 정적 서빙 (사진/PDF 다운로드용)

- [ ] **Step 1: `app/routers/__init__.py` 생성 (빈 파일)**

```python
```

- [ ] **Step 2: `app/routers/ocr.py` 작성**

```python
from fastapi import APIRouter, File, UploadFile

from .. import ocr

router = APIRouter()


@router.post("/ocr")
async def run_ocr(file: UploadFile = File(...)):
    image_bytes = await file.read()
    try:
        raw_response = ocr.call_upstage_ocr(image_bytes, filename=file.filename or "invoice.jpg")
    except Exception:
        return {field: "" for field in ocr.STANDARD_FIELDS}
    text = ocr.extract_text(raw_response)
    return ocr.normalize_fields(text)
```

- [ ] **Step 3: `app/routers/invoices.py` 작성**

```python
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import crud, excel, pdf, photos, schemas
from ..database import get_db

router = APIRouter()


@router.post("/invoices", response_model=schemas.InvoiceOut)
async def create_invoice(
    material_type: str = Form(...),
    vendor: Optional[str] = Form(None),
    delivery_date: Optional[date] = Form(None),
    vehicle_no: Optional[str] = Form(None),
    invoice_no: Optional[str] = Form(None),
    item_name: Optional[str] = Form(None),
    spec: Optional[str] = Form(None),
    unit: Optional[str] = Form(None),
    quantity: Optional[float] = Form(None),
    weight: Optional[float] = Form(None),
    note: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    data = schemas.InvoiceCreate(
        material_type=material_type,
        vendor=vendor,
        delivery_date=delivery_date,
        vehicle_no=vehicle_no,
        invoice_no=invoice_no,
        item_name=item_name,
        spec=spec,
        unit=unit,
        quantity=quantity,
        weight=weight,
        note=note,
    )
    invoice = crud.create_invoice(db, data)

    if photo is not None:
        try:
            image_bytes = await photo.read()
            photo_path = photos.save_photo(image_bytes, photo.filename or "invoice.jpg")
            invoice.photo_path = photo_path
            db.commit()
            db.refresh(invoice)
        except Exception as error:
            print(f"[invoices] 사진 저장 실패: {error}")

    try:
        excel.append_invoice(invoice)
    except Exception as error:
        print(f"[invoices] 엑셀 저장 실패: {error}")

    if pdf.is_major_material(invoice.material_type):
        try:
            pdf.generate_pdf(invoice)
        except Exception as error:
            print(f"[invoices] PDF 생성 실패: {error}")

    return invoice


@router.get("/invoices", response_model=list[schemas.InvoiceOut])
def search_invoices(
    vendor: Optional[str] = None,
    material_type: Optional[str] = None,
    invoice_no: Optional[str] = None,
    delivery_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return crud.list_invoices(
        db,
        vendor=vendor,
        material_type=material_type,
        invoice_no=invoice_no,
        delivery_date=delivery_date,
    )


@router.get("/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = crud.get_invoice(db, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="송장을 찾을 수 없습니다")
    return invoice


@router.put("/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def update_invoice(invoice_id: int, data: schemas.InvoiceUpdate, db: Session = Depends(get_db)):
    invoice = crud.update_invoice(db, invoice_id, data)
    if invoice is None:
        raise HTTPException(status_code=404, detail="송장을 찾을 수 없습니다")
    return invoice
```

- [ ] **Step 4: `app/main.py` 수정 (라우터 연결 + 정적 서빙 + CORS)**

```python
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
```

- [ ] **Step 5: 실패하는 테스트 작성 — `tests/test_ocr_endpoint.py`**

```python
from fastapi.testclient import TestClient

from app import ocr as ocr_module
from app.main import app

client = TestClient(app)


def test_ocr_endpoint_returns_normalized_fields(monkeypatch):
    monkeypatch.setattr(ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": {"text": "거래처: 대한제강"})
    response = client.post("/ocr", files={"file": ("test.jpg", b"fake-image-bytes", "image/jpeg")})
    assert response.status_code == 200
    assert response.json()["vendor"] == "대한제강"


def test_ocr_endpoint_returns_blank_fields_on_failure(monkeypatch):
    def raise_error(*args, **kwargs):
        raise RuntimeError("network error")

    monkeypatch.setattr(ocr_module, "call_upstage_ocr", raise_error)
    response = client.post("/ocr", files={"file": ("test.jpg", b"fake-image-bytes", "image/jpeg")})
    assert response.status_code == 200
    body = response.json()
    for field in ocr_module.STANDARD_FIELDS:
        assert body[field] == ""
```

- [ ] **Step 6: 실패하는 테스트 작성 — `tests/test_invoices_api.py`**

```python
import io

from fastapi.testclient import TestClient

from app import excel as excel_module
from app import pdf as pdf_module
from app.main import app

client = TestClient(app)


def test_create_invoice_persists_and_returns_photo_path(monkeypatch):
    monkeypatch.setattr(excel_module, "append_invoice", lambda invoice: None)
    monkeypatch.setattr(pdf_module, "generate_pdf", lambda invoice: "pdf/x.pdf")

    response = client.post(
        "/invoices",
        data={"material_type": "철근", "vendor": "대한제강", "invoice_no": "INV-100"},
        files={"photo": ("test.jpg", io.BytesIO(b"fake"), "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["vendor"] == "대한제강"
    assert body["photo_path"] is not None


def test_search_invoices_by_vendor(monkeypatch):
    monkeypatch.setattr(excel_module, "append_invoice", lambda invoice: None)
    monkeypatch.setattr(pdf_module, "generate_pdf", lambda invoice: "pdf/x.pdf")

    client.post("/invoices", data={"material_type": "시멘트", "vendor": "검색전용업체"})
    response = client.get("/invoices", params={"vendor": "검색전용업체"})
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["vendor"] == "검색전용업체"


def test_get_invoice_not_found_returns_404():
    response = client.get("/invoices/999999")
    assert response.status_code == 404


def test_update_invoice_changes_field(monkeypatch):
    monkeypatch.setattr(excel_module, "append_invoice", lambda invoice: None)
    monkeypatch.setattr(pdf_module, "generate_pdf", lambda invoice: "pdf/x.pdf")

    create_response = client.post("/invoices", data={"material_type": "골재", "vendor": "원래업체"})
    invoice_id = create_response.json()["id"]

    update_response = client.put(
        f"/invoices/{invoice_id}",
        json={"material_type": "골재", "vendor": "변경된업체"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["vendor"] == "변경된업체"
```

- [ ] **Step 7: 테스트 실행해서 통과 확인**

Run: `pytest tests/ -v`
Expected: 이전 태스크 테스트 포함 전체 PASSED (Task 1~7 누적)

- [ ] **Step 8: 커밋**

```bash
git add backend/app/routers backend/app/main.py backend/tests/test_ocr_endpoint.py backend/tests/test_invoices_api.py
git commit -m "feat: OCR/Invoices API 라우터 연결 및 정적 파일 서빙"
```

---

### Task 8: 프론트엔드 스캐폴드 (React + Vite + PWA) 및 API 클라이언트

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/api.js`
- Create: `frontend/src/pages/CapturePage.jsx` (placeholder, Task 9에서 완성)

**Interfaces:**
- Consumes: 백엔드 `/ocr`, `/invoices` 엔드포인트 (Task 7)
- Produces: `runOcr(file)`, `createInvoice(fields, photoFile)`, `searchInvoices(params)`, `getInvoice(id)`, `updateInvoice(id, fields)` (모두 `src/api.js`에서 export, Task 9~11에서 사용)

- [ ] **Step 1: `frontend/package.json` 작성**

```json
{
  "name": "invoice-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.0",
    "vite-plugin-pwa": "^0.20.5"
  }
}
```

- [ ] **Step 2: 의존성 설치**

Run: `cd frontend && npm install`
Expected: `node_modules` 생성, 에러 없음

- [ ] **Step 3: `frontend/vite.config.js` 작성**

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: '입고자재 송장관리',
        short_name: '송장관리',
        start_url: '.',
        display: 'standalone',
        background_color: '#ffffff',
        theme_color: '#1f6feb',
        icons: [],
      },
    }),
  ],
  server: {
    host: true,
    port: 5173,
  },
})
```

- [ ] **Step 4: `frontend/index.html` 작성**

```html
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>입고자재 송장관리</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 5: `frontend/src/main.jsx` 작성**

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
```

- [ ] **Step 6: `frontend/src/api.js` 작성**

```js
const API_BASE = import.meta.env.VITE_API_BASE || ''

export async function runOcr(imageFile) {
  const formData = new FormData()
  formData.append('file', imageFile)
  const response = await fetch(`${API_BASE}/ocr`, { method: 'POST', body: formData })
  if (!response.ok) throw new Error('OCR 요청 실패')
  return response.json()
}

export async function createInvoice(fields, photoFile) {
  const formData = new FormData()
  Object.entries(fields).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      formData.append(key, value)
    }
  })
  if (photoFile) formData.append('photo', photoFile)
  const response = await fetch(`${API_BASE}/invoices`, { method: 'POST', body: formData })
  if (!response.ok) throw new Error('저장 실패')
  return response.json()
}

export async function searchInvoices(params) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value)).toString()
  const response = await fetch(`${API_BASE}/invoices?${query}`)
  if (!response.ok) throw new Error('검색 실패')
  return response.json()
}

export async function getInvoice(id) {
  const response = await fetch(`${API_BASE}/invoices/${id}`)
  if (!response.ok) throw new Error('조회 실패')
  return response.json()
}

export async function updateInvoice(id, fields) {
  const response = await fetch(`${API_BASE}/invoices/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fields),
  })
  if (!response.ok) throw new Error('수정 실패')
  return response.json()
}
```

- [ ] **Step 7: `frontend/src/pages/CapturePage.jsx` placeholder 작성**

```jsx
export default function CapturePage() {
  return <div style={{ padding: 16 }}>촬영 화면 준비 중</div>
}
```

- [ ] **Step 8: `frontend/src/App.jsx` 작성 (라우팅 골격)**

```jsx
import { Link, Route, Routes } from 'react-router-dom'
import CapturePage from './pages/CapturePage.jsx'

export default function App() {
  return (
    <div>
      <nav style={{ display: 'flex', gap: 12, padding: 12 }}>
        <Link to="/">촬영</Link>
      </nav>
      <Routes>
        <Route path="/" element={<CapturePage />} />
      </Routes>
    </div>
  )
}
```

- [ ] **Step 9: 개발 서버로 렌더링 확인**

Run: `npm run dev` (frontend 디렉터리 안에서)
Expected: `http://localhost:5173`에서 "촬영 화면 준비 중" 텍스트가 보임. 확인 후 `Ctrl+C`로 종료.

- [ ] **Step 10: 커밋**

```bash
git add frontend/package.json frontend/vite.config.js frontend/index.html frontend/src/main.jsx frontend/src/App.jsx frontend/src/api.js frontend/src/pages/CapturePage.jsx frontend/package-lock.json
git commit -m "chore: 프론트엔드 Vite+React+PWA 스캐폴드 및 API 클라이언트 추가"
```

---

### Task 9: 촬영 화면 (Capture) — 카메라/갤러리 + OCR 호출

**Files:**
- Modify: `frontend/src/pages/CapturePage.jsx`

**Interfaces:**
- Consumes: `api.js`의 `runOcr(file)`
- Produces: `/edit` 라우트로 `{ fields, photoFile }`를 `navigate(..., { state })`로 전달 (Task 10이 소비)

- [ ] **Step 1: `CapturePage.jsx`를 실제 촬영/업로드 화면으로 교체**

```jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { runOcr } from '../api.js'

export default function CapturePage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function handleFileChange(event) {
    const file = event.target.files[0]
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const fields = await runOcr(file)
      navigate('/edit', { state: { fields, photoFile: file } })
    } catch (err) {
      setError('인식에 실패했습니다. 직접 입력해주세요.')
      navigate('/edit', { state: { fields: {}, photoFile: file } })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: 16 }}>
      <h1>송장 촬영</h1>
      <input type="file" accept="image/*" capture="environment" onChange={handleFileChange} />
      {loading && <p>인식 중...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
    </div>
  )
}
```

- [ ] **Step 2: 수동 확인 (백엔드 실행 중인 상태에서)**

터미널 1: `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
터미널 2: `cd frontend && npm run dev`
브라우저에서 `http://localhost:5173` 접속 → 파일 선택으로 이미지 업로드 → 네트워크 탭에서 `/ocr` 호출이 발생하고 `/edit`로 이동(현재는 라우트 없어 빈 화면)하는지 확인.
Expected: 콘솔에 라우팅 에러 없이 URL이 `/edit`로 바뀜 (Task 10에서 라우트 추가 예정이므로 이번 단계에서는 화면이 비어 있어도 정상)

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/pages/CapturePage.jsx
git commit -m "feat: 촬영/갤러리 업로드 및 OCR 호출 화면 구현"
```

---

### Task 10: 수정/저장 화면 (Edit)

**Files:**
- Create: `frontend/src/pages/EditPage.jsx`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: Task 9가 넘긴 `location.state.fields`, `location.state.photoFile`; `api.js`의 `createInvoice(fields, photoFile)`
- Produces: 저장 성공 시 `/search`로 이동 (Task 11이 그 라우트를 만듦)

- [ ] **Step 1: `frontend/src/pages/EditPage.jsx` 작성**

```jsx
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { createInvoice } from '../api.js'

const FIELD_DEFS = [
  ['material_type', '자재종류'],
  ['vendor', '거래처'],
  ['delivery_date', '납품일'],
  ['vehicle_no', '차량번호'],
  ['invoice_no', '송장번호'],
  ['item_name', '품명'],
  ['spec', '규격'],
  ['unit', '단위'],
  ['quantity', '수량'],
  ['weight', '중량'],
  ['note', '비고'],
]

export default function EditPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const initialFields = location.state?.fields || {}
  const photoFile = location.state?.photoFile || null
  const [fields, setFields] = useState(initialFields)
  const [saving, setSaving] = useState(false)

  function handleChange(key, value) {
    setFields((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await createInvoice(fields, photoFile)
      navigate('/search')
    } catch (err) {
      alert('저장에 실패했습니다. 다시 시도해주세요.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: 16 }}>
      <h1>내용 확인 및 수정</h1>
      {FIELD_DEFS.map(([key, label]) => (
        <div key={key} style={{ marginBottom: 8 }}>
          <label>
            {label}
            <input
              type="text"
              value={fields[key] || ''}
              onChange={(e) => handleChange(key, e.target.value)}
              style={{ display: 'block', width: '100%' }}
            />
          </label>
        </div>
      ))}
      <button onClick={handleSave} disabled={saving || !fields.material_type}>
        {saving ? '저장 중...' : '저장'}
      </button>
    </div>
  )
}
```

- [ ] **Step 2: `frontend/src/App.jsx`에 `/edit` 라우트 추가**

```jsx
import { Link, Route, Routes } from 'react-router-dom'
import CapturePage from './pages/CapturePage.jsx'
import EditPage from './pages/EditPage.jsx'

export default function App() {
  return (
    <div>
      <nav style={{ display: 'flex', gap: 12, padding: 12 }}>
        <Link to="/">촬영</Link>
      </nav>
      <Routes>
        <Route path="/" element={<CapturePage />} />
        <Route path="/edit" element={<EditPage />} />
      </Routes>
    </div>
  )
}
```

- [ ] **Step 3: 수동 확인**

백엔드/프론트 둘 다 실행 중인 상태에서 촬영→OCR→`/edit` 화면에 필드가 채워지는지, "저장" 클릭 시 `POST /invoices`가 성공하고 `/search`로 이동(현재는 라우트 없어 빈 화면)하는지 확인.
Expected: 저장 클릭 후 네트워크 탭에 `POST /invoices` 200 응답, URL이 `/search`로 변경됨.

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/pages/EditPage.jsx frontend/src/App.jsx
git commit -m "feat: 인식 결과 수정 및 저장 화면 구현"
```

---

### Task 11: 검색 화면 및 상세/수정 화면

**Files:**
- Create: `frontend/src/pages/SearchPage.jsx`
- Create: `frontend/src/pages/DetailPage.jsx`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: `api.js`의 `searchInvoices(params)`, `getInvoice(id)`, `updateInvoice(id, fields)`
- Produces: 없음 (마지막 화면 계층)

- [ ] **Step 1: `frontend/src/pages/SearchPage.jsx` 작성**

```jsx
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { searchInvoices } from '../api.js'

export default function SearchPage() {
  const [vendor, setVendor] = useState('')
  const [materialType, setMaterialType] = useState('')
  const [results, setResults] = useState([])

  async function handleSearch() {
    const data = await searchInvoices({ vendor, material_type: materialType })
    setResults(data)
  }

  return (
    <div style={{ padding: 16 }}>
      <h1>검색</h1>
      <input placeholder="거래처" value={vendor} onChange={(e) => setVendor(e.target.value)} />
      <input placeholder="자재종류" value={materialType} onChange={(e) => setMaterialType(e.target.value)} />
      <button onClick={handleSearch}>검색</button>
      <ul>
        {results.map((item) => (
          <li key={item.id}>
            <Link to={`/invoices/${item.id}`}>
              {item.material_type} / {item.vendor} / {item.invoice_no}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Step 2: `frontend/src/pages/DetailPage.jsx` 작성**

```jsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getInvoice, updateInvoice } from '../api.js'

const FIELD_DEFS = [
  ['material_type', '자재종류'],
  ['vendor', '거래처'],
  ['delivery_date', '납품일'],
  ['vehicle_no', '차량번호'],
  ['invoice_no', '송장번호'],
  ['item_name', '품명'],
  ['spec', '규격'],
  ['unit', '단위'],
  ['quantity', '수량'],
  ['weight', '중량'],
  ['note', '비고'],
]

export default function DetailPage() {
  const { id } = useParams()
  const [invoice, setInvoice] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getInvoice(id).then(setInvoice)
  }, [id])

  if (!invoice) return <p style={{ padding: 16 }}>불러오는 중...</p>

  function handleChange(key, value) {
    setInvoice((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await updateInvoice(id, invoice)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: 16 }}>
      <h1>상세/수정</h1>
      {invoice.photo_path && (
        <img src={`/storage/${invoice.photo_path}`} alt="원본 사진" style={{ maxWidth: '100%' }} />
      )}
      {FIELD_DEFS.map(([key, label]) => (
        <div key={key} style={{ marginBottom: 8 }}>
          <label>
            {label}
            <input
              type="text"
              value={invoice[key] || ''}
              onChange={(e) => handleChange(key, e.target.value)}
              style={{ display: 'block', width: '100%' }}
            />
          </label>
        </div>
      ))}
      <button onClick={handleSave} disabled={saving}>
        {saving ? '저장 중...' : '수정 저장'}
      </button>
    </div>
  )
}
```

- [ ] **Step 3: `frontend/src/App.jsx`에 나머지 라우트 추가**

```jsx
import { Link, Route, Routes } from 'react-router-dom'
import CapturePage from './pages/CapturePage.jsx'
import DetailPage from './pages/DetailPage.jsx'
import EditPage from './pages/EditPage.jsx'
import SearchPage from './pages/SearchPage.jsx'

export default function App() {
  return (
    <div>
      <nav style={{ display: 'flex', gap: 12, padding: 12 }}>
        <Link to="/">촬영</Link>
        <Link to="/search">검색</Link>
      </nav>
      <Routes>
        <Route path="/" element={<CapturePage />} />
        <Route path="/edit" element={<EditPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/invoices/:id" element={<DetailPage />} />
      </Routes>
    </div>
  )
}
```

- [ ] **Step 4: 수동 E2E 확인 (백엔드/프론트 모두 실행 중인 상태)**

1. `/` 에서 이미지 업로드 → `/edit`에서 필드 확인/수정 → 저장 → `/search`로 이동
2. `/search`에서 방금 저장한 거래처로 검색 → 목록에 표시되는지 확인
3. 목록 항목 클릭 → `/invoices/:id`에서 사진과 필드가 보이는지, 필드 수정 후 "수정 저장"이 동작하는지 확인
4. 백엔드 `storage/Master.xlsx`를 열어 해당 자재종류 시트에 행이 추가되었는지 확인
5. `MAJOR_MATERIALS`에 포함된 자재종류로 저장했다면 `storage/pdf/invoice_<id>.pdf`가 생성되었는지 확인

Expected: 위 5가지 모두 통과.

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/pages/SearchPage.jsx frontend/src/pages/DetailPage.jsx frontend/src/App.jsx
git commit -m "feat: 검색 및 상세/수정 화면 구현"
```

---

### Task 12: 배포 준비 (프로덕션 빌드 연결 + LAN 접속 문서화)

**Files:**
- Create: `README.md` (프로젝트 루트)

**Interfaces:**
- Consumes: Task 7의 `FRONTEND_DIST` 정적 서빙 로직
- Produces: 없음 (문서/운영 절차)

- [ ] **Step 1: 프론트엔드 프로덕션 빌드**

Run: `cd frontend && npm run build`
Expected: `frontend/dist` 폴더 생성, 에러 없음

- [ ] **Step 2: 백엔드가 빌드 결과물을 서빙하는지 확인**

Run: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000`
브라우저에서 `http://localhost:8000` 접속.
Expected: React 앱이 렌더링됨 (Task 7에서 `FRONTEND_DIST` 마운트 로직을 이미 작성했으므로 `dist`가 존재하면 자동으로 서빙됨)

- [ ] **Step 3: `README.md` 작성 (Windows PowerShell 기준 실행/배포 절차)**

```markdown
# 입고자재 송장관리 시스템

## 최초 설정

### 백엔드

    cd backend
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt

### 프론트엔드

    cd frontend
    npm install
    npm run build

## 실행 (매번)

1. Upstage API 키와 저장 경로를 환경변수로 설정 (PowerShell):

    $env:UPSTAGE_API_KEY = "발급받은 API 키"
    $env:STORAGE_DIR = "C:\경로\원하는\저장폴더"

2. 백엔드 실행:

    cd backend
    venv\Scripts\activate
    uvicorn app.main:app --host 0.0.0.0 --port 8000

3. 방화벽에서 8000번 포트를 한 번만 허용 (관리자 권한 PowerShell):

    New-NetFirewallRule -DisplayName "InvoiceApp" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow

4. PC의 로컬 IP 확인:

    ipconfig

   "IPv4 주소" 값을 확인 (예: 192.168.0.15)

5. 같은 Wi-Fi에 연결된 폰에서 브라우저로 접속:

    http://192.168.0.15:8000

## 프론트엔드 코드 수정 후 재배포

    cd frontend
    npm run build

빌드 결과가 `frontend/dist`에 생성되면 백엔드를 재시작할 때 자동으로 반영됩니다.

## 데이터 위치

`STORAGE_DIR` 환경변수로 지정한 폴더 안에:
- `invoices.db` — SQLite DB
- `Master.xlsx` — 자재종류별 시트로 누적되는 엑셀
- `photos/` — 원본 사진
- `pdf/` — 주요자재 입고서류 PDF
```

- [ ] **Step 4: 커밋**

```bash
git add README.md
git commit -m "docs: 실행 및 LAN 배포 절차 문서화"
```

---

## Self-Review 요약

- **스펙 커버리지**: 촬영/갤러리(Task 9), OCR(Task 3, 7, 9), 수정화면(Task 10), 사진 저장(Task 4, 7), DB 저장(Task 2, 7), 엑셀 자동작성(Task 5, 7), 주요자재 PDF(Task 6, 7), 검색/수정(Task 11) — 스펙의 MVP 기능 전부가 태스크로 매핑됨. 로그인/발주서대조/체크리스트/대시보드/오프라인/전자결재는 설계 문서대로 범위 밖으로 명시적으로 제외.
- **플레이스홀더 스캔**: "TBD"/"나중에" 등 표현 없음. 모든 스텝에 실제 코드/명령어 포함.
- **타입/시그니처 일관성**: 표준 필드명(`material_type` 등)이 `schemas.py`(Task 2) → `ocr.py`(Task 3) → `excel.py`/`pdf.py`(Task 5, 6) → 라우터(Task 7) → 프론트 `FIELD_DEFS`(Task 10, 11)까지 동일하게 사용됨을 확인.
