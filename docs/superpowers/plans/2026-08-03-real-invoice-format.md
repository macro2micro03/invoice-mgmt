# 실제 철근 납품 확인서 양식 인식 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `report_parser.py`의 다중 자재 갑지 인식 로직을 실제 현장 송장 양식("철근 납품 확인서" — 컬럼: 철근경/가공중량,Ton/할증(%)/로스감안중량,Ton/커플러/비고)에 맞게 전면 교체한다. 지금까지 가정했던 가상 양식("송장별 총괄 내역서")은 실제로 쓰이지 않으므로 완전히 대체한다.

**Architecture:** 제목 매칭은 공백을 무시하고 비교한다. 표 컬럼은 헤더 셀 텍스트("철근경"/"로스감안중량")로 찾아 컬럼 순서 변화에 안전하게 만든다. 납품일/송장번호/차량번호/공장명(거래처) 라벨 값은 더 이상 표 안쪽만 뒤지지 않고 `ocr.extract_text`로 얻은 문서 전체 텍스트에서, 라벨 글자 사이에 공백이 끼어 있어도(장식적 자간) 인식하고, 다음에 나오는 알려진 라벨 직전까지만 값으로 잡는 비탐욕적 정규식으로 추출한다. 로스감안중량 열은 이미 톤 단위이므로 `build_report_data`는 변환 없이 그대로 합산하고, `build_capture_records`는 기존 DB `Invoice.weight` 컬럼이 kg 단위라는 기존 계약을 지키기 위해 ×1000 해서 저장한다.

**Tech Stack:** Python, pytest, 정규식 기반 HTML 파싱(기존 방식 유지)

## Global Constraints

- 현장에서는 이 "철근 납품 확인서" 양식 하나만 실사용한다 — 옛 가상 양식 지원은 완전히 제거한다.
- `find_cover_pages`, `build_capture_records`, `build_report_data`의 반환 형태(딕셔너리 키/구조)는 그대로 유지한다 — 호출부(`routers/ocr.py`, `routers/reports.py`)는 수정하지 않는다.
- `로스감안중량,Ton` 값은 이미 톤 단위다 — `build_report_data`(파일 업로드 경로)는 변환 없이 그대로 합산하고, `build_capture_records`(DB 저장 경로)는 `Invoice.weight`가 kg 단위라는 기존 계약을 지키기 위해 ×1000 한다.
- 라벨 텍스트(예: "납품일", "송장번호")는 실제 Upstage 응답에서 글자 사이에 공백이 들어갈 수 있다(장식적 자간) — 라벨 매칭은 이 공백을 허용해야 한다.
- 표 셀이 `<br>` 없이 한 줄로 뭉쳐 나올 수 있다 — 라벨 값 추출은 다음에 나오는 알려진 라벨 직전까지만 잡아야 한다(탐욕적 캡처 금지).

---

### Task 1: `report_parser.py` 전면 교체 + 단위 테스트 재작성

**Files:**
- Modify: `backend/app/report_parser.py`
- Modify: `backend/tests/test_report_parser.py` (전체 교체)

**Interfaces:**
- Consumes: `ocr.extract_text(raw_response)`, `ocr._content_to_text(content)` (기존, 변경 없음)
- Produces: `find_cover_pages(raw_response) -> list[int]`, `extract_material_rows(raw_response, page) -> list[dict]`(각 항목 `{"spec": str, "weight_ton": float, "note": str}` — 필드명이 `weight_kg`에서 `weight_ton`으로 바뀜, Task 2에서 이 필드명 변경을 인지해야 함), `find_vendor_heading(raw_response, page) -> str`, `find_delivery_date(raw_response, page) -> str`, `find_vehicle_no(raw_response, page) -> str`, `find_invoice_no(raw_response, page) -> str`, `build_capture_records(raw_response, material_type="철근") -> list[dict]`(반환 딕셔너리 키는 기존과 동일: material_type/vendor/delivery_date/vehicle_no/invoice_no/item_name/spec/unit/quantity/weight/note — `weight`는 kg 단위), `build_report_data(raw_responses) -> dict`(반환 키 동일: specs/vendor/skipped_pages/delivery_date).

