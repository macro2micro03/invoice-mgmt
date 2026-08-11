from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "material_ledger.xlsx"

LEDGER_ROW_START = 7
REBAR_SHEET_NAME = "철근"


def fill_material_ledger(template_path: Path, ledger_entries: list) -> bytes:
    wb = load_workbook(template_path)
    sheet = wb[REBAR_SHEET_NAME]

    for offset, entry in enumerate(ledger_entries):
        row = LEDGER_ROW_START + offset
        invoice = entry.invoice
        sheet[f"B{row}"] = offset + 1
        sheet[f"C{row}"] = invoice.delivery_date
        sheet[f"D{row}"] = invoice.spec
        sheet[f"G{row}"] = invoice.weight
        sheet[f"J{row}"] = entry.defect_qty
        sheet[f"K{row}"] = entry.defect_reason
        sheet[f"N{row}"] = entry.release_date
        sheet[f"O{row}"] = entry.release_qty
        sheet[f"P{row}"] = entry.remaining_qty
        sheet[f"Q{row}"] = entry.inspector
        sheet[f"R{row}"] = entry.supervisor

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
