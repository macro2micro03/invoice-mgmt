# 자재검수요청서 엑셀 서식 전환 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `report_docx.py`(python-docx 기반 워드 생성)를 제거하고, 실제 서식 파일 `backend/app/templates/material_inspection_form.xlsx`를 열어 특정 셀만 채워 반환하는 `report_excel.py`로 완전히 대체한다. 반입일자 자동 추출과 사진대지 사진 삽입(격자 배치) 기능도 함께 추가한다.

**Architecture:** 기존 `report_parser.py`의 갑지 탐지/규격 합산/거래처 인식 로직은 그대로 재사용하고, 반입일자 추출 함수를 추가한다. 새 `report_excel.py` 모듈이 openpyxl로 템플릿을 로드해 텍스트/숫자 셀을 채우고, 새 `report_photos.py` 모듈이 사진 격자 배치 계산과 openpyxl 이미지 삽입을 담당한다. `routers/reports.py`는 이 두 모듈을 조합해 xlsx 바이트를 반환하도록 재작성한다. 프론트엔드는 사진대지용 업로드 입력 2개를 추가하고 다운로드 확장자를 `.xlsx`로 바꾼다.

**Tech Stack:** FastAPI, openpyxl, Pillow(PIL), pytest, React

## Global Constraints

- 데이터 추출/합산 로직(`report_parser.py`)은 그대로 재사용 — 갑지 탐지, 규격별 합산, 거래처 인식 함수는 변경하지 않는다(반입일자 추출만 신규 추가).
- `report_docx.py`와 `backend/tests/test_report_docx.py`는 완전히 삭제한다.
- 산출물은 `.xlsx`(media type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`)로 완전히 대체한다 — `.docx` 관련 코드/의존성을 남기지 않는다.
- 템플릿 경로: `backend/app/templates/material_inspection_form.xlsx` (이미 커밋되어 있음, 실제 예시 이름 포함 — 그대로 사용).
- 자재 내역 표는 최대 16행(9~24행)까지만 지원 — 초과분은 버리지 않고 `skipped_specs`로 응답 경고에 포함한다.
- 사진대지 상단(81행)/하단(84행) 블록은 각각 약 658×378px — 사진 격자는 `cols = ceil(sqrt(N))`, `rows = ceil(N/cols)`로 계산한다.
- 실제 원본 21페이지 PDF로 로컬 검증(Task 6)까지 마쳐야 완료로 간주한다.

---

### Task 1: `report_parser.py`에 반입일자 추출 추가

**Files:**
- Modify: `backend/app/report_parser.py`
- Test: `backend/tests/test_report_parser.py`

**Interfaces:**
- Consumes: 기존 `_parse_table_rows(table_html) -> list[list[str]]`, `_collapse_spaces(text) -> str`
- Produces: `find_delivery_date(raw_response: dict, page: int) -> str` (YYYY-MM-DD 또는 빈 문자열). `build_report_data(...)`의 반환 dict에 `"delivery_date": str` 키 추가(여러 갑지 중 최댓값, 못 찾으면 빈 문자열).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_report_parser.py` 파일 상단의 `make_cover_response` 헬퍼를 찾아 `delivery_date=None` 파라미터를 추가하도록 아래처럼 교체한다(기존 시그니처와 하위 호환 — 기존 호출부는 그대로 동작):

```python
def make_cover_response(page, vendor_heading, spec_weight_pairs, note="동국제강", delivery_date=None):
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
    return {"elements": elements}
```

(주의: 이 헬퍼가 파일 안에 이미 정의되어 있다면 helper 정의부 전체를 위 코드로 교체한다. `_table_html`은 기존 헬퍼를 그대로 사용한다.)

파일 맨 아래에 다음 테스트들을 추가한다:

```python
def test_find_delivery_date_extracts_first_date_from_info_table():
    info_table_html = (
        "<table><tbody>"
        "<tr><td>송</td><td>장 번 호 :</td><td>20260331-023 ( 97 회차 )</td></tr>"
        "<tr><td>도</td><td>착 일</td><td>: 2026-03-31 / 2026-03-31 연 락 처 : 김민영 철근부장</td></tr>"
        "</tbody></table>"
    )
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>송장별 총괄 내역서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": info_table_html, "text": ""}},
        ]
    }
    assert report_parser.find_delivery_date(raw, page=1) == "2026-03-31"


def test_find_delivery_date_returns_empty_when_not_found():
    raw = {
        "elements": [
            {"page": 1, "category": "table", "content": {"html": "<table><tbody></tbody></table>", "text": ""}},
        ]
    }
    assert report_parser.find_delivery_date(raw, page=1) == ""


def test_find_delivery_date_ignores_other_pages():
    info_table_html = (
        "<table><tbody>"
        "<tr><td>도</td><td>착 일</td><td>: 2026-03-31</td></tr>"
        "</tbody></table>"
    )
    raw = {
        "elements": [
            {"page": 2, "category": "table", "content": {"html": info_table_html, "text": ""}},
        ]
    }
    assert report_parser.find_delivery_date(raw, page=1) == ""


def test_build_report_data_uses_latest_delivery_date_across_pages():
    raw1 = make_cover_response(1, "동경강업(주)", [("SHD10", 675000)], delivery_date="2026-03-30")
    raw2 = make_cover_response(1, "동경강업(주)", [("SHD13", 2111000)], delivery_date="2026-03-31")
    data = report_parser.build_report_data([raw1, raw2])
    assert data["delivery_date"] == "2026-03-31"


def test_build_report_data_delivery_date_empty_when_not_found():
    raw = make_cover_response(1, "동경강업(주)", [("SHD10", 675000)])
    data = report_parser.build_report_data([raw])
    assert data["delivery_date"] == ""
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_report_parser.py -v`
Expected: FAIL — `AttributeError: module 'app.report_parser' has no attribute 'find_delivery_date'` 및 `KeyError: 'delivery_date'`

- [ ] **Step 3: `report_parser.py`에 반입일자 추출 로직 구현**

`backend/app/report_parser.py`에서 `TOTAL_ROW_LABELS` 정의 아래에 날짜 정규식 상수를 추가한다:

```python
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
```

`find_vendor_heading` 함수 뒤, `build_report_data` 함수 앞에 다음 함수를 추가한다:

```python
def find_delivery_date(raw_response: dict, page: int) -> str:
    for element in raw_response.get("elements", []):
        if element.get("category") != "table" or element.get("page") != page:
            continue
        table_html = element.get("content", {}).get("html", "")
        for row in _parse_table_rows(table_html):
            joined = _collapse_spaces("".join(row))
            if joined.startswith("도착일"):
                match = DATE_PATTERN.search(joined)
                if match:
                    return match.group(0)
    return ""
```

`build_report_data` 함수를 아래처럼 교체한다(반입일자 수집 로직 추가):

```python
def build_report_data(raw_responses: list[dict]) -> dict:
    totals: dict[str, float] = {}
    vendor = ""
    manufacturer = ""
    skipped_pages: list[int] = []
    cover_pages_found = 0
    delivery_dates: list[str] = []

    for raw_response in raw_responses:
        for page in find_cover_pages(raw_response):
            cover_pages_found += 1
            rows = extract_material_rows(raw_response, page)
            if not rows:
                skipped_pages.append(page)
                continue
            page_vendor = find_vendor_heading(raw_response, page)
            if page_vendor:
                vendor = page_vendor
            delivery_date = find_delivery_date(raw_response, page)
            if delivery_date:
                delivery_dates.append(delivery_date)
            for row in rows:
                totals[row["spec"]] = totals.get(row["spec"], 0.0) + row["weight_kg"]
                if row["note"] and not manufacturer:
                    manufacturer = row["note"]

    if cover_pages_found == 0:
        raise ValueError("송장별 총괄 내역서 페이지를 찾을 수 없습니다")

    specs = [
        {"spec": spec, "quantity_ton": round(weight_kg / 1000, 3)}
        for spec, weight_kg in sorted(totals.items())
    ]
    vendor_display = f"{vendor}/{manufacturer}" if vendor and manufacturer else vendor

    return {
        "specs": specs,
        "vendor": vendor_display,
        "skipped_pages": skipped_pages,
        "delivery_date": max(delivery_dates) if delivery_dates else "",
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_report_parser.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/report_parser.py backend/tests/test_report_parser.py
git commit -m "feat: 갑지에서 반입일자(도착일) 추출 로직 추가"
```

---

### Task 2: `report_excel.py` — 템플릿 텍스트/숫자 셀 채우기

**Files:**
- Create: `backend/app/report_excel.py`
- Test: `backend/tests/test_report_excel.py`

**Interfaces:**
- Consumes: `openpyxl.load_workbook`, 템플릿 파일 `backend/app/templates/material_inspection_form.xlsx` (이미 저장소에 존재)
- Produces: `TEMPLATE_PATH: Path` (모듈 상수), `fill_material_inspection_form(template_path, *, project_name: str, work_type: str, material_type: str, document_number: str, sender: str, receiver: str, specs: list[dict], vendor: str, delivery_date: str, top_photos: list[bytes] | None = None, bottom_photos: list[bytes] | None = None) -> tuple[bytes, list[dict]]` — 반환값은 `(엑셀 바이트, skipped_specs)`. (주의: `top_photos`/`bottom_photos` 파라미터는 이 Task에서는 시그니처에 추가하되 본문에서는 무시하지 않고 그대로 받기만 하며 실제 삽입 로직은 Task 3에서 구현한다. 이번 Task 테스트는 이 두 인자를 넘기지 않고 기본값(`None`)으로 호출한다.)

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_report_excel.py`를 새로 만든다:

```python
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

from app import report_excel

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "app" / "templates" / "material_inspection_form.xlsx"


def _make_specs():
    return [
        {"spec": "SHD10", "quantity_ton": 3.606},
        {"spec": "SHD13", "quantity_ton": 21.11},
    ]


def _fill(**overrides):
    kwargs = dict(
        template_path=TEMPLATE_PATH,
        project_name="테스트현장 신축공사",
        work_type="건축",
        material_type="철근",
        document_number="건축(자검)-철근-1호",
        sender="김현장",
        receiver="박감리",
        specs=_make_specs(),
        vendor="동경강업(주)/동국제강",
        delivery_date="2026-03-31",
    )
    kwargs.update(overrides)
    return report_excel.fill_material_inspection_form(**kwargs)


def test_fill_material_inspection_form_sets_header_fields():
    xlsx_bytes, skipped = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["B2"].value == "테스트현장 신축공사"
    assert sheet["B4"].value == "건축(자검)-철근-1호"
    assert sheet["C28"].value == " 김현장    (인)"
    assert sheet["H28"].value == " 박감리    (인)"
    assert skipped == []


def test_fill_material_inspection_form_marks_selected_work_type_checkbox():
    xlsx_bytes, _ = _fill(work_type="토목")
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert "토목 ■" in sheet["B3"].value
    assert "건축 □" in sheet["B3"].value


def test_fill_material_inspection_form_fills_material_rows():
    xlsx_bytes, _ = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["A9"].value == "철근"
    assert sheet["B9"].value == "SHD10"
    assert sheet["D9"].value == "Ton"
    assert sheet["E9"].value == 3.606
    assert sheet["F9"].value == "동경강업(주)/동국제강"
    assert sheet["B10"].value == "SHD13"
    assert sheet["E10"].value == 21.11


def test_fill_material_inspection_form_computes_summary_fields():
    xlsx_bytes, _ = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["H35"].value == "2026-03-31"
    assert sheet["H37"].value == "동경강업(주)/동국제강"
    assert sheet["H38"].value == "24.716 Ton"
    assert sheet["C39"].value == "철근 SHD10 외 1"
    assert sheet["H83"].value == "2026-03-31"
    assert sheet["H86"].value == "2026-03-31"


def test_fill_material_inspection_form_single_spec_summary_omits_count():
    xlsx_bytes, _ = _fill(specs=[{"spec": "SHD10", "quantity_ton": 3.606}])
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["C39"].value == "철근 SHD10"


def test_fill_material_inspection_form_clears_checklist_result_column():
    xlsx_bytes, _ = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    for row in range(63, 80):
        assert sheet[f"G{row}"].value is None


def test_fill_material_inspection_form_leaves_inspection_result_columns_blank():
    xlsx_bytes, _ = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["H9"].value is None
    assert sheet["I9"].value is None
    assert sheet["J9"].value is None


def test_fill_material_inspection_form_reports_skipped_specs_beyond_capacity():
    many_specs = [{"spec": f"SPEC{i}", "quantity_ton": 1.0} for i in range(20)]
    xlsx_bytes, skipped = _fill(specs=many_specs)
    assert len(skipped) == 4
    assert skipped[0]["spec"] == "SPEC16"
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["A24"].value == "철근"
    assert sheet["B24"].value == "SPEC15"
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_report_excel.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.report_excel'`

- [ ] **Step 3: `report_excel.py` 구현**

`backend/app/report_excel.py`를 새로 만든다:

```python
from datetime import date
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "material_inspection_form.xlsx"

MATERIAL_ROW_START = 9
MATERIAL_ROW_END = 24
MATERIAL_ROW_CAPACITY = MATERIAL_ROW_END - MATERIAL_ROW_START + 1

WORK_TYPE_CELL = "B3"
CHECKLIST_RESULT_ROWS = range(63, 80)


def _mark_work_type_checkbox(text: str, work_type: str) -> str:
    return text.replace(f"{work_type} □", f"{work_type} ■", 1)


def _format_ton(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _build_material_spec_summary(material_type: str, specs: list[dict]) -> str:
    if not specs:
        return material_type
    first_spec = specs[0]["spec"]
    remaining = len(specs) - 1
    if remaining <= 0:
        return f"{material_type} {first_spec}"
    return f"{material_type} {first_spec} 외 {remaining}"


def fill_material_inspection_form(
    template_path,
    *,
    project_name: str,
    work_type: str,
    material_type: str,
    document_number: str,
    sender: str,
    receiver: str,
    specs: list[dict],
    vendor: str,
    delivery_date: str,
    top_photos: list[bytes] | None = None,
    bottom_photos: list[bytes] | None = None,
) -> tuple[bytes, list[dict]]:
    workbook = load_workbook(template_path)
    sheet = workbook.active

    today = date.today().strftime("%Y-%m-%d")

    sheet["B2"] = project_name
    sheet[WORK_TYPE_CELL] = _mark_work_type_checkbox(str(sheet[WORK_TYPE_CELL].value or ""), work_type)
    sheet["B4"] = document_number
    sheet["G4"] = today
    sheet["G5"] = today

    fillable_specs = specs[:MATERIAL_ROW_CAPACITY]
    skipped_specs = specs[MATERIAL_ROW_CAPACITY:]
    for offset, spec_row in enumerate(fillable_specs):
        row = MATERIAL_ROW_START + offset
        sheet[f"A{row}"] = material_type
        sheet[f"B{row}"] = spec_row["spec"]
        sheet[f"D{row}"] = "Ton"
        sheet[f"E{row}"] = spec_row["quantity_ton"]
        sheet[f"F{row}"] = vendor

    sheet["C27"] = today
    sheet["H27"] = today
    sheet["C28"] = f" {sender}    (인)"
    sheet["H28"] = f" {receiver}    (인)"

    sheet["H35"] = delivery_date
    sheet["H36"] = today
    sheet["H37"] = vendor
    total_ton = round(sum(spec_row["quantity_ton"] for spec_row in specs), 3)
    sheet["H38"] = f"{_format_ton(total_ton)} Ton"
    sheet["C39"] = _build_material_spec_summary(material_type, specs)

    for row in CHECKLIST_RESULT_ROWS:
        sheet[f"G{row}"] = None

    sheet["H83"] = delivery_date
    sheet["H86"] = delivery_date

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue(), skipped_specs
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_report_excel.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/report_excel.py backend/tests/test_report_excel.py
git commit -m "feat: 자재검수요청서 엑셀 서식 채우기 모듈 추가"
```

---

### Task 3: 사진대지 사진 격자 삽입 (`report_photos.py`)

**Files:**
- Create: `backend/app/report_photos.py`
- Modify: `backend/app/report_excel.py`
- Test: `backend/tests/test_report_photos.py`
- Test: `backend/tests/test_report_excel.py` (사진 삽입 검증 추가)

**Interfaces:**
- Consumes: `report_excel.fill_material_inspection_form`의 기존 시그니처(Task 2에서 이미 `top_photos`/`bottom_photos` 파라미터를 받도록 되어 있음), `openpyxl.drawing.image.Image`, `PIL.Image`
- Produces: `report_photos.compute_grid(count: int) -> tuple[int, int]` (cols, rows), `report_photos.insert_photo_grid(worksheet, anchor_row: int, photos: list[bytes]) -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_report_photos.py`를 새로 만든다:

```python
from io import BytesIO

from openpyxl import Workbook
from PIL import Image

from app import report_photos


def _make_test_image_bytes(width=200, height=100, color=(255, 0, 0)):
    img = Image.new("RGB", (width, height), color)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def test_compute_grid_matches_expected_dimensions():
    assert report_photos.compute_grid(1) == (1, 1)
    assert report_photos.compute_grid(2) == (2, 1)
    assert report_photos.compute_grid(3) == (2, 2)
    assert report_photos.compute_grid(4) == (2, 2)
    assert report_photos.compute_grid(5) == (3, 2)
    assert report_photos.compute_grid(6) == (3, 2)


def test_insert_photo_grid_adds_correct_number_of_images():
    wb = Workbook()
    sheet = wb.active
    photos = [_make_test_image_bytes() for _ in range(3)]
    report_photos.insert_photo_grid(sheet, anchor_row=81, photos=photos)
    assert len(sheet._images) == 3


def test_insert_photo_grid_does_nothing_when_no_photos():
    wb = Workbook()
    sheet = wb.active
    report_photos.insert_photo_grid(sheet, anchor_row=81, photos=[])
    assert len(sheet._images) == 0


def test_insert_photo_grid_preserves_aspect_ratio_within_cell_bounds():
    wb = Workbook()
    sheet = wb.active
    photos = [_make_test_image_bytes(width=800, height=200)]
    report_photos.insert_photo_grid(sheet, anchor_row=81, photos=photos)
    image = sheet._images[0]
    assert image.width <= report_photos.BLOCK_WIDTH_PX
    assert image.height <= report_photos.BLOCK_HEIGHT_PX
    assert abs((image.width / image.height) - (800 / 200)) < 0.05
```

`backend/tests/test_report_excel.py` 맨 아래에 다음 테스트를 추가한다:

```python
def test_fill_material_inspection_form_inserts_top_and_bottom_photos():
    from io import BytesIO as _BytesIO

    from PIL import Image as _PILImage

    def _photo_bytes():
        img = _PILImage.new("RGB", (100, 100), (0, 255, 0))
        buf = _BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    xlsx_bytes, _ = _fill(top_photos=[_photo_bytes(), _photo_bytes()], bottom_photos=[_photo_bytes()])
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert len(sheet._images) == 3


def test_fill_material_inspection_form_no_photos_means_no_images():
    xlsx_bytes, _ = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert len(sheet._images) == 0
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_report_photos.py backend/tests/test_report_excel.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.report_photos'`

- [ ] **Step 3: `report_photos.py` 구현**

`backend/app/report_photos.py`를 새로 만든다:

```python
import math
from io import BytesIO

from openpyxl.drawing.image import Image as XLImage
from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, OneCellAnchor
from openpyxl.drawing.xdr import XDRPositiveSize2D
from openpyxl.utils.units import pixels_to_EMU
from PIL import Image as PILImage

BLOCK_WIDTH_PX = 658
BLOCK_HEIGHT_PX = 378


def compute_grid(count: int) -> tuple[int, int]:
    if count <= 0:
        return (0, 0)
    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)
    return (cols, rows)


def _resize_to_fit(image_bytes: bytes, max_width: int, max_height: int) -> tuple[bytes, int, int]:
    with PILImage.open(BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        ratio = min(max_width / img.width, max_height / img.height, 1.0)
        new_size = (max(1, round(img.width * ratio)), max(1, round(img.height * ratio)))
        resized = img.resize(new_size)
        buffer = BytesIO()
        resized.save(buffer, format="PNG")
        return buffer.getvalue(), new_size[0], new_size[1]


def insert_photo_grid(worksheet, anchor_row: int, photos: list[bytes]) -> None:
    if not photos:
        return

    cols, rows = compute_grid(len(photos))
    cell_width = BLOCK_WIDTH_PX // cols
    cell_height = BLOCK_HEIGHT_PX // rows

    for index, photo_bytes in enumerate(photos):
        col_index = index % cols
        row_index = index // cols
        resized_bytes, width, height = _resize_to_fit(photo_bytes, cell_width, cell_height)

        image = XLImage(BytesIO(resized_bytes))
        marker = AnchorMarker(
            col=0,
            colOff=pixels_to_EMU(col_index * cell_width),
            row=anchor_row - 1,
            rowOff=pixels_to_EMU(row_index * cell_height),
        )
        image.anchor = OneCellAnchor(
            _from=marker,
            ext=XDRPositiveSize2D(pixels_to_EMU(width), pixels_to_EMU(height)),
        )
        worksheet.add_image(image)
```

`backend/app/report_excel.py`를 수정한다. 우선 import 목록에 추가:

```python
from . import report_photos
```

`fill_material_inspection_form` 함수 안, `sheet["H86"] = delivery_date` 줄 다음(버퍼 저장 이전)에 다음을 추가한다:

```python
    report_photos.insert_photo_grid(sheet, anchor_row=81, photos=top_photos or [])
    report_photos.insert_photo_grid(sheet, anchor_row=84, photos=bottom_photos or [])
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_report_photos.py backend/tests/test_report_excel.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/report_photos.py backend/app/report_excel.py backend/tests/test_report_photos.py backend/tests/test_report_excel.py
git commit -m "feat: 사진대지 사진 격자 배치 삽입 기능 추가"
```

---

### Task 4: `routers/reports.py` 재작성 및 `report_docx.py` 삭제

**Files:**
- Modify: `backend/app/routers/reports.py`
- Delete: `backend/app/report_docx.py`
- Delete: `backend/tests/test_report_docx.py`
- Modify: `backend/tests/test_reports_api.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: `report_parser.build_report_data(raw_responses) -> dict` (Task 1에서 `delivery_date` 키 추가됨), `report_excel.fill_material_inspection_form(...) -> tuple[bytes, list[dict]]` (Task 2/3), `crud.get_next_report_number(db) -> int`
- Produces: `POST /reports/material-inspection` 엔드포인트가 `.xlsx` 바이트를 반환. 새 폼 필드 `top_photos`, `bottom_photos`(둘 다 선택, 여러 파일).

- [ ] **Step 1: 기존 docx 관련 파일 삭제**

```bash
git rm backend/app/report_docx.py backend/tests/test_report_docx.py
```

`backend/requirements.txt`에서 `python-docx` 줄을 찾아 삭제한다(파일을 열어 해당 줄만 제거).

- [ ] **Step 2: `test_reports_api.py`를 xlsx 기준으로 재작성**

`backend/tests/test_reports_api.py` 전체를 아래 내용으로 교체한다:

```python
from urllib.parse import unquote

from openpyxl import load_workbook
from io import BytesIO

from fastapi.testclient import TestClient

from app import ocr as ocr_module
from app.main import app

client = TestClient(app)


def _table_html(headers, rows):
    thead = "<tr>" + "".join(f"<td>{h}</td>" for h in headers) + "</tr>"
    tbody = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>"


def _cover_response(spec_weight_pairs, delivery_date="2026-03-31"):
    material_rows = [[spec, "0.560", str(kg), str(kg), "동국제강"] for spec, kg in spec_weight_pairs]
    total_kg = sum(kg for _, kg in spec_weight_pairs)
    table_html = _table_html(
        ["직경", "단위중량(kg/m)", "발송중량(kg)", "할증중량(kg)", "비고"],
        material_rows + [["총 합", "", str(total_kg), "", ""]],
    )
    info_table_html = (
        "<table><tbody>"
        f"<tr><td>도</td><td>착 일</td><td>: {delivery_date} / {delivery_date} 연 락 처 : 테스트</td></tr>"
        "</tbody></table>"
    )
    return {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>송장별 총괄 내역서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": table_html, "text": ""}},
            {"page": 1, "category": "heading1", "content": {"html": "<h1>가짜상사(주)</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": info_table_html, "text": ""}},
        ]
    }


