# 촬영 탭 갑지 다중 레코드 생성 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 촬영 탭에서 "송장별 총괄 내역서" 갑지(표 형식) 문서를 찍으면, 자재 규격별로 여러 개의 송장 레코드를 자동 생성하도록 바꾼다. 거래처/납품일/차량번호/송장번호는 공통값, 규격/중량은 레코드별로 채운다.

**Architecture:** `report_parser.py`(이미 보고서 생성에서 검증된 갑지 표 파싱 로직)에 차량번호/송장번호 추출 함수와 다중 레코드 빌더를 추가하고, `/ocr` 엔드포인트가 갑지 감지 시 이를 사용하도록 분기한다. 프론트엔드는 OCR 응답이 레코드 배열임을 반영해 촬영→편집 흐름을 공통정보+자재별 카드 여러 개 구조로 재구성한다.

**Tech Stack:** FastAPI, pytest, React, Vite

## Global Constraints

- 자유 양식 문서(갑지가 아닌 문서)에 대한 기존 `normalize_fields()` 동작은 전혀 변경하지 않는다.
- `/ocr` 응답 형식이 `{필드: 값, ...}` 평평한 dict에서 `{"records": [...]}` 배열로 바뀐다 — 프론트엔드도 함께 수정해 하위 호환을 유지하지 않는다(백엔드/프론트 동시 배포이므로 문제 없음).
- 자재종류/품명은 기본값 "철근"으로 채우고, 수량(quantity)과 단위(unit)는 이 문서 형식에 해당 컬럼이 없으므로 공란으로 둔다 — 사용자가 필요 시 직접 입력.
- 사진 1장에서 나온 모든 레코드는 동일한 원본 사진을 공유한다.
- 이 작업은 백엔드는 TDD로, 프론트엔드는 이 세션의 다른 UI 작업과 동일하게 자동 테스트 없이 빌드 확인 + 브라우저 프리뷰로 검증한다.

---

### Task 1: `report_parser.py` — 차량번호/송장번호 추출 + 다중 레코드 빌더

**Files:**
- Modify: `backend/app/report_parser.py`
- Test: `backend/tests/test_report_parser.py`

**Interfaces:**
- Consumes: 기존 `_parse_table_rows`, `_collapse_spaces`, `find_cover_pages`, `extract_material_rows`, `find_vendor_heading`, `find_delivery_date` (전부 변경 없음)
- Produces: `find_vehicle_no(raw_response: dict, page: int) -> str`, `find_invoice_no(raw_response: dict, page: int) -> str`, `build_capture_records(raw_response: dict, material_type: str = "철근") -> list[dict]` — 각 dict는 키 `material_type, vendor, delivery_date, vehicle_no, invoice_no, item_name, spec, unit, quantity, weight, note`를 가짐 (`unit`은 빈 문자열, `quantity`는 `None`, `weight`는 float)

- [ ] **Step 1: `make_cover_response` 헬퍼에 차량번호/송장번호 파라미터 추가 + 실패하는 테스트 작성**

`backend/tests/test_report_parser.py` 최상단의 `make_cover_response` 함수 전체를 찾아 아래 내용으로 교체한다 (기존 호출부와 하위 호환 — 새 파라미터는 기본값 `None`):

```python
def make_cover_response(
    page,
    vendor_heading,
    spec_weight_pairs,
    note="동국제강",
    delivery_date=None,
    vehicle_no=None,
    invoice_no=None,
):
    material_rows = [
        [spec, "0.560", str(weight_kg), str(weight_kg), note] for spec, weight_kg in spec_weight_pairs
    ]
    total_kg = sum(weight_kg for _, weight_kg in spec_weight_pairs)
    table_html = _table_html(
        ["직경", "단위중량(kg/m)", "발송중량(kg)", "할증중량(kg)", "비고"],
        material_rows + [["총 합", "", str(total_kg), "", ""]],
    )
    elements = [
        {"page": page, "category": "heading1", "content": {"html": "<h1>송장별 총괄 내역서</h1>", "text": ""}},
        {"page": page, "category": "table", "content": {"html": table_html, "text": ""}},
        {"page": page, "category": "heading1", "content": {"html": f"<h1>{vendor_heading}</h1>", "text": ""}},
    ]
    if delivery_date:
        info_table_html = (
            "<table><tbody>"
            f"<tr><td>도</td><td>착 일</td><td>: {delivery_date} / {delivery_date} 연 락 처 : 테스트</td></tr>"
            "</tbody></table>"
        )
        elements.append({"page": page, "category": "table", "content": {"html": info_table_html, "text": ""}})
    if vehicle_no:
        vehicle_table_html = (
            "<table><tbody>"
            f"<tr><td>차 량 번 호</td><td>: {vehicle_no} 홍길동 010-1234-5678</td></tr>"
            "</tbody></table>"
        )
        elements.append({"page": page, "category": "table", "content": {"html": vehicle_table_html, "text": ""}})
    if invoice_no:
        invoice_table_html = (
            "<table><tbody>"
            f"<tr><td>송 장 번 호</td><td>: {invoice_no} ( 1 회차 )</td></tr>"
            "</tbody></table>"
        )
        elements.append({"page": page, "category": "table", "content": {"html": invoice_table_html, "text": ""}})
    return {"elements": elements}
```

