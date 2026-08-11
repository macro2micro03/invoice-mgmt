# 누적 수불부 관리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 수불부를 "매번 새로 만드는 파일"이 아니라 "계속 쌓이는 하나의 장부"로 관리한다. 송장에서 자동으로 오는 값(반입일/규격/반입량)은 매번 최신 상태로 다시 채우고, 수불부에만 있는 수동 항목(불합격량/사유/반출일/반출량/잔량/검수자/담당감리원)은 `/ledger` 화면에서 입력·수정하며 DB에 영구 저장한다.

**Architecture:** 새 테이블 `LedgerEntry`(송장 1건 = 수불부 1행, `invoice_id`에 unique 제약으로 "포함 여부"를 겸함)를 추가한다. 다운로드할 때마다 현재 존재하는 모든 `LedgerEntry`를 연결된 `Invoice`의 반입일 순으로 정렬해 템플릿에 처음부터 다시 채운다. `/ledger` 화면은 이 테이블의 CRUD를 그대로 노출하는 표 형태다.

**Tech Stack:** 기존 스택 그대로 (FastAPI, SQLAlchemy, openpyxl, React)

## Global Constraints

- 자동 채움 컬럼(연번/반입일/규격/반입량)은 항상 `Invoice`에서 가져오고 사용자가 수정할 수 없다(엑셀 파일이 아니라 앱에서 편집).
- 수동 컬럼(불합격량/사유/반출일/반출량/잔량/검수자/담당감리원)은 `LedgerEntry`에 저장하고 `/ledger` 화면 표에서 편집한다.
- `LedgerEntry`를 삭제해도 `Invoice`는 삭제되지 않는다.
- 커플러(`item_name == "커플러"`)·비철근(`material_type != "철근"`)은 여전히 `LedgerEntry` 생성 대상에서 제외한다.

---

### Task 1: `LedgerEntry` 모델 + CRUD 함수

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/crud.py`
- Test: `backend/tests/test_ledger_crud.py` (신규)

**Interfaces:**
- Produces:
  - `models.LedgerEntry` — 필드: `id`, `invoice_id`(FK, unique), `defect_qty: float|None`, `defect_reason: str|None`, `release_date: date|None`, `release_qty: float|None`, `remaining_qty: float|None`, `inspector: str|None`, `supervisor: str|None`, `invoice`(relationship)
  - `crud.create_ledger_entries(db, invoice_ids: list[int], inspector: str, supervisor: str) -> tuple[list[models.LedgerEntry], int]` — 반환값은 `(새로_생성된_엔트리_목록, 건너뛴_건수)`. 건너뛴 건수는 "커플러/비철근이라 제외" + "이미 LedgerEntry가 있어서 건너뜀"을 합친 값이 아니라, 이 함수는 **이미 존재/커플러/비철근을 모두 걸러내고 신규만 생성**하며 몇 건을 걸렀는지를 반환한다.
  - `crud.list_ledger_entries(db) -> list[models.LedgerEntry]` — `Invoice.delivery_date` 오름차순 정렬 (join)
  - `crud.update_ledger_entry(db, invoice_id: int, fields: dict) -> models.LedgerEntry | None` — 존재하지 않으면 `None`
  - `crud.delete_ledger_entry(db, invoice_id: int) -> bool` — 존재하지 않아도 `True`(멱등)는 아니고, 실제 삭제 여부를 반환(라우터에서 존재 여부와 무관하게 204를 주도록 처리)

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_ledger_crud.py`:

```python
from datetime import date

from app import crud, schemas


def _make_invoice(db_session, spec="SHD10", weight=1.0, delivery_date=date(2026, 4, 20), item_name="철근", material_type="철근"):
    data = schemas.InvoiceCreate(
        material_type=material_type,
        vendor="테스트업체",
        delivery_date=delivery_date,
        item_name=item_name,
        spec=spec,
        unit="Ton",
        quantity=weight,
        weight=weight,
    )
    return crud.create_invoice(db_session, data)


def test_create_ledger_entries_creates_new_entries_and_returns_skipped_count(db_session):
    rebar = _make_invoice(db_session, delivery_date=date(2026, 4, 20))
    coupler = _make_invoice(db_session, item_name="커플러", delivery_date=date(2026, 4, 21))

    entries, skipped = crud.create_ledger_entries(db_session, [rebar.id, coupler.id], "김검수", "박감리")

    assert len(entries) == 1
    assert entries[0].invoice_id == rebar.id
    assert entries[0].inspector == "김검수"
    assert entries[0].supervisor == "박감리"
    assert skipped == 1


def test_create_ledger_entries_skips_already_included_invoices(db_session):
    invoice = _make_invoice(db_session)
    crud.create_ledger_entries(db_session, [invoice.id], "김검수", "박감리")

    entries, skipped = crud.create_ledger_entries(db_session, [invoice.id], "이검수", "최감리")

    assert entries == []
    assert skipped == 1
    all_entries = crud.list_ledger_entries(db_session)
    assert len(all_entries) == 1
    assert all_entries[0].inspector == "김검수"  # 기존 값 유지, 덮어쓰지 않음


def test_list_ledger_entries_sorted_by_invoice_delivery_date(db_session):
    later = _make_invoice(db_session, spec="SHD13", delivery_date=date(2026, 5, 2))
    earlier = _make_invoice(db_session, spec="SHD10", delivery_date=date(2026, 5, 1))
    crud.create_ledger_entries(db_session, [later.id, earlier.id], "", "")

    entries = crud.list_ledger_entries(db_session)

    assert [e.invoice.spec for e in entries] == ["SHD10", "SHD13"]


def test_update_ledger_entry_sets_manual_fields(db_session):
    invoice = _make_invoice(db_session)
    crud.create_ledger_entries(db_session, [invoice.id], "", "")

    updated = crud.update_ledger_entry(
        db_session,
        invoice.id,
        {
            "defect_qty": 0.5,
            "defect_reason": "표면 손상",
            "release_date": date(2026, 5, 10),
            "release_qty": 0.3,
            "remaining_qty": 0.2,
            "inspector": "김검수",
            "supervisor": "박감리",
        },
    )

    assert updated.defect_qty == 0.5
    assert updated.defect_reason == "표면 손상"
    assert updated.release_date == date(2026, 5, 10)
    assert updated.release_qty == 0.3
    assert updated.remaining_qty == 0.2
    assert updated.inspector == "김검수"
    assert updated.supervisor == "박감리"


def test_update_ledger_entry_missing_returns_none(db_session):
    assert crud.update_ledger_entry(db_session, 999999, {"defect_qty": 1.0}) is None


def test_delete_ledger_entry_removes_entry_but_keeps_invoice(db_session):
    invoice = _make_invoice(db_session)
    crud.create_ledger_entries(db_session, [invoice.id], "", "")

    deleted = crud.delete_ledger_entry(db_session, invoice.id)

    assert deleted is True
    assert crud.list_ledger_entries(db_session) == []
    assert crud.get_invoice(db_session, invoice.id) is not None


def test_delete_ledger_entry_missing_returns_false(db_session):
    assert crud.delete_ledger_entry(db_session, 999999) is False
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_ledger_crud.py -v`
Expected: FAIL (`AttributeError: module 'app.crud' has no attribute 'create_ledger_entries'` 등)

- [ ] **Step 3: `models.py`에 `LedgerEntry` 추가**

`backend/app/models.py` 상단 import 수정 및 클래스 추가:

```python
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class Invoice(Base):
    ...  # 기존 그대로


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False, unique=True)
    defect_qty = Column(Float, nullable=True)
    defect_reason = Column(String, nullable=True)
    release_date = Column(Date, nullable=True)
    release_qty = Column(Float, nullable=True)
    remaining_qty = Column(Float, nullable=True)
    inspector = Column(String, nullable=True)
    supervisor = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    invoice = relationship("Invoice")


class ReportSequence(Base):
    ...  # 기존 그대로
```

- [ ] **Step 4: `crud.py`에 함수 추가**

`backend/app/crud.py` 맨 아래에 추가:

```python
def create_ledger_entries(
    db: Session, invoice_ids: list[int], inspector: str, supervisor: str
) -> tuple[list[models.LedgerEntry], int]:
    if not invoice_ids:
        return [], 0
    invoices = list_invoices_by_ids(db, invoice_ids)
    existing_ids = {
        row[0]
        for row in db.query(models.LedgerEntry.invoice_id)
        .filter(models.LedgerEntry.invoice_id.in_(invoice_ids))
        .all()
    }
    skipped = 0
    created: list[models.LedgerEntry] = []
    for invoice in invoices:
        if invoice.item_name == "커플러" or invoice.material_type != "철근":
            skipped += 1
            continue
        if invoice.id in existing_ids:
            skipped += 1
            continue
        entry = models.LedgerEntry(invoice_id=invoice.id, inspector=inspector, supervisor=supervisor)
        db.add(entry)
        created.append(entry)
    db.commit()
    for entry in created:
        db.refresh(entry)
    return created, skipped


def list_ledger_entries(db: Session) -> list[models.LedgerEntry]:
    return (
        db.query(models.LedgerEntry)
        .join(models.Invoice)
        .order_by(models.Invoice.delivery_date)
        .all()
    )


def update_ledger_entry(db: Session, invoice_id: int, fields: dict) -> Optional[models.LedgerEntry]:
    entry = db.query(models.LedgerEntry).filter(models.LedgerEntry.invoice_id == invoice_id).first()
    if entry is None:
        return None
    for key, value in fields.items():
        setattr(entry, key, value)
    db.commit()
    db.refresh(entry)
    return entry


def delete_ledger_entry(db: Session, invoice_id: int) -> bool:
    entry = db.query(models.LedgerEntry).filter(models.LedgerEntry.invoice_id == invoice_id).first()
    if entry is None:
        return False
    db.delete(entry)
    db.commit()
    return True
```

