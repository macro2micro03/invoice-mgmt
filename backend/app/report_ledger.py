from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "material_ledger.xlsx"

LEDGER_ROW_START = 7
REBAR_SHEET_NAME = "철근"


def fill_material_ledger(template_path: Path, invoices: list, inspector: str, supervisor: str) -> bytes:
    wb = load_workbook(template_path)
    sheet = wb[REBAR_SHEET_NAME]

    for offset, invoice in enumerate(invoices):
        row = LEDGER_ROW_START + offset
        sheet[f"B{row}"] = offset + 1
        sheet[f"C{row}"] = invoice.delivery_date
        sheet[f"D{row}"] = invoice.spec
        sheet[f"G{row}"] = invoice.weight
        sheet[f"Q{row}"] = inspector
        sheet[f"R{row}"] = supervisor

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
