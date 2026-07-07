# 반입송장 → 자재검수요청서 자동 생성 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 반입송장 갑지(PDF 또는 사진 여러 장)를 업로드하면 규격별로 자동 합산해 "자재검수요청서/검수결과통보"와 동일한 표 레이아웃의 워드(.docx) 파일을 생성하는, 기존 앱과는 독립적인 새 기능을 만든다.

**Architecture:** 기존 `app.ocr.call_upstage_ocr`을 그대로 재사용해 업로드된 각 파일을 Upstage document-parse로 보낸다. 새 모듈 `app.report_parser`가 응답에서 "송장별 총괄 내역서" 제목의 페이지(갑지)를 찾아 규격별 표와 반입업체명을 뽑아 규격별로 합산한다. 새 모듈 `app.report_docx`가 python-docx로 결과를 채운 .docx를 생성해 반환한다. 프론트엔드는 새 화면 하나(다중 파일 업로드 + 1회성 입력 폼)로 이 흐름을 구동한다.

**Tech Stack:** 기존 FastAPI/SQLAlchemy/React 그대로, 신규 의존성 `python-docx`.

## Global Constraints

- 갑지 판별 기준: Upstage 응답의 `category == "heading1"` 요소 텍스트가 정확히 "송장별 총괄 내역서"인 페이지.
- 규격별 내역 표 판별 기준: `category == "table"` 요소의 파싱된 첫 행(헤더)에 "직경"이 포함된 표.
- 발송중량(kg)을 규격별로 합산한 뒤 1000으로 나눠 Ton으로 환산, 소수 3자리로 반올림.
- "총 합"/"총합" 행은 합산 대상에서 제외한다.
- 거래처 표시 형식: `"{반입업체명}/{제조회사명}"` (제조회사명이 없으면 반입업체명만). 반입업체명은 여러 갑지에서 다르면 **마지막으로 발견된 값**을 사용하고, 제조회사명(표의 "비고" 컬럼)은 **첫 번째로 발견된 비어있지 않은 값**을 사용한다.
- 갑지를 하나도 못 찾으면 `400` 에러 + 명확한 한국어 메시지 ("송장별 총괄 내역서 페이지를 찾을 수 없습니다"). 이 기능은 실패를 침묵 처리하지 않는다 (기존 `/ocr`의 "절대 막지 않는다" 원칙은 이 기능에 적용하지 않음).
- 문서번호 형식: `"건축(자검)-{자재종류}-{N}호"`, N은 DB에 저장된 마지막 값 +1.
- 이 기능은 `/ocr`, `/invoices` 등 기존 엔드포인트나 화면을 전혀 수정하지 않는다 (완전히 새로운 라우터/화면 추가).
- 새 라우터도 기존과 동일하게 공유 비밀번호 인증(`verify_password`) 대상이다.

---

### Task 1: 갑지 탐지 및 규격별 합산 로직 (`app/report_parser.py`)

**Files:**
- Create: `backend/app/report_parser.py`
- Test: `backend/tests/test_report_parser.py`

**Interfaces:**
- Consumes: `app.ocr._content_to_text(content: dict) -> str` (이미 존재하는 HTML→텍스트 헬퍼, page1/8 실제 응답 검증에 사용된 것과 동일)
- Produces:
  - `report_parser.COVER_TITLE: str` (= `"송장별 총괄 내역서"`)
  - `report_parser.find_cover_pages(raw_response: dict) -> list[int]`
  - `report_parser.extract_material_rows(raw_response: dict, page: int) -> list[dict]` (각 dict: `{"spec": str, "weight_kg": float, "note": str}`)
  - `report_parser.find_vendor_heading(raw_response: dict, page: int) -> str`
  - `report_parser.build_report_data(raw_responses: list[dict]) -> dict` (`{"specs": [{"spec": str, "quantity_ton": float}], "vendor": str, "skipped_pages": list[int]}`, 갑지를 하나도 못 찾으면 `ValueError` 발생)

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_report_parser.py`**

```python
import pytest

from app import report_parser


def _table_html(headers, rows):
    thead = "<tr>" + "".join(f"<td>{h}</td>" for h in headers) + "</tr>"
    tbody = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>"