- [ ] **Step 1: 실패하는 테스트로 전체 교체**

`backend/tests/test_report_parser.py` 전체를 다음으로 교체:

```python
import pytest

from app import report_parser


def _table_html(headers, rows):
    thead = "<tr>" + "".join(f"<td>{h}</td>" for h in headers) + "</tr>"
    tbody = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>"


def _material_table_html(spec_weight_pairs, note="동국제강,현대제철"):
    rows = [[spec, "1.000", "3", str(weight_ton), "0", note] for spec, weight_ton in spec_weight_pairs]
    total_ton = round(sum(weight_ton for _, weight_ton in spec_weight_pairs), 3)
    rows.append(["계", str(total_ton), "", str(total_ton), "", ""])
    return _table_html(["철근경", "가공중량,Ton", "할증(%)", "로스감안중량,Ton", "커플러", "비고"], rows)


def make_cover_response(
    page,
    factory_name,
    spec_weight_pairs,
    note="동국제강,현대제철",
    delivery_date=None,
    vehicle_no=None,
    invoice_no=None,
    title="철근 납품 확인서",
):
    info_lines = [
        "공사명: 삼성물산-서소문빌딩재개발 현장",
        "공정명: 10차-지하1층 1-3구간 테두리보",
        "납품차수: 제 1 차",
    ]
    if delivery_date:
        info_lines.append(f"납품일: {delivery_date}")
    if invoice_no:
        info_lines.append(f"송장번호: {invoice_no}")
    if vehicle_no:
        info_lines.append(f"차량번호: {vehicle_no}")
    info_lines.append(f"공장명: {factory_name}")
    info_html = "<p>" + "<br>".join(info_lines) + "</p>"

    return {
        "elements": [
            {"page": page, "category": "heading1", "content": {"html": f"<h1>{title}</h1>", "text": ""}},
            {"page": page, "category": "paragraph", "content": {"html": info_html, "text": ""}},
            {
                "page": page,
                "category": "table",
                "content": {"html": _material_table_html(spec_weight_pairs, note), "text": ""},
            },
        ]
    }


def test_find_cover_pages_detects_matching_title():
    raw = make_cover_response(1, "(주)대건건철", [("SHD10", 0.544)])
    assert report_parser.find_cover_pages(raw) == [1]


def test_find_cover_pages_ignores_other_titles():
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>자재검수 checklist</h1>", "text": ""}},
        ]
    }
    assert report_parser.find_cover_pages(raw) == []


def test_find_cover_pages_detects_title_classified_as_paragraph():
    raw = {
        "elements": [
            {"page": 3, "category": "paragraph", "content": {"html": "<p>철근 납품 확인서</p>", "text": ""}},
        ]
    }
    assert report_parser.find_cover_pages(raw) == [3]


def test_find_cover_pages_tolerates_letter_spaced_title():
    # 실제 문서에서 제목이 장식적으로 자간이 벌어져 "철 근 납 품 확 인 서"처럼
    # 글자 사이에 공백이 들어간 채로 인식되는 경우가 있다.
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철 근 납 품 확 인 서</h1>", "text": ""}},
        ]
    }
    assert report_parser.find_cover_pages(raw) == [1]


def test_extract_material_rows_parses_table_and_skips_total_row():
    raw = make_cover_response(1, "(주)대건건철", [("SHD10", 0.544), ("SHD13", 1.531)])
    rows = report_parser.extract_material_rows(raw, page=1)
    assert rows == [
        {"spec": "SHD10", "weight_ton": 0.544, "note": "동국제강,현대제철"},
        {"spec": "SHD13", "weight_ton": 1.531, "note": "동국제강,현대제철"},
    ]


def test_extract_material_rows_handles_real_sample_four_specs():
    raw = make_cover_response(
        1,
        "(주)대건건철",
        [("SHD10", 0.544), ("SHD13", 1.531), ("UHD16", 0.177), ("UHD22", 5.801)],
    )
    rows = report_parser.extract_material_rows(raw, page=1)
    assert [row["spec"] for row in rows] == ["SHD10", "SHD13", "UHD16", "UHD22"]
    assert [row["weight_ton"] for row in rows] == [0.544, 1.531, 0.177, 5.801]


def test_extract_material_rows_skips_total_row_labeled_gye():
    table_html = _table_html(
        ["철근경", "가공중량,Ton", "할증(%)", "로스감안중량,Ton", "커플러", "비고"],
        [["SHD10", "0.528", "3", "0.544", "0", "동국제강"], ["계", "0.528", "", "0.544", "", ""]],
    )
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": table_html, "text": ""}},
        ]
    }
    rows = report_parser.extract_material_rows(raw, page=1)
    assert rows == [{"spec": "SHD10", "weight_ton": 0.544, "note": "동국제강"}]


def test_extract_material_rows_skips_total_row_labeled_chonghap_or_hapgye():
    for total_label in ("총합", "총계", "합계"):
        table_html = _table_html(
            ["철근경", "가공중량,Ton", "할증(%)", "로스감안중량,Ton", "커플러", "비고"],
            [["SHD10", "0.528", "3", "0.544", "0", "동국제강"], [total_label, "0.528", "", "0.544", "", ""]],
        )
        raw = {
            "elements": [
                {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
                {"page": 1, "category": "table", "content": {"html": table_html, "text": ""}},
            ]
        }
        rows = report_parser.extract_material_rows(raw, page=1)
        assert [row["spec"] for row in rows] == ["SHD10"], f"failed for total label {total_label!r}"


def test_extract_material_rows_uses_header_lookup_not_fixed_column_order():
    # 철근경/로스감안중량 컬럼 순서가 바뀌어도 헤더 텍스트로 찾아야 한다.
    table_html = _table_html(
        ["비고", "철근경", "로스감안중량,Ton"],
        [["동국제강", "SHD10", "0.544"], ["", "계", "0.544"]],
    )
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": table_html, "text": ""}},
        ]
    }
    rows = report_parser.extract_material_rows(raw, page=1)
    assert rows == [{"spec": "SHD10", "weight_ton": 0.544, "note": "동국제강"}]


def test_extract_material_rows_returns_empty_when_table_not_found():
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
        ]
    }
    assert report_parser.extract_material_rows(raw, page=1) == []


def test_find_vendor_heading_extracts_factory_name_label():
    raw = make_cover_response(1, "(주)대건건철", [("SHD10", 0.544)])
    assert report_parser.find_vendor_heading(raw, page=1) == "(주)대건건철"


def test_find_vendor_heading_tolerates_letter_spaced_label():
    raw = {
        "elements": [
            {
                "page": 1,
                "category": "paragraph",
                "content": {"html": "<p>공 장 명 : (주)대건건철<br>발 송 자 :</p>", "text": ""},
            },
        ]
    }
    assert report_parser.find_vendor_heading(raw, page=1) == "(주)대건건철"


def test_find_vendor_heading_returns_empty_when_not_found():
    raw = {"elements": []}
    assert report_parser.find_vendor_heading(raw, page=1) == ""


def test_find_delivery_date_extracts_date_from_label():
    raw = make_cover_response(1, "(주)대건건철", [("SHD10", 0.544)], delivery_date="2026-07-30")
    assert report_parser.find_delivery_date(raw, page=1) == "2026-07-30"


def test_find_delivery_date_returns_empty_when_not_found():
    raw = make_cover_response(1, "(주)대건건철", [("SHD10", 0.544)])
    assert report_parser.find_delivery_date(raw, page=1) == ""


def test_find_invoice_no_extracts_flexible_digit_count():
    for invoice_no in ("1178-001", "20260731-001"):
        raw = make_cover_response(1, "(주)대건건철", [("SHD10", 0.544)], invoice_no=invoice_no)
        assert report_parser.find_invoice_no(raw, page=1) == invoice_no


def test_find_invoice_no_returns_empty_when_not_found():
    raw = make_cover_response(1, "(주)대건건철", [("SHD10", 0.544)])
    assert report_parser.find_invoice_no(raw, page=1) == ""


def test_find_vehicle_no_extracts_plate_number():
    raw = make_cover_response(1, "(주)대건건철", [("SHD10", 0.544)], vehicle_no="서울85바3204")
    assert report_parser.find_vehicle_no(raw, page=1) == "서울85바3204"


def test_find_vehicle_no_returns_empty_when_blank():
    # 실제 샘플에서 차량번호 칸이 비어있는 경우 — 값이 없으므로 빈 문자열.
    raw = make_cover_response(1, "(주)대건건철", [("SHD10", 0.544)])
    assert report_parser.find_vehicle_no(raw, page=1) == ""


def test_labeled_values_do_not_bleed_into_next_label_when_concatenated():
    # 표/문단이 <br> 없이 한 줄로 뭉쳐 나오는 최악의 경우를 재현한다.
    # 탐욕적 정규식이면 "납품일" 값이 "송장번호" 값까지 삼켜버린다.
    info_html = "<p>납품일: 2026-07-30송장번호: 1178-001공장명: (주)대건건철</p>"
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {"page": 1, "category": "paragraph", "content": {"html": info_html, "text": ""}},
        ]
    }
    assert report_parser.find_delivery_date(raw, page=1) == "2026-07-30"
    assert report_parser.find_invoice_no(raw, page=1) == "1178-001"
    assert report_parser.find_vendor_heading(raw, page=1) == "(주)대건건철"


def test_build_capture_records_creates_one_record_per_spec_and_converts_ton_to_kg():
    raw = make_cover_response(
        1,
        "(주)대건건철",
        [("SHD10", 0.544), ("SHD13", 1.531)],
        note="동국제강,현대제철",
        delivery_date="2026-07-30",
        invoice_no="1178-001",
    )
    records = report_parser.build_capture_records(raw)
    assert len(records) == 2
    for record in records:
        assert record["material_type"] == "철근"
        assert record["item_name"] == "철근"
        assert record["vendor"] == "(주)대건건철"
        assert record["delivery_date"] == "2026-07-30"
        assert record["invoice_no"] == "1178-001"
        assert record["unit"] == ""
        assert record["quantity"] is None
        assert record["note"] == "동국제강,현대제철"

    weights = {record["spec"]: record["weight"] for record in records}
    # weight는 kg 단위로 저장해야 한다(Invoice.weight 컬럼의 기존 계약) — Ton * 1000.
    assert weights["SHD10"] == pytest.approx(544.0)
    assert weights["SHD13"] == pytest.approx(1531.0)


def test_build_capture_records_uses_custom_material_type():
    raw = make_cover_response(1, "(주)대건건철", [("SHD10", 0.544)])
    records = report_parser.build_capture_records(raw, material_type="H형강")
    assert records[0]["material_type"] == "H형강"
    assert records[0]["item_name"] == "H형강"


def test_build_capture_records_returns_empty_when_no_cover_page():
    raw = {"elements": []}
    assert report_parser.build_capture_records(raw) == []


def test_build_capture_records_only_uses_first_cover_page():
    page1 = make_cover_response(1, "(주)대건건철", [("SHD10", 0.544)], invoice_no="1178-001")
    page2 = make_cover_response(2, "다른공장(주)", [("SHD22", 5.0)], invoice_no="9999-002")
    raw = {"elements": page1["elements"] + page2["elements"]}

    records = report_parser.build_capture_records(raw)

    assert len(records) == 1
    assert records[0]["vendor"] == "(주)대건건철"
    assert records[0]["spec"] == "SHD10"
    specs = {record["spec"] for record in records}
    assert "SHD22" not in specs


def test_build_report_data_aggregates_across_multiple_files_by_spec_no_unit_conversion():
    raw1 = make_cover_response(1, "(주)대건건철", [("SHD10", 0.544), ("SHD13", 1.531)])
    raw2 = make_cover_response(1, "(주)대건건철", [("SHD10", 2.931)])
    data = report_parser.build_report_data([raw1, raw2])
    specs = {row["spec"]: row["quantity_ton"] for row in data["specs"]}
    assert specs["SHD10"] == pytest.approx(3.475)
    assert specs["SHD13"] == pytest.approx(1.531)
    assert data["vendor"] == "(주)대건건철/동국제강,현대제철"
    assert data["skipped_pages"] == []


def test_build_report_data_raises_when_no_cover_page_found():
    raw = {"elements": []}
    with pytest.raises(ValueError):
        report_parser.build_report_data([raw])


def test_build_report_data_records_skipped_pages_without_material_table():
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
        ]
    }
    data = report_parser.build_report_data([raw])
    assert data["specs"] == []
    assert data["skipped_pages"] == [1]


def test_build_report_data_uses_latest_delivery_date_across_pages():
    raw1 = make_cover_response(1, "(주)대건건철", [("SHD10", 0.544)], delivery_date="2026-07-29")
    raw2 = make_cover_response(1, "(주)대건건철", [("SHD13", 1.531)], delivery_date="2026-07-30")
    data = report_parser.build_report_data([raw1, raw2])
    assert data["delivery_date"] == "2026-07-30"


def test_build_report_data_delivery_date_empty_when_not_found():
    raw = make_cover_response(1, "(주)대건건철", [("SHD10", 0.544)])
    data = report_parser.build_report_data([raw])
    assert data["delivery_date"] == ""
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_report_parser.py -v`
Expected: 대부분 FAIL — 옛 로직이 새 양식("철근 납품 확인서", "철근경", "로스감안중량", `weight_ton` 키 등)을 인식하지 못함