- [ ] **Step 5: 테스트 실행해서 통과 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_ledger_crud.py -v`
Expected: PASS (8 passed)

- [ ] **Step 6: 전체 백엔드 테스트로 회귀 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 모두 PASS (새 테이블이 `Base.metadata.create_all`로 자동 생성되므로 기존 테스트 영향 없어야 함)

- [ ] **Step 7: 커밋**

```bash
git add backend/app/models.py backend/app/crud.py backend/tests/test_ledger_crud.py
git commit -m "feat: LedgerEntry 모델 및 CRUD 함수 추가"
```

---

### Task 2: `report_ledger.fill_material_ledger`를 `LedgerEntry` 기반으로 변경

**Files:**
- Modify: `backend/app/report_ledger.py`
- Modify: `backend/tests/test_report_ledger.py`

**Interfaces:**
- Consumes: `models.LedgerEntry`와 동일한 속성을 가진 객체 리스트 — `.invoice.delivery_date`, `.invoice.spec`, `.invoice.weight`, `.defect_qty`, `.defect_reason`, `.release_date`, `.release_qty`, `.remaining_qty`, `.inspector`, `.supervisor`
- Produces: `fill_material_ledger(template_path: Path, ledger_entries: list) -> bytes` (기존 `inspector`/`supervisor` 파라미터 제거 — 이제 엔트리마다 개별 값을 가짐)

- [ ] **Step 1: 기존 테스트를 새 시그니처에 맞게 재작성**

`backend/tests/test_report_ledger.py` 전체를 아래로 교체:

```python
from datetime import date
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook

from app import report_ledger

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "app" / "templates" / "material_ledger.xlsx"


def _entry(spec, weight, delivery_date, **overrides):
    invoice = SimpleNamespace(delivery_date=delivery_date, spec=spec, weight=weight)
    defaults = dict(
        invoice=invoice,
        defect_qty=None,
        defect_reason=None,
        release_date=None,
        release_qty=None,
        remaining_qty=None,
        inspector=None,
        supervisor=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_fill_material_ledger_writes_rows_in_order_starting_at_row_7():
    entries = [
        _entry("SHD10", 1.5, date(2026, 4, 20)),
        _entry("SHD13", 2.75, date(2026, 4, 21)),
    ]
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, entries)
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["철근"]

    assert sheet["B7"].value == 1
    assert sheet["C7"].value.date() == date(2026, 4, 20)
    assert sheet["D7"].value == "SHD10"
    assert sheet["G7"].value == 1.5

    assert sheet["B8"].value == 2
    assert sheet["C8"].value.date() == date(2026, 4, 21)
    assert sheet["D8"].value == "SHD13"
    assert sheet["G8"].value == 2.75


def test_fill_material_ledger_writes_manual_fields():
    entries = [
        _entry(
            "SHD10",
            1.5,
            date(2026, 4, 20),
            defect_qty=0.2,
            defect_reason="표면 손상",
            release_date=date(2026, 5, 1),
            release_qty=1.0,
            remaining_qty=0.3,
            inspector="김검수",
            supervisor="박감리",
        )
    ]
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, entries)
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["철근"]

    assert sheet["J7"].value == 0.2
    assert sheet["K7"].value == "표면 손상"
    assert sheet["N7"].value.date() == date(2026, 5, 1)
    assert sheet["O7"].value == 1.0
    assert sheet["P7"].value == 0.3
    assert sheet["Q7"].value == "김검수"
    assert sheet["R7"].value == "박감리"


def test_fill_material_ledger_leaves_manual_fields_blank_when_none():
    entries = [_entry("SHD10", 1.0, date(2026, 4, 20))]
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, entries)
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["철근"]

    assert sheet["J7"].value is None
    assert sheet["K7"].value is None
    assert sheet["Q7"].value is None


def test_fill_material_ledger_preserves_existing_formulas():
    entries = [_entry("SHD10", 1.0, date(2026, 4, 20))]
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, entries)
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["철근"]

    assert sheet["F7"].value == "=G7"
    assert sheet["H7"].value == '=IF(G7="","",(G7-J7))'