def make_cover_response(page, vendor_heading, spec_weight_pairs, note="동국제강"):
    material_rows = [[spec, "0.560", str(kg), str(kg), note] for spec, kg in spec_weight_pairs]
    total_kg = sum(kg for _, kg in spec_weight_pairs)
    table_html = _table_html(
        ["직경", "단위중량(kg/m)", "발송중량(kg)", "할증중량(kg)", "비고"],
        material_rows + [["총 합", "", str(total_kg), "", ""]],
    )
    return {
        "elements": [
            {"page": page, "category": "heading1", "content": {"html": "<h1>송장별 총괄 내역서</h1>", "text": ""}},
            {"page": page, "category": "table", "content": {"html": table_html, "text": ""}},
            {"page": page, "category": "heading1", "content": {"html": f"<h1>{vendor_heading}</h1>", "text": ""}},
        ]
    }


def test_find_cover_pages_detects_matching_heading():
    raw = make_cover_response(1, "동경강업(주)", [("SHD10", 675)])
    assert report_parser.find_cover_pages(raw) == [1]


def test_find_cover_pages_ignores_other_headings():
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>자재검수 checklist</h1>", "text": ""}},
        ]
    }
    assert report_parser.find_cover_pages(raw) == []


def test_extract_material_rows_parses_table_and_skips_total_row():
    raw = make_cover_response(1, "동경강업(주)", [("SHD10", 675), ("SHD13", 21110)])
    rows = report_parser.extract_material_rows(raw, page=1)
    assert rows == [
        {"spec": "SHD10", "weight_kg": 675.0, "note": "동국제강"},
        {"spec": "SHD13", "weight_kg": 21110.0, "note": "동국제강"},
    ]


def test_extract_material_rows_handles_comma_thousand_separators():
    # 실제 Upstage 응답은 큰 숫자를 "21,110"처럼 천단위 콤마와 함께 인식한다.
    table_html = _table_html(
        ["직경", "단위중량(kg/m)", "발송중량(kg)", "할증중량(kg)", "비고"],
        [["SHD13", "0.995", "21,110", "21,743", "동국제강"], ["총 합", "", "21,110", "21,743", ""]],
    )
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>송장별 총괄 내역서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": table_html, "text": ""}},
        ]
    }
    rows = report_parser.extract_material_rows(raw, page=1)
    assert rows[0]["weight_kg"] == 21110.0


def test_find_vendor_heading_ignores_title_and_weight_heading():
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>송장별 총괄 내역서</h1>", "text": ""}},
            {"page": 1, "category": "heading1", "content": {"html": "<h1>송장중량 : 23,887</h1>", "text": ""}},
            {"page": 1, "category": "heading1", "content": {"html": "<h1>동 경 강 업 ( 주 )</h1>", "text": ""}},
        ]
    }
    assert report_parser.find_vendor_heading(raw, page=1) == "동경강업(주)"


def test_build_report_data_aggregates_across_multiple_files_by_spec():
    raw1 = make_cover_response(1, "동경강업(주)", [("SHD10", 675), ("SHD13", 21110)])
    raw2 = make_cover_response(1, "동경강업(주)", [("SHD10", 2931)])
    data = report_parser.build_report_data([raw1, raw2])
    specs = {row["spec"]: row["quantity_ton"] for row in data["specs"]}
    assert specs["SHD10"] == 3.606
    assert specs["SHD13"] == 21.11
    assert data["vendor"] == "동경강업(주)/동국제강"
    assert data["skipped_pages"] == []


def test_build_report_data_raises_when_no_cover_page_found():
    raw = {"elements": []}
    with pytest.raises(ValueError):
        report_parser.build_report_data([raw])


def test_build_report_data_records_skipped_pages_without_material_table():
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>송장별 총괄 내역서</h1>", "text": ""}},
        ]
    }
    data = report_parser.build_report_data([raw])
    assert data["specs"] == []
    assert data["skipped_pages"] == [1]
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd backend && venv\Scripts\python.exe -m pytest tests/test_report_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.report_parser'`

- [ ] **Step 3: `app/report_parser.py` 구현**