파일 맨 아래에 다음 테스트들을 추가한다:

```python
def test_find_vehicle_no_extracts_plate_number():
    raw = make_cover_response(1, "동경강업(주)", [("SHD10", 9401)], vehicle_no="서울85바3204")
    assert report_parser.find_vehicle_no(raw, page=1) == "서울85바3204"


def test_find_vehicle_no_returns_empty_when_not_found():
    raw = make_cover_response(1, "동경강업(주)", [("SHD10", 9401)])
    assert report_parser.find_vehicle_no(raw, page=1) == ""


def test_find_invoice_no_extracts_number():
    raw = make_cover_response(1, "동경강업(주)", [("SHD10", 9401)], invoice_no="20260420-024")
    assert report_parser.find_invoice_no(raw, page=1) == "20260420-024"


def test_find_invoice_no_returns_empty_when_not_found():
    raw = make_cover_response(1, "동경강업(주)", [("SHD10", 9401)])
    assert report_parser.find_invoice_no(raw, page=1) == ""


def test_build_capture_records_creates_one_record_per_spec():
    raw = make_cover_response(
        1,
        "동경강업(주)",
        [("SHD10", 9401), ("SHD13", 17082), ("UHD16", 1720)],
        note="현대제철",
        delivery_date="2026-04-20",
        vehicle_no="서울85바3204",
        invoice_no="20260420-024",
    )
    records = report_parser.build_capture_records(raw)
    assert len(records) == 3
    for record in records:
        assert record["material_type"] == "철근"
        assert record["item_name"] == "철근"
        assert record["vendor"] == "동경강업(주)"
        assert record["delivery_date"] == "2026-04-20"
        assert record["vehicle_no"] == "서울85바3204"
        assert record["invoice_no"] == "20260420-024"
        assert record["unit"] == ""
        assert record["quantity"] is None
        assert record["note"] == "현대제철"

    specs = {record["spec"] for record in records}
    assert specs == {"SHD10", "SHD13", "UHD16"}
    weights = {record["spec"]: record["weight"] for record in records}
    assert weights["SHD10"] == 9401.0
    assert weights["SHD13"] == 17082.0
    assert weights["UHD16"] == 1720.0


def test_build_capture_records_uses_custom_material_type():
    raw = make_cover_response(1, "동경강업(주)", [("SHD10", 9401)])
    records = report_parser.build_capture_records(raw, material_type="H형강")
    assert records[0]["material_type"] == "H형강"
    assert records[0]["item_name"] == "H형강"


def test_build_capture_records_returns_empty_when_no_cover_page():
    raw = {"elements": []}
    assert report_parser.build_capture_records(raw) == []


def test_build_capture_records_returns_empty_when_table_not_found():
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>송장별 총괄 내역서</h1>", "text": ""}},
        ]
    }
    assert report_parser.build_capture_records(raw) == []
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_report_parser.py -v`
Expected: FAIL — `AttributeError: module 'app.report_parser' has no attribute 'find_vehicle_no'` (그리고 이어서 `find_invoice_no`, `build_capture_records`도 동일)

- [ ] **Step 3: `report_parser.py`에 구현 추가**

`backend/app/report_parser.py`에서 `DATE_PATTERN` 상수 정의 바로 아래에 다음 상수를 추가한다:

```python
VEHICLE_NO_PATTERN = re.compile(r"[가-힣]{0,3}\d{2,3}[가-힣]\d{4}")
INVOICE_NO_PATTERN = re.compile(r"\d{8}-\d{3}")
```

`find_delivery_date` 함수 바로 뒤, `build_report_data` 함수 앞에 다음 함수 3개를 추가한다:

```python
def find_vehicle_no(raw_response: dict, page: int) -> str:
    for element in raw_response.get("elements", []):
        if element.get("category") != "table" or element.get("page") != page:
            continue
        table_html = element.get("content", {}).get("html", "")
        for row in _parse_table_rows(table_html):
            joined = _collapse_spaces("".join(row))
            if joined.startswith("차량번호"):
                match = VEHICLE_NO_PATTERN.search(joined)
                if match:
                    return match.group(0)
    return ""


def find_invoice_no(raw_response: dict, page: int) -> str:
    for element in raw_response.get("elements", []):
        if element.get("category") != "table" or element.get("page") != page:
            continue
        table_html = element.get("content", {}).get("html", "")
        for row in _parse_table_rows(table_html):
            joined = _collapse_spaces("".join(row))
            if joined.startswith("송장번호"):
                match = INVOICE_NO_PATTERN.search(joined)
                if match:
                    return match.group(0)
    return ""


def build_capture_records(raw_response: dict, material_type: str = "철근") -> list[dict]:
    records: list[dict] = []
    for page in find_cover_pages(raw_response):
        rows = extract_material_rows(raw_response, page)
        if not rows:
            continue
        vendor = find_vendor_heading(raw_response, page)
        delivery_date = find_delivery_date(raw_response, page)
        vehicle_no = find_vehicle_no(raw_response, page)
        invoice_no = find_invoice_no(raw_response, page)
        for row in rows:
            records.append(
                {
                    "material_type": material_type,
                    "vendor": vendor,
                    "delivery_date": delivery_date,
                    "vehicle_no": vehicle_no,
                    "invoice_no": invoice_no,
                    "item_name": material_type,
                    "spec": row["spec"],
                    "unit": "",
                    "quantity": None,
                    "weight": row["weight_kg"],
                    "note": row["note"],
                }
            )
    return records
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_report_parser.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/report_parser.py backend/tests/test_report_parser.py
git commit -m "feat: 갑지에서 차량번호/송장번호 추출 및 자재별 다중 레코드 빌더 추가"
```

---

### Task 2: `/ocr` 엔드포인트 — 갑지 감지 시 다중 레코드 반환

**Files:**
- Modify: `backend/app/routers/ocr.py`
- Test: `backend/tests/test_ocr_endpoint.py`

**Interfaces:**
- Consumes: `report_parser.find_cover_pages`, `report_parser.build_capture_records` (Task 1), 기존 `ocr.extract_text`, `ocr.normalize_fields`, `ocr.STANDARD_FIELDS`
- Produces: `POST /ocr` 응답이 `{"records": [dict, ...]}` 형태로 바뀜 (갑지면 레코드 여러 개, 아니면 `normalize_fields` 결과 1개짜리 배열, OCR 실패 시 빈 필드 1개짜리 배열)

- [ ] **Step 1: 기존 테스트를 새 응답 형식에 맞게 교체 + 갑지 테스트 추가**

`backend/tests/test_ocr_endpoint.py` 전체를 아래 내용으로 교체한다:

```python
from fastapi.testclient import TestClient

from app import ocr as ocr_module
from app.main import app

client = TestClient(app)


def _cover_table_html():
    return (
        "<table><thead><tr><td>직경</td><td>단위중량(kg/m)</td><td>발송중량(kg)</td>"
        "<td>할증중량(kg)</td><td>비고</td></tr></thead><tbody>"
        "<tr><td>SHD10</td><td>0.560</td><td>9401</td><td>9683</td><td>동국제강</td></tr>"
        "<tr><td>SHD13</td><td>0.995</td><td>17082</td><td>17594</td><td>동국제강</td></tr>"
        "<tr><td>총 합</td><td></td><td>26483</td><td></td><td></td></tr>"
        "</tbody></table>"
    )


def _cover_page_response():
    return {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>송장별 총괄 내역서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": _cover_table_html(), "text": ""}},
            {"page": 1, "category": "heading1", "content": {"html": "<h1>동경강업(주)</h1>", "text": ""}},
        ]
    }


def test_ocr_endpoint_returns_normalized_fields_for_free_form_document(monkeypatch):
    monkeypatch.setattr(ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": {"text": "거래처: 대한제강"})
    response = client.post("/ocr", files={"file": ("test.jpg", b"fake-image-bytes", "image/jpeg")})
    assert response.status_code == 200
    body = response.json()
    assert len(body["records"]) == 1
    assert body["records"][0]["vendor"] == "대한제강"


def test_ocr_endpoint_returns_blank_fields_on_failure(monkeypatch):
    def raise_error(*args, **kwargs):
        raise RuntimeError("network error")

    monkeypatch.setattr(ocr_module, "call_upstage_ocr", raise_error)
    response = client.post("/ocr", files={"file": ("test.jpg", b"fake-image-bytes", "image/jpeg")})
    assert response.status_code == 200
    body = response.json()
    assert len(body["records"]) == 1
    for field in ocr_module.STANDARD_FIELDS:
        assert body["records"][0][field] == ""


def test_ocr_endpoint_returns_multiple_records_for_cover_page_document(monkeypatch):
    monkeypatch.setattr(ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": _cover_page_response())
    response = client.post("/ocr", files={"file": ("cover.jpg", b"fake-image-bytes", "image/jpeg")})
    assert response.status_code == 200
    body = response.json()
    assert len(body["records"]) == 2
    specs = {record["spec"] for record in body["records"]}
    assert specs == {"SHD10", "SHD13"}
    for record in body["records"]:
        assert record["vendor"] == "동경강업(주)"
        assert record["material_type"] == "철근"
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_ocr_endpoint.py -v`
Expected: FAIL — 기존 두 테스트는 `body["records"]` 키가 없어서 `KeyError`, 새 테스트는 `AttributeError`나 `KeyError`