- [ ] **Step 3: `report_parser.py` 전체 교체**

`backend/app/report_parser.py` 전체를 다음으로 교체:

```python
import html
import re

from . import ocr

COVER_TITLE = "철근납품확인서"

TOTAL_ROW_LABELS = {"총합", "총계", "합계", "계"}

DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
VEHICLE_NO_PATTERN = re.compile(r"[가-힣]{0,3}\d{2,3}[가-힣]\d{4}")
INVOICE_NO_PATTERN = re.compile(r"\d+-\d+")

# Upstage의 category 분류(heading1 vs paragraph)는 동일한 문서 안에서도
# 페이지마다 비결정적으로 갈리는 경우가 실제로 확인되었다. 제목 판별은
# heading1 하나만 신뢰하지 않고 paragraph도 함께 확인한다.
TITLE_CATEGORIES = {"heading1", "paragraph"}

# 라벨 값을 추출할 때 "다음 라벨 직전까지만" 잡기 위한 경계 목록.
# 표/문단이 <br> 없이 한 줄로 뭉쳐 나오는 경우, 탐욕적 정규식은 다음 라벨의
# 값까지 삼켜버리므로 이 목록으로 경계를 정한다.
_INFO_LABELS = (
    "공사명", "공정명", "납품차수", "납품일", "송장번호",
    "착지담당", "착지주소", "연락처", "차량번호", "운전자",
    "공장명", "발송자", "인수처", "인수자", "인수일", "상기",
)


def _collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _label_pattern(label: str) -> str:
    # 실제 문서에서 라벨 글자 사이에 장식적 공백이 들어가는 경우
    # ("납 품 일")를 허용하기 위해 글자 사이에 \s*를 끼워 넣는다.
    return r"\s*".join(re.escape(ch) for ch in label)


_LABEL_LOOKAHEAD = "|".join(
    _label_pattern(label) for label in sorted(_INFO_LABELS, key=len, reverse=True)
)


def _find_labeled_value(text: str, label: str) -> str:
    match = re.search(
        rf"{_label_pattern(label)}\s*[:：]?\s*(.+?)(?=\s*(?:{_LABEL_LOOKAHEAD})|$)",
        text,
    )
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


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
        if element.get("category") not in TITLE_CATEGORIES:
            continue
        text = ocr._content_to_text(element.get("content", {}))
        if _collapse_spaces(text.strip()) == COVER_TITLE:
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
        if rows and any("철근경" in _collapse_spaces(cell) for cell in rows[0]):
            return table_html
    return ""


def extract_material_rows(raw_response: dict, page: int) -> list[dict]:
    table_html = _find_material_table_html(raw_response, page)
    if not table_html:
        return []
    rows = _parse_table_rows(table_html)
    header = rows[0]
    try:
        spec_idx = next(i for i, cell in enumerate(header) if "철근경" in _collapse_spaces(cell))
        weight_idx = next(i for i, cell in enumerate(header) if "로스감안중량" in _collapse_spaces(cell))
    except StopIteration:
        return []
    note_idx = next((i for i, cell in enumerate(header) if "비고" in _collapse_spaces(cell)), None)

    result = []
    for row in rows[1:]:
        if not row or spec_idx >= len(row):
            continue
        spec = row[spec_idx].strip()
        if not spec or _collapse_spaces(spec) in TOTAL_ROW_LABELS:
            continue
        if weight_idx >= len(row):
            continue
        weight_text = row[weight_idx].strip().replace(",", "")
        if not weight_text:
            continue
        try:
            weight_ton = float(weight_text)
        except ValueError:
            continue
        note = row[note_idx].strip() if note_idx is not None and note_idx < len(row) else ""
        result.append({"spec": spec, "weight_ton": weight_ton, "note": note})
    return result


def find_vendor_heading(raw_response: dict, page: int) -> str:
    text = ocr.extract_text(raw_response)
    return _find_labeled_value(text, "공장명")


def find_delivery_date(raw_response: dict, page: int) -> str:
    text = ocr.extract_text(raw_response)
    value = _find_labeled_value(text, "납품일")
    match = DATE_PATTERN.search(value)
    return match.group(0) if match else ""


def find_vehicle_no(raw_response: dict, page: int) -> str:
    text = ocr.extract_text(raw_response)
    value = _find_labeled_value(text, "차량번호")
    match = VEHICLE_NO_PATTERN.search(value)
    return match.group(0) if match else ""


def find_invoice_no(raw_response: dict, page: int) -> str:
    text = ocr.extract_text(raw_response)
    value = _find_labeled_value(text, "송장번호")
    match = INVOICE_NO_PATTERN.search(value)
    return match.group(0) if match else ""


def build_capture_records(raw_response: dict, material_type: str = "철근") -> list[dict]:
    records: list[dict] = []
    for page in find_cover_pages(raw_response)[:1]:
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
                    # Invoice.weight 컬럼은 kg 단위(기존 계약) — 표는 Ton이므로 변환한다.
                    "weight": row["weight_ton"] * 1000,
                    "note": row["note"],
                }
            )
    return records


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
                totals[row["spec"]] = totals.get(row["spec"], 0.0) + row["weight_ton"]
                if row["note"] and not manufacturer:
                    manufacturer = row["note"]

    if cover_pages_found == 0:
        raise ValueError("철근 납품 확인서 페이지를 찾을 수 없습니다")

    specs = [
        {"spec": spec, "quantity_ton": round(weight_ton, 3)}
        for spec, weight_ton in sorted(totals.items())
    ]
    vendor_display = f"{vendor}/{manufacturer}" if vendor and manufacturer else vendor

    return {
        "specs": specs,
        "vendor": vendor_display,
        "skipped_pages": skipped_pages,
        "delivery_date": max(delivery_dates) if delivery_dates else "",
    }
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_report_parser.py -v`
Expected: PASS (전부 통과)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/report_parser.py backend/tests/test_report_parser.py
git commit -m "fix: 실제 철근 납품 확인서 양식(철근경/로스감안중량,Ton)으로 갑지 인식 로직 교체"
```

---

### Task 2: 통합 테스트 fixture를 새 양식으로 갱신

**Files:**
- Modify: `backend/tests/test_ocr_endpoint.py`
- Modify: `backend/tests/test_reports_api.py`

**Interfaces:**
- Consumes: Task 1에서 교체된 `report_parser.find_cover_pages`/`build_capture_records`/`build_report_data`(반환 형태는 동일하지만, 내부적으로 새 제목/컬럼명을 요구함)

이 두 파일은 `/ocr`과 `/reports/material-inspection` 엔드포인트를 통해 Task 1에서 교체된 파서를 실행하는 통합 테스트다. 옛 가상 양식("송장별 총괄 내역서", "직경", "발송중량(kg)") 기준의 fixture를 그대로 두면 Task 1 이후 `find_cover_pages`가 더 이상 그 제목을 인식하지 못해 커버리지 있는 테스트들이 깨진다. fixture만 새 양식으로 바꾸고, 테스트 본문(assert)은 이미 검증하려는 동작(레코드 수, 경고 문구 등)과 무관하므로 그대로 둔다.

- [ ] **Step 1: `test_ocr_endpoint.py`의 갑지 fixture 교체**

`backend/tests/test_ocr_endpoint.py`에서 `_cover_table_html`/`_cover_page_response` 함수를 다음으로 교체:

```python
def _cover_table_html():
    return (
        "<table><thead><tr><td>철근경</td><td>가공중량,Ton</td><td>할증(%)</td>"
        "<td>로스감안중량,Ton</td><td>커플러</td><td>비고</td></tr></thead><tbody>"
        "<tr><td>SHD10</td><td>0.528</td><td>3</td><td>0.544</td><td>0</td><td>동국제강</td></tr>"
        "<tr><td>SHD13</td><td>1.486</td><td>3</td><td>1.531</td><td>0</td><td>동국제강</td></tr>"
        "<tr><td>계</td><td>2.014</td><td></td><td>2.075</td><td></td><td></td></tr>"
        "</tbody></table>"
    )