```python
import html
import re

from . import ocr

COVER_TITLE = "송장별 총괄 내역서"


def _collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _parse_table_rows(table_html: str) -> list[list[str]]:
    rows = []
    for tr_match in re.finditer(r"<tr>(.*?)</tr>", table_html, re.DOTALL):
        cells = re.findall(r"<td>(.*?)</td>", tr_match.group(1), re.DOTALL)
        cleaned = [html.unescape(re.sub(r"<[^>]+>", "", cell)).strip() for cell in cells]
        rows.append(cleaned)
    return rows


def find_cover_pages(raw_response: dict) -> list[int]:
    pages = set()
    for element in raw_response.get("elements", []):
        if element.get("category") != "heading1":
            continue
        text = ocr._content_to_text(element.get("content", {}))
        if text.strip() == COVER_TITLE:
            page = element.get("page")
            if page is not None:
                pages.add(page)
    return sorted(pages)


def _find_material_table_html(raw_response: dict, page: int) -> str:
    for element in raw_response.get("elements", []):
        if element.get("category") != "table" or element.get("page") != page:
            continue
        table_html = element.get("content", {}).get("html", "")
        rows = _parse_table_rows(table_html)
        if rows and rows[0] and "직경" in rows[0][0]:
            return table_html
    return ""


def extract_material_rows(raw_response: dict, page: int) -> list[dict]:
    table_html = _find_material_table_html(raw_response, page)
    if not table_html:
        return []
    rows = _parse_table_rows(table_html)
    header = rows[0]
    try:
        spec_idx = header.index("직경")
        weight_idx = next(i for i, cell in enumerate(header) if "발송중량" in cell)
    except (ValueError, StopIteration):
        return []
    note_idx = header.index("비고") if "비고" in header else None

    result = []
    for row in rows[1:]:
        if not row or not row[0].strip() or "총" in row[0]:
            continue
        spec = row[0].strip()
        if weight_idx >= len(row):
            continue
        weight_text = row[weight_idx].strip().replace(",", "")
        if not weight_text:
            continue
        try:
            weight_kg = float(weight_text)
        except ValueError:
            continue
        note = row[note_idx].strip() if note_idx is not None and note_idx < len(row) else ""
        result.append({"spec": spec, "weight_kg": weight_kg, "note": note})
    return result


def find_vendor_heading(raw_response: dict, page: int) -> str:
    candidate = ""
    for element in raw_response.get("elements", []):
        if element.get("category") != "heading1" or element.get("page") != page:
            continue
        text = ocr._content_to_text(element.get("content", {})).strip()
        if not text or text == COVER_TITLE or text.startswith("송장중량"):
            continue
        candidate = _collapse_spaces(text)
    return candidate


def build_report_data(raw_responses: list[dict]) -> dict:
    totals: dict[str, float] = {}
    vendor = ""
    manufacturer = ""
    skipped_pages: list[int] = []
    cover_pages_found = 0

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

    return {"specs": specs, "vendor": vendor_display, "skipped_pages": skipped_pages}
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `cd backend && venv\Scripts\python.exe -m pytest tests/test_report_parser.py -v`
Expected: 9개 테스트 모두 PASSED

- [ ] **Step 5: 커밋**

```bash
git add backend/app/report_parser.py backend/tests/test_report_parser.py
git commit -m "feat: 반입송장 갑지 탐지 및 규격별 합산 로직 추가"
```

---

### Task 2: 문서번호 자동 증가 (`ReportSequence` 모델 + CRUD)

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/crud.py`
- Test: `backend/tests/test_crud.py`

**Interfaces:**
- Consumes: `app.database.Base` (기존)
- Produces: `app.models.ReportSequence` (컬럼: `id`, `last_number`), `app.crud.get_next_report_number(db: Session) -> int`

- [ ] **Step 1: `app/models.py`에 `ReportSequence` 추가**

`backend/app/models.py` 맨 끝에 추가:

```python


class ReportSequence(Base):
    __tablename__ = "report_sequences"

    id = Column(Integer, primary_key=True)
    last_number = Column(Integer, nullable=False, default=0)
```

- [ ] **Step 2: 실패하는 테스트 작성 — `tests/test_crud.py`에 추가**

`backend/tests/test_crud.py` 맨 끝에 추가:

```python


def test_get_next_report_number_starts_at_one_and_increments(db_session):
    first = crud.get_next_report_number(db_session)
    second = crud.get_next_report_number(db_session)
    third = crud.get_next_report_number(db_session)
    assert first == 1
    assert second == 2
    assert third == 3
```

- [ ] **Step 3: 테스트 실행해서 실패 확인**

