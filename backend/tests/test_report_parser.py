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
