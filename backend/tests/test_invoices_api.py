import io

from fastapi.testclient import TestClient

from app import excel as excel_module
from app import pdf as pdf_module
from app.main import app

client = TestClient(app)


def test_create_invoice_persists_and_returns_photo_path(monkeypatch):
    monkeypatch.setattr(excel_module, "append_invoice", lambda invoice: None)
    monkeypatch.setattr(pdf_module, "generate_pdf", lambda invoice: "pdf/x.pdf")

    response = client.post(
        "/invoices",
        data={"material_type": "철근", "vendor": "대한제강", "invoice_no": "INV-100"},
        files={"photo": ("test.jpg", io.BytesIO(b"fake"), "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["vendor"] == "대한제강"
    assert body["photo_path"] is not None


def test_search_invoices_by_vendor(monkeypatch):
    monkeypatch.setattr(excel_module, "append_invoice", lambda invoice: None)
    monkeypatch.setattr(pdf_module, "generate_pdf", lambda invoice: "pdf/x.pdf")

    client.post("/invoices", data={"material_type": "시멘트", "vendor": "검색전용업체"})
    response = client.get("/invoices", params={"vendor": "검색전용업체"})
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["vendor"] == "검색전용업체"


def test_get_invoice_not_found_returns_404():
    response = client.get("/invoices/999999")
    assert response.status_code == 404


def test_update_invoice_changes_field(monkeypatch):
    monkeypatch.setattr(excel_module, "append_invoice", lambda invoice: None)
    monkeypatch.setattr(pdf_module, "generate_pdf", lambda invoice: "pdf/x.pdf")

    create_response = client.post("/invoices", data={"material_type": "골재", "vendor": "원래업체"})
    invoice_id = create_response.json()["id"]

    update_response = client.put(
        f"/invoices/{invoice_id}",
        json={"material_type": "골재", "vendor": "변경된업체"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["vendor"] == "변경된업체"


def test_create_invoice_with_tag_fields_and_photo_computes_match_status(monkeypatch):
    monkeypatch.setattr(excel_module, "append_invoice", lambda invoice: None)
    monkeypatch.setattr(pdf_module, "generate_pdf", lambda invoice: "pdf/x.pdf")

    response = client.post(
        "/invoices",
        data={
            "material_type": "철근",
            "spec": "SHD13",
            "tag_grade": "SD500",
            "tag_diameter": "13",
            "tag_site_name": "서소문 재개발",
        },
        files={"tag_photo": ("tag.jpg", io.BytesIO(b"fake-tag"), "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tag_match_status"] == "matched"
    assert body["tag_photo_path"] is not None
    assert body["tag_site_name"] == "서소문 재개발"


def test_get_invoice_round_trip_returns_tag_fields(monkeypatch):
    monkeypatch.setattr(excel_module, "append_invoice", lambda invoice: None)
    monkeypatch.setattr(pdf_module, "generate_pdf", lambda invoice: "pdf/x.pdf")

    create_response = client.post(
        "/invoices",
        data={
            "material_type": "철근",
            "spec": "SHD13",
            "tag_grade": "SD500",
            "tag_diameter": "13",
            "tag_site_name": "서소문 재개발",
        },
        files={"tag_photo": ("tag.jpg", io.BytesIO(b"fake-tag"), "image/jpeg")},
    )
    invoice_id = create_response.json()["id"]

    get_response = client.get(f"/invoices/{invoice_id}")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["tag_grade"] == "SD500"
    assert body["tag_diameter"] == "13"
    assert body["tag_site_name"] == "서소문 재개발"
    assert body["tag_match_status"] == "matched"
    assert body["tag_photo_path"] is not None


def test_update_invoice_ignores_client_supplied_tag_match_status(monkeypatch):
    monkeypatch.setattr(excel_module, "append_invoice", lambda invoice: None)
    monkeypatch.setattr(pdf_module, "generate_pdf", lambda invoice: "pdf/x.pdf")

    create_response = client.post(
        "/invoices",
        data={
            "material_type": "철근",
            "spec": "SHD13",
            "tag_grade": "SD600",
            "tag_diameter": "16",
        },
    )
    invoice_id = create_response.json()["id"]
    assert create_response.json()["tag_match_status"] == "mismatched"

    update_response = client.put(
        f"/invoices/{invoice_id}",
        json={
            "material_type": "철근",
            "spec": "SHD13",
            "tag_grade": "SD600",
            "tag_diameter": "16",
            "tag_match_status": "matched",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["tag_match_status"] == "mismatched"


def test_delete_invoice_removes_it(monkeypatch):
    monkeypatch.setattr(excel_module, "append_invoice", lambda invoice: None)
    monkeypatch.setattr(pdf_module, "generate_pdf", lambda invoice: "pdf/x.pdf")

    create_response = client.post("/invoices", data={"material_type": "철근", "vendor": "삭제대상"})
    invoice_id = create_response.json()["id"]

    delete_response = client.delete(f"/invoices/{invoice_id}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/invoices/{invoice_id}")
    assert get_response.status_code == 404


def test_delete_invoice_missing_returns_404():
    response = client.delete("/invoices/999999")
    assert response.status_code == 404
