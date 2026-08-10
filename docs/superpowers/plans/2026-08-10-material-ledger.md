# 주요자재 검사 및 수불부 자동 생성 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 검색 화면에서 선택한 철근 송장 기록으로 "주요자재 검사 및 수불부" 엑셀 장부(철근 시트)를 자동으로 채워 다운로드한다.

**Architecture:** 기존 `report_excel.py`/`routers/reports.py` 패턴을 그대로 따른다 — 저장소에 포함된 고정 템플릿을 openpyxl로 열어 특정 셀만 채운 사본을 반환한다. 커플러 시트는 이번 범위에서 제외한다(EA 수량 미저장).

**Tech Stack:** FastAPI, openpyxl, React, react-router-dom (기존 스택 그대로)

## Global Constraints

- 커플러(`item_name == "커플러"`) 및 자재종류가 철근이 아닌 기록은 채우기 대상에서 제외하고 경고로 안내한다.
- 템플릿의 F~P열(설계량/합격량/사용량/반출량/잔량 등 수식·기본값)은 절대 덮어쓰지 않는다 — B/C/D/G/Q/R만 쓴다.
- 파일명: `주요자재검사및수불부_YYMMDD.xlsx` (문서번호 없음).
- 검수자/담당감리원은 생성 화면에서 한 번만 입력받아 모든 행에 동일하게 채운다.

---

### Task 1: 수불부 템플릿 파일 저장 + `report_ledger.py` 핵심 채우기 함수

**Files:**
- Create: `backend/app/templates/material_ledger.xlsx` (사용자가 제공한 `(철근)(건축)주요자재 검사 및 수불부.xlsx` 그대로 복사)
- Create: `backend/app/report_ledger.py`
- Test: `backend/tests/test_report_ledger.py`

**Interfaces:**
- Produces: `fill_material_ledger(template_path: Path, invoices: list, inspector: str, supervisor: str) -> bytes` — `invoices`는 각 항목이 `.delivery_date`(date), `.spec`(str), `.weight`(float) 속성을 가진 객체 리스트(SQLAlchemy `models.Invoice` 인스턴스 또는 동일 속성을 가진 SimpleNamespace). 호출 전에 커플러/비철근 필터링과 날짜 정렬은 호출자(라우터)가 끝내둔 상태로 넘어온다고 가정한다 — 이 함수는 순서대로 7행부터 채우기만 한다.

- [ ] **Step 1: 템플릿 파일을 저장소에 복사**

```bash
cp "C:\Users\user\Downloads\(철근)(건축)주요자재 검사 및 수불부.xlsx" "backend/app/templates/material_ledger.xlsx"
```

- [ ] **Step 2: 실패하는 테스트 작성**

`backend/tests/test_report_ledger.py`:

```python
from datetime import date
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook

from app import report_ledger

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "app" / "templates" / "material_ledger.xlsx"


def _invoice(delivery_date, spec, weight):
    return SimpleNamespace(delivery_date=delivery_date, spec=spec, weight=weight)


def test_fill_material_ledger_writes_rows_in_order_starting_at_row_7():
    invoices = [
        _invoice(date(2026, 4, 20), "SHD10", 1.5),
        _invoice(date(2026, 4, 21), "SHD13", 2.75),
    ]
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, invoices, "김검수", "박감리")
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["철근"]

    assert sheet["B7"].value == 1
    assert sheet["C7"].value == date(2026, 4, 20)
    assert sheet["D7"].value == "SHD10"
    assert sheet["G7"].value == 1.5

    assert sheet["B8"].value == 2
    assert sheet["C8"].value == date(2026, 4, 21)
    assert sheet["D8"].value == "SHD13"
    assert sheet["G8"].value == 2.75


def test_fill_material_ledger_fills_inspector_and_supervisor_on_every_row():
    invoices = [
        _invoice(date(2026, 4, 20), "SHD10", 1.0),
        _invoice(date(2026, 4, 21), "SHD13", 2.0),
    ]
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, invoices, "김검수", "박감리")
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["철근"]

    assert sheet["Q7"].value == "김검수"
    assert sheet["R7"].value == "박감리"
    assert sheet["Q8"].value == "김검수"
    assert sheet["R8"].value == "박감리"


def test_fill_material_ledger_preserves_existing_formulas():
    # F~P열은 템플릿에 이미 있는 수식/기본값을 그대로 둬야 한다 — 덮어쓰지 않는다.
    invoices = [_invoice(date(2026, 4, 20), "SHD10", 1.0)]
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, invoices, "김검수", "박감리")
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["철근"]

    assert sheet["F7"].value == "=G7"
    assert sheet["H7"].value == '=IF(G7="","",(G7-J7))'


def test_fill_material_ledger_does_not_touch_coupler_sheet():
    invoices = [_invoice(date(2026, 4, 20), "SHD10", 1.0)]
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, invoices, "김검수", "박감리")
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["커플러"]

    assert sheet["B7"].value is None
    assert sheet["G7"].value is None


def test_fill_material_ledger_empty_invoices_writes_no_rows():
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, [], "김검수", "박감리")
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["철근"]

    assert sheet["B7"].value is None
```

