# 촬영 기록 기반 보고서 생성(날짜 선택 방식) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 보고서 생성 탭에 "날짜로 생성" 옵션을 추가해, 촬영 탭에서 이미 DB에 저장된 철근 송장 기록을 반입일자 기준으로 조회해 자재검수요청서 엑셀을 만든다. 기존 "파일 업로드" 방식(그 자리에서 OCR 파싱)은 그대로 유지한다.

**Architecture:** 기존 `report_excel.fill_material_inspection_form`을 그대로 재사용하되, 자재 내역 표의 거래처 칸을 행별로 지정할 수 있도록 확장한다. 새 모듈 `report_from_records.py`가 DB에서 조회한 촬영 기록들을 규격+거래처 조합으로 집계해 `report_parser.build_report_data`와 동일한 형태의 dict를 만든다. `routers/reports.py`는 요청에 `delivery_date`가 있는지에 따라 DB 조회 경로/기존 OCR 경로로 분기한다.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React, Vite

## Global Constraints

- 자재종류는 이번 기능에서 **"철근"으로 고정**한다 — DB 조회 조건과 프론트엔드 입력란 모두 고정.
- 자재 내역 표의 행은 **규격(spec) + 거래처(vendor) 조합** 단위로 구분한다. 같은 조합이 여러 건이면 중량을 합산하고, 비고(제조사 등)는 **쉼표로 나열**해 이어붙인다.
- 각 행의 거래처 칸은 기존 관례(`거래처/비고`)를 따라 `f"{vendor}/{합쳐진 비고}"` 형태로 채운다(비고가 없으면 거래처만).
- 상단 요약란(H37, 납품회사)에는 보고서에 포함된 모든 행의 거래처 표시 문자열을 쉼표로 나열한다.
- 기존 "파일 업로드" 경로(`report_parser.py`, 기존 OCR 흐름)는 전혀 수정하지 않는다 — 회귀 없이 그대로 동작해야 한다.
- 사진대지(상단/하단 사진 업로드)는 두 방식 모두 지금처럼 별도 업로드로 유지한다 — 촬영 기록의 사진과 연계하지 않는다.

---

### Task 1: `report_excel.py` — 자재 내역 표 거래처 칸을 행별로 채우도록 확장

**Files:**
- Modify: `backend/app/report_excel.py`
- Test: `backend/tests/test_report_excel.py`

**Interfaces:**
- Consumes: 기존 `fill_material_inspection_form(...)` 시그니처 (변경 없음 — `specs` 리스트의 각 항목이 선택적으로 `"vendor"` 키를 가질 수 있게 됨)
- Produces: `specs` 항목에 `"vendor"` 키가 있으면 그 값을 F열에, 없으면 기존처럼 함수 파라미터 `vendor`를 F열에 채움

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_report_excel.py`의 `test_fill_material_inspection_form_fills_material_rows` 함수 바로 뒤에 다음 테스트를 추가한다:

```python
def test_fill_material_inspection_form_uses_per_row_vendor_when_provided():
    xlsx_bytes, _ = _fill(
        specs=[
            {"spec": "SHD10", "quantity_ton": 1.0, "vendor": "동경강업(주)/동국제강"},
            {"spec": "SHD13", "quantity_ton": 0.5, "vendor": "대한제강"},
        ]
    )
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["F9"].value == "동경강업(주)/동국제강"
    assert sheet["F10"].value == "대한제강"


def test_fill_material_inspection_form_falls_back_to_top_level_vendor_when_row_has_none():
    xlsx_bytes, _ = _fill(specs=[{"spec": "SHD10", "quantity_ton": 1.0}], vendor="공통거래처")
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["F9"].value == "공통거래처"
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_report_excel.py::test_fill_material_inspection_form_uses_per_row_vendor_when_provided -v`
Expected: FAIL — `assert '동경강업(주)/동국제강' == '동경강업(주)/동국제강'` 형태가 아니라 두 행 모두 `_fill`의 기본 `vendor="동경강업(주)/동국제강"`로 채워져 있어서 F10도 F9와 같은 값이 나와 실패 (두 번째 assert가 실패)

- [ ] **Step 3: `report_excel.py` 수정**

`backend/app/report_excel.py`에서 자재 행 채우기 루프의 이 줄을:

```python
        sheet[f"F{row}"] = vendor
