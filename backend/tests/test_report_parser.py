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