def test_fill_material_ledger_does_not_touch_coupler_sheet():
    entries = [_entry("SHD10", 1.0, date(2026, 4, 20))]
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, entries)
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["커플러"]

    assert sheet["B7"].value is None


def test_fill_material_ledger_empty_entries_writes_no_rows():
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, [])
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["철근"]

    assert sheet["B7"].value is None
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_report_ledger.py -v`
Expected: FAIL (시그니처 불일치로 TypeError)

- [ ] **Step 3: `report_ledger.py` 수정**

```python
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "material_ledger.xlsx"

LEDGER_ROW_START = 7
REBAR_SHEET_NAME = "철근"


def fill_material_ledger(template_path: Path, ledger_entries: list) -> bytes:
    wb = load_workbook(template_path)
    sheet = wb[REBAR_SHEET_NAME]

    for offset, entry in enumerate(ledger_entries):
        row = LEDGER_ROW_START + offset
        invoice = entry.invoice
        sheet[f"B{row}"] = offset + 1
        sheet[f"C{row}"] = invoice.delivery_date
        sheet[f"D{row}"] = invoice.spec
        sheet[f"G{row}"] = invoice.weight
        sheet[f"J{row}"] = entry.defect_qty
        sheet[f"K{row}"] = entry.defect_reason
        sheet[f"N{row}"] = entry.release_date
        sheet[f"O{row}"] = entry.release_qty
        sheet[f"P{row}"] = entry.remaining_qty
        sheet[f"Q{row}"] = entry.inspector
        sheet[f"R{row}"] = entry.supervisor

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_report_ledger.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/report_ledger.py backend/tests/test_report_ledger.py
git commit -m "feat: 수불부 채우기 함수가 LedgerEntry의 수동 입력 항목까지 채우도록 변경"
```

---

### Task 3: 엔드포인트 재작성 (`POST /reports/material-ledger` 수정 + `entries` CRUD 엔드포인트 3개 신규)

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/reports.py`
- Test: `backend/tests/test_ledger_api.py` (기존 파일 전체 교체)

**Interfaces:**
- Consumes: Task 1의 `crud.create_ledger_entries`/`list_ledger_entries`/`update_ledger_entry`/`delete_ledger_entry`, Task 2의 `report_ledger.fill_material_ledger(template_path, ledger_entries)`
- Produces:
  - `POST /reports/material-ledger` (invoice_ids, inspector, supervisor) → xlsx (변경 없는 외부 계약, 내부 로직만 LedgerEntry 기반으로 교체)
  - `GET /reports/material-ledger/entries` → `list[LedgerEntryOut]`
  - `PUT /reports/material-ledger/entries/{invoice_id}` (body: `LedgerEntryUpdate`) → `LedgerEntryOut` 또는 404
  - `DELETE /reports/material-ledger/entries/{invoice_id}` → 204 (존재 여부 무관하게 항상 204)

- [ ] **Step 1: `schemas.py`에 스키마 추가**

`backend/app/schemas.py`에 추가:

```python
class LedgerEntryUpdate(BaseModel):
    defect_qty: Optional[float] = None
    defect_reason: Optional[str] = None
    release_date: Optional[date] = None
    release_qty: Optional[float] = None
    remaining_qty: Optional[float] = None
    inspector: Optional[str] = None
    supervisor: Optional[str] = None


class LedgerEntryOut(BaseModel):
    invoice_id: int
    delivery_date: Optional[date] = None
    spec: Optional[str] = None
    weight: Optional[float] = None
    defect_qty: Optional[float] = None
    defect_reason: Optional[str] = None
    release_date: Optional[date] = None
    release_qty: Optional[float] = None
    remaining_qty: Optional[float] = None
    inspector: Optional[str] = None
    supervisor: Optional[str] = None
```

(`LedgerEntryOut`은 `Invoice`와 `LedgerEntry` 값을 합친 평평한 구조이므로 라우터에서 직접 dict로 조립해 반환한다 — `from_attributes`로 자동 매핑하지 않는다. 연번은 응답 배열의 순서 자체가 반입일 순이므로 필드로 넣지 않고 프론트에서 `index + 1`로 표시한다.)

- [ ] **Step 2: 실패하는 테스트로 전체 교체**

`backend/tests/test_ledger_api.py`를 아래로 전체 교체:

```python
from io import BytesIO
from urllib.parse import unquote

from openpyxl import load_workbook

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_invoice(vendor="테스트업체", spec="SHD10", weight="1.5", delivery_date="2026-04-20", item_name="철근"):
    response = client.post(
        "/invoices",
        data={
            "material_type": "철근",
            "vendor": vendor,
            "delivery_date": delivery_date,
            "item_name": item_name,
            "spec": spec,
            "unit": "Ton",
            "weight": weight,
            "quantity": weight,
        },
    )
    return response.json()["id"]


def test_ledger_endpoint_fills_rebar_sheet_and_returns_xlsx():
    id1 = _create_invoice(spec="SHD10", weight="1.5", delivery_date="2026-04-20")
    id2 = _create_invoice(spec="SHD13", weight="2.75", delivery_date="2026-04-21")

    response = client.post(
        "/reports/material-ledger",
        data={"invoice_ids": f"{id1},{id2}", "inspector": "김검수", "supervisor": "박감리"},
    )
    assert response.status_code == 200
    wb = load_workbook(BytesIO(response.content))
    sheet = wb["철근"]
    assert sheet["D7"].value == "SHD10"
    assert sheet["G7"].value == 1.5
    assert sheet["D8"].value == "SHD13"
    assert sheet["Q7"].value == "김검수"


def test_ledger_endpoint_accumulates_across_multiple_generations():
    id1 = _create_invoice(spec="SHD10", weight="1.0", delivery_date="2026-06-01")
    response = client.post(
        "/reports/material-ledger", data={"invoice_ids": str(id1), "inspector": "김검수", "supervisor": "박감리"}
    )
    assert response.status_code == 200

    id2 = _create_invoice(spec="SHD13", weight="2.0", delivery_date="2026-06-02")
    # id1은 다시 선택해도 이미 포함되어 있으므로 건너뛰고, id2만 새로 추가된다.
    response = client.post(
        "/reports/material-ledger", data={"invoice_ids": f"{id1},{id2}", "inspector": "이검수", "supervisor": "최감리"}
    )
    assert response.status_code == 200
    wb = load_workbook(BytesIO(response.content))
    sheet = wb["철근"]
    assert sheet["D7"].value == "SHD10"
    assert sheet["Q7"].value == "김검수"  # 처음 생성 시 값 유지, 덮어쓰지 않음
    assert sheet["D8"].value == "SHD13"
    assert sheet["Q8"].value == "이검수"

    warnings_header = response.headers.get("x-report-warnings")
    assert warnings_header is not None
    assert "1건" in unquote(warnings_header)


def test_ledger_endpoint_excludes_coupler_and_warns():
    rebar_id = _create_invoice(spec="SHD10", weight="1.0", item_name="철근")
    coupler_id = _create_invoice(spec="SHD10", weight="1.0", item_name="커플러")

    response = client.post(
        "/reports/material-ledger",
        data={"invoice_ids": f"{rebar_id},{coupler_id}"},
    )
    assert response.status_code == 200
    warnings_header = response.headers.get("x-report-warnings")
    assert warnings_header is not None
    assert "1건" in unquote(warnings_header)


def test_ledger_endpoint_400_when_nothing_to_include():
    coupler_id = _create_invoice(spec="SHD10", weight="1.0", item_name="커플러")
    response = client.post(
        "/reports/material-ledger",
        data={"invoice_ids": str(coupler_id)},
    )
    assert response.status_code == 400


def test_ledger_endpoint_400_when_invoice_ids_missing():
    response = client.post("/reports/material-ledger", data={})
    assert response.status_code == 400


def test_ledger_endpoint_is_protected_by_shared_password(monkeypatch):
    from app import config

    invoice_id = _create_invoice()
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    response = client.post(
        "/reports/material-ledger",
        data={"invoice_ids": str(invoice_id)},
    )
    assert response.status_code == 401


def test_get_ledger_entries_returns_sorted_list():
    id1 = _create_invoice(spec="SHD13", weight="1.0", delivery_date="2026-07-02")
    id2 = _create_invoice(spec="SHD10", weight="1.0", delivery_date="2026-07-01")
    client.post("/reports/material-ledger", data={"invoice_ids": f"{id1},{id2}"})

    response = client.get("/reports/material-ledger/entries")
    assert response.status_code == 200
    body = response.json()
    specs = [entry["spec"] for entry in body]
    assert "SHD10" in specs and "SHD13" in specs
    assert specs.index("SHD10") < specs.index("SHD13")


def test_put_ledger_entry_updates_manual_fields():
    invoice_id = _create_invoice()
    client.post("/reports/material-ledger", data={"invoice_ids": str(invoice_id)})

    response = client.put(
        f"/reports/material-ledger/entries/{invoice_id}",
        json={
            "defect_qty": 0.5,
            "defect_reason": "표면 손상",
            "release_date": "2026-05-10",
            "release_qty": 0.3,
            "remaining_qty": 0.2,
            "inspector": "김검수",
            "supervisor": "박감리",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["defect_qty"] == 0.5
    assert body["defect_reason"] == "표면 손상"
    assert body["inspector"] == "김검수"


def test_put_ledger_entry_missing_returns_404():
    response = client.put("/reports/material-ledger/entries/999999", json={"defect_qty": 1.0})
    assert response.status_code == 404


def test_delete_ledger_entry_removes_it_and_keeps_invoice():
    invoice_id = _create_invoice()
    client.post("/reports/material-ledger", data={"invoice_ids": str(invoice_id)})

    response = client.delete(f"/reports/material-ledger/entries/{invoice_id}")
    assert response.status_code == 204

    entries = client.get("/reports/material-ledger/entries").json()
    assert all(entry["invoice_id"] != invoice_id for entry in entries)

    invoice_response = client.get(f"/invoices/{invoice_id}")
    assert invoice_response.status_code == 200


def test_delete_ledger_entry_missing_still_returns_204():
    response = client.delete("/reports/material-ledger/entries/999999")
    assert response.status_code == 204
```