```

아래로 교체한다:

```python
        sheet[f"F{row}"] = spec_row.get("vendor", vendor)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_report_excel.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/report_excel.py backend/tests/test_report_excel.py
git commit -m "feat: 자재 내역 표 거래처 칸을 행별로 지정 가능하도록 확장"
```

---

### Task 2: DB 조회 함수 + 촬영 기록 집계 모듈

**Files:**
- Modify: `backend/app/crud.py`
- Create: `backend/app/report_from_records.py`
- Test: `backend/tests/test_report_from_records.py`

**Interfaces:**
- Consumes: `models.Invoice` (기존 필드: `material_type`, `vendor`, `delivery_date`, `spec`, `weight`, `note`)
- Produces: `crud.list_invoices_by_material_and_date(db: Session, material_type: str, delivery_date: date) -> list[models.Invoice]`, `report_from_records.build_report_data_from_invoices(invoices, delivery_date: str) -> dict` — 반환 형태는 `report_parser.build_report_data`와 동일: `{"specs": list[dict], "vendor": str, "skipped_pages": list, "delivery_date": str}`. `specs`의 각 항목은 `{"spec": str, "quantity_ton": float, "vendor": str}`.

- [ ] **Step 1: `crud.py`에 조회 함수 추가**

`backend/app/crud.py`의 `update_invoice` 함수 뒤, `get_next_report_number` 함수 앞에 다음 함수를 추가한다:

```python
def list_invoices_by_material_and_date(db: Session, material_type: str, delivery_date: date) -> list[models.Invoice]:
    return (
        db.query(models.Invoice)
        .filter(models.Invoice.material_type == material_type)
        .filter(models.Invoice.delivery_date == delivery_date)
        .order_by(models.Invoice.id)
        .all()
    )
```

(`date` 타입은 이미 파일 상단에 `from datetime import date`로 임포트되어 있다.)

- [ ] **Step 2: `report_from_records.py`에 대한 실패하는 테스트 작성**

`backend/tests/test_report_from_records.py`를 새로 만든다:

```python
from types import SimpleNamespace

from app import report_from_records


def _invoice(spec, vendor, weight, note=""):
    return SimpleNamespace(spec=spec, vendor=vendor, weight=weight, note=note)


def test_build_report_data_from_invoices_separates_rows_by_spec_and_vendor():
    invoices = [
        _invoice("SHD10", "동경강업(주)", 1000, "동국제강"),
        _invoice("SHD10", "대한제강", 500, "한영철강"),
    ]
    data = report_from_records.build_report_data_from_invoices(invoices, delivery_date="2026-04-20")
    assert len(data["specs"]) == 2
    specs_by_vendor = {s["vendor"]: s for s in data["specs"]}
    assert specs_by_vendor["동경강업(주)/동국제강"]["quantity_ton"] == 1.0
    assert specs_by_vendor["대한제강/한영철강"]["quantity_ton"] == 0.5


def test_build_report_data_from_invoices_merges_same_spec_and_vendor_summing_weight_and_joining_notes():
    invoices = [
        _invoice("SHD10", "동경강업(주)", 1000, "동국제강"),
        _invoice("SHD10", "동경강업(주)", 500, "한영철강"),
    ]
    data = report_from_records.build_report_data_from_invoices(invoices, delivery_date="2026-04-20")
    assert len(data["specs"]) == 1
    assert data["specs"][0]["vendor"] == "동경강업(주)/동국제강, 한영철강"
    assert data["specs"][0]["quantity_ton"] == 1.5


def test_build_report_data_from_invoices_does_not_duplicate_repeated_notes():
    invoices = [
        _invoice("SHD10", "동경강업(주)", 1000, "동국제강"),
        _invoice("SHD10", "동경강업(주)", 500, "동국제강"),
    ]
    data = report_from_records.build_report_data_from_invoices(invoices, delivery_date="2026-04-20")
    assert data["specs"][0]["vendor"] == "동경강업(주)/동국제강"
    assert data["specs"][0]["quantity_ton"] == 1.5