def _cover_page_response():
    return {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": _cover_table_html(), "text": ""}},
            {
                "page": 1,
                "category": "paragraph",
                "content": {"html": "<p>공장명: 동경강업(주)</p>", "text": ""},
            },
        ]
    }
```

이 파일의 기존 테스트(`test_ocr_endpoint_returns_multiple_records_for_cover_page_document` 등)는 그대로 두되, 이 fixture 교체로 인해 다시 통과해야 한다(vendor는 여전히 "동경강업(주)", specs는 여전히 `{"SHD10", "SHD13"}`).

- [ ] **Step 2: `test_reports_api.py`의 갑지 fixture 교체**

`backend/tests/test_reports_api.py`에서 `_cover_response`/`_cover_response_no_vendor`/`_cover_response_no_table` 함수를 다음으로 교체:

```python
def _cover_response(spec_weight_pairs, delivery_date="2026-03-31"):
    material_rows = [[spec, "1.000", "3", str(weight), "0", "동국제강"] for spec, weight in spec_weight_pairs]
    total = sum(weight for _, weight in spec_weight_pairs)
    table_html = _table_html(
        ["철근경", "가공중량,Ton", "할증(%)", "로스감안중량,Ton", "커플러", "비고"],
        material_rows + [["계", str(total), "", str(total), "", ""]],
    )
    info_html = f"<p>납품일: {delivery_date}<br>공장명: 가짜상사(주)</p>"
    return {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": table_html, "text": ""}},
            {"page": 1, "category": "paragraph", "content": {"html": info_html, "text": ""}},
        ]
    }


