# 철근 택 촬영·대조 기능 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 송장 촬영 직후 이어지는 편집 화면에서 레코드(규격)별로 철근다발 택 사진을 촬영해 현장명/부재시공위치/직경/강도/길이/수량/가공형상을 인식하고, 직경+강도를 송장 규격과 대조해 불일치 시 경고를 보여준다. 저장은 불일치와 무관하게 항상 허용한다.

**Architecture:** 백엔드에 규격 문자열(`SHD13` 등)에서 강도(SD500/SD600)+직경을 파싱하고 택 정보와 대조하는 순수 함수 모듈(`spec_grade.py`)을 추가한다. `Invoice` 모델에 택 관련 컬럼을 추가하고, `Base.metadata.create_all`이 새 컬럼까지 만들어주지 않는 기존 테이블(운영 Postgres)을 위해 idempotent한 `ALTER TABLE` 마이그레이션 헬퍼를 앱 시작 시 실행한다. 새 `POST /ocr/tag` 엔드포인트가 택 사진을 OCR해 필드를 파싱하고, `spec`이 함께 오면 대조 결과까지 반환한다. `POST /invoices`/`PUT /invoices/{id}`가 택 필드·사진을 저장하고 `tag_match_status`를 서버에서 계산한다. 프론트엔드는 `EditPage.jsx`의 레코드 카드마다 "택 촬영" 버튼을 추가해 즉시 대조 결과를 보여주고, `DetailPage.jsx`는 저장된 택 정보를 표시한다.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React

## Global Constraints

- 자동 대조 판정은 직경+강도만 사용한다 — 현장명/부재시공위치/길이/수량/가공형상은 참고용으로만 저장·표시한다.
- 대조 결과가 `mismatched`여도 저장은 항상 허용한다 — 저장을 막지 않는다.
- 규격 접두어→강도 매핑은 `SHD→SD500`, `UHD→SD600`만 다루고, 그 외 접두어는 판정 없이 건너뛴다(딕셔너리 확장으로 향후 추가 가능한 구조).
- 레코드(규격)마다 택 사진 1장이 대응한다.
- 기존 테이블(운영 Postgres 포함)에 컬럼을 안전하게 추가할 수 있어야 한다 — `Base.metadata.create_all`만으로는 기존 테이블에 컬럼이 추가되지 않으므로 별도 마이그레이션이 필요하다.

---

### Task 1: `spec_grade.py` — 규격 강도/직경 파싱 및 대조 로직

**Files:**
- Create: `backend/app/spec_grade.py`
- Test: `backend/tests/test_spec_grade.py`

**Interfaces:**
- Produces: `parse_spec_grade_diameter(spec: str) -> tuple[str | None, str | None]`, `match_tag_to_spec(tag_grade: str | None, tag_diameter: str | None, spec: str) -> str | None` (`"matched"` / `"mismatched"` / `None`).이후 모든 태스크가 이 두 함수를 사용한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_spec_grade.py`:

```python
from app.spec_grade import match_tag_to_spec, parse_spec_grade_diameter


def test_parse_spec_grade_diameter_shd_is_sd500():
    assert parse_spec_grade_diameter("SHD13") == ("SD500", "13")


def test_parse_spec_grade_diameter_uhd_is_sd600():
    assert parse_spec_grade_diameter("UHD16") == ("SD600", "16")


def test_parse_spec_grade_diameter_unknown_prefix_returns_none():
    assert parse_spec_grade_diameter("HD13") == (None, None)


def test_parse_spec_grade_diameter_empty_spec_returns_none():
    assert parse_spec_grade_diameter("") == (None, None)


def test_match_tag_to_spec_matched():
    assert match_tag_to_spec("SD500", "13", "SHD13") == "matched"


def test_match_tag_to_spec_mismatched_diameter():
    assert match_tag_to_spec("SD500", "10", "SHD13") == "mismatched"


def test_match_tag_to_spec_mismatched_grade():
    assert match_tag_to_spec("SD600", "13", "SHD13") == "mismatched"


def test_match_tag_to_spec_missing_tag_info_returns_none():
    assert match_tag_to_spec(None, None, "SHD13") is None


def test_match_tag_to_spec_unsupported_spec_prefix_returns_none():
    assert match_tag_to_spec("SD400", "13", "HD13") is None


def test_match_tag_to_spec_diameter_with_unit_suffix_normalizes():
    assert match_tag_to_spec("SD500", "13mm", "SHD13") == "matched"