- [ ] **Step 3: 테스트 실행해서 실패 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_report_ledger.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.report_ledger'`

- [ ] **Step 4: `report_ledger.py` 구현**

```python
from pathlib import Path

from openpyxl import load_workbook

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "material_ledger.xlsx"

LEDGER_ROW_START = 7
REBAR_SHEET_NAME = "철근"


def fill_material_ledger(template_path: Path, invoices: list, inspector: str, supervisor: str) -> bytes:
    from io import BytesIO

    wb = load_workbook(template_path)
    sheet = wb[REBAR_SHEET_NAME]

    for offset, invoice in enumerate(invoices):
        row = LEDGER_ROW_START + offset
        sheet[f"B{row}"] = offset + 1
        sheet[f"C{row}"] = invoice.delivery_date
        sheet[f"D{row}"] = invoice.spec
        sheet[f"G{row}"] = invoice.weight
        sheet[f"Q{row}"] = inspector
        sheet[f"R{row}"] = supervisor

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
```

- [ ] **Step 5: 테스트 실행해서 통과 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_report_ledger.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: 커밋**

```bash
git add backend/app/templates/material_ledger.xlsx backend/app/report_ledger.py backend/tests/test_report_ledger.py
git commit -m "feat: 주요자재 검사 및 수불부(철근 시트) 채우기 함수 추가"
```

---

### Task 2: `/reports/material-ledger` 엔드포인트

**Files:**
- Modify: `backend/app/routers/reports.py`
- Test: `backend/tests/test_ledger_api.py`

**Interfaces:**
- Consumes: `report_ledger.fill_material_ledger(template_path, invoices, inspector, supervisor) -> bytes` (Task 1), `crud.list_invoices_by_ids(db, invoice_ids) -> list[models.Invoice]` (기존 함수, `backend/app/crud.py`에 이미 존재).
- Produces: `POST /reports/material-ledger` — Form 필드 `invoice_ids`(콤마 구분 문자열, 필수), `inspector`(문자열, 선택, 기본값 ""), `supervisor`(문자열, 선택, 기본값 ""). 응답은 xlsx 파일 또는 400 에러.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_ledger_api.py`:

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
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    wb = load_workbook(BytesIO(response.content))
    sheet = wb["철근"]
    assert sheet["D7"].value == "SHD10"
    assert sheet["G7"].value == 1.5
    assert sheet["D8"].value == "SHD13"
    assert sheet["Q7"].value == "김검수"


def test_ledger_endpoint_sorts_by_delivery_date_ascending():
    id_later = _create_invoice(spec="SHD13", weight="1.0", delivery_date="2026-05-02")
    id_earlier = _create_invoice(spec="SHD10", weight="1.0", delivery_date="2026-05-01")

    response = client.post(
        "/reports/material-ledger",
        data={"invoice_ids": f"{id_later},{id_earlier}"},
    )
    assert response.status_code == 200
    wb = load_workbook(BytesIO(response.content))
    sheet = wb["철근"]
    assert sheet["D7"].value == "SHD10"
    assert sheet["D8"].value == "SHD13"


def test_ledger_endpoint_excludes_coupler_and_warns():
    rebar_id = _create_invoice(spec="SHD10", weight="1.0", item_name="철근")
    coupler_id = _create_invoice(spec="SHD10", weight="1.0", item_name="커플러")

    response = client.post(
        "/reports/material-ledger",
        data={"invoice_ids": f"{rebar_id},{coupler_id}"},
    )
    assert response.status_code == 200
    wb = load_workbook(BytesIO(response.content))
    sheet = wb["철근"]
    assert sheet["B8"].value is None  # 커플러 건은 채워지지 않음

    warnings_header = response.headers.get("x-report-warnings")
    assert warnings_header is not None
    assert "1건" in unquote(warnings_header)


def test_ledger_endpoint_400_when_no_rebar_records_remain():
    coupler_id = _create_invoice(spec="SHD10", weight="1.0", item_name="커플러")
    response = client.post(
        "/reports/material-ledger",
        data={"invoice_ids": str(coupler_id)},
    )
    assert response.status_code == 400
    assert "철근 자재 기록이 없습니다" in response.json()["detail"]


def test_ledger_endpoint_400_when_invoice_ids_missing():
    response = client.post("/reports/material-ledger", data={})
    assert response.status_code == 400


def test_ledger_endpoint_filename_and_is_protected_by_shared_password(monkeypatch):
    from app import config

    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    invoice_id = _create_invoice()
    response = client.post(
        "/reports/material-ledger",
        data={"invoice_ids": str(invoice_id)},
    )
    assert response.status_code == 401
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_ledger_api.py -v`
Expected: FAIL with 404 (라우트 없음)

