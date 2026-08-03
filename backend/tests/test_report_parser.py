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


# --- Critical #1: rowspan/colspan/<th> must not silently yield zero rows ---


def test_parse_table_rows_handles_rowspan_colspan_and_th():
    table_html = (
        '<table><tr><th rowspan="2">철근경</th><th colspan="2">로스감안중량,Ton</th></tr>'
        '<tr class="data-row"><td rowspan="1">SHD10</td><td>0.544</td></tr></table>'
    )
    rows = report_parser._parse_table_rows(table_html)
    assert rows == [["철근경", "로스감안중량,Ton"], ["SHD10", "0.544"]]


def test_extract_material_rows_parses_table_with_attributes_and_th_cells():
    table_html = (
        '<table><tr class="hdr"><th>철근경</th><th>로스감안중량,Ton</th><th>비고</th></tr>'
        '<tr><td rowspan="1">SHD10</td><td>0.544</td><td>동국제강</td></tr>'
        '<tr><td>계</td><td>0.544</td><td></td></tr></table>'
    )
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": table_html, "text": ""}},
        ]
    }
    rows = report_parser.extract_material_rows(raw, page=1)
    assert rows == [{"spec": "SHD10", "weight_ton": 0.544, "note": "동국제강"}]


# --- Critical #2: header row is not necessarily rows[0] ---


def test_extract_material_rows_finds_header_when_info_rows_precede_it_in_same_table():
    # Upstage가 정보 블록(공사명/납품일 등)과 자재 표를 하나의 테이블 요소로
    # 합쳐버리는 경우, 헤더 행은 rows[0]이 아니라 몇 행 아래에 있다.
    table_html = (
        "<table>"
        "<tr><td>공사명</td><td>삼성물산-서소문빌딩재개발 현장</td><td></td></tr>"
        "<tr><td>납품일</td><td>2026-07-30</td><td></td></tr>"
        "<tr><td>철근경</td><td>로스감안중량,Ton</td><td>비고</td></tr>"
        "<tr><td>SHD10</td><td>0.544</td><td>동국제강</td></tr>"
        "<tr><td>계</td><td>0.544</td><td></td></tr>"
        "</table>"
    )
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": table_html, "text": ""}},
        ]
    }
    rows = report_parser.extract_material_rows(raw, page=1)
    assert rows == [{"spec": "SHD10", "weight_ton": 0.544, "note": "동국제강"}]


# --- Critical #3: value-side letter-spacing must be collapsed before pattern matching ---


def test_find_delivery_date_tolerates_letter_spaced_value():
    raw = {
        "elements": [
            {"page": 1, "category": "paragraph", "content": {"html": "<p>납 품 일 : 2026 - 07 - 30</p>", "text": ""}},
        ]
    }
    assert report_parser.find_delivery_date(raw, page=1) == "2026-07-30"


def test_find_invoice_no_tolerates_letter_spaced_value():
    raw = {
        "elements": [
            {"page": 1, "category": "paragraph", "content": {"html": "<p>송 장 번 호 : 1178 - 001</p>", "text": ""}},
        ]
    }
    assert report_parser.find_invoice_no(raw, page=1) == "1178-001"


def test_find_vehicle_no_tolerates_letter_spaced_value():
    raw = {
        "elements": [
            {
                "page": 1,
                "category": "paragraph",
                "content": {"html": "<p>차 량 번 호 : 서울 85바 3204</p>", "text": ""},
            },
        ]
    }
    assert report_parser.find_vehicle_no(raw, page=1) == "서울85바3204"


def test_find_vendor_heading_collapses_letter_spaced_value():
    raw = {
        "elements": [
            {
                "page": 1,
                "category": "paragraph",
                "content": {"html": "<p>공 장 명 : ( 주 ) 대 건 건 철</p>", "text": ""},
            },
        ]
    }
    assert report_parser.find_vendor_heading(raw, page=1) == "(주)대건건철"


# --- Important #4: blank labeled value must not bleed into the next line ---