def _cover_response_no_vendor(spec_weight_pairs):
    material_rows = [[spec, "1.000", "3", str(weight), "0", "동국제강"] for spec, weight in spec_weight_pairs]
    total = sum(weight for _, weight in spec_weight_pairs)
    table_html = _table_html(
        ["철근경", "가공중량,Ton", "할증(%)", "로스감안중량,Ton", "커플러", "비고"],
        material_rows + [["계", str(total), "", str(total), "", ""]],
    )
    return {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": table_html, "text": ""}},
        ]
    }


def _cover_response_no_table():
    return {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {"page": 1, "category": "paragraph", "content": {"html": "<p>공장명: 가짜상사(주)</p>", "text": ""}},
        ]
    }
```

기존 호출부(`_cover_response([("SHD10", 1000)])` 등)는 숫자 인자를 그대로 두어도 된다 — 이 숫자들은 새 fixture에서 "로스감안중량,Ton" 셀 값으로 그대로 들어가며, 이 파일의 어떤 테스트도 그 값에서 계산된 정확한 톤 수치를 assert하지 않는다(레코드 존재 여부/경고 문구/성공 여부만 검증).

- [ ] **Step 3: 전체 테스트 실행해 통과 확인**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 전부 통과, 출력에 경고 외 에러 없음

- [ ] **Step 4: 커밋**

```bash
git add backend/tests/test_ocr_endpoint.py backend/tests/test_reports_api.py
git commit -m "test: 통합 테스트 fixture를 실제 철근 납품 확인서 양식으로 갱신"
```