def test_match_tag_to_spec_grade_case_insensitive():
    assert match_tag_to_spec("sd500", "13", "SHD13") == "matched"
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_spec_grade.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.spec_grade'`

- [ ] **Step 3: 최소 구현 작성**

`backend/app/spec_grade.py`:

```python
import re

GRADE_BY_PREFIX = {
    "SHD": "SD500",
    "UHD": "SD600",
}


def parse_spec_grade_diameter(spec: str) -> tuple[str | None, str | None]:
    if not spec:
        return None, None
    spec_upper = spec.strip().upper()
    for prefix, grade in GRADE_BY_PREFIX.items():
        if spec_upper.startswith(prefix):
            diameter = re.sub(r"[^0-9]", "", spec_upper[len(prefix):])
            return grade, diameter or None
    return None, None


def _normalize_diameter(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"[^0-9]", "", value)
    return digits or None


def _normalize_grade(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().upper()


def match_tag_to_spec(tag_grade: str | None, tag_diameter: str | None, spec: str) -> str | None:
    spec_grade, spec_diameter = parse_spec_grade_diameter(spec)
    norm_tag_grade = _normalize_grade(tag_grade)
    norm_tag_diameter = _normalize_diameter(tag_diameter)
    if spec_grade is None or norm_tag_grade is None or norm_tag_diameter is None:
        return None
    if spec_grade == norm_tag_grade and spec_diameter == norm_tag_diameter:
        return "matched"
    return "mismatched"
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_spec_grade.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/spec_grade.py backend/tests/test_spec_grade.py
git commit -m "feat: 규격 문자열에서 철근 강도/직경 파싱 및 택 대조 로직 추가"
```

---

### Task 2: DB 스키마 확장 — Invoice 택 컬럼 + 마이그레이션 헬퍼

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/app/migrations.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_migrations.py`

**Interfaces:**
- Consumes: 없음
- Produces: `models.Invoice`에 `tag_photo_path`, `tag_site_name`, `tag_location`, `tag_diameter`, `tag_grade`, `tag_length`, `tag_quantity`, `tag_shape`, `tag_match_status` 컬럼(모두 `String, nullable=True`). `schemas.InvoiceBase`에 `tag_site_name`~`tag_shape`(`Optional[str] = None`) 추가, `schemas.InvoiceOut`에 `tag_photo_path`, `tag_match_status`(`Optional[str] = None`) 추가. `migrations.run_migrations(engine) -> None`, `migrations.TAG_COLUMNS: dict[str, str]`.

- [ ] **Step 1: 실패하는 마이그레이션 테스트 작성**

`backend/tests/test_migrations.py`:

```python
from sqlalchemy import create_engine, inspect, text

from app.migrations import TAG_COLUMNS, run_migrations


def _make_legacy_engine(tmp_path):
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE invoices (id INTEGER PRIMARY KEY, material_type VARCHAR)"))
    return engine


def test_run_migrations_adds_missing_tag_columns(tmp_path):
    engine = _make_legacy_engine(tmp_path)
    run_migrations(engine)
    columns = {c["name"] for c in inspect(engine).get_columns("invoices")}
    for column in TAG_COLUMNS:
        assert column in columns


def test_run_migrations_is_idempotent(tmp_path):
    engine = _make_legacy_engine(tmp_path)
    run_migrations(engine)
    run_migrations(engine)  # 두 번째 실행에서 에러가 나면 안 됨
    columns = {c["name"] for c in inspect(engine).get_columns("invoices")}
    for column in TAG_COLUMNS:
        assert column in columns


def test_run_migrations_skips_table_that_does_not_exist_yet(tmp_path):
    db_path = tmp_path / "empty.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine)  # invoices 테이블이 아예 없어도 에러 없이 통과해야 함
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_migrations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.migrations'`

- [ ] **Step 3: 모델·스키마·마이그레이션 구현**

`backend/app/models.py`의 `Invoice` 클래스에 `photo_path = Column(...)` 줄 바로 아래 추가:

```python
    tag_photo_path = Column(String, nullable=True)
    tag_site_name = Column(String, nullable=True)
    tag_location = Column(String, nullable=True)
    tag_diameter = Column(String, nullable=True)
    tag_grade = Column(String, nullable=True)
    tag_length = Column(String, nullable=True)
    tag_quantity = Column(String, nullable=True)
    tag_shape = Column(String, nullable=True)
    tag_match_status = Column(String, nullable=True)
```

