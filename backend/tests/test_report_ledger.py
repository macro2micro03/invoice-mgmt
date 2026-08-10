from datetime import date
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook

from app import report_ledger

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "app" / "templates" / "material_ledger.xlsx"


def _invoice(delivery_date, spec, weight):
    return SimpleNamespace(delivery_date=delivery_date, spec=spec, weight=weight)


def test_fill_material_ledger_writes_rows_in_order_starting_at_row_7():
    invoices = [
        _invoice(date(2026, 4, 20), "SHD10", 1.5),
        _invoice(date(2026, 4, 21), "SHD13", 2.75),
    ]
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, invoices, "김검수", "박감리")
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["철근"]

    assert sheet["B7"].value == 1
    assert sheet["C7"].value.date() == date(2026, 4, 20)
    assert sheet["D7"].value == "SHD10"
    assert sheet["G7"].value == 1.5

    assert sheet["B8"].value == 2
    assert sheet["C8"].value.date() == date(2026, 4, 21)
    assert sheet["D8"].value == "SHD13"
    assert sheet["G8"].value == 2.75


def test_fill_material_ledger_fills_inspector_and_supervisor_on_every_row():
    invoices = [
        _invoice(date(2026, 4, 20), "SHD10", 1.0),
        _invoice(date(2026, 4, 21), "SHD13", 2.0),
    ]
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, invoices, "김검수", "박감리")
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["철근"]

    assert sheet["Q7"].value == "김검수"
    assert sheet["R7"].value == "박감리"
    assert sheet["Q8"].value == "김검수"
    assert sheet["R8"].value == "박감리"


def test_fill_material_ledger_preserves_existing_formulas():
    # F~P열은 템플릿에 이미 있는 수식/기본값을 그대로 둬야 한다 — 덮어쓰지 않는다.
    invoices = [_invoice(date(2026, 4, 20), "SHD10", 1.0)]
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, invoices, "김검수", "박감리")
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["철근"]

    assert sheet["F7"].value == "=G7"
    assert sheet["H7"].value == '=IF(G7="","",(G7-J7))'


def test_fill_material_ledger_does_not_touch_coupler_sheet():
    invoices = [_invoice(date(2026, 4, 20), "SHD10", 1.0)]
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, invoices, "김검수", "박감리")
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["커플러"]

    assert sheet["B7"].value is None
    assert sheet["G7"].value is None


def test_fill_material_ledger_empty_invoices_writes_no_rows():
    xlsx_bytes = report_ledger.fill_material_ledger(TEMPLATE_PATH, [], "김검수", "박감리")
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb["철근"]

    assert sheet["B7"].value is None
