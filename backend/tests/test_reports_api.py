from urllib.parse import unquote

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

    # Assert RFC 5987 form is present for Korean text support
    assert "filename*=UTF-8''" in content_disposition

    # Assert ASCII filename fallback is present for legacy client compatibility
    assert 'filename="report.docx"' in content_disposition

    # Extract and decode the RFC 5987 encoded portion
    # Format: attachment; filename="report.docx"; filename*=UTF-8''<percent-encoded>
    if "filename*=UTF-8''" in content_disposition:
        encoded_part = content_disposition.split("filename*=UTF-8''")[1]
        decoded_filename = unquote(encoded_part)

        # Verify the decoded filename matches expected format with Korean text
        # material_type is "철근" from _form_fields(), report_number starts at 1
        assert decoded_filename.startswith("건축(자검)-철근-")
        assert decoded_filename.endswith("호.docx")