def test_build_report_data_from_invoices_summary_vendor_lists_all_rows_comma_separated():
    invoices = [
        _invoice("SHD10", "동경강업(주)", 1000, "동국제강"),
        _invoice("SHD13", "대한제강", 500, ""),
    ]
    data = report_from_records.build_report_data_from_invoices(invoices, delivery_date="2026-04-20")
    assert data["vendor"] == "동경강업(주)/동국제강, 대한제강"


def test_build_report_data_from_invoices_sets_delivery_date_and_empty_skipped_pages():
    data = report_from_records.build_report_data_from_invoices([], delivery_date="2026-04-20")
    assert data["delivery_date"] == "2026-04-20"
    assert data["skipped_pages"] == []
    assert data["specs"] == []
    assert data["vendor"] == ""
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_report_from_records.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.report_from_records'`

- [ ] **Step 4: `report_from_records.py` 구현**

`backend/app/report_from_records.py`를 새로 만든다:

```python
def build_report_data_from_invoices(invoices, delivery_date: str) -> dict:
    groups: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []

    for invoice in invoices:
        key = (invoice.spec or "", invoice.vendor or "")
        if key not in groups:
            groups[key] = {"weight_kg": 0.0, "notes": []}
            order.append(key)
        groups[key]["weight_kg"] += invoice.weight or 0.0
        if invoice.note and invoice.note not in groups[key]["notes"]:
            groups[key]["notes"].append(invoice.note)

    specs = []
    vendor_displays = []
    for spec, vendor in order:
        data = groups[(spec, vendor)]
        notes_joined = ", ".join(data["notes"])
        vendor_display = f"{vendor}/{notes_joined}" if vendor and notes_joined else vendor
        specs.append(
            {
                "spec": spec,
                "quantity_ton": round(data["weight_kg"] / 1000, 3),
                "vendor": vendor_display,
            }
        )
        vendor_displays.append(vendor_display)

    return {
        "specs": specs,
        "vendor": ", ".join(dict.fromkeys(v for v in vendor_displays if v)),
        "skipped_pages": [],
        "delivery_date": delivery_date,
    }
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_report_from_records.py -v`
Expected: PASS (전체)

- [ ] **Step 6: 커밋**

```bash
git add backend/app/crud.py backend/app/report_from_records.py backend/tests/test_report_from_records.py
git commit -m "feat: 자재종류+반입일자 기준 촬영 기록 조회 및 보고서 데이터 집계 추가"
```

---

### Task 3: `routers/reports.py` — 날짜 기반 생성 경로 연결

**Files:**
- Modify: `backend/app/routers/reports.py`
- Test: `backend/tests/test_reports_api.py`

**Interfaces:**
- Consumes: `crud.list_invoices_by_material_and_date` (Task 2), `report_from_records.build_report_data_from_invoices` (Task 2), `report_excel.fill_material_inspection_form` (Task 1에서 확장된 채로 그대로 재사용)
- Produces: `POST /reports/material-inspection`가 폼 필드 `delivery_date`(선택, `"YYYY-MM-DD"` 문자열)를 받는다. `delivery_date`가 있으면 DB 조회 경로, 없으면 기존 `files` 기반 OCR 경로(단, `files`도 없으면 400).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_reports_api.py` 맨 아래에 다음 테스트를 추가한다:

```python
def test_create_report_from_delivery_date_returns_xlsx(monkeypatch):
    from app import excel as excel_module
    from app import pdf as pdf_module

    monkeypatch.setattr(excel_module, "append_invoice", lambda invoice: None)
    monkeypatch.setattr(pdf_module, "generate_pdf", lambda invoice: "pdf/x.pdf")

    client.post(
        "/invoices",
        data={
            "material_type": "철근",
            "vendor": "동경강업(주)",
            "delivery_date": "2026-04-20",
            "spec": "SHD10",
            "weight": "1000",
            "note": "동국제강",
        },
    )
    client.post(
        "/invoices",
        data={
            "material_type": "철근",
            "vendor": "대한제강",
            "delivery_date": "2026-04-20",
            "spec": "SHD13",
            "weight": "500",
            "note": "",
        },
    )

    response = client.post(
        "/reports/material-inspection",
        data={**_form_fields(), "delivery_date": "2026-04-20"},
    )
    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.content))
    sheet = workbook.active
    assert sheet["A9"].value == "철근"
    assert sheet["F9"].value == "동경강업(주)/동국제강"
    assert sheet["F10"].value == "대한제강"
    assert sheet["H35"].value == "2026-04-20"