- [ ] **Step 3: `routers/ocr.py` 재작성**

`backend/app/routers/ocr.py` 전체를 아래 내용으로 교체한다:

```python
from fastapi import APIRouter, Depends, File, UploadFile

from .. import ocr, report_parser
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/ -v`
Expected: PASS (전체)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/routers/ocr.py backend/tests/test_ocr_endpoint.py
git commit -m "feat: 갑지 문서 촬영 시 자재별 다중 레코드를 반환하도록 /ocr 변경"
```

---

### Task 3: 프론트엔드 — 촬영/편집 화면을 다중 레코드 구조로 변경

**Files:**
- Modify: `frontend/src/pages/CapturePage.jsx`
- Modify: `frontend/src/pages/EditPage.jsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `runOcr(file)`가 이제 `{records: [...]}`를 반환함(Task 2), 기존 `createInvoice(fields, photoFile)` (변경 없음)
- Produces: 없음(최종 페이지)

- [ ] **Step 1: `CapturePage.jsx`에서 OCR 응답을 레코드 배열로 처리**

`frontend/src/pages/CapturePage.jsx`의 현재 전체 내용:

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
    <div className="page">
      <h1>송장 촬영</h1>
      <div className="card">
        <div className="field">
          <label>송장 사진 또는 PDF</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <label className="btn btn-primary photo-picker-add">
              📷 촬영
              <input
                className="photo-picker-input"
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleFileChange}
              />
            </label>
            <label className="btn btn-secondary photo-picker-add">
              📁 파일 선택
              <input
                className="photo-picker-input"
                type="file"
                accept="image/*,application/pdf"
                onChange={handleFileChange}
              />
            </label>
          </div>
        </div>
        {loading && <p className="banner banner-success">인식 중...</p>}
        {error && <p className="banner banner-error">{error}</p>}
      </div>
    </div>
  )
}
```

`handleFileChange` 함수만 아래 내용으로 교체(나머지는 그대로 유지):

```jsx
  async function handleFileChange(event) {
    const file = event.target.files[0]
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const { records } = await runOcr(file)
      navigate('/edit', { state: { records, photoFile: file } })
    } catch (err) {
      setError('인식에 실패했습니다. 직접 입력해주세요.')
      navigate('/edit', { state: { records: [{}], photoFile: file } })
    } finally {
      setLoading(false)
    }
  }
```

- [ ] **Step 2: `EditPage.jsx` 전면 재구성**

`frontend/src/pages/EditPage.jsx`의 현재 전체 내용:

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
    <div className="page">
      <h1>내용 확인 및 수정</h1>
      <div className="card">
        {FIELD_DEFS.map(([key, label]) => (
          <div key={key} className="field">
            <label>{label}</label>
            <input
              className="input"
              type="text"
              value={fields[key] || ''}
              onChange={(e) => handleChange(key, e.target.value)}
            />
          </div>
        ))}
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saving || !fields.material_type}
          style={{ width: '100%' }}
        >
          {saving ? '저장 중...' : '저장'}
        </button>
      </div>
    </div>
  )
}
```

아래 내용으로 전체 교체:

```jsx
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { createInvoice } from '../api.js'

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
  const [items, setItems] = useState(() =>
    initialRecords.map((record) => ({
      material_type: record.material_type || '',
      item_name: record.item_name || '',
      spec: record.spec || '',
      unit: record.unit || '',
      quantity: record.quantity ?? '',
      weight: record.weight ?? '',
      note: record.note || '',
    })),
  )
  const [saving, setSaving] = useState(false)

  function handleCommonChange(key, value) {
    setCommon((prev) => ({ ...prev, [key]: value }))
  }

  function handleItemChange(index, key, value) {
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, [key]: value } : item)))
  }

  function handleRemoveItem(index) {
    setItems((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleSave() {
    setSaving(true)
    try {
      for (const item of items) {
        await createInvoice({ ...common, ...item }, photoFile)
      }
      navigate('/search')
    } catch (err) {
      alert('저장에 실패했습니다. 다시 시도해주세요.')
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
        </div>
      ))}
      <button className="btn btn-primary" onClick={handleSave} disabled={saving || !canSave} style={{ width: '100%' }}>
        {saving ? '저장 중...' : `저장 (${items.length}건)`}
      </button>
    </div>
  )
}
```

- [ ] **Step 3: `styles.css`에 카드 그룹 라벨/삭제 버튼 스타일 추가**

`frontend/src/styles.css` 맨 끝(`.photo-thumb-remove` 규칙 뒤)에 다음을 추가한다:

```css
.field-group-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-muted);
  margin: 0 0 var(--space-sm);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.item-card {
  margin-bottom: var(--space-md);
}

.item-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-sm);
}

.item-remove {
  width: 24px;
  height: 24px;
  min-height: 0;
  padding: 0;
  border-radius: 50%;
  border: none;
  background: var(--color-error-bg);
  color: var(--color-error-text);
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
}
```

- [ ] **Step 4: 빌드 확인**

Run: `cd frontend && npm run build`
Expected: 에러 없이 빌드 성공

- [ ] **Step 5: 브라우저 프리뷰로 동작 확인**

Vite 개발 서버를 모바일 뷰포트로 띄우고, `sessionStorage.setItem('appPassword', 'dummy')`로 비밀번호 게이트를 우회한 뒤, `/edit` 경로에 아래와 같은 상태를 주입해서(개발자 도구 콘솔 또는 `window.history.replaceState` + React Router `state`를 통한 직접 네비게이션이 어렵다면, 임시로 `CapturePage`에서 실제 `runOcr` 대신 테스트용 더미 배열을 반환하도록 하지 않고, 브라우저 콘솔에서 `history.pushState`로 접근하는 대신 실제로는 `/` 페이지에서 실제 이미지 파일 업로드로 흐름을 태워 확인한다) 공통 정보 카드 1개 + 자재별 카드 여러 개가 렌더링되는지, 카드 삭제(X) 버튼이 동작하는지, 저장 버튼 라벨에 건수가 표시되는지 확인한다.

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/pages/CapturePage.jsx frontend/src/pages/EditPage.jsx frontend/src/styles.css
git commit -m "feat: 촬영 탭에서 갑지 문서 인식 시 자재별 다중 레코드 편집 화면 지원"
```

---

## 자체 점검 결과

- **스펙 커버리지**: 설계 문서의 `find_vehicle_no`/`find_invoice_no`/`build_capture_records`(Task 1), `/ocr` 응답 형식 변경 및 갑지 감지 분기(Task 2), 프론트엔드 공통정보+자재별 카드 구조 및 카드 삭제(Task 3)가 각 태스크에 매핑됨. 자유 양식 문서 처리(`normalize_fields`) 무변경과 범위 밖 항목(자재종류 고도화, 수량 자동 채움 안 함)은 Task 1/3의 구현 내용 자체가 이를 만족함(기본값 "철근", `unit`/`quantity` 공란).
- **플레이스홀더 스캔**: 모든 스텝에 실제 코드/명령어 포함. Task 3 Step 5는 자동화된 테스트가 아니라 수동 브라우저 확인 절차라 다소 서술적이지만, 이는 이 세션에서 반복적으로 써온 "프론트엔드 순수 UI 변경은 빌드+프리뷰로 검증" 패턴과 일치하며 실제 실행 가능한 대안(실제 파일 업로드로 흐름 확인)을 명시함.
- **타입/시그니처 일관성**: `build_capture_records`가 반환하는 dict의 키(`material_type, vendor, delivery_date, vehicle_no, invoice_no, item_name, spec, unit, quantity, weight, note`)가 Task 2의 `/ocr` 응답과 Task 3의 `EditPage.jsx`가 기대하는 필드명과 정확히 일치함.