def test_find_vendor_heading_returns_empty_when_blank_field_bleeds_into_disclaimer():
    raw = {
        "elements": [
            {
                "page": 1,
                "category": "paragraph",
                "content": {
                    "html": "<p>공장명:<br>상차된 제품에 누락이 없음을 확인함</p>",
                    "text": "",
                },
            },
        ]
    }
    assert report_parser.find_vendor_heading(raw, page=1) == ""


# --- Round 2 regression: label alone on its own line, value on the NEXT line ---


def test_find_vendor_heading_extracts_value_split_onto_next_line():
    # Upstage가 라벨과 값을 서로 다른 요소로 나눠 반환하는 경우
    # (ocr.extract_text가 요소들을 "\n"으로 이어붙이므로 라벨 줄에는
    # 아무 값도 없고, 값은 바로 다음 줄에 온다). 콜론이 전혀 없다는 점이
    # Important #4의 "라벨: <br>무관한 문단" 사례와 다르다.
    raw = {
        "elements": [
            {"page": 1, "category": "paragraph", "content": {"html": "<p>공장명</p>", "text": ""}},
            {"page": 1, "category": "paragraph", "content": {"html": "<p>(주)대건건철</p>", "text": ""}},
        ]
    }
    assert report_parser.find_vendor_heading(raw, page=1) == "(주)대건건철"


def test_find_delivery_date_extracts_value_split_onto_next_line():
    raw = {
        "elements": [
            {"page": 1, "category": "paragraph", "content": {"html": "<p>납품일</p>", "text": ""}},
            {"page": 1, "category": "paragraph", "content": {"html": "<p>2026-07-30</p>", "text": ""}},
        ]
    }
    assert report_parser.find_delivery_date(raw, page=1) == "2026-07-30"


def test_find_labeled_values_split_across_lines_for_two_labels_in_sequence():
    # 두 개의 라벨이 연달아 각각 다음 줄에 값을 가진 경우도 모두 추출돼야 한다.
    raw = {
        "elements": [
            {"page": 1, "category": "paragraph", "content": {"html": "<p>공장명</p>", "text": ""}},
            {"page": 1, "category": "paragraph", "content": {"html": "<p>(주)대건건철</p>", "text": ""}},
            {"page": 1, "category": "paragraph", "content": {"html": "<p>납품일</p>", "text": ""}},
            {"page": 1, "category": "paragraph", "content": {"html": "<p>2026-07-30</p>", "text": ""}},
        ]
    }
    assert report_parser.find_vendor_heading(raw, page=1) == "(주)대건건철"
    assert report_parser.find_delivery_date(raw, page=1) == "2026-07-30"


# --- Important #5: per-page scoping must not silently use page 1's values for every page ---


def _two_page_response():
    page1 = make_cover_response(
        1,
        "가공장(주)",
        [("SHD10", 0.544)],
        delivery_date="2026-07-29",
        invoice_no="1111-001",
        vehicle_no="서울11가1111",
    )
    page2 = make_cover_response(
        2,
        "나공장(주)",
        [("SHD13", 1.531)],
        delivery_date="2026-07-30",
        invoice_no="2222-002",
        vehicle_no="서울22나2222",
    )
    return {"elements": page1["elements"] + page2["elements"]}


def test_find_delivery_date_scoped_to_requested_page():
    raw = _two_page_response()
    assert report_parser.find_delivery_date(raw, page=1) == "2026-07-29"
    assert report_parser.find_delivery_date(raw, page=2) == "2026-07-30"


def test_find_vendor_heading_scoped_to_requested_page():
    raw = _two_page_response()
    assert report_parser.find_vendor_heading(raw, page=1) == "가공장(주)"
    assert report_parser.find_vendor_heading(raw, page=2) == "나공장(주)"


def test_find_invoice_no_scoped_to_requested_page():
    raw = _two_page_response()
    assert report_parser.find_invoice_no(raw, page=1) == "1111-001"
    assert report_parser.find_invoice_no(raw, page=2) == "2222-002"


def test_find_vehicle_no_scoped_to_requested_page():
    raw = _two_page_response()
    assert report_parser.find_vehicle_no(raw, page=1) == "서울11가1111"
    assert report_parser.find_vehicle_no(raw, page=2) == "서울22나2222"


