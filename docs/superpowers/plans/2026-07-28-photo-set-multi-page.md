# 사진대지 다중 세트(최대 5세트) 지원 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 자재검수요청서 엑셀의 사진대지 섹션(상단 사진 블록 + 하단 사진 블록, 6행짜리 세트)을 최대 5세트까지 반복 생성할 수 있게 한다. 사진이 있는 세트만 실제로 생성하고, 프론트엔드는 "+ 세트 추가" 버튼으로 최대 5개까지 늘어난다.

**Architecture:** `report_excel.py`에 템플릿의 81~86행(세트 1) 서식을 그대로 복제해 아래에 추가하는 헬퍼를 만들고, `fill_material_inspection_form`의 `top_photos`/`bottom_photos` 파라미터를 `photo_sets` 리스트로 교체한다. `routers/reports.py`는 세트별로 이름 붙은 10개의 폼 필드(`photo_set_N_top`/`photo_set_N_bottom`)를 받아 `photo_sets` 리스트로 조립한다. 프론트엔드는 세트 배열 상태와 "+ 세트 추가" 버튼으로 UI를 구성한다.

**Tech Stack:** FastAPI, openpyxl, pytest, React

## Global Constraints

- 세트가 정확히 1개(또는 0개)일 때는 행 삽입이 전혀 일어나지 않아 기존 동작과 완전히 동일해야 한다 — 하위 호환 필수.
- 사진이 하나도 없는 세트(top/bottom 둘 다 빈 리스트)는 건너뛰고 생성하지 않는다.
- 최대 5세트까지만 반영한다 — 6번째 세트부터는 무시한다.
- 세트별 공종명/위치/내용 텍스트는 커스터마이징하지 않는다 — 템플릿 기본값을 그대로 복제한다.

---

### Task 1: `report_excel.py` — 사진대지 세트 반복 생성 로직

**Files:**
- Modify: `backend/app/report_excel.py`
- Test: `backend/tests/test_report_excel.py`

**Interfaces:**
- Consumes: 기존 `report_photos.insert_photo_grid(sheet, anchor_row, photos)` (변경 없음)
- Produces: `fill_material_inspection_form(...)`의 `top_photos`/`bottom_photos` 파라미터가 `photo_sets: list[dict] | None = None`로 교체됨. 각 항목은 `{"top": list[bytes], "bottom": list[bytes]}` 형태.

- [ ] **Step 1: 기존 사진 테스트를 새 API에 맞게 교체 + 다중 세트 테스트 추가**

`backend/tests/test_report_excel.py`에서 `from datetime import date` 임포트 바로 아래에 다음 헬퍼를 추가한다:

```python
from PIL import Image as _PILImage


def _photo_bytes():
    img = _PILImage.new("RGB", (100, 100), (0, 255, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
```

`test_fill_material_inspection_form_inserts_top_and_bottom_photos`와 `test_fill_material_inspection_form_no_photos_means_no_images` 두 함수를 찾아 아래 내용으로 전체 교체한다(기존의 지역 함수 `_photo_bytes` 정의는 제거하고 위에서 새로 만든 모듈 레벨 헬퍼를 사용):

```python
def test_fill_material_inspection_form_inserts_top_and_bottom_photos():
    xlsx_bytes, _ = _fill(photo_sets=[{"top": [_photo_bytes(), _photo_bytes()], "bottom": [_photo_bytes()]}])
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert len(sheet._images) == 3


def test_fill_material_inspection_form_no_photos_means_no_images():
    xlsx_bytes, _ = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert len(sheet._images) == 0
```

파일 맨 아래에 다음 테스트들을 추가한다:

```python
def test_fill_material_inspection_form_single_set_matches_original_positions():
    xlsx_bytes, _ = _fill(photo_sets=[{"top": [_photo_bytes()], "bottom": [_photo_bytes()]}])
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["A80"].value == "사 진 대 지"
    assert sheet["H83"].value == "2026-03-31"
    assert sheet["H86"].value == "2026-03-31"
    assert len(sheet._images) == 2


def test_fill_material_inspection_form_creates_additional_rows_for_second_set():
    xlsx_bytes, _ = _fill(
        photo_sets=[
            {"top": [_photo_bytes()], "bottom": [_photo_bytes()]},
            {"top": [_photo_bytes()], "bottom": [_photo_bytes()]},
        ]
    )
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert len(sheet._images) == 4
    assert sheet["H89"].value == "2026-03-31"
    assert sheet["H92"].value == "2026-03-31"


def test_fill_material_inspection_form_skips_empty_sets():
    xlsx_bytes, _ = _fill(
        photo_sets=[
            {"top": [], "bottom": []},
            {"top": [_photo_bytes()], "bottom": []},
        ]
    )
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert len(sheet._images) == 1
    assert sheet["H83"].value == "2026-03-31"


def test_fill_material_inspection_form_caps_at_five_sets():
    photo_sets = [{"top": [_photo_bytes()], "bottom": []} for _ in range(7)]
    xlsx_bytes, _ = _fill(photo_sets=photo_sets)
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert len(sheet._images) == 5
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_report_excel.py -v`
Expected: FAIL — `fill_material_inspection_form() got an unexpected keyword argument 'photo_sets'` (기존 함수는 아직 `top_photos`/`bottom_photos`만 받음)

- [ ] **Step 3: `report_excel.py` 수정**

`backend/app/report_excel.py`의 임포트 부분을 아래로 교체한다:

```python
from copy import copy as copy_style
from datetime import date
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

from . import report_photos
```

`CHECKLIST_RESULT_ROWS = range(63, 80)` 줄 뒤에 다음 상수를 추가한다:

```python
PHOTO_SET_ROW_START = 81
PHOTO_SET_BLOCK_ROWS = 6
MAX_PHOTO_SETS = 5
```

`_build_material_spec_summary` 함수 뒤, `fill_material_inspection_form` 함수 앞에 다음 헬퍼를 추가한다:

```python
def _copy_photo_set_block(sheet, source_start: int, target_start: int) -> None:
    row_offset = target_start - source_start
    for offset in range(PHOTO_SET_BLOCK_ROWS):
        src_row = source_start + offset
        dst_row = target_start + offset
        sheet.row_dimensions[dst_row].height = sheet.row_dimensions[src_row].height
        for col in range(1, 11):
            src_cell = sheet.cell(row=src_row, column=col)
            dst_cell = sheet.cell(row=dst_row, column=col)
            dst_cell.value = src_cell.value
            dst_cell.font = copy_style(src_cell.font)
            dst_cell.border = copy_style(src_cell.border)
            dst_cell.fill = copy_style(src_cell.fill)
            dst_cell.alignment = copy_style(src_cell.alignment)
            dst_cell.number_format = src_cell.number_format

    for merged_range in list(sheet.merged_cells.ranges):
        if merged_range.min_row >= source_start and merged_range.max_row < source_start + PHOTO_SET_BLOCK_ROWS:
            min_col_letter = get_column_letter(merged_range.min_col)
            max_col_letter = get_column_letter(merged_range.max_col)
            new_min_row = merged_range.min_row + row_offset
            new_max_row = merged_range.max_row + row_offset
            sheet.merge_cells(f"{min_col_letter}{new_min_row}:{max_col_letter}{new_max_row}")
```

`fill_material_inspection_form`의 시그니처에서 이 두 줄을:

```python
    top_photos: list[bytes] | None = None,
    bottom_photos: list[bytes] | None = None,
```

아래로 교체한다:

```python
    photo_sets: list[dict] | None = None,
```

함수 본문 끝부분의 이 코드를:

```python
    sheet["H83"] = delivery_date
    sheet["H86"] = delivery_date

    report_photos.insert_photo_grid(sheet, anchor_row=81, photos=top_photos or [])
    report_photos.insert_photo_grid(sheet, anchor_row=84, photos=bottom_photos or [])

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue(), skipped_specs
```

아래로 교체한다:

```python
    photo_sets = photo_sets or []
    non_empty_sets = [s for s in photo_sets[:MAX_PHOTO_SETS] if s.get("top") or s.get("bottom")]

    for index, photo_set in enumerate(non_empty_sets):
        if index > 0:
            target_start = PHOTO_SET_ROW_START + index * PHOTO_SET_BLOCK_ROWS
            sheet.insert_rows(target_start, amount=PHOTO_SET_BLOCK_ROWS)
            _copy_photo_set_block(sheet, PHOTO_SET_ROW_START, target_start)
        top_anchor = PHOTO_SET_ROW_START + index * PHOTO_SET_BLOCK_ROWS
        bottom_anchor = top_anchor + 3
        sheet[f"H{top_anchor + 2}"] = delivery_date
        sheet[f"H{bottom_anchor + 2}"] = delivery_date
        report_photos.insert_photo_grid(sheet, anchor_row=top_anchor, photos=photo_set.get("top") or [])
        report_photos.insert_photo_grid(sheet, anchor_row=bottom_anchor, photos=photo_set.get("bottom") or [])

    if not non_empty_sets:
        sheet["H83"] = delivery_date
        sheet["H86"] = delivery_date

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue(), skipped_specs
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_report_excel.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 전체 백엔드 테스트 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/ -v`
Expected: FAIL — `backend/app/routers/reports.py`가 아직 `top_photos`/`bottom_photos`로 `fill_material_inspection_form`을 호출하고 있어 `test_reports_api.py`의 사진 관련 테스트가 실패함 (Task 2에서 해결)

- [ ] **Step 6: 커밋**

```bash
git add backend/app/report_excel.py backend/tests/test_report_excel.py
git commit -m "feat: 사진대지 세트를 최대 5개까지 반복 생성하도록 report_excel.py 확장"
```

---

### Task 2: `routers/reports.py` — 세트별 사진 업로드 필드 연결

**Files:**
- Modify: `backend/app/routers/reports.py`
- Test: `backend/tests/test_reports_api.py`

**Interfaces:**
- Consumes: `report_excel.fill_material_inspection_form(..., photo_sets=[...])` (Task 1)
- Produces: `POST /reports/material-inspection`가 `photo_set_1_top`/`photo_set_1_bottom` ~ `photo_set_5_top`/`photo_set_5_bottom` (전부 선택 사항) 폼 필드를 받는다. 기존 `top_photos`/`bottom_photos` 필드는 제거된다.

- [ ] **Step 1: 기존 사진 테스트를 새 필드명으로 교체 + 다중 세트 테스트 추가**

`backend/tests/test_reports_api.py`의 `test_create_report_accepts_photo_uploads` 함수 전체를 찾아 아래 내용으로 교체한다:

```python
def test_create_report_accepts_photo_uploads(monkeypatch):
    from io import BytesIO as _BytesIO

    from PIL import Image as _PILImage

    def _photo_bytes():
        img = _PILImage.new("RGB", (100, 100), (0, 255, 0))
        buf = _BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    monkeypatch.setattr(
        ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": _cover_response([("SHD10", 1000)])
    )

    response = client.post(
        "/reports/material-inspection",
        data=_form_fields(),
        files=[
            ("files", ("cover.jpg", b"fake-image-bytes", "image/jpeg")),
            ("photo_set_1_top", ("top1.png", _photo_bytes(), "image/png")),
            ("photo_set_1_bottom", ("bottom1.png", _photo_bytes(), "image/png")),
        ],
    )
    assert response.status_code == 200
    workbook = load_workbook(_BytesIO(response.content))
    sheet = workbook.active
    assert len(sheet._images) == 2
```

파일 맨 아래에 다음 테스트를 추가한다:

```python
def test_create_report_accepts_multiple_photo_sets(monkeypatch):
    from io import BytesIO as _BytesIO

    from PIL import Image as _PILImage

    def _photo_bytes():
        img = _PILImage.new("RGB", (100, 100), (0, 255, 0))
        buf = _BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    monkeypatch.setattr(
        ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": _cover_response([("SHD10", 1000)])
    )

    response = client.post(
        "/reports/material-inspection",
        data=_form_fields(),
        files=[
            ("files", ("cover.jpg", b"fake-image-bytes", "image/jpeg")),
            ("photo_set_1_top", ("s1top.png", _photo_bytes(), "image/png")),
            ("photo_set_2_top", ("s2top.png", _photo_bytes(), "image/png")),
            ("photo_set_2_bottom", ("s2bottom.png", _photo_bytes(), "image/png")),
        ],
    )
    assert response.status_code == 200
    workbook = load_workbook(_BytesIO(response.content))
    sheet = workbook.active
    assert len(sheet._images) == 3
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_reports_api.py -v`
Expected: FAIL — 라우터가 아직 `photo_set_1_top` 같은 필드를 받지 않아서 사진이 무시되고 `sheet._images`가 0이 되어 assert 실패