`backend/app/schemas.py`의 `InvoiceBase`에 `note: Optional[str] = None` 줄 바로 아래 추가:

```python
    tag_site_name: Optional[str] = None
    tag_location: Optional[str] = None
    tag_diameter: Optional[str] = None
    tag_grade: Optional[str] = None
    tag_length: Optional[str] = None
    tag_quantity: Optional[str] = None
    tag_shape: Optional[str] = None
```

`InvoiceOut`에 `photo_path: Optional[str] = None` 줄 바로 아래 추가:

```python
    tag_photo_path: Optional[str] = None
    tag_match_status: Optional[str] = None
```

`backend/app/migrations.py` (신규):

```python
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

TAG_COLUMNS = {
    "tag_photo_path": "VARCHAR",
    "tag_site_name": "VARCHAR",
    "tag_location": "VARCHAR",
    "tag_diameter": "VARCHAR",
    "tag_grade": "VARCHAR",
    "tag_length": "VARCHAR",
    "tag_quantity": "VARCHAR",
    "tag_shape": "VARCHAR",
    "tag_match_status": "VARCHAR",
}


def run_migrations(engine: Engine) -> None:
    inspector = inspect(engine)
    if "invoices" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("invoices")}
    missing = {name: col_type for name, col_type in TAG_COLUMNS.items() if name not in existing_columns}
    if not missing:
        return
    with engine.begin() as conn:
        for column, col_type in missing.items():
            conn.execute(text(f"ALTER TABLE invoices ADD COLUMN {column} {col_type}"))
```

`backend/app/main.py`에서 `Base.metadata.create_all(bind=engine)` 바로 아래에 추가:

```python
from . import migrations
...
Base.metadata.create_all(bind=engine)
migrations.run_migrations(engine)
```

(기존 `from .database import Base, engine` 임포트 줄 아래에 `from . import migrations`를 추가한다.)

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_migrations.py -v`
Expected: PASS (3 passed)

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 기존 테스트 전부 통과 (conftest.py가 매 테스트마다 `Base.metadata.create_all`로 새 컬럼까지 포함된 테이블을 만들기 때문에 회귀 없음)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/models.py backend/app/schemas.py backend/app/migrations.py backend/app/main.py backend/tests/test_migrations.py
git commit -m "feat: Invoice에 택 정보 컬럼 추가 및 기존 테이블용 마이그레이션 헬퍼 도입"
```

---

### Task 3: 택 OCR 필드 파싱 + `/ocr/tag` 엔드포인트

**Files:**
- Modify: `backend/app/ocr.py`
- Modify: `backend/app/routers/ocr.py`
- Test: `backend/tests/test_ocr.py`
- Test: `backend/tests/test_ocr_endpoint.py`

**Interfaces:**
- Consumes: `spec_grade.match_tag_to_spec` (Task 1), `ocr.call_upstage_ocr`/`ocr.extract_text` (기존)
- Produces: `ocr.TAG_FIELD_LABELS`, `ocr.TAG_FIELDS`, `ocr.normalize_tag_fields(raw_text: str) -> dict`. `POST /ocr/tag` — `file`(필수), `spec`(선택, 폼 필드) → `{tag_site_name, tag_location, tag_diameter, tag_grade, tag_length, tag_quantity, tag_shape, tag_match_status}` JSON.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_ocr.py` 끝에 추가:

```python
def test_normalize_tag_fields_extracts_labeled_values():
    text = (
        "현장명: 서소문 재개발\n"
        "부재시공위치: 지하 2층 슬라브\n"
        "직경: 13\n"
        "강도: SD500\n"
        "길이: 12000\n"
        "수량: 50\n"
        "가공형상: 직선\n"
    )
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_site_name"] == "서소문 재개발"
    assert fields["tag_location"] == "지하 2층 슬라브"
    assert fields["tag_diameter"] == "13"
    assert fields["tag_grade"] == "SD500"
    assert fields["tag_length"] == "12000"
    assert fields["tag_quantity"] == "50"
    assert fields["tag_shape"] == "직선"


def test_normalize_tag_fields_missing_label_returns_empty_strings():
    fields = ocr.normalize_tag_fields("아무 관련 없는 텍스트")
    for field in ocr.TAG_FIELDS:
        assert fields[field] == ""