Run: `cd backend && venv\Scripts\python.exe -m pytest tests/test_crud.py -v`
Expected: FAIL — `AttributeError: module 'app.crud' has no attribute 'get_next_report_number'`

- [ ] **Step 4: `app/crud.py`에 함수 추가**

`backend/app/crud.py` 맨 끝에 추가:

```python


def get_next_report_number(db: Session) -> int:
    sequence = db.query(models.ReportSequence).filter(models.ReportSequence.id == 1).first()
    if sequence is None:
        sequence = models.ReportSequence(id=1, last_number=0)
        db.add(sequence)
    sequence.last_number += 1
    db.commit()
    db.refresh(sequence)
    return sequence.last_number
```

- [ ] **Step 5: 테스트 실행해서 통과 확인**

Run: `cd backend && venv\Scripts\python.exe -m pytest tests/ -v`
Expected: 전체 테스트 통과 (기존 테스트 포함, 새 테스트도 PASSED)

- [ ] **Step 6: 커밋**

```bash
git add backend/app/models.py backend/app/crud.py backend/tests/test_crud.py
git commit -m "feat: 자재검수요청서 문서번호 자동 증가 시퀀스 추가"
```

---

### Task 3: 워드(.docx) 생성 (`app/report_docx.py`)

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/report_docx.py`
- Test: `backend/tests/test_report_docx.py`

**Interfaces:**
- Consumes: Task 1의 `build_report_data`가 반환하는 `specs`(`list[{"spec": str, "quantity_ton": float}]`)와 `vendor`(str)
- Produces: `report_docx.generate_material_inspection_docx(*, project_name: str, work_type: str, material_type: str, document_number: str, sender: str, receiver: str, specs: list[dict], vendor: str) -> bytes`

- [ ] **Step 1: `requirements.txt`에 `python-docx` 추가**

`backend/requirements.txt`에 한 줄 추가 (파일 끝에):

```
python-docx==1.1.2
```

- [ ] **Step 2: 의존성 설치**

Run: `cd backend && venv\Scripts\python.exe -m pip install python-docx==1.1.2`
Expected: `Successfully installed python-docx-1.1.2`

- [ ] **Step 3: 실패하는 테스트 작성 — `tests/test_report_docx.py`**

```python
from io import BytesIO

from docx import Document

from app import report_docx


def _make_specs():
    return [
        {"spec": "SHD10", "quantity_ton": 3.606},
        {"spec": "SHD13", "quantity_ton": 21.11},
    ]


def _combined_text(doc: Document) -> str:
    paragraph_text = "\n".join(p.text for p in doc.paragraphs)
    table_text = "\n".join(
        cell.text for table in doc.tables for row in table.rows for cell in row.cells
    )
    return paragraph_text + "\n" + table_text


def test_generate_material_inspection_docx_contains_header_fields():
    docx_bytes = report_docx.generate_material_inspection_docx(
        project_name="테스트현장 신축공사",
        work_type="건축",
        material_type="철근",
        document_number="건축(자검)-철근-1호",
        sender="김현장",
        receiver="박감리",
        specs=_make_specs(),
        vendor="동경강업(주)/동국제강",
    )
    doc = Document(BytesIO(docx_bytes))
    combined = _combined_text(doc)
    assert "테스트현장 신축공사" in combined
    assert "건축" in combined
    assert "건축(자검)-철근-1호" in combined
    assert "김현장" in combined
    assert "박감리" in combined


def test_generate_material_inspection_docx_contains_material_rows_and_total():
    docx_bytes = report_docx.generate_material_inspection_docx(
        project_name="테스트현장",
        work_type="건축",
        material_type="철근",
        document_number="건축(자검)-철근-1호",
        sender="김현장",
        receiver="박감리",
        specs=_make_specs(),
        vendor="동경강업(주)/동국제강",
    )
    doc = Document(BytesIO(docx_bytes))
    combined = _combined_text(doc)
    assert "SHD10" in combined
    assert "3.606" in combined
    assert "SHD13" in combined
    assert "21.11" in combined
    assert "동경강업(주)/동국제강" in combined
    assert "24.716" in combined  # 3.606 + 21.11 합계
```

- [ ] **Step 4: 테스트 실행해서 실패 확인**

Run: `cd backend && venv\Scripts\python.exe -m pytest tests/test_report_docx.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.report_docx'`