def test_build_report_data_uses_genuinely_different_per_page_values():
    raw = _two_page_response()
    data = report_parser.build_report_data([raw])
    assert data["delivery_date"] == "2026-07-30"
    # 마지막으로 처리된 페이지(2)의 거래처가 반영되어야 한다(비고란 제조회사명은
    # 두 페이지가 동일해 그대로 결합된다).
    assert data["vendor"] == "나공장(주)/동국제강,현대제철"


# --- Important #6: comma on the Ton weight column, and an implausible-weight sanity bound ---


def test_extract_material_rows_treats_comma_as_decimal_point():
    table_html = _table_html(
        ["철근경", "가공중량,Ton", "할증(%)", "로스감안중량,Ton", "커플러", "비고"],
        [["SHD10", "0,528", "3", "0,544", "0", "동국제강"]],
    )
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": table_html, "text": ""}},
        ]
    }
    rows = report_parser.extract_material_rows(raw, page=1)
    assert rows == [{"spec": "SHD10", "weight_ton": 0.544, "note": "동국제강"}]


def test_extract_material_rows_rejects_implausibly_large_weight():
    table_html = _table_html(
        ["철근경", "가공중량,Ton", "할증(%)", "로스감안중량,Ton", "커플러", "비고"],
        [["SHD10", "0.528", "3", "544.0", "0", "동국제강"]],
    )
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": table_html, "text": ""}},
        ]
    }
    rows = report_parser.extract_material_rows(raw, page=1)
    assert rows == []


def test_build_report_data_reports_skipped_rows_for_implausible_weight():
    table_html = _table_html(
        ["철근경", "가공중량,Ton", "할증(%)", "로스감안중량,Ton", "커플러", "비고"],
        [
            ["SHD10", "0.528", "3", "0.544", "0", "동국제강"],
            ["SHD13", "150", "0", "150", "0", "동국제강"],
        ],
    )
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": table_html, "text": ""}},
        ]
    }
    data = report_parser.build_report_data([raw])
    specs = {row["spec"] for row in data["specs"]}
    assert specs == {"SHD10"}
    assert data["skipped_rows"] == 1


# --- Important #7: title match must tolerate extra text around it ---


def test_find_cover_pages_matches_title_with_extra_annotation_text():
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서 (제1차)</h1>", "text": ""}},
        ]
    }
    assert report_parser.find_cover_pages(raw) == [1]


def test_find_cover_pages_ignores_long_boilerplate_paragraph_quoting_the_title():
    # 제목 문구를 인용하는 무관한 안내 문단(예: 발행 부수 안내)까지 표지
    # 페이지로 잘못 인식되면 안 된다 — 실제 자재 내역 표가 없는 페이지가
    # skipped_pages에 들어가 사용자에게 잘못된 경고가 뜬다.
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {
                "page": 2,
                "category": "paragraph",
                "content": {
                    "html": (
                        "<p>본 철근 납품 확인서는 납품 완료 후 2부를 작성하여 발주처와 "
                        "협력업체가 각각 1부씩 보관하는 것을 원칙으로 한다.</p>"
                    ),
                    "text": "",
                },
            },
        ]
    }
    assert report_parser.find_cover_pages(raw) == [1]


# --- Round 2 new issue: page-scoped text must not drop page-less elements ---


def test_page_scoped_finders_include_elements_with_no_page_key():
    # OCR 응답에 page 번호가 아예 없는 요소(예: Upstage가 특정 페이지에
    # 귀속시키지 못한 요약/폼 요소)가 섞여 있어도, 페이지 스코프 검색에서
    # 완전히 제외되면 안 된다 — Important #5 이전에는 문서 전체 텍스트에서
    # 찾았으므로 이런 요소도 정상적으로 검색됐었다.
    raw = {
        "elements": [
            {"page": 1, "category": "paragraph", "content": {"html": "<p>납품일: 2026-07-29</p>", "text": ""}},
            {"category": "paragraph", "content": {"html": "<p>공장명: (주)대건건철</p>", "text": ""}},
        ]
    }
    assert report_parser.find_delivery_date(raw, page=1) == "2026-07-29"
    assert report_parser.find_vendor_heading(raw, page=1) == "(주)대건건철"