- [ ] **Step 3: 테스트 실행해서 실패 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_ledger_api.py -v`
Expected: FAIL (기존 `/reports/material-ledger`는 있지만 새 동작/새 라우트가 없음)

- [ ] **Step 4: `routers/reports.py`의 `create_material_ledger` 교체 + 신규 엔드포인트 추가**

기존 `@router.post("/reports/material-ledger")` 함수 전체를 아래로 교체:

```python
@router.post("/reports/material-ledger")
async def create_material_ledger(
    invoice_ids: Optional[str] = Form(None),
    inspector: str = Form(""),
    supervisor: str = Form(""),
    db: Session = Depends(get_db),
):
    if not invoice_ids:
        raise HTTPException(status_code=400, detail="선택 항목이 없습니다")
    try:
        ids = [int(part) for part in invoice_ids.split(",") if part.strip()]
    except ValueError as error:
        raise HTTPException(status_code=400, detail="선택 항목 형식이 올바르지 않습니다") from error

    _new_entries, skipped_count = crud.create_ledger_entries(db, ids, inspector, supervisor)

    ledger_entries = crud.list_ledger_entries(db)
    if not ledger_entries:
        raise HTTPException(status_code=400, detail="수불부에 포함할 철근 자재 기록이 없습니다")

    xlsx_bytes = report_ledger.fill_material_ledger(report_ledger.TEMPLATE_PATH, ledger_entries)

    filename = f"주요자재검사및수불부_{date.today():%y%m%d}.xlsx"
    encoded_filename = quote(filename)
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"ledger.xlsx\"; filename*=UTF-8''{encoded_filename}"
        )
    }
    if skipped_count:
        headers["X-Report-Warnings"] = quote(
            f"이미 포함되었거나 대상이 아닌 자재 {skipped_count}건은 건너뛰었습니다"
        )

    return Response(
        content=xlsx_bytes,
        media_type=XLSX_MEDIA_TYPE,
        headers=headers,
    )


def _ledger_entry_to_out(entry) -> dict:
    return {
        "invoice_id": entry.invoice_id,
        "delivery_date": entry.invoice.delivery_date,
        "spec": entry.invoice.spec,
        "weight": entry.invoice.weight,
        "defect_qty": entry.defect_qty,
        "defect_reason": entry.defect_reason,
        "release_date": entry.release_date,
        "release_qty": entry.release_qty,
        "remaining_qty": entry.remaining_qty,
        "inspector": entry.inspector,
        "supervisor": entry.supervisor,
    }


@router.get("/reports/material-ledger/entries", response_model=list[schemas.LedgerEntryOut])
def get_ledger_entries(db: Session = Depends(get_db)):
    entries = crud.list_ledger_entries(db)
    return [_ledger_entry_to_out(entry) for entry in entries]


@router.put("/reports/material-ledger/entries/{invoice_id}", response_model=schemas.LedgerEntryOut)
def update_ledger_entry(invoice_id: int, data: schemas.LedgerEntryUpdate, db: Session = Depends(get_db)):
    entry = crud.update_ledger_entry(db, invoice_id, data.model_dump())
    if entry is None:
        raise HTTPException(status_code=404, detail="수불부 항목을 찾을 수 없습니다")
    return _ledger_entry_to_out(entry)


@router.delete("/reports/material-ledger/entries/{invoice_id}", status_code=204)
def delete_ledger_entry(invoice_id: int, db: Session = Depends(get_db)):
    crud.delete_ledger_entry(db, invoice_id)
