import io

from fastapi.testclient import TestClient

from app import excel as excel_module
from app import pdf as pdf_module
from app import photos as photos_module
from app.main import app

client = TestClient(app)


def test_excel_failure_does_not_block_response_and_db_row_persists(monkeypatch):
    def boom(invoice):
        raise RuntimeError("excel boom")

    monkeypatch.setattr(excel_module, "append_invoice", boom)
    monkeypatch.setattr(pdf_module, "generate_pdf", lambda invoice: "pdf/x.pdf")

    response = client.post(
        "/invoices",
        data={"material_type": "골재", "vendor": "엑셀실패업체", "invoice_no": "INV-EXCEL-FAIL"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] is not None

    get_response = client.get(f"/invoices/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["vendor"] == "엑셀실패업체"


def test_pdf_failure_does_not_block_response_and_db_row_persists(monkeypatch):
    def boom(invoice):
        raise RuntimeError("pdf boom")

    monkeypatch.setattr(excel_module, "append_invoice", lambda invoice: None)
    monkeypatch.setattr(pdf_module, "generate_pdf", boom)

    response = client.post(
        "/invoices",
        data={"material_type": "철근", "vendor": "PDF실패업체", "invoice_no": "INV-PDF-FAIL"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] is not None

    get_response = client.get(f"/invoices/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["vendor"] == "PDF실패업체"


def test_photo_save_failure_does_not_block_response_and_photo_path_is_none(monkeypatch):
    def boom(image_bytes, original_filename):
        raise RuntimeError("photo boom")

    monkeypatch.setattr(photos_module, "save_photo", boom)
    monkeypatch.setattr(excel_module, "append_invoice", lambda invoice: None)
    monkeypatch.setattr(pdf_module, "generate_pdf", lambda invoice: "pdf/x.pdf")

    response = client.post(
        "/invoices",
        data={"material_type": "골재", "vendor": "사진실패업체", "invoice_no": "INV-PHOTO-FAIL"},
        files={"photo": ("test.jpg", io.BytesIO(b"fake"), "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] is not None
    assert body["photo_path"] is None

    get_response = client.get(f"/invoices/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["photo_path"] is None