```

`backend/tests/test_ocr_endpoint.py` 끝에 추가:

```python
def test_tag_ocr_endpoint_returns_parsed_fields_and_match_status(monkeypatch):
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_ocr",
        lambda image_bytes, filename="x": {"text": "직경: 13\n강도: SD500\n"},
    )
    response = client.post(
        "/ocr/tag",
        data={"spec": "SHD13"},
        files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tag_diameter"] == "13"
    assert body["tag_grade"] == "SD500"
    assert body["tag_match_status"] == "matched"


def test_tag_ocr_endpoint_without_spec_skips_match_status(monkeypatch):
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_ocr",
        lambda image_bytes, filename="x": {"text": "직경: 13\n강도: SD500\n"},
    )
    response = client.post("/ocr/tag", files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")})
    assert response.status_code == 200
    assert response.json()["tag_match_status"] is None


def test_tag_ocr_endpoint_returns_blank_fields_on_ocr_failure(monkeypatch):
    def raise_error(*args, **kwargs):
        raise RuntimeError("network error")

    monkeypatch.setattr(ocr_module, "call_upstage_ocr", raise_error)
    response = client.post("/ocr/tag", files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")})
    assert response.status_code == 200
    body = response.json()
    for field in ocr_module.TAG_FIELDS:
        assert body[field] == ""
    assert body["tag_match_status"] is None
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_ocr.py tests/test_ocr_endpoint.py -v`
Expected: FAIL — `normalize_tag_fields` 없음(`AttributeError`), `/ocr/tag`는 404

- [ ] **Step 3: 구현**

`backend/app/ocr.py`의 `STANDARD_FIELDS = list(FIELD_LABELS.keys())` 줄 바로 아래에 추가:

```python
TAG_FIELD_LABELS = {
    "tag_site_name": ["현장명", "현장"],
    "tag_location": ["부재시공위치", "시공위치", "위치"],
    "tag_diameter": ["직경", "호칭경"],
    "tag_grade": ["강도", "강종"],
    "tag_length": ["길이"],
    "tag_quantity": ["수량"],
    "tag_shape": ["가공형상", "형상"],
}

TAG_FIELDS = list(TAG_FIELD_LABELS.keys())


def normalize_tag_fields(raw_text: str) -> dict:
    result = {field: "" for field in TAG_FIELDS}
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    for line in lines:
        for field, labels in TAG_FIELD_LABELS.items():
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

`backend/app/routers/ocr.py` 전체를 다음으로 교체:

```python
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile

from .. import ocr, report_parser, spec_grade
from ..auth import verify_password

router = APIRouter(dependencies=[Depends(verify_password)])


@router.post("/ocr")
async def run_ocr(file: UploadFile = File(...)):
    image_bytes = await file.read()
    try:
        raw_response = ocr.call_upstage_ocr(image_bytes, filename=file.filename or "invoice.jpg")
    except Exception:
        return {"records": [{field: "" for field in ocr.STANDARD_FIELDS}]}

    if report_parser.find_cover_pages(raw_response):
        records = report_parser.build_capture_records(raw_response)
        if records:
            return {"records": records}

    text = ocr.extract_text(raw_response)
    return {"records": [ocr.normalize_fields(text)]}


@router.post("/ocr/tag")
async def run_tag_ocr(file: UploadFile = File(...), spec: Optional[str] = Form(None)):
    image_bytes = await file.read()
    try:
        raw_response = ocr.call_upstage_ocr(image_bytes, filename=file.filename or "tag.jpg")
    except Exception:
        return {**{field: "" for field in ocr.TAG_FIELDS}, "tag_match_status": None}

    text = ocr.extract_text(raw_response)
    fields = ocr.normalize_tag_fields(text)
    tag_match_status = None
    if spec:
        tag_match_status = spec_grade.match_tag_to_spec(
            fields["tag_grade"] or None, fields["tag_diameter"] or None, spec
        )
    return {**fields, "tag_match_status": tag_match_status}
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_ocr.py tests/test_ocr_endpoint.py -v`
Expected: PASS (전부 통과)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/ocr.py backend/app/routers/ocr.py backend/tests/test_ocr.py backend/tests/test_ocr_endpoint.py
git commit -m "feat: 택 사진 OCR 필드 파싱 및 /ocr/tag 엔드포인트 추가"
```

---

### Task 4: 송장 생성/수정이 택 필드·사진·대조 결과를 저장하도록 확장

**Files:**
- Modify: `backend/app/crud.py`
- Modify: `backend/app/routers/invoices.py`
- Test: `backend/tests/test_crud.py`
- Test: `backend/tests/test_invoices_api.py`

**Interfaces:**
- Consumes: `spec_grade.match_tag_to_spec` (Task 1), `photos.save_photo` (기존)
- Produces: `crud.create_invoice(db, data, photo_path=None, tag_photo_path=None)` — 생성 시 `tag_match_status`를 자동 계산해 저장. `crud.update_invoice(db, invoice_id, data)` — 수정 시 `tag_match_status`를 재계산. `POST /invoices`가 `tag_site_name`~`tag_shape`(폼 필드)와 `tag_photo`(파일) 파라미터를 받는다.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_crud.py`의 `make_invoice_data` 아래에 추가:

```python
def test_create_invoice_computes_matched_tag_status(db_session):
    created = crud.create_invoice(
        db_session,
        make_invoice_data(spec="SHD13", tag_grade="SD500", tag_diameter="13"),
        tag_photo_path="photos/tag1.jpg",
    )
    assert created.tag_match_status == "matched"
    assert created.tag_photo_path == "photos/tag1.jpg"


def test_create_invoice_computes_mismatched_tag_status(db_session):
    created = crud.create_invoice(
        db_session, make_invoice_data(spec="SHD13", tag_grade="SD600", tag_diameter="13")
    )
    assert created.tag_match_status == "mismatched"


def test_create_invoice_without_tag_info_leaves_status_none(db_session):
    created = crud.create_invoice(db_session, make_invoice_data(spec="SHD13"))
    assert created.tag_match_status is None


def test_update_invoice_recomputes_tag_match_status(db_session):
    created = crud.create_invoice(db_session, make_invoice_data(spec="SHD13"))
    update_data = schemas.InvoiceUpdate(
        **{**make_invoice_data(spec="SHD13").model_dump(), "tag_grade": "SD500", "tag_diameter": "13"}
    )
    updated = crud.update_invoice(db_session, created.id, update_data)
    assert updated.tag_match_status == "matched"
```

`backend/tests/test_invoices_api.py`에 추가:

```python
def test_create_invoice_with_tag_fields_and_photo_computes_match_status(monkeypatch):
    monkeypatch.setattr(excel_module, "append_invoice", lambda invoice: None)
    monkeypatch.setattr(pdf_module, "generate_pdf", lambda invoice: "pdf/x.pdf")

    response = client.post(
        "/invoices",
        data={
            "material_type": "철근",
            "spec": "SHD13",
            "tag_grade": "SD500",
            "tag_diameter": "13",
            "tag_site_name": "서소문 재개발",
        },
        files={"tag_photo": ("tag.jpg", io.BytesIO(b"fake-tag"), "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tag_match_status"] == "matched"
    assert body["tag_photo_path"] is not None
    assert body["tag_site_name"] == "서소문 재개발"
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_crud.py tests/test_invoices_api.py -v`
Expected: FAIL — `create_invoice()`가 `tag_photo_path` 키워드 인자를 모르거나, `tag_match_status`가 항상 `None`, `/invoices`가 `tag_photo`/`tag_grade` 등을 무시

- [ ] **Step 3: 구현**

`backend/app/crud.py` 맨 위 임포트에 `spec_grade` 추가:

```python
from . import models, schemas, spec_grade
```

`create_invoice`를 다음으로 교체:

```python
def create_invoice(
    db: Session,
    data: schemas.InvoiceCreate,
    photo_path: Optional[str] = None,
    tag_photo_path: Optional[str] = None,
) -> models.Invoice:
    invoice = models.Invoice(
        **data.model_dump(),
        photo_path=photo_path,
        tag_photo_path=tag_photo_path,
        tag_match_status=spec_grade.match_tag_to_spec(data.tag_grade, data.tag_diameter, data.spec or ""),
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice
```

`update_invoice`를 다음으로 교체:

```python
def update_invoice(db: Session, invoice_id: int, data: schemas.InvoiceUpdate) -> Optional[models.Invoice]:
    invoice = get_invoice(db, invoice_id)
    if invoice is None:
        return None
    for key, value in data.model_dump().items():
        setattr(invoice, key, value)
    invoice.tag_match_status = spec_grade.match_tag_to_spec(invoice.tag_grade, invoice.tag_diameter, invoice.spec or "")
    db.commit()
    db.refresh(invoice)
    return invoice
```

`backend/app/routers/invoices.py`의 `create_invoice` 함수 시그니처에 `note: Optional[str] = Form(None),` 줄 바로 아래 추가:

```python
    tag_site_name: Optional[str] = Form(None),
    tag_location: Optional[str] = Form(None),
    tag_diameter: Optional[str] = Form(None),
    tag_grade: Optional[str] = Form(None),
    tag_length: Optional[str] = Form(None),
    tag_quantity: Optional[str] = Form(None),
    tag_shape: Optional[str] = Form(None),
```

`photo: Optional[UploadFile] = File(None),` 줄 바로 아래 추가:

```python
    tag_photo: Optional[UploadFile] = File(None),
```

`schemas.InvoiceCreate(...)` 생성자 호출의 `note=note,` 줄 바로 아래 추가:

```python
        tag_site_name=tag_site_name,
        tag_location=tag_location,
        tag_diameter=tag_diameter,
        tag_grade=tag_grade,
        tag_length=tag_length,
        tag_quantity=tag_quantity,
        tag_shape=tag_shape,
```

기존 `if photo is not None:` 블록 바로 아래에 동일한 패턴으로 추가:

```python
    if tag_photo is not None:
        try:
            tag_image_bytes = await tag_photo.read()
            tag_photo_path = photos.save_photo(tag_image_bytes, tag_photo.filename or "tag.jpg")
            invoice.tag_photo_path = tag_photo_path
            db.commit()
            db.refresh(invoice)
        except Exception:
            logger.exception("택 사진 저장 실패")
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 전부 통과

- [ ] **Step 5: 커밋**

```bash
git add backend/app/crud.py backend/app/routers/invoices.py backend/tests/test_crud.py backend/tests/test_invoices_api.py
git commit -m "feat: 송장 생성/수정 시 택 필드·사진 저장 및 대조 결과 계산"
```

---

### Task 5: 프론트엔드 — `api.js` + `EditPage.jsx` 레코드별 택 촬영

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/pages/EditPage.jsx`

**Interfaces:**
- Consumes: `POST /ocr/tag` (Task 3), `POST /invoices`의 `tag_*`/`tag_photo` 필드 (Task 4)
- Produces: `api.js`의 `runTagOcr(file, spec)`, `createInvoice(fields, photoFile, tagPhotoFile)`(세 번째 인자 추가)

- [ ] **Step 1: `api.js`에 택 OCR 호출 및 사진 전송 추가**

`frontend/src/api.js`의 `runOcr` 함수 바로 아래에 추가:

```javascript
export async function runTagOcr(imageFile, spec) {
  const formData = new FormData()
  formData.append('file', imageFile)
  if (spec) formData.append('spec', spec)
  const response = await fetch(`${API_BASE}/ocr/tag`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('택 인식 요청 실패')
  return response.json()
}
```

`createInvoice` 함수를 다음으로 교체:

```javascript
export async function createInvoice(fields, photoFile, tagPhotoFile) {
  const formData = new FormData()
  Object.entries(fields).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      formData.append(key, value)
    }
  })
  if (photoFile) formData.append('photo', photoFile)
  if (tagPhotoFile) formData.append('tag_photo', tagPhotoFile)
  const response = await fetch(`${API_BASE}/invoices`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('저장 실패')
  return response.json()
}
```

- [ ] **Step 2: `EditPage.jsx`에 레코드별 택 촬영 UI 추가**

`frontend/src/pages/EditPage.jsx` 전체를 다음으로 교체:

```jsx
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { createInvoice, runTagOcr } from '../api.js'

const COMMON_FIELD_DEFS = [
  ['vendor', '거래처'],
  ['delivery_date', '납품일'],
  ['vehicle_no', '차량번호'],
  ['invoice_no', '송장번호'],
]

const ITEM_FIELD_DEFS = [
  ['material_type', '자재종류'],
  ['item_name', '품명'],
  ['spec', '규격'],
  ['unit', '단위'],
  ['quantity', '수량'],
  ['weight', '중량'],
  ['note', '비고'],
]

const TAG_FIELD_KEYS = [
  'tag_site_name',
  'tag_location',
  'tag_diameter',
  'tag_grade',
  'tag_length',
  'tag_quantity',
  'tag_shape',
]

function makeItem(record) {
  return {
    material_type: record.material_type || '',
    item_name: record.item_name || '',
    spec: record.spec || '',
    unit: record.unit || '',
    quantity: record.quantity ?? '',
    weight: record.weight ?? '',
    note: record.note || '',
    tag_site_name: '',
    tag_location: '',
    tag_diameter: '',
    tag_grade: '',
    tag_length: '',
    tag_quantity: '',
    tag_shape: '',
    tag_match_status: null,
    tagPhotoFile: null,
  }
}

export default function EditPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const initialRecords = location.state?.records?.length ? location.state.records : [{}]
  const photoFile = location.state?.photoFile || null

  const [common, setCommon] = useState(() => ({
    vendor: initialRecords[0]?.vendor || '',
    delivery_date: initialRecords[0]?.delivery_date || '',
    vehicle_no: initialRecords[0]?.vehicle_no || '',
    invoice_no: initialRecords[0]?.invoice_no || '',
  }))
  const [items, setItems] = useState(() => initialRecords.map(makeItem))
  const [saving, setSaving] = useState(false)
  const [tagLoadingIndex, setTagLoadingIndex] = useState(null)

  function handleCommonChange(key, value) {
    setCommon((prev) => ({ ...prev, [key]: value }))
  }

  function handleItemChange(index, key, value) {
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, [key]: value } : item)))
  }

  function handleRemoveItem(index) {
    setItems((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleTagPhotoChange(index, event) {
    const file = event.target.files[0]
    if (!file) return
    setTagLoadingIndex(index)
    try {
      const result = await runTagOcr(file, items[index].spec)
      setItems((prev) =>
        prev.map((item, i) =>
          i === index
            ? {
                ...item,
                tag_site_name: result.tag_site_name || '',
                tag_location: result.tag_location || '',
                tag_diameter: result.tag_diameter || '',
                tag_grade: result.tag_grade || '',
                tag_length: result.tag_length || '',
                tag_quantity: result.tag_quantity || '',
                tag_shape: result.tag_shape || '',
                tag_match_status: result.tag_match_status,
                tagPhotoFile: file,
              }
            : item,
        ),
      )
    } catch (err) {
      alert('택 인식에 실패했습니다.')
    } finally {
      setTagLoadingIndex(null)
    }
  }

  async function handleSave() {
    setSaving(true)
    let saved = 0
    try {
      for (const item of items) {
        const { tagPhotoFile, tag_match_status, ...fields } = item
        await createInvoice({ ...common, ...fields }, photoFile, tagPhotoFile)
        saved += 1
      }
      navigate('/search')
    } catch (err) {
      setItems((prev) => prev.slice(saved))
      alert(`${saved}건 저장 후 실패했습니다. 남은 ${items.length - saved}건을 다시 시도해주세요.`)
    } finally {
      setSaving(false)
    }
  }

  const canSave = items.length > 0 && items.every((item) => item.material_type)

  return (
    <div className="page">
      <h1>내용 확인 및 수정</h1>
      <div className="card">
        <p className="field-group-label">공통 정보</p>
        {COMMON_FIELD_DEFS.map(([key, label]) => (
          <div key={key} className="field">
            <label>{label}</label>
            <input
              className="input"
              type="text"
              value={common[key] || ''}
              onChange={(e) => handleCommonChange(key, e.target.value)}
            />
          </div>
        ))}
      </div>
      {items.map((item, index) => (
        <div key={index} className="card item-card">
          <div className="item-card-header">
            <p className="field-group-label">자재 {index + 1}</p>
            {items.length > 1 && (
              <button
                type="button"
                className="item-remove"
                onClick={() => handleRemoveItem(index)}
                aria-label={`자재 ${index + 1} 삭제`}
              >
                ×
              </button>
            )}
          </div>
          {ITEM_FIELD_DEFS.map(([key, label]) => (
            <div key={key} className="field">
              <label>{label}</label>
              <input
                className="input"
                type="text"
                value={item[key] ?? ''}
                onChange={(e) => handleItemChange(index, key, e.target.value)}
              />
            </div>
          ))}
          <div className="field">
            <label>택 촬영</label>
            <label className="btn btn-secondary photo-picker-add">
              {tagLoadingIndex === index ? '인식 중...' : item.tagPhotoFile ? '택 다시 촬영' : '📷 택 촬영'}
              <input
                className="photo-picker-input"
                type="file"
                accept="image/*"
                capture="environment"
                onChange={(e) => handleTagPhotoChange(index, e)}
              />
            </label>
          </div>
          {item.tag_match_status === 'mismatched' && (
            <p className="banner banner-warning">
              택 규격({item.tag_grade} D{item.tag_diameter})이 송장 규격({item.spec})과 다릅니다
            </p>
          )}
        </div>
      ))}
      <button className="btn btn-primary" onClick={handleSave} disabled={saving || !canSave} style={{ width: '100%' }}>
        {saving ? '저장 중...' : `저장 (${items.length}건)`}
      </button>
    </div>
  )
}
```

(`TAG_FIELD_KEYS`는 이 파일에서 직접 참조하지 않지만, 다음 태스크나 리뷰에서 필드 목록을 한눈에 보기 위해 남겨둔다. 사용하지 않는 경고가 린트에서 발생하면 제거해도 무방하다.)

- [ ] **Step 3: 빌드로 문법 오류 확인**

Run: `cd frontend && npm run build`
Expected: 빌드 성공, 에러 없음

- [ ] **Step 4: 브라우저 프리뷰로 동작 확인**

로컬 백엔드(`uvicorn app.main:app --port 8000`)와 `npm run dev`를 띄운 뒤:
1. 촬영 화면에서 아무 이미지나 촬영/업로드해 편집 화면으로 이동.
2. 자재 카드에서 "📷 택 촬영" 버튼으로 사진을 선택.
3. 인식 결과가 반영되고, 규격을 일부러 다르게 바꿔 "택 규격이 송장 규격과 다릅니다" 경고 배너가 뜨는지 확인.
4. 저장 버튼을 눌러 정상 저장되는지 확인(불일치 상태에서도 저장 가능해야 함).

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/api.js frontend/src/pages/EditPage.jsx
git commit -m "feat: 편집 화면에 레코드별 택 촬영 및 규격 불일치 경고 추가"
```

---

### Task 6: 프론트엔드 — `DetailPage.jsx` 택 정보 표시

**Files:**
- Modify: `frontend/src/pages/DetailPage.jsx`

**Interfaces:**
- Consumes: `GET /invoices/{id}` 응답의 `tag_photo_path`, `tag_site_name`~`tag_shape`, `tag_match_status` (Task 2, 4에서 이미 반환됨)

- [ ] **Step 1: 상세 화면에 택 정보 섹션 추가**

`frontend/src/pages/DetailPage.jsx`의 `FIELD_DEFS` 배열 바로 아래에 추가:

```jsx
const TAG_FIELD_DEFS = [
  ['tag_site_name', '택 현장명'],
  ['tag_location', '택 부재시공위치'],
  ['tag_diameter', '택 직경'],
  ['tag_grade', '택 강도'],
  ['tag_length', '택 길이'],
  ['tag_quantity', '택 수량'],
  ['tag_shape', '택 가공형상'],
]

function tagMatchLabel(status) {
  if (status === 'matched') return '일치'
  if (status === 'mismatched') return '불일치'
  return '택 미촬영'
}
```

기존 `{invoice.photo_path && (...)}` 블록 바로 아래에 추가:

```jsx
        {invoice.tag_photo_path && (
          <img className="photo-preview" src={`/storage/${invoice.tag_photo_path}`} alt="택 사진" />
        )}
        <p className="field-group-label">
          택 대조 결과: {tagMatchLabel(invoice.tag_match_status)}
        </p>
        {invoice.tag_match_status === 'mismatched' && (
          <p className="banner banner-warning">
            택 규격({invoice.tag_grade} D{invoice.tag_diameter})이 송장 규격({invoice.spec})과 다릅니다
          </p>
        )}
        {TAG_FIELD_DEFS.map(([key, label]) => (
          <div key={key} className="field">
            <label>{label}</label>
            <input className="input" type="text" value={invoice[key] || ''} readOnly disabled />
          </div>
        ))}
```

(이 섹션은 `FIELD_DEFS.map(...)`로 만드는 기존 편집 가능 필드 목록보다 위, `photo_path` 이미지 블록 바로 다음에 위치시킨다. 택 필드는 읽기 전용으로만 표시한다 — 이번 범위에서는 상세 화면에서 택 정보를 직접 수정하지 않는다.)

- [ ] **Step 2: 빌드로 문법 오류 확인**

Run: `cd frontend && npm run build`
Expected: 빌드 성공, 에러 없음

- [ ] **Step 3: 브라우저 프리뷰로 동작 확인**

1. Task 5에서 택을 촬영해 저장한 레코드를 검색 화면에서 열어 상세 화면으로 이동.
2. 택 사진, 택 필드, "일치"/"불일치" 배지가 올바르게 표시되는지 확인.
3. 택을 촬영하지 않고 저장한 기존 레코드를 열어 "택 미촬영"으로 표시되는지 확인.

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/pages/DetailPage.jsx
git commit -m "feat: 상세 화면에 택 사진·정보·대조 결과 표시"
```
