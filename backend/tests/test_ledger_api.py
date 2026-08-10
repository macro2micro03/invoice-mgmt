from io import BytesIO
from urllib.parse import unquote

from openpyxl import load_workbook

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_invoice(vendor="테스트업체", spec="SHD10", weight="1.5", delivery_date="2026-04-20", item_name="철근"):
    response = client.post(
        "/invoices",
        data={
            "material_type": "철근",
            "vendor": vendor,
            "delivery_date": delivery_date,
            "item_name": item_name,
            "spec": spec,
            "unit": "Ton",
            "weight": weight,
            "quantity": weight,
        },
    )
    return response.json()["id"]


def test_ledger_endpoint_fills_rebar_sheet_and_returns_xlsx():
    id1 = _create_invoice(spec="SHD10", weight="1.5", delivery_date="2026-04-20")
    id2 = _create_invoice(spec="SHD13", weight="2.75", delivery_date="2026-04-21")

    response = client.post(
        "/reports/material-ledger",
        data={"invoice_ids": f"{id1},{id2}", "inspector": "김검수", "supervisor": "박감리"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    wb = load_workbook(BytesIO(response.content))
    sheet = wb["철근"]
    assert sheet["D7"].value == "SHD10"
    assert sheet["G7"].value == 1.5
    assert sheet["D8"].value == "SHD13"
    assert sheet["Q7"].value == "김검수"


def test_ledger_endpoint_sorts_by_delivery_date_ascending():
    id_later = _create_invoice(spec="SHD13", weight="1.0", delivery_date="2026-05-02")
    id_earlier = _create_invoice(spec="SHD10", weight="1.0", delivery_date="2026-05-01")

    response = client.post(
        "/reports/material-ledger",
        data={"invoice_ids": f"{id_later},{id_earlier}"},
    )
    assert response.status_code == 200
    wb = load_workbook(BytesIO(response.content))
    sheet = wb["철근"]
    assert sheet["D7"].value == "SHD10"
    assert sheet["D8"].value == "SHD13"


def test_ledger_endpoint_excludes_coupler_and_warns():
    rebar_id = _create_invoice(spec="SHD10", weight="1.0", item_name="철근")
    coupler_id = _create_invoice(spec="SHD10", weight="1.0", item_name="커플러")

    response = client.post(
        "/reports/material-ledger",
        data={"invoice_ids": f"{rebar_id},{coupler_id}"},
    )
    assert response.status_code == 200
    wb = load_workbook(BytesIO(response.content))
    sheet = wb["철근"]
    assert sheet["B8"].value is None  # 커플러 건은 채워지지 않음

    warnings_header = response.headers.get("x-report-warnings")
    assert warnings_header is not None
    assert "1건" in unquote(warnings_header)


def test_ledger_endpoint_400_when_no_rebar_records_remain():
    coupler_id = _create_invoice(spec="SHD10", weight="1.0", item_name="커플러")
    response = client.post(
        "/reports/material-ledger",
        data={"invoice_ids": str(coupler_id)},
    )
    assert response.status_code == 400
    assert "철근 자재 기록이 없습니다" in response.json()["detail"]


def test_ledger_endpoint_400_when_invoice_ids_missing():
    response = client.post("/reports/material-ledger", data={})
    assert response.status_code == 400


def test_ledger_endpoint_filename_and_is_protected_by_shared_password(monkeypatch):
    from app import config

    invoice_id = _create_invoice()
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    response = client.post(
        "/reports/material-ledger",
        data={"invoice_ids": str(invoice_id)},
    )
    assert response.status_code == 401