- [ ] **Step 5: `app/report_docx.py` 구현**

```python
from datetime import date
from io import BytesIO

from docx import Document

MATERIAL_HEADERS = ["품명", "규격", "단위", "수량", "반입업체명/제조회사명", "검수결과", "검수자"]


def generate_material_inspection_docx(
    *,
    project_name: str,
    work_type: str,
    material_type: str,
    document_number: str,
    sender: str,
    receiver: str,
    specs: list[dict],
    vendor: str,
) -> bytes:
    today = date.today().strftime("%Y년 %m월 %d일")
    doc = Document()
    doc.add_heading("자재검수요청서/검수결과통보", level=1)

    info_table = doc.add_table(rows=5, cols=4)
    info_table.style = "Table Grid"
    info_rows = info_table.rows
    info_rows[0].cells[0].text = "공 사 명"
    info_rows[0].cells[1].text = project_name
    info_rows[0].cells[2].text = "승인구분"
    info_rows[0].cells[3].text = ""
    info_rows[1].cells[0].text = "공 종 명"
    info_rows[1].cells[1].text = work_type
    info_rows[1].cells[2].text = "문서번호"
    info_rows[1].cells[3].text = document_number
    info_rows[2].cells[0].text = "발 신 자"
    info_rows[2].cells[1].text = sender
    info_rows[2].cells[2].text = "접수일자"
    info_rows[2].cells[3].text = today
    info_rows[3].cells[0].text = "수 신 자"
    info_rows[3].cells[1].text = receiver
    info_rows[3].cells[2].text = "검수일자"
    info_rows[3].cells[3].text = today
    info_rows[4].cells[0].text = "검수위치"
    info_rows[4].cells[1].text = "현장 내"
    info_rows[4].cells[2].text = ""
    info_rows[4].cells[3].text = ""

    doc.add_paragraph("")

    material_table = doc.add_table(rows=1 + len(specs) + 1, cols=len(MATERIAL_HEADERS))
    material_table.style = "Table Grid"
    for cell, header_text in zip(material_table.rows[0].cells, MATERIAL_HEADERS):
        cell.text = header_text

    total_ton = 0.0
    for row_index, spec_row in enumerate(specs, start=1):
        cells = material_table.rows[row_index].cells
        cells[0].text = material_type
        cells[1].text = spec_row["spec"]
        cells[2].text = "Ton"
        cells[3].text = f"{spec_row['quantity_ton']:.3f}".rstrip("0").rstrip(".")
        cells[4].text = vendor
        cells[5].text = "적합"
        cells[6].text = ""
        total_ton += spec_row["quantity_ton"]

    total_cells = material_table.rows[-1].cells
    total_cells[0].text = material_type
    total_cells[1].text = "계"
    total_cells[2].text = "Ton"
    total_cells[3].text = f"{round(total_ton, 3):.3f}".rstrip("0").rstrip(".")

    doc.add_paragraph("")
    doc.add_paragraph(f"위 자재에 대하여 검수를 요청합니다.")
    doc.add_paragraph(f"검수 요청일: {today}    현장 대리인: {sender}")
    doc.add_paragraph(f"위 자재 검수결과를 통보합니다.")
    doc.add_paragraph(f"통보 일자: {today}    총괄 관리원: {receiver}")
    doc.add_paragraph("미승인 사유: ")
    doc.add_paragraph("처리 방안: ")
    doc.add_paragraph("붙임: 1. 반입송장 2. 사진대지")

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
```

**참고:** 수량 문자열은 `f"{value:.3f}".rstrip("0").rstrip(".")`로 끝의 불필요한 0을 제거한다 (예: `21.110` → `21.11`, `3.606` → `3.606` 그대로 유지). 테스트의 기대값(`"21.11"`, `"3.606"`)과 정확히 일치하도록 이 방식을 그대로 사용할 것.

- [ ] **Step 6: 테스트 실행해서 통과 확인**

Run: `cd backend && venv\Scripts\python.exe -m pytest tests/test_report_docx.py -v`
Expected: 2개 테스트 모두 PASSED

- [ ] **Step 7: 커밋**

```bash
git add backend/requirements.txt backend/app/report_docx.py backend/tests/test_report_docx.py
git commit -m "feat: 자재검수요청서 워드(.docx) 생성 추가"
```

---