- [ ] **Step 3: `routers/reports.py` 수정**

`backend/app/routers/reports.py`에서 함수 시그니처의 이 두 줄을:

```python
    top_photos: List[UploadFile] = File(default=[]),
    bottom_photos: List[UploadFile] = File(default=[]),
```

아래로 교체한다:

```python
    photo_set_1_top: List[UploadFile] = File(default=[]),
    photo_set_1_bottom: List[UploadFile] = File(default=[]),
    photo_set_2_top: List[UploadFile] = File(default=[]),
    photo_set_2_bottom: List[UploadFile] = File(default=[]),
    photo_set_3_top: List[UploadFile] = File(default=[]),
    photo_set_3_bottom: List[UploadFile] = File(default=[]),
    photo_set_4_top: List[UploadFile] = File(default=[]),
    photo_set_4_bottom: List[UploadFile] = File(default=[]),
    photo_set_5_top: List[UploadFile] = File(default=[]),
    photo_set_5_bottom: List[UploadFile] = File(default=[]),
```

함수 본문의 이 두 줄을:

```python
    top_photo_bytes = [await photo.read() for photo in top_photos]
    bottom_photo_bytes = [await photo.read() for photo in bottom_photos]
```

아래로 교체한다:

```python
    photo_set_fields = [
        (photo_set_1_top, photo_set_1_bottom),
        (photo_set_2_top, photo_set_2_bottom),
        (photo_set_3_top, photo_set_3_bottom),
        (photo_set_4_top, photo_set_4_bottom),
        (photo_set_5_top, photo_set_5_bottom),
    ]
    photo_sets = []
    for top_files, bottom_files in photo_set_fields:
        top_bytes = [await photo.read() for photo in top_files]
        bottom_bytes = [await photo.read() for photo in bottom_files]
        photo_sets.append({"top": top_bytes, "bottom": bottom_bytes})
```

`fill_material_inspection_form` 호출부의 이 두 줄을:

```python
        top_photos=top_photo_bytes,
        bottom_photos=bottom_photo_bytes,
```

아래로 교체한다:

```python
        photo_sets=photo_sets,
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/ -v`
Expected: PASS (전체)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/routers/reports.py backend/tests/test_reports_api.py
git commit -m "feat: 보고서 생성 API가 세트별 사진 업로드 필드를 받도록 확장"
```

---

### Task 3: 프론트엔드 — 사진대지 세트 추가 UI

**Files:**
- Modify: `frontend/src/pages/ReportPage.jsx`
- Modify: `frontend/src/api.js`

**Interfaces:**
- Consumes: 백엔드가 이제 `photo_set_1_top` ~ `photo_set_5_bottom` 필드를 받음(Task 2)
- Produces: `createMaterialInspectionReport(fields, files, photoSets, deliveryDate)` — `topPhotos`/`bottomPhotos` 두 인자 대신 `photoSets: [{top: File[], bottom: File[]}]` 배열 하나로 교체(4개 인자로 축소)

- [ ] **Step 1: `api.js`의 `createMaterialInspectionReport` 시그니처 변경**

`frontend/src/api.js`에서 `createMaterialInspectionReport` 함수 전체를 찾아 아래 내용으로 교체한다:

```js
export async function createMaterialInspectionReport(fields, files, photoSets = [], deliveryDate = '') {
  const formData = new FormData()
  Object.entries(fields).forEach(([key, value]) => {
    formData.append(key, value)
  })
  files.forEach((file) => {
    formData.append('files', file)
  })
  const nonEmptySets = photoSets.filter((set) => set.top.length > 0 || set.bottom.length > 0)
  nonEmptySets.forEach((set, index) => {
    const setNumber = index + 1
    set.top.forEach((file) => {
      formData.append(`photo_set_${setNumber}_top`, file)
    })
    set.bottom.forEach((file) => {
      formData.append(`photo_set_${setNumber}_bottom`, file)
    })
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

- [ ] **Step 2: `ReportPage.jsx`에 사진대지 세트 배열 + "+ 세트 추가" UI 적용**

`frontend/src/pages/ReportPage.jsx`의 현재 전체 내용:

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

아래 내용으로 전체 교체:

```jsx
import { useState } from 'react'
import PhotoPicker from '../components/PhotoPicker.jsx'
import { createMaterialInspectionReport } from '../api.js'

const MAX_PHOTO_SETS = 5

export default function ReportPage() {
  const [mode, setMode] = useState('file')
  const [projectName, setProjectName] = useState('서소문 재개발')
  const [workType, setWorkType] = useState('건축')
  const [materialType, setMaterialType] = useState('철근')
  const [sender, setSender] = useState('')
  const [receiver, setReceiver] = useState('')
  const [files, setFiles] = useState([])
  const [deliveryDate, setDeliveryDate] = useState('')
  const [photoSets, setPhotoSets] = useState([{ top: [], bottom: [] }])
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [generating, setGenerating] = useState(false)

  const effectiveMaterialType = mode === 'date' ? '철근' : materialType
  const canSubmit = mode === 'file' ? files.length > 0 : !!deliveryDate

  function handleAddPhotoSet() {
    setPhotoSets((prev) => (prev.length < MAX_PHOTO_SETS ? [...prev, { top: [], bottom: [] }] : prev))
  }

  function handleSetTopChange(index, newFiles) {
    setPhotoSets((prev) => prev.map((set, i) => (i === index ? { ...set, top: newFiles } : set)))
  }

  function handleSetBottomChange(index, newFiles) {
    setPhotoSets((prev) => prev.map((set, i) => (i === index ? { ...set, bottom: newFiles } : set)))
  }

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
        photoSets,
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
        {photoSets.map((set, index) => (
          <div key={index} className="card item-card">
            <p className="field-group-label">사진대지 {index + 1}세트</p>
            <PhotoPicker
              label={`사진대지 ${index + 1}세트 상단 사진 (선택, 여러 장 가능)`}
              accept="image/*"
              files={set.top}
              onFilesChange={(newFiles) => handleSetTopChange(index, newFiles)}
            />
            <PhotoPicker
              label={`사진대지 ${index + 1}세트 하단 사진 (선택, 여러 장 가능)`}
              accept="image/*"
              files={set.bottom}
              onFilesChange={(newFiles) => handleSetBottomChange(index, newFiles)}
            />
          </div>
        ))}
        {photoSets.length < MAX_PHOTO_SETS && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleAddPhotoSet}
            style={{ width: '100%', marginBottom: 16 }}
          >
            + 세트 추가
          </button>
        )}
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

- [ ] **Step 4: 브라우저 프리뷰로 세트 추가 동작 확인**

Vite 개발 서버를 띄우고 `sessionStorage.setItem('appPassword', 'dummy')`로 비밀번호 게이트를 우회한 뒤 `/report`로 이동해:
- 기본으로 "사진대지 1세트" 카드 하나만 보이는지
- "+ 세트 추가"를 누르면 "사진대지 2세트" 카드가 추가되는지, 5번 누르면 버튼이 사라지는지(5세트가 상한)
- 각 세트 카드 안에 상단/하단 PhotoPicker가 독립적으로 동작하는지

확인한다.

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/pages/ReportPage.jsx frontend/src/api.js
git commit -m "feat: 보고서 생성 화면에 사진대지 세트 추가(최대 5세트) 기능 적용"
```

---

## 자체 점검 결과

- **스펙 커버리지**: 세트 1개일 때 기존 동작과 동일(Task 1의 `if index > 0` 가드), 빈 세트 스킵(Task 1의 `non_empty_sets` 필터), 5세트 상한(Task 1의 `photo_sets[:MAX_PHOTO_SETS]`), 세트별 텍스트 커스터마이징 배제(템플릿 값 그대로 복제, 별도 입력란 없음), 프론트엔드 "+ 세트 추가" 최대 5개(Task 3의 `MAX_PHOTO_SETS` 체크)가 각 태스크에 매핑됨.
- **플레이스홀더 스캔**: 모든 스텝에 실제 코드/명령어 포함, "TODO"/"나중에" 등 표현 없음.
- **타입/시그니처 일관성**: `photo_sets` 파라미터 형태(`{"top": list[bytes], "bottom": list[bytes]}`)가 Task 1(`report_excel.py`)과 Task 2(`routers/reports.py`의 조립 로직)에서 동일하게 사용됨. 프론트엔드 `photoSets` 배열 형태(`{top: File[], bottom: File[]}`)가 Task 3의 `api.js`와 `ReportPage.jsx` 양쪽에서 일치함.