# --- Round 3, item 1: next-line fallback must validate the candidate value ---


def test_find_vendor_heading_returns_empty_when_no_colon_label_bleeds_into_disclaimer():
    # 1a: 콜론이 아예 없는 라벨 뒤에 무관한 면책 문구가 다음 줄로 오는 경우도
    # Important #4와 동일하게 빈 값을 반환해야 한다.
    raw = {
        "elements": [
            {"page": 1, "category": "paragraph", "content": {"html": "<p>공장명</p>", "text": ""}},
            {
                "page": 1,
                "category": "paragraph",
                "content": {"html": "<p>상차된 제품에 누락이 없음을 확인함</p>", "text": ""},
            },
        ]
    }
    assert report_parser.find_vendor_heading(raw, page=1) == ""


def test_find_vendor_heading_returns_empty_when_next_line_is_another_label():
    # 1b: 다음 줄이 또 다른 서식 라벨(예: "납품일: ...")이면 그 값을 그대로
    # 삼키면 안 된다 — 라벨 줄은 절대 값이 될 수 없다.
    raw = {
        "elements": [
            {"page": 1, "category": "paragraph", "content": {"html": "<p>공장명</p>", "text": ""}},
            {"page": 1, "category": "paragraph", "content": {"html": "<p>납품일: 2026-07-30</p>", "text": ""}},
        ]
    }
    assert report_parser.find_vendor_heading(raw, page=1) == ""


def test_find_vendor_heading_returns_empty_when_next_line_is_table_header_text():
    # 1b: 다음 줄이 자재 내역 표의 헤더 행이어도 값으로 삼키면 안 된다.
    raw = {
        "elements": [
            {"page": 1, "category": "paragraph", "content": {"html": "<p>공장명</p>", "text": ""}},
            {"page": 1, "category": "paragraph", "content": {"html": "<p>철근경 가공중량 할증</p>", "text": ""}},
        ]
    }
    assert report_parser.find_vendor_heading(raw, page=1) == ""


def test_find_vendor_heading_still_extracts_value_split_onto_next_line():
    # 라운드 2에서 고친 정상 케이스는 계속 동작해야 한다.
    raw = {
        "elements": [
            {"page": 1, "category": "paragraph", "content": {"html": "<p>공장명</p>", "text": ""}},
            {"page": 1, "category": "paragraph", "content": {"html": "<p>(주)대건건철</p>", "text": ""}},
        ]
    }
    assert report_parser.find_vendor_heading(raw, page=1) == "(주)대건건철"


# --- Round 3, item 2: title-containment guard must be shape-based, not length-based ---


def test_find_cover_pages_rejects_exact_reported_boilerplate_sentence():
    # 라운드 2 원본 리포트의 실제 예문(길이 16자, 21자 기준선 밑) 자체가
    # 여전히 표지로 오탐지되던 문제. 문장 전체가 아니라 제목이 반드시
    # 문두에 와야 한다는 형태 기반 판별로 고쳐야 한다.
    raw = {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {
                "page": 2,
                "category": "paragraph",
                "content": {"html": "<p>본 철근 납품 확인서는 2부 작성한다.</p>", "text": ""},
            },
        ]
    }
    assert report_parser.find_cover_pages(raw) == [1]


def test_find_cover_pages_accepts_long_legitimate_title_annotation():
    # 21자 기준선을 살짝 넘는 정당한 제목 주석(날짜+회차)까지 거부되면 안
    # 된다 — 거부되면 그 페이지의 자재 내역 표가 아예 파싱되지 않는 새로운
    # 데이터 유실 경로가 생긴다.
    raw = {
        "elements": [
            {
                "page": 1,
                "category": "heading1",
                "content": {"html": "<h1>철근 납품 확인서 (2026-07-30 제1차)</h1>", "text": ""},
            },
        ]
    }
    assert report_parser.find_cover_pages(raw) == [1]