### Task 4: API 라우터 연결 (`POST /reports/material-inspection`)

**Files:**
- Create: `backend/app/routers/reports.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_reports_api.py`

**Interfaces:**
- Consumes: `app.ocr.call_upstage_ocr`, `app.report_parser.build_report_data`, `app.crud.get_next_report_number`, `app.report_docx.generate_material_inspection_docx`, `app.auth.verify_password`
- Produces: `POST /reports/material-inspection` (multipart form: `project_name`, `work_type`, `material_type`, `sender`, `receiver` 텍스트 필드 + `files`(여러 개, PDF 또는 이미지)) → 성공 시 `.docx` 바이너리 응답(Content-Disposition 첨부파일), 갑지 미발견 시 `400`

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_reports_api.py`**

```python
from fastapi.testclient import TestClient

from app import ocr as ocr_module
from app.main import app

client = TestClient(app)


def _table_html(headers, rows):
    thead = "<tr>" + "".join(f"<td>{h}</td>" for h in headers) + "</tr>"
    tbody = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>"


def _cover_response(spec_weight_pairs):
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


def test_create_report_returns_docx(monkeypatch):
    monkeypatch.setattr(
        ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": _cover_response([("SHD10", 1000)])
    )

    response = client.post(
        "/reports/material-inspection",
        data=_form_fields(),
        files={"files": ("cover.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(response.content) > 0


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
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd backend && venv\Scripts\python.exe -m pytest tests/test_reports_api.py -v`
Expected: FAIL — `assert 404 == 200` (아직 `/reports/material-inspection` 라우트가 등록되지 않아 존재하지 않는 경로로 취급됨)

- [ ] **Step 3: `app/routers/reports.py` 작성**

```python
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import crud, ocr, report_docx, report_parser
from ..auth import verify_password
from ..database import get_db

router = APIRouter(dependencies=[Depends(verify_password)])

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.post("/reports/material-inspection")
async def create_material_inspection_report(
    project_name: str = Form(...),
    work_type: str = Form(...),
    material_type: str = Form(...),
    sender: str = Form(...),
    receiver: str = Form(...),
    files: List[UploadFile] = File(...),
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

    report_number = crud.get_next_report_number(db)
    document_number = f"건축(자검)-{material_type}-{report_number}호"

    docx_bytes = report_docx.generate_material_inspection_docx(
        project_name=project_name,
        work_type=work_type,
        material_type=material_type,
        document_number=document_number,
        sender=sender,
        receiver=receiver,
        specs=report_data["specs"],
        vendor=report_data["vendor"],
    )

    filename = f"{document_number}.docx"
    return Response(
        content=docx_bytes,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 4: `app/main.py`에 라우터 연결**

`backend/app/main.py`의 기존 임포트 줄:

```python
from .routers import invoices, ocr
```

을 다음으로 교체:

```python
from .routers import invoices, ocr, reports
```

그리고 기존:

```python
app.include_router(ocr.router)
app.include_router(invoices.router)
```

을 다음으로 교체:

```python
app.include_router(ocr.router)
app.include_router(invoices.router)
app.include_router(reports.router)
```

- [ ] **Step 5: 테스트 실행해서 통과 확인**

Run: `cd backend && venv\Scripts\python.exe -m pytest tests/ -v`
Expected: 전체 테스트 통과 (기존 테스트 포함, 새 테스트 4개도 PASSED)

- [ ] **Step 6: 커밋**

```bash
git add backend/app/routers/reports.py backend/app/main.py backend/tests/test_reports_api.py
git commit -m "feat: 자재검수요청서 생성 API 라우터 연결"
```

---

### Task 5: 프론트엔드 — 보고서 생성 화면

**Files:**
- Modify: `frontend/src/api.js`
- Create: `frontend/src/pages/ReportPage.jsx`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: 백엔드 `POST /reports/material-inspection` (Task 4), 기존 `frontend/src/api.js`의 `authHeaders()`/`handleUnauthorized()` 헬퍼
- Produces: `api.js`의 `createMaterialInspectionReport(fields: object, files: File[]) -> Promise<Blob>`

- [ ] **Step 1: `frontend/src/api.js`에 함수 추가**

`frontend/src/api.js` 맨 끝에 추가:

```js

export async function createMaterialInspectionReport(fields, files) {
  const formData = new FormData()
  Object.entries(fields).forEach(([key, value]) => {
    formData.append(key, value)
  })
  files.forEach((file) => {
    formData.append('files', file)
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
  return response.blob()
}
```

- [ ] **Step 2: `frontend/src/pages/ReportPage.jsx` 작성**

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
  const [error, setError] = useState('')
  const [generating, setGenerating] = useState(false)

  function handleFilesChange(event) {
    setFiles(Array.from(event.target.files))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setGenerating(true)
    try {
      const blob = await createMaterialInspectionReport(
        {
          project_name: projectName,
          work_type: workType,
          material_type: materialType,
          sender,
          receiver,
        },
        files,
      )
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `자재검수요청서-${materialType || '자재'}.docx`
      link.click()
      URL.revokeObjectURL(url)
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
        <div style={{ marginBottom: 8 }}>
          <label>
            공사명
            <input value={projectName} onChange={(e) => setProjectName(e.target.value)} style={{ display: 'block', width: '100%' }} />
          </label>
        </div>
        <div style={{ marginBottom: 8 }}>
          <label>
            공종명
            <select value={workType} onChange={(e) => setWorkType(e.target.value)} style={{ display: 'block', width: '100%' }}>
              <option value="건축">건축</option>
              <option value="토목">토목</option>
              <option value="기계">기계</option>
              <option value="전기">전기</option>
            </select>
          </label>
        </div>
        <div style={{ marginBottom: 8 }}>
          <label>
            자재종류
            <input value={materialType} onChange={(e) => setMaterialType(e.target.value)} style={{ display: 'block', width: '100%' }} />
          </label>
        </div>
        <div style={{ marginBottom: 8 }}>
          <label>
            발신자(현장대리인)
            <input value={sender} onChange={(e) => setSender(e.target.value)} style={{ display: 'block', width: '100%' }} />
          </label>
        </div>
        <div style={{ marginBottom: 8 }}>
          <label>
            수신자(총괄감리원)
            <input value={receiver} onChange={(e) => setReceiver(e.target.value)} style={{ display: 'block', width: '100%' }} />
          </label>
        </div>
        <div style={{ marginBottom: 8 }}>
          <label>
            반입송장 PDF 또는 갑지 사진 (여러 개 선택 가능)
            <input type="file" accept="application/pdf,image/*" multiple onChange={handleFilesChange} style={{ display: 'block' }} />
          </label>
        </div>
        <button type="submit" disabled={generating || files.length === 0}>
          {generating ? '생성 중...' : '보고서 생성'}
        </button>
      </form>
      {error && <p style={{ color: 'red' }}>{error}</p>}
    </div>
  )
}
```

- [ ] **Step 3: `frontend/src/App.jsx`에 라우트/네비 추가**

`backend/app/main.py`가 아니라 `frontend/src/App.jsx`에서, 기존:

```jsx
import { Link, Route, Routes } from 'react-router-dom'
import CapturePage from './pages/CapturePage.jsx'
import DetailPage from './pages/DetailPage.jsx'
import EditPage from './pages/EditPage.jsx'
import PasswordGate from './PasswordGate.jsx'
import SearchPage from './pages/SearchPage.jsx'
```

을 다음으로 교체 (`ReportPage` 임포트 추가):

```jsx
import { Link, Route, Routes } from 'react-router-dom'
import CapturePage from './pages/CapturePage.jsx'
import DetailPage from './pages/DetailPage.jsx'
import EditPage from './pages/EditPage.jsx'
import PasswordGate from './PasswordGate.jsx'
import ReportPage from './pages/ReportPage.jsx'
import SearchPage from './pages/SearchPage.jsx'
```

그리고 네비게이션의 기존:

```jsx
        <nav style={{ display: 'flex', gap: 12, padding: 12 }}>
          <Link to="/">촬영</Link>
          <Link to="/search">검색</Link>
        </nav>
```

을 다음으로 교체:

```jsx
        <nav style={{ display: 'flex', gap: 12, padding: 12 }}>
          <Link to="/">촬영</Link>
          <Link to="/search">검색</Link>
          <Link to="/report">보고서 생성</Link>
        </nav>
```

그리고 라우트 목록의 기존:

```jsx
        <Routes>
          <Route path="/" element={<CapturePage />} />
          <Route path="/edit" element={<EditPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/invoices/:id" element={<DetailPage />} />
        </Routes>
```

을 다음으로 교체:

```jsx
        <Routes>
          <Route path="/" element={<CapturePage />} />
          <Route path="/edit" element={<EditPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/invoices/:id" element={<DetailPage />} />
          <Route path="/report" element={<ReportPage />} />
        </Routes>
```

- [ ] **Step 4: 빌드로 문법 확인**

Run: `cd frontend && npm run build`
Expected: 에러 없이 빌드 성공

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/api.js frontend/src/pages/ReportPage.jsx frontend/src/App.jsx
git commit -m "feat: 자재검수요청서 생성 화면 추가"
```

---

### Task 6: 실제 Upstage API로 합성 갑지 검증 + README 문서화

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 1~5에서 만든 전체 파이프라인
- Produces: 없음 (수동 검증 + 운영 문서)

- [ ] **Step 1: 합성 갑지 이미지 생성**

실사용자의 실명/전화번호가 들어있지 않은 가짜 데이터로, 실제 문서와 같은 레이아웃(제목 "송장별 총괄 내역서" + 직경/단위중량/발송중량/할증중량/비고 표 + 반입업체명 큰 글씨)의 이미지를 하나 만든다 (Pillow와 한글 폰트 `C:\Windows\Fonts\malgun.ttf` 사용). 스크래치 디렉터리에 저장하고 저장소에는 커밋하지 않는다.

- [ ] **Step 2: 실제 Upstage API로 `/reports/material-inspection` 수동 호출**

`UPSTAGE_API_KEY` 환경변수를 설정한 채로 백엔드를 실행한 상태에서, 위 합성 이미지 1~2장을 `POST /reports/material-inspection`에 실제로 업로드해 응답으로 받은 .docx 파일을 열어 값(공사명/문서번호/규격/수량/거래처)이 기대한 대로 채워졌는지 확인한다.

- [ ] **Step 3: `README.md`에 새 기능 섹션 추가**

`README.md`의 "데이터 위치" 섹션 뒤(또는 "클라우드 배포" 섹션 앞)에 추가:

```markdown

## 자재검수요청서 자동 생성 (별도 기능)

기존 촬영/저장/검색 기능과 별개로, 반입송장(PDF 또는 갑지 사진 여러 장)을 규격별로 합산해 "자재검수요청서/검수결과통보" 서식의 워드(.docx) 파일을 자동 생성하는 화면이 `/report` 경로에 있습니다.

- 입력: 반입송장 PDF 1개(여러 갑지가 합쳐진 파일) 또는 갑지를 낱장으로 찍은 사진 여러 장 (섞어서 올려도 됩니다)
- 자동 인식 기준: 페이지 제목이 정확히 "송장별 총괄 내역서"인 페이지만 갑지로 인식합니다. 이 제목이 아니면 인식하지 못하니, 다른 형식의 반입송장이라면 제목을 확인해주세요.
- 자동 채움: 규격별 합산 수량(Ton), 거래처(반입업체명/제조회사명), 문서번호(자동 증가), 접수일자/검수일자(생성일)
- 사람이 직접 해야 하는 것: 승인구분, 검수결과(부적합인 경우), 서명, 인쇄 후 날인
```

- [ ] **Step 4: 커밋**

```bash
git add README.md
git commit -m "docs: 자재검수요청서 자동 생성 기능 문서화"
```

## Self-Review 요약

- **스펙 커버리지**: 갑지 탐지(Task 1), 규격별 합산 및 거래처 처리(Task 1), 문서번호 자동 증가(Task 2), 워드 생성(Task 3), API 통합 및 인증 적용(Task 4), 다중 파일(PDF+사진) 업로드 프론트엔드(Task 5), 실제 API 검증 및 문서화(Task 6) — 설계 문서의 모든 항목이 태스크로 매핑됨.
- **플레이스홀더 스캔**: 없음. 모든 스텝에 실제 코드/명령어 포함.
- **타입/시그니처 일관성**: `build_report_data`가 반환하는 `specs`/`vendor` 키 이름이 `report_docx.generate_material_inspection_docx`의 파라미터명과 `routers/reports.py`의 호출부에서 동일하게 사용됨을 확인. `verify_password` 의존성이 기존 `ocr.router`/`invoices.router`와 동일한 패턴으로 `reports.router`에도 적용됨.