def _cover_response_no_vendor(spec_weight_pairs):
    material_rows = [[spec, "0.560", str(kg), str(kg), "동국제강"] for spec, kg in spec_weight_pairs]
    total_kg = sum(kg for _, kg in spec_weight_pairs)
    table_html = _table_html(
        ["직경", "단위중량(kg/m)", "발송중량(kg)", "할증중량(kg)", "비고"],
        material_rows + [["총 합", "", str(total_kg), "", ""]],
    )
    return {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>송장별 총괄 내역서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": table_html, "text": ""}},
        ]
    }


def _cover_response_no_table():
    return {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>송장별 총괄 내역서</h1>", "text": ""}},
            {"page": 1, "category": "heading1", "content": {"html": "<h1>가짜상사(주)</h1>", "text": ""}},
        ]
    }


def _form_fields():
    return {
        "project_name": "테스트현장 신축공사",
        "work_type": "건축",
        "material_type": "철근",
        "sender": "김현장",
        "receiver": "박감리",
    }


XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_create_report_returns_xlsx(monkeypatch):
    monkeypatch.setattr(
        ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": _cover_response([("SHD10", 1000)])
    )

    response = client.post(
        "/reports/material-inspection",
        data=_form_fields(),
        files={"files": ("cover.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(XLSX_MEDIA_TYPE)
    workbook = load_workbook(BytesIO(response.content))
    sheet = workbook.active
    assert sheet["B2"].value == "테스트현장 신축공사"


def test_create_report_400_when_no_cover_page_found(monkeypatch):
    monkeypatch.setattr(ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": {"elements": []})

    response = client.post(
        "/reports/material-inspection",
        data=_form_fields(),
        files={"files": ("random.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 400
    assert "송장별 총괄 내역서" in response.json()["detail"]


def test_create_report_aggregates_multiple_uploaded_files(monkeypatch):
    responses = [
        _cover_response([("SHD10", 675)]),
        _cover_response([("SHD10", 2931)]),
    ]
    call_count = {"n": 0}

    def fake_ocr(image_bytes, filename="x"):
        result = responses[call_count["n"]]
        call_count["n"] += 1
        return result

    monkeypatch.setattr(ocr_module, "call_upstage_ocr", fake_ocr)

    response = client.post(
        "/reports/material-inspection",
        data=_form_fields(),
        files=[
            ("files", ("cover1.jpg", b"fake-1", "image/jpeg")),
            ("files", ("cover2.jpg", b"fake-2", "image/jpeg")),
        ],
    )
    assert response.status_code == 200
    assert call_count["n"] == 2


def test_create_report_is_protected_by_shared_password(monkeypatch):
    from app import config

    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    monkeypatch.setattr(
        ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": _cover_response([("SHD10", 1000)])
    )

    response = client.post(
        "/reports/material-inspection",
        data=_form_fields(),
        files={"files": ("cover.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 401


def test_create_report_content_disposition_korean_filename(monkeypatch):
    monkeypatch.setattr(
        ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": _cover_response([("SHD10", 1000)])
    )

    response = client.post(
        "/reports/material-inspection",
        data=_form_fields(),
        files={"files": ("cover.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200

    content_disposition = response.headers.get("content-disposition", "")

    assert "filename*=UTF-8''" in content_disposition
    assert 'filename="report.xlsx"' in content_disposition

    encoded_part = content_disposition.split("filename*=UTF-8''")[1]
    decoded_filename = unquote(encoded_part)

    assert decoded_filename.startswith("건축(자검)-철근-")
    assert decoded_filename.endswith("호.xlsx")


def test_create_report_no_warning_header_when_everything_parses_cleanly(monkeypatch):
    monkeypatch.setattr(
        ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": _cover_response([("SHD10", 1000)])
    )

    response = client.post(
        "/reports/material-inspection",
        data=_form_fields(),
        files={"files": ("cover.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    assert "x-report-warnings" not in response.headers


def test_create_report_warns_when_vendor_not_recognized(monkeypatch):
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_ocr",
        lambda image_bytes, filename="x": _cover_response_no_vendor([("SHD10", 1000)]),
    )

    response = client.post(
        "/reports/material-inspection",
        data=_form_fields(),
        files={"files": ("cover.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200

    warnings_header = response.headers.get("x-report-warnings")
    assert warnings_header is not None
    decoded = unquote(warnings_header)
    assert "거래처" in decoded


def test_create_report_warns_when_pages_skipped(monkeypatch):
    responses = [
        _cover_response([("SHD10", 1000)]),
        _cover_response_no_table(),
    ]
    call_count = {"n": 0}

    def fake_ocr(image_bytes, filename="x"):
        result = responses[call_count["n"]]
        call_count["n"] += 1
        return result

    monkeypatch.setattr(ocr_module, "call_upstage_ocr", fake_ocr)

    response = client.post(
        "/reports/material-inspection",
        data=_form_fields(),
        files=[
            ("files", ("cover1.jpg", b"fake-1", "image/jpeg")),
            ("files", ("cover2.jpg", b"fake-2", "image/jpeg")),
        ],
    )
    assert response.status_code == 200

    warnings_header = response.headers.get("x-report-warnings")
    assert warnings_header is not None
    decoded = unquote(warnings_header)
    assert "1개 페이지" in decoded


def test_create_report_warns_when_delivery_date_not_found(monkeypatch):
    responses = [_cover_response_no_vendor([("SHD10", 1000)])]

    def fake_ocr(image_bytes, filename="x"):
        return responses[0]

    monkeypatch.setattr(ocr_module, "call_upstage_ocr", fake_ocr)

    response = client.post(
        "/reports/material-inspection",
        data=_form_fields(),
        files={"files": ("cover.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200

    warnings_header = response.headers.get("x-report-warnings")
    assert warnings_header is not None
    decoded = unquote(warnings_header)
    assert "반입일자" in decoded


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
            ("top_photos", ("top1.png", _photo_bytes(), "image/png")),
            ("bottom_photos", ("bottom1.png", _photo_bytes(), "image/png")),
        ],
    )
    assert response.status_code == 200
    workbook = load_workbook(_BytesIO(response.content))
    sheet = workbook.active
    assert len(sheet._images) == 2
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_reports_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.report_docx'` (라우터가 아직 옛 모듈을 import함)

- [ ] **Step 4: `routers/reports.py` 재작성**

`backend/app/routers/reports.py` 전체를 아래 내용으로 교체한다:

```python
from typing import List
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import crud, ocr, report_excel, report_parser
from ..auth import verify_password
from ..database import get_db

router = APIRouter(dependencies=[Depends(verify_password)])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/reports/material-inspection")
async def create_material_inspection_report(
    project_name: str = Form(...),
    work_type: str = Form(...),
    material_type: str = Form(...),
    sender: str = Form(...),
    receiver: str = Form(...),
    files: List[UploadFile] = File(...),
    top_photos: List[UploadFile] = File(default=[]),
    bottom_photos: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
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
    document_number = f"건축(자검)-{material_type}-{report_number}호"

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

- [ ] **Step 5: 테스트 통과 확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/ -v`
Expected: PASS (전체 — report_docx 관련 테스트는 이미 삭제되었으므로 수집되지 않음)

- [ ] **Step 6: 커밋**

```bash
git add backend/app/routers/reports.py backend/tests/test_reports_api.py backend/requirements.txt
git commit -m "feat: 자재검수요청서 응답을 엑셀(.xlsx)로 전환, 사진대지 업로드 필드 추가"
```

---

### Task 5: 프론트엔드 — 사진 업로드 입력 추가 및 확장자 전환

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/pages/ReportPage.jsx`

**Interfaces:**
- Consumes: 백엔드 `POST /reports/material-inspection`이 이제 `top_photos`/`bottom_photos` 멀티파트 필드를 선택적으로 받고 `.xlsx`를 반환함(Task 4)
- Produces: `createMaterialInspectionReport(fields, files, topPhotos, bottomPhotos) -> Promise<{blob, warnings}>`

- [ ] **Step 1: `api.js`의 `createMaterialInspectionReport` 수정**

`frontend/src/api.js`에서 기존 `createMaterialInspectionReport` 함수 전체를 찾아 아래 내용으로 교체한다:

```js
export async function createMaterialInspectionReport(fields, files, topPhotos = [], bottomPhotos = []) {
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

- [ ] **Step 2: `ReportPage.jsx`에 사진 업로드 입력 추가 및 확장자 변경**

`frontend/src/pages/ReportPage.jsx` 전체를 아래 내용으로 교체한다:

```jsx
import { useState } from 'react'
import { createMaterialInspectionReport } from '../api.js'

export default function ReportPage() {
  const [projectName, setProjectName] = useState('')
  const [workType, setWorkType] = useState('건축')
  const [materialType, setMaterialType] = useState('')
  const [sender, setSender] = useState('')
  const [receiver, setReceiver] = useState('')
  const [files, setFiles] = useState([])
  const [topPhotos, setTopPhotos] = useState([])
  const [bottomPhotos, setBottomPhotos] = useState([])
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [generating, setGenerating] = useState(false)

  function handleFilesChange(event) {
    setFiles(Array.from(event.target.files))
  }

  function handleTopPhotosChange(event) {
    setTopPhotos(Array.from(event.target.files))
  }

  function handleBottomPhotosChange(event) {
    setBottomPhotos(Array.from(event.target.files))
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
    <div style={{ padding: 16 }}>
      <h1>자재검수요청서 생성</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label>
            공사명
            <input value={projectName} onChange={(e) => setProjectName(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>
            공종
            <select value={workType} onChange={(e) => setWorkType(e.target.value)}>
              <option value="건축">건축</option>
              <option value="토목">토목</option>
              <option value="기계">기계</option>
              <option value="전기">전기</option>
            </select>
          </label>
        </div>
        <div>
          <label>
            자재종류
            <input value={materialType} onChange={(e) => setMaterialType(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>
            발신자(현장대리인)
            <input value={sender} onChange={(e) => setSender(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>
            수신자(총괄관리원)
            <input value={receiver} onChange={(e) => setReceiver(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>
            송장 갑지 파일 (PDF 또는 이미지, 여러 장 가능)
            <input type="file" accept="application/pdf,image/*" multiple onChange={handleFilesChange} required />
          </label>
        </div>
        <div>
          <label>
            사진대지 상단 사진 (선택, 여러 장 가능)
            <input type="file" accept="image/*" multiple onChange={handleTopPhotosChange} />
          </label>
        </div>
        <div>
          <label>
            사진대지 하단 사진 (선택, 여러 장 가능)
            <input type="file" accept="image/*" multiple onChange={handleBottomPhotosChange} />
          </label>
        </div>
        <button type="submit" disabled={generating || files.length === 0}>
          {generating ? '생성 중...' : '보고서 생성'}
        </button>
      </form>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {warning && <p style={{ color: '#b8860b' }}>{warning}</p>}
    </div>
  )
}
```

- [ ] **Step 3: 프론트엔드 빌드 확인**

Run: `cd frontend && npm run build`
Expected: 빌드 성공, 에러 없음

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/api.js frontend/src/pages/ReportPage.jsx
git commit -m "feat: 사진대지 사진 업로드 입력 추가, 다운로드 확장자를 xlsx로 변경"
```

---

### Task 6: 실제 문서로 로컬 검증 및 README 업데이트

**Files:**
- Modify: `README.md` (또는 관련 기능 설명이 있는 문서)

**Interfaces:**
- Consumes: 완성된 전체 파이프라인(Task 1~5)
- Produces: 없음 (검증 + 문서 갱신)

- [ ] **Step 1: 백엔드 전체 테스트 재확인**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/ -v`
Expected: PASS (전체)

- [ ] **Step 2: 로컬 서버 기동**

Run: `cd backend && venv/Scripts/python.exe -m uvicorn app.main:app --reload` (백그라운드 실행)

- [ ] **Step 3: 실제 21페이지 원본 PDF로 수동 검증**

이전 라운드에서 사용한 실제 원본 PDF(`302. 철근-65.pdf`, 사용자 데스크톱 경로)를 이용해 프론트엔드 `/report` 화면에서 업로드 후 생성된 `.xlsx`를 열어 다음을 확인한다:
- `H35`(반입일자)가 실제 갑지 3부 중 가장 늦은 도착일과 일치하는지
- `H38`(반입량)이 이전 검증된 총합 `68.902 Ton`과 일치하는지
- `C39`(자재규격 요약)가 `"철근 SHD10 외 4"` 형태로 올바르게 나오는지
- `G63:G79`가 비어 있는지 (템플릿 예시값이 지워졌는지)
- 사진대지에 임의의 사진 2~3장을 상단/하단에 업로드했을 때 격자로 올바르게 배치되는지 (엑셀에서 육안 확인)

발견되는 문제가 있으면 관련 모듈(`report_parser.py`/`report_excel.py`/`report_photos.py`)을 수정하고 회귀 테스트를 추가한 뒤 재검증한다.

- [ ] **Step 4: README 갱신**

`README.md`에서 자재검수요청서 관련 기능 설명 섹션을 찾아, "워드(.docx) 자동 생성"으로 되어 있는 문구를 "엑셀(.xlsx) 서식 자동 채움 — 실제 서식 파일(`(Form)자재검수요청서.xlsx`)에 데이터를 채워 반환하며, 사진대지 상단/하단에 업로드한 사진을 격자로 자동 배치함"으로 갱신한다. (정확한 기존 문구는 README를 열어 확인 후 그 문맥에 맞게 자연스럽게 교체한다.)

- [ ] **Step 5: 커밋**

```bash
git add README.md
git commit -m "docs: 자재검수요청서 산출물이 엑셀 서식임을 반영"
```

---

## 자체 점검 결과

- **스펙 커버리지**: 설계 문서의 자동 채움 셀 매핑표(Task 2), 사진대지 삽입 규칙(Task 3), 반입일자 추출(Task 1), 아키텍처 변경/엔드포인트 필드(Task 4), 에러 처리(Task 4의 경고 로직), 테스트 전략(각 Task의 테스트), 범위 밖 항목(체크리스트/서명란 등은 건드리지 않음 — Task 2에서 해당 셀들을 아예 다루지 않음으로써 보장)을 모두 반영함.
- **플레이스홀더 스캔**: 모든 스텝에 실제 코드/명령어 포함, "TODO"/"나중에" 등 표현 없음.
- **타입/시그니처 일관성**: `fill_material_inspection_form`의 반환 타입 `tuple[bytes, list[dict]]`이 Task 2/3/4 전체에서 동일하게 사용됨. `report_photos.compute_grid`/`insert_photo_grid` 시그니처가 Task 3 정의와 Task 2 수정본에서 일치함.