- [ ] **Step 3: `routers/reports.py`에 엔드포인트 추가**

`backend/app/routers/reports.py` 상단 import에 `report_ledger` 추가:

```python
from .. import crud, ocr, report_excel, report_from_records, report_ledger, report_parser
```

파일 맨 아래에 추가:

```python
@router.post("/reports/material-ledger")
async def create_material_ledger(
    invoice_ids: str = Form(...),
    inspector: str = Form(""),
    supervisor: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        ids = [int(part) for part in invoice_ids.split(",") if part.strip()]
    except ValueError as error:
        raise HTTPException(status_code=400, detail="선택 항목 형식이 올바르지 않습니다") from error

    invoices = crud.list_invoices_by_ids(db, ids)
    if not invoices:
        raise HTTPException(status_code=400, detail="선택한 송장 기록을 찾을 수 없습니다")

    excluded_count = sum(
        1 for invoice in invoices if invoice.item_name == "커플러" or invoice.material_type != "철근"
    )
    rebar_invoices = sorted(
        (
            invoice
            for invoice in invoices
            if invoice.item_name != "커플러" and invoice.material_type == "철근"
        ),
        key=lambda invoice: invoice.delivery_date or date.min,
    )
    if not rebar_invoices:
        raise HTTPException(status_code=400, detail="선택한 기록 중 철근 자재 기록이 없습니다")

    xlsx_bytes = report_ledger.fill_material_ledger(
        report_ledger.TEMPLATE_PATH, rebar_invoices, inspector, supervisor
    )

    filename = f"주요자재검사및수불부_{date.today():%y%m%d}.xlsx"
    encoded_filename = quote(filename)
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"ledger.xlsx\"; filename*=UTF-8''{encoded_filename}"
        )
    }
    if excluded_count:
        headers["X-Report-Warnings"] = quote(
            f"커플러 또는 철근이 아닌 자재 {excluded_count}건은 수불부에서 제외했습니다"
        )

    return Response(
        content=xlsx_bytes,
        media_type=XLSX_MEDIA_TYPE,
        headers=headers,
    )
```

(`date`, `quote`, `Form`, `HTTPException`, `Session`, `Response`, `Depends`, `get_db`, `XLSX_MEDIA_TYPE`는 이 파일에 이미 import/정의되어 있음 — 그대로 재사용)

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_ledger_api.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 백엔드 전체 테스트 실행**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 모두 PASS (기존 214개 + 이번에 추가한 11개)

- [ ] **Step 6: 커밋**

```bash
git add backend/app/routers/reports.py backend/tests/test_ledger_api.py
git commit -m "feat: /reports/material-ledger 엔드포인트 추가"
```

---

### Task 3: 프론트엔드 — 검색 화면 버튼 + 수불부 생성 화면

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/pages/SearchPage.jsx`
- Create: `frontend/src/pages/LedgerPage.jsx`

**Interfaces:**
- Produces: `api.js`의 `createMaterialLedger(invoiceIds: number[], inspector: string, supervisor: string) -> Promise<{ blob: Blob, warnings: string|null, filename: string|null }>`

- [ ] **Step 1: `api.js`에 함수 추가**

`createMaterialInspectionReport` 함수 바로 아래에 추가:

```js
export async function createMaterialLedger(invoiceIds, inspector, supervisor) {
  const formData = new FormData()
  formData.append('invoice_ids', invoiceIds.join(','))
  if (inspector) formData.append('inspector', inspector)
  if (supervisor) formData.append('supervisor', supervisor)
  const response = await fetch(`${API_BASE}/reports/material-ledger`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  handleUnauthorized(response)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || '수불부 생성에 실패했습니다')
  }
  const blob = await response.blob()
  const encodedWarnings = response.headers.get('X-Report-Warnings')
  const warnings = encodedWarnings ? decodeURIComponent(encodedWarnings) : null
  const contentDisposition = response.headers.get('Content-Disposition') || ''
  const filenameMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)
  const filename = filenameMatch ? decodeURIComponent(filenameMatch[1]) : null
  return { blob, warnings, filename }
}
```

- [ ] **Step 2: `LedgerPage.jsx` 작성**

```jsx
import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { createMaterialLedger } from '../api.js'