```

`date` import는 이미 파일 상단에 있음(`from datetime import date`). `schemas` 모듈은 이미 `from .. import crud, ocr, report_excel, report_from_records, report_ledger, report_parser`에서 빠져 있으므로 `schemas`를 import 목록에 추가한다: `from .. import crud, ocr, report_excel, report_from_records, report_ledger, report_parser, schemas`.

- [ ] **Step 5: 테스트 실행해서 통과 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_ledger_api.py -v`
Expected: PASS (11 passed)

- [ ] **Step 6: 전체 백엔드 테스트 실행**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 모두 PASS

- [ ] **Step 7: 커밋**

```bash
git add backend/app/schemas.py backend/app/routers/reports.py backend/tests/test_ledger_api.py
git commit -m "feat: 수불부 엔드포인트를 LedgerEntry 기반 누적 구조로 재작성"
```

---

### Task 4: 프론트엔드 — `/ledger` 화면을 편집 가능한 누적 표로 재작성

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/pages/LedgerPage.jsx`

**Interfaces:**
- Produces:
  - `getLedgerEntries()`: `GET /reports/material-ledger/entries`
  - `updateLedgerEntry(invoiceId, fields)`: `PUT /reports/material-ledger/entries/{invoiceId}`
  - `deleteLedgerEntry(invoiceId)`: `DELETE /reports/material-ledger/entries/{invoiceId}`

- [ ] **Step 1: `api.js`에 함수 추가**

`createMaterialLedger` 함수 아래에 추가:

```js
export async function getLedgerEntries() {
  const response = await fetch(`${API_BASE}/reports/material-ledger/entries`, {
    headers: authHeaders(),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('수불부 목록 조회 실패')
  return response.json()
}

export async function updateLedgerEntry(invoiceId, fields) {
  const response = await fetch(`${API_BASE}/reports/material-ledger/entries/${invoiceId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(fields),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('수불부 항목 수정 실패')
  return response.json()
}

export async function deleteLedgerEntry(invoiceId) {
  const response = await fetch(`${API_BASE}/reports/material-ledger/entries/${invoiceId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('수불부 항목 삭제 실패')
}
```

- [ ] **Step 2: `LedgerPage.jsx` 전체 교체**

```jsx
import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import {
  createMaterialLedger,
  deleteLedgerEntry,
  getLedgerEntries,
  updateLedgerEntry,
} from '../api.js'

const MANUAL_FIELDS = [
  ['defect_qty', '불합격량'],
  ['defect_reason', '사유'],
  ['release_date', '반출일'],
  ['release_qty', '반출량'],
  ['remaining_qty', '잔량'],
  ['inspector', '검수자'],
  ['supervisor', '담당감리원'],
]

export default function LedgerPage() {
  const location = useLocation()
  const invoiceIds = location.state?.invoiceIds ?? []
  const [inspector, setInspector] = useState('')
  const [supervisor, setSupervisor] = useState('')
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [entries, setEntries] = useState([])
  const [loadingEntries, setLoadingEntries] = useState(true)

  async function loadEntries() {
    setLoadingEntries(true)
    try {
      const data = await getLedgerEntries()
      setEntries(data)
    } catch (err) {
      setError(err.message || '수불부 목록을 불러오지 못했습니다')
    } finally {
      setLoadingEntries(false)
    }
  }

  useEffect(() => {
    loadEntries()
  }, [])

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setWarning('')
    setGenerating(true)
    try {
      const { blob, warnings, filename } = await createMaterialLedger(invoiceIds, inspector, supervisor)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename || '주요자재검사및수불부.xlsx'
      link.click()
      URL.revokeObjectURL(url)
      if (warnings) {
        setWarning(warnings)
      }
      await loadEntries()
    } catch (err) {
      setError(err.message || '수불부 생성에 실패했습니다')
    } finally {
      setGenerating(false)
    }
  }

  async function handleFieldChange(invoiceId, key, value) {
    setEntries((prev) =>
      prev.map((entry) => (entry.invoice_id === invoiceId ? { ...entry, [key]: value } : entry))
    )
  }

  async function handleFieldBlur(entry) {
    try {
      await updateLedgerEntry(entry.invoice_id, {
        defect_qty: entry.defect_qty === '' ? null : Number(entry.defect_qty),
        defect_reason: entry.defect_reason || null,
        release_date: entry.release_date || null,
        release_qty: entry.release_qty === '' ? null : Number(entry.release_qty),
        remaining_qty: entry.remaining_qty === '' ? null : Number(entry.remaining_qty),
        inspector: entry.inspector || null,
        supervisor: entry.supervisor || null,
      })
    } catch (err) {
      setError(err.message || '수불부 항목 저장에 실패했습니다')
    }
  }

  async function handleExclude(invoiceId) {
    if (!window.confirm('이 항목을 수불부에서 제외하시겠습니까? 송장 기록 자체는 삭제되지 않습니다.')) return
    try {
      await deleteLedgerEntry(invoiceId)
      setEntries((prev) => prev.filter((entry) => entry.invoice_id !== invoiceId))
    } catch (err) {
      setError(err.message || '제외에 실패했습니다')
    }
  }

  return (
    <div className="page page-wide">
      <h1>주요자재 검사 및 수불부</h1>
      <form className="card" onSubmit={handleSubmit}>
        {invoiceIds.length > 0 ? (
          <p className="banner banner-success">검색에서 선택한 {invoiceIds.length}건을 수불부에 추가합니다.</p>
        ) : (
          <p className="banner banner-warning">
            검색 화면에서 항목을 선택한 뒤 "선택 항목으로 수불부 생성" 버튼으로 들어오면 새 항목을 추가할 수 있습니다.
            아래 목록만 보거나 내려받는 것은 지금도 가능합니다.
          </p>
        )}
        <div className="field">
          <label>검수자 (신규 추가 항목 기본값)</label>
          <input className="input" value={inspector} onChange={(e) => setInspector(e.target.value)} />
        </div>
        <div className="field">
          <label>담당감리원 (신규 추가 항목 기본값)</label>
          <input className="input" value={supervisor} onChange={(e) => setSupervisor(e.target.value)} />
        </div>
        <button
          className="btn btn-primary"
          type="submit"
          disabled={generating || invoiceIds.length === 0}
          style={{ width: '100%' }}
        >
          {generating ? '생성 중...' : '수불부 생성 (선택 항목 추가 + 다운로드)'}
        </button>
      </form>
      {error && <p className="banner banner-error">{error}</p>}
      {warning && <p className="banner banner-warning">{warning}</p>}

      <h2 style={{ fontSize: 16, margin: '24px 0 8px' }}>현재 수불부 포함 목록 ({entries.length}건)</h2>
      {loadingEntries ? (
        <p>불러오는 중...</p>
      ) : entries.length === 0 ? (
        <p className="banner banner-warning">아직 수불부에 포함된 기록이 없습니다.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>연번</th>
                <th>반입일</th>
                <th>규격</th>
                <th>반입량</th>
                {MANUAL_FIELDS.map(([key, label]) => (
                  <th key={key}>{label}</th>
                ))}
                <th>제외</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, index) => (
                <tr key={entry.invoice_id}>
                  <td>{index + 1}</td>
                  <td>{entry.delivery_date ?? ''}</td>
                  <td>{entry.spec ?? ''}</td>
                  <td>{entry.weight ?? ''}</td>
                  {MANUAL_FIELDS.map(([key]) => (
                    <td key={key}>
                      <input
                        className="input"
                        type={key.includes('date') ? 'date' : key.includes('qty') ? 'number' : 'text'}
                        value={entry[key] ?? ''}
                        onChange={(e) => handleFieldChange(entry.invoice_id, key, e.target.value)}
                        onBlur={() => handleFieldBlur(entries.find((row) => row.invoice_id === entry.invoice_id))}
                      />
                    </td>
                  ))}
                  <td>
                    <button
                      type="button"
                      className="btn btn-danger"
                      onClick={() => handleExclude(entry.invoice_id)}
                    >
                      제외
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: 프론트엔드 빌드 확인**

Run: `cd frontend && npm run build`
Expected: 빌드 성공

- [ ] **Step 4: 브라우저로 수동 검증**

로컬 백엔드(8000) + 프론트 dev 서버(5173), 테스트 송장 2~3건 시딩 후:
1. `/search`에서 2건 선택 → "선택 항목으로 수불부 생성" → `/ledger` 이동
2. 검수자/담당감리원 입력 → "수불부 생성" 클릭 → 다운로드 확인
3. 페이지에 표시된 목록에 2건이 반입일 순으로 보이는지 확인
4. 불합격량/사유 등 입력 후 다른 칸 클릭(blur) → 새로고침 후에도 값이 유지되는지 확인 (저장 확인)
5. 한 건 "제외" 클릭 → 목록에서 사라지는지, 검색 화면에서 그 송장은 여전히 조회되는지 확인
6. 검색에서 새 송장 1건 더 선택해서 다시 수불부 생성 → 목록에 기존 1건 + 신규 1건 총 2건 보이는지, 다운로드한 파일에도 둘 다 들어있는지 확인

- [ ] **Step 5: 커밋 및 푸시**

```bash
git add frontend/src/api.js frontend/src/pages/LedgerPage.jsx
git commit -m "feat: 수불부 화면을 누적 목록 편집 화면으로 재작성"
git push origin master
```