def test_create_report_from_delivery_date_400_when_no_records():
    response = client.post(
        "/reports/material-inspection",
        data={**_form_fields(), "delivery_date": "2099-01-01"},
    )
    assert response.status_code == 400
    assert "철근 기록이 없습니다" in response.json()["detail"]


def test_create_report_400_when_neither_files_nor_delivery_date_given():
    response = client.post(
        "/reports/material-inspection",
        data=_form_fields(),
    )
    assert response.status_code == 400
    assert "파일을 업로드하거나 반입일자를 선택" in response.json()["detail"]
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_reports_api.py -v`
Expected: FAIL — `test_create_report_from_delivery_date_returns_xlsx`와 `test_create_report_from_delivery_date_400_when_no_records`는 `delivery_date` 폼 필드가 아직 라우터에 없어 무시되고 기존 "파일 없음" 경로로 빠져 422 또는 다른 에러; `test_create_report_400_when_neither_files_nor_delivery_date_given`은 `files`가 아직 필수라 422

- [ ] **Step 3: `routers/reports.py` 재작성**

`backend/app/routers/reports.py` 전체를 아래 내용으로 교체한다:

```python
from datetime import date
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import crud, ocr, report_excel, report_from_records, report_parser
from ..auth import verify_password
from ..database import get_db

router = APIRouter(dependencies=[Depends(verify_password)])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CAPTURE_REPORT_MATERIAL_TYPE = "철근"