export default function LedgerPage() {
  const location = useLocation()
  const invoiceIds = location.state?.invoiceIds ?? []
  const [inspector, setInspector] = useState('')
  const [supervisor, setSupervisor] = useState('')
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')

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
    } catch (err) {
      setError(err.message || '수불부 생성에 실패했습니다')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="page">
      <h1>주요자재 검사 및 수불부 생성</h1>
      <form className="card" onSubmit={handleSubmit}>
        {invoiceIds.length > 0 ? (
          <p className="banner banner-success">검색에서 선택한 {invoiceIds.length}건으로 수불부를 생성합니다.</p>
        ) : (
          <p className="banner banner-warning">
            검색 화면에서 항목을 선택한 뒤 "선택 항목으로 수불부 생성" 버튼으로 들어와주세요.
          </p>
        )}
        <div className="field">
          <label>검수자</label>
          <input className="input" value={inspector} onChange={(e) => setInspector(e.target.value)} />
        </div>
        <div className="field">
          <label>담당감리원</label>
          <input className="input" value={supervisor} onChange={(e) => setSupervisor(e.target.value)} />
        </div>
        <button
          className="btn btn-primary"
          type="submit"
          disabled={generating || invoiceIds.length === 0}
          style={{ width: '100%' }}
        >
          {generating ? '생성 중...' : '수불부 생성'}
        </button>
      </form>
      {error && <p className="banner banner-error">{error}</p>}
      {warning && <p className="banner banner-warning">{warning}</p>}
    </div>
  )
}
```

- [ ] **Step 3: `App.jsx`에 라우트/네비 추가**

```jsx
import { Link, Route, Routes } from 'react-router-dom'
import CapturePage from './pages/CapturePage.jsx'
import DetailPage from './pages/DetailPage.jsx'
import EditPage from './pages/EditPage.jsx'
import LedgerPage from './pages/LedgerPage.jsx'
import PasswordGate from './PasswordGate.jsx'
import ReportPage from './pages/ReportPage.jsx'
import SearchPage from './pages/SearchPage.jsx'

export default function App() {
  return (
    <PasswordGate>
      <div>
        <nav className="nav">
          <Link to="/">촬영</Link>
          <Link to="/search">검색</Link>
          <Link to="/report">보고서 생성</Link>
          <Link to="/ledger">수불부 생성</Link>
        </nav>
        <Routes>
          <Route path="/" element={<CapturePage />} />
          <Route path="/edit" element={<EditPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/invoices/:id" element={<DetailPage />} />
          <Route path="/report" element={<ReportPage />} />
          <Route path="/ledger" element={<LedgerPage />} />
        </Routes>
      </div>
    </PasswordGate>
  )
}
```

- [ ] **Step 4: `SearchPage.jsx` 선택 항목 액션 바에 버튼 추가**

`frontend/src/pages/SearchPage.jsx`의 기존 액션 바(`{selectedIds.length > 0 && (...)}`  블록) 안, "선택 항목으로 보고서 생성" 버튼 뒤에 추가:

```jsx
          <button
            className="btn btn-secondary"
            style={{ flex: 1 }}
            onClick={() => navigate('/ledger', { state: { invoiceIds: selectedIds } })}
          >
            선택 항목으로 수불부 생성 ({selectedIds.length})
          </button>
```

(버튼 3개가 되므로 flex:1 유지, 한 줄에 안 맞으면 `flex-wrap: wrap`을 액션 바 컨테이너 스타일에 추가)

- [ ] **Step 5: 프론트엔드 빌드 확인**

Run: `cd frontend && npm run build`
Expected: 빌드 성공, 에러 없음

- [ ] **Step 6: 브라우저로 수동 검증**

로컬 백엔드(포트 8000) + 프론트 dev 서버(포트 5173) 기동, 테스트 송장 2~3건 시딩 후:
1. `/search`에서 검색 → 체크박스로 선택 → "선택 항목으로 수불부 생성 (N)" 버튼 표시 확인
2. 클릭 → `/ledger`로 이동, "검색에서 선택한 N건으로..." 배너 확인
3. 검수자/담당감리원 입력 → "수불부 생성" 클릭
4. 다운로드된 파일명이 `주요자재검사및수불부_YYMMDD.xlsx` 형식인지 확인 (link.download 캡처 방식 재사용)
5. 커플러 품목 하나 섞어서 다시 시도 → 경고 배너 표시 확인

- [ ] **Step 7: 커밋 및 푸시**

```bash
git add frontend/src/api.js frontend/src/App.jsx frontend/src/pages/SearchPage.jsx frontend/src/pages/LedgerPage.jsx
git commit -m "feat: 검색 항목으로 주요자재 검사 및 수불부 생성 화면 추가"
git push origin master
```
