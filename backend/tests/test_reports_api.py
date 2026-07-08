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