@router.post("/reports/material-inspection")
async def create_material_inspection_report(
    project_name: str = Form(...),
    work_type: str = Form(...),
    material_type: str = Form(...),
    sender: str = Form(...),
    receiver: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    delivery_date: Optional[str] = Form(None),
    top_photos: List[UploadFile] = File(default=[]),
    bottom_photos: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    if delivery_date:
        parsed_date = date.fromisoformat(delivery_date)
        invoices = crud.list_invoices_by_material_and_date(db, CAPTURE_REPORT_MATERIAL_TYPE, parsed_date)
        if not invoices:
            raise HTTPException(status_code=400, detail="해당 날짜에 촬영된 철근 기록이 없습니다")
        report_data = report_from_records.build_report_data_from_invoices(invoices, delivery_date=delivery_date)
    else:
        if not files:
            raise HTTPException(status_code=400, detail="파일을 업로드하거나 반입일자를 선택해주세요")
        raw_responses = []
        for uploaded_file in files:
            image_bytes = await uploaded_file.read()
            try:
                raw_response = ocr.call_upstage_ocr(image_bytes, filename=uploaded_file.filename or "invoice.jpg")
            except Exception as error:
                raise HTTPException(status_code=502, detail=f"OCR 호출 실패: {error}") from error
            raw_responses.append(raw_response)

        try:
            report_data = report_parser.build_report_data(raw_responses)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    top_photo_bytes = [await photo.read() for photo in top_photos]
    bottom_photo_bytes = [await photo.read() for photo in bottom_photos]

    report_number = crud.get_next_report_number(db)
    document_number = f"건축(자검) - {material_type} - {report_number}호"

    xlsx_bytes, skipped_specs = report_excel.fill_material_inspection_form(
        report_excel.TEMPLATE_PATH,
        project_name=project_name,
        work_type=work_type,
        material_type=material_type,
        document_number=document_number,
        sender=sender,
        receiver=receiver,
        specs=report_data["specs"],
        vendor=report_data["vendor"],
        delivery_date=report_data["delivery_date"],
        top_photos=top_photo_bytes,
        bottom_photos=bottom_photo_bytes,
    )

    warnings: List[str] = []
    if report_data["skipped_pages"]:
        warnings.append(
            f"{len(report_data['skipped_pages'])}개 페이지에서 자재 내역 표를 찾지 못해 제외했습니다"
        )
    if not report_data["vendor"]:
        warnings.append("거래처(반입업체명)를 자동으로 인식하지 못했습니다 — 문서에서 직접 확인해주세요")
    if not report_data["delivery_date"]:
        warnings.append("반입일자를 자동으로 인식하지 못했습니다 — 문서에서 직접 확인해주세요")
    if skipped_specs:
        warnings.append(
            f"자재 규격이 {len(skipped_specs)}개 더 있었지만 표 용량을 초과해 제외했습니다"
        )

    filename = f"{document_number}.xlsx"
    encoded_filename = quote(filename)
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"report.xlsx\"; filename*=UTF-8''{encoded_filename}"
        )
    }
    if warnings:
        headers["X-Report-Warnings"] = quote(" | ".join(warnings))

    return Response(
        content=xlsx_bytes,
        media_type=XLSX_MEDIA_TYPE,
        headers=headers,
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/ -v`
Expected: PASS (전체 — 기존 파일 업로드 경로 테스트들도 회귀 없이 통과해야 함)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/routers/reports.py backend/tests/test_reports_api.py
git commit -m "feat: 보고서 생성에 반입일자 기반 촬영 기록 조회 경로 추가"
```

---

### Task 4: 프론트엔드 — 보고서 생성 화면에 "날짜로 생성" 모드 추가

**Files:**
- Modify: `frontend/src/pages/ReportPage.jsx`
- Modify: `frontend/src/api.js`

**Interfaces:**
- Consumes: 백엔드 `POST /reports/material-inspection`이 이제 선택적 `delivery_date` 폼 필드를 받음(Task 3)
- Produces: `createMaterialInspectionReport(fields, files, topPhotos, bottomPhotos, deliveryDate)` — 다섯 번째 인자 추가, 기본값 `''`

- [ ] **Step 1: `api.js`의 `createMaterialInspectionReport`에 `deliveryDate` 인자 추가**

`frontend/src/api.js`에서 `createMaterialInspectionReport` 함수 전체를 찾아 아래 내용으로 교체한다:

```js
export async function createMaterialInspectionReport(fields, files, topPhotos = [], bottomPhotos = [], deliveryDate = '') {
  const formData = new FormData()
  Object.entries(fields).forEach(([key, value]) => {
    formData.append(key, value)
  })
  files.forEach((file) => {
    formData.append('files', file)
  })
  topPhotos.forEach((file) => {
    formData.append('top_photos', file)
  })
  bottomPhotos.forEach((file) => {
    formData.append('bottom_photos', file)
  })
  if (deliveryDate) {
    formData.append('delivery_date', deliveryDate)
  }
  const response = await fetch(`${API_BASE}/reports/material-inspection`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  handleUnauthorized(response)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || '보고서 생성에 실패했습니다')
  }
  const blob = await response.blob()
  const encodedWarnings = response.headers.get('X-Report-Warnings')
  const warnings = encodedWarnings ? decodeURIComponent(encodedWarnings) : null
  return { blob, warnings }
}
```

- [ ] **Step 2: `ReportPage.jsx`에 모드 전환 UI 추가**

`frontend/src/pages/ReportPage.jsx`의 현재 전체 내용:

```jsx
import { useState } from 'react'
import PhotoPicker from '../components/PhotoPicker.jsx'
import { createMaterialInspectionReport } from '../api.js'

export default function ReportPage() {
  const [projectName, setProjectName] = useState('서소문 재개발')
  const [workType, setWorkType] = useState('건축')
  const [materialType, setMaterialType] = useState('철근')
  const [sender, setSender] = useState('')
  const [receiver, setReceiver] = useState('')
  const [files, setFiles] = useState([])
  const [topPhotos, setTopPhotos] = useState([])
  const [bottomPhotos, setBottomPhotos] = useState([])
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [generating, setGenerating] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setWarning('')
    setGenerating(true)
    try {
      const { blob, warnings } = await createMaterialInspectionReport(
        {
          project_name: projectName,
          work_type: workType,
          material_type: materialType,
          sender,
          receiver,
        },
        files,
        topPhotos,
        bottomPhotos,
      )
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `자재검수요청서-${materialType || '자재'}.xlsx`
      link.click()
      URL.revokeObjectURL(url)
      if (warnings) {
        setWarning(warnings)
      }
    } catch (err) {
      setError(err.message || '보고서 생성에 실패했습니다')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="page">
      <h1>자재검수요청서 생성</h1>
      <form className="card" onSubmit={handleSubmit}>
        <div className="field">
          <label>공사명</label>
          <input className="input" value={projectName} onChange={(e) => setProjectName(e.target.value)} required />
        </div>
        <div className="field">
          <label>공종</label>
          <select className="select" value={workType} onChange={(e) => setWorkType(e.target.value)}>
            <option value="건축">건축</option>
            <option value="토목">토목</option>
            <option value="기계">기계</option>
            <option value="전기">전기</option>
          </select>
        </div>
        <div className="field">
          <label>자재종류</label>
          <input className="input" value={materialType} onChange={(e) => setMaterialType(e.target.value)} required />
        </div>
        <div className="field">
          <label>발신자(현장대리인)</label>
          <input className="input" value={sender} onChange={(e) => setSender(e.target.value)} required />
        </div>
        <div className="field">
          <label>수신자(총괄관리원)</label>
          <input className="input" value={receiver} onChange={(e) => setReceiver(e.target.value)} required />
        </div>
        <PhotoPicker
          label="송장 갑지 파일 (PDF 또는 이미지, 여러 장 가능)"
          accept="application/pdf,image/*"
          files={files}
          onFilesChange={setFiles}
        />
        <PhotoPicker
          label="사진대지 상단 사진 (선택, 여러 장 가능)"
          accept="image/*"
          files={topPhotos}
          onFilesChange={setTopPhotos}
        />
        <PhotoPicker
          label="사진대지 하단 사진 (선택, 여러 장 가능)"
          accept="image/*"
          files={bottomPhotos}
          onFilesChange={setBottomPhotos}
        />
        <button
          className="btn btn-primary"
          type="submit"
          disabled={generating || files.length === 0}
          style={{ width: '100%' }}
        >
          {generating ? '생성 중...' : '보고서 생성'}
        </button>
      </form>
      {error && <p className="banner banner-error">{error}</p>}
      {warning && <p className="banner banner-warning">{warning}</p>}
    </div>
  )
}
```

아래 내용으로 전체 교체:

```jsx
import { useState } from 'react'
import PhotoPicker from '../components/PhotoPicker.jsx'
import { createMaterialInspectionReport } from '../api.js'

export default function ReportPage() {
  const [mode, setMode] = useState('file')
  const [projectName, setProjectName] = useState('서소문 재개발')
  const [workType, setWorkType] = useState('건축')
  const [materialType, setMaterialType] = useState('철근')
  const [sender, setSender] = useState('')
  const [receiver, setReceiver] = useState('')
  const [files, setFiles] = useState([])
  const [deliveryDate, setDeliveryDate] = useState('')
  const [topPhotos, setTopPhotos] = useState([])
  const [bottomPhotos, setBottomPhotos] = useState([])
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [generating, setGenerating] = useState(false)

  const effectiveMaterialType = mode === 'date' ? '철근' : materialType
  const canSubmit = mode === 'file' ? files.length > 0 : !!deliveryDate

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setWarning('')
    setGenerating(true)
    try {
      const { blob, warnings } = await createMaterialInspectionReport(
        {
          project_name: projectName,
          work_type: workType,
          material_type: effectiveMaterialType,
          sender,
          receiver,
        },
        mode === 'file' ? files : [],
        topPhotos,
        bottomPhotos,
        mode === 'date' ? deliveryDate : '',
      )
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `자재검수요청서-${effectiveMaterialType || '자재'}.xlsx`
      link.click()
      URL.revokeObjectURL(url)
      if (warnings) {
        setWarning(warnings)
      }
    } catch (err) {
      setError(err.message || '보고서 생성에 실패했습니다')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="page">
      <h1>자재검수요청서 생성</h1>
      <form className="card" onSubmit={handleSubmit}>
        <div className="field">
          <label>생성 방식</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              className={`btn ${mode === 'file' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setMode('file')}
              style={{ flex: 1 }}
            >
              파일 업로드
            </button>
            <button
              type="button"
              className={`btn ${mode === 'date' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setMode('date')}
              style={{ flex: 1 }}
            >
              날짜로 생성
            </button>
          </div>
        </div>
        <div className="field">
          <label>공사명</label>
          <input className="input" value={projectName} onChange={(e) => setProjectName(e.target.value)} required />
        </div>
        <div className="field">
          <label>공종</label>
          <select className="select" value={workType} onChange={(e) => setWorkType(e.target.value)}>
            <option value="건축">건축</option>
            <option value="토목">토목</option>
            <option value="기계">기계</option>
            <option value="전기">전기</option>
          </select>
        </div>
        <div className="field">
          <label>자재종류</label>
          <input
            className="input"
            value={effectiveMaterialType}
            onChange={(e) => setMaterialType(e.target.value)}
            disabled={mode === 'date'}
            required
          />
        </div>
        <div className="field">
          <label>발신자(현장대리인)</label>
          <input className="input" value={sender} onChange={(e) => setSender(e.target.value)} required />
        </div>
        <div className="field">
          <label>수신자(총괄관리원)</label>
          <input className="input" value={receiver} onChange={(e) => setReceiver(e.target.value)} required />
        </div>
        {mode === 'file' ? (
          <PhotoPicker
            label="송장 갑지 파일 (PDF 또는 이미지, 여러 장 가능)"
            accept="application/pdf,image/*"
            files={files}
            onFilesChange={setFiles}
          />
        ) : (
          <div className="field">
            <label>반입일자</label>
            <input
              className="input"
              type="date"
              value={deliveryDate}
              onChange={(e) => setDeliveryDate(e.target.value)}
            />
          </div>
        )}
        <PhotoPicker
          label="사진대지 상단 사진 (선택, 여러 장 가능)"
          accept="image/*"
          files={topPhotos}
          onFilesChange={setTopPhotos}
        />
        <PhotoPicker
          label="사진대지 하단 사진 (선택, 여러 장 가능)"
          accept="image/*"
          files={bottomPhotos}
          onFilesChange={setBottomPhotos}
        />
        <button
          className="btn btn-primary"
          type="submit"
          disabled={generating || !canSubmit}
          style={{ width: '100%' }}
        >
          {generating ? '생성 중...' : '보고서 생성'}
        </button>
      </form>
      {error && <p className="banner banner-error">{error}</p>}
      {warning && <p className="banner banner-warning">{warning}</p>}
    </div>
  )
}
```

- [ ] **Step 3: 빌드 확인**

Run: `cd frontend && npm run build`
Expected: 에러 없이 빌드 성공

- [ ] **Step 4: 브라우저 프리뷰로 모드 전환 확인**

Vite 개발 서버를 띄우고, `sessionStorage.setItem('appPassword', 'dummy')`로 비밀번호 게이트를 우회한 뒤 `/report`로 이동해:
- 기본 상태("파일 업로드" 모드)에서 "송장 갑지 파일" 입력이 보이는지
- "날짜로 생성" 버튼을 누르면 자재종류 입력란이 "철근"으로 고정/비활성화되고, "송장 갑지 파일" 대신 날짜 입력란이 나타나는지
- 날짜를 선택하지 않은 상태에서 "보고서 생성" 버튼이 비활성화되어 있는지, 날짜를 선택하면 활성화되는지

확인한다.

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/pages/ReportPage.jsx frontend/src/api.js
git commit -m "feat: 보고서 생성 화면에 반입일자 기반 생성 모드 추가"
```

---

## 자체 점검 결과

- **스펙 커버리지**: 설계 문서의 자재종류 "철근" 고정(Task 3의 `CAPTURE_REPORT_MATERIAL_TYPE`, Task 4의 `effectiveMaterialType`), 규격+거래처 조합 행 구분/쉼표 나열 병합(Task 2), 거래처 칸 행별 지정(Task 1), 상단 요약 거래처 쉼표 나열(Task 2), 기존 파일 업로드 경로 무변경(Task 3에서 else 분기로 그대로 보존), 사진대지 업로드 방식 무변경(Task 4에서 그대로 유지)이 각 태스크에 매핑됨.
- **플레이스홀더 스캔**: 모든 스텝에 실제 코드/명령어 포함, "TODO"/"나중에" 등 표현 없음.
- **타입/시그니처 일관성**: `build_report_data_from_invoices`의 반환 키(`specs`, `vendor`, `skipped_pages`, `delivery_date`)가 `report_parser.build_report_data`와 동일해 Task 3의 라우터가 두 경로 모두에서 같은 후속 코드를 쓸 수 있음을 확인. `specs` 항목의 `"vendor"` 키가 Task 1에서 확장한 `fill_material_inspection_form`의 `spec_row.get("vendor", vendor)`와 정확히 맞물림.
