from datetime import date
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment

from . import report_photos

CENTER_ALIGNMENT = Alignment(horizontal="center", vertical="center")

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "material_inspection_form.xlsx"

MATERIAL_ROW_START = 9
MATERIAL_ROW_END = 24
MATERIAL_ROW_CAPACITY = MATERIAL_ROW_END - MATERIAL_ROW_START + 1

WORK_TYPE_CELL = "B3"
CHECKLIST_RESULT_ROWS = range(63, 80)


def _mark_work_type_checkbox(text: str, work_type: str) -> str:
    return text.replace(f"{work_type} □", f"{work_type} ■", 1)


def _format_ton(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _format_korean_date(value: date) -> str:
    return f"{value:%Y}년 {value:%m}월 {value:%d}일"


def _build_material_spec_summary(material_type: str, specs: list[dict]) -> str:
    if not specs:
        return material_type
    first_spec = specs[0]["spec"]
    remaining = len(specs) - 1
    if remaining <= 0:
        return f"{material_type} {first_spec}"
    return f"{material_type} {first_spec} 외 {remaining}"


def fill_material_inspection_form(
    template_path,
    *,
    project_name: str,
    work_type: str,
    material_type: str,
    document_number: str,
    sender: str,
    receiver: str,
    specs: list[dict],
    vendor: str,
    delivery_date: str,
    top_photos: list[bytes] | None = None,
    bottom_photos: list[bytes] | None = None,
) -> tuple[bytes, list[dict]]:
    workbook = load_workbook(template_path)
    sheet = workbook.active

    today_date = date.today()
    today = today_date.strftime("%Y-%m-%d")
    today_korean = _format_korean_date(today_date)

    sheet["B2"] = project_name
    sheet[WORK_TYPE_CELL] = _mark_work_type_checkbox(str(sheet[WORK_TYPE_CELL].value or ""), work_type)
    sheet["B4"] = document_number
    sheet["G4"] = today_korean
    sheet["G5"] = today_korean

    fillable_specs = specs[:MATERIAL_ROW_CAPACITY]
    skipped_specs = specs[MATERIAL_ROW_CAPACITY:]
    for offset, spec_row in enumerate(fillable_specs):
        row = MATERIAL_ROW_START + offset
        sheet[f"A{row}"] = material_type
        sheet[f"A{row}"].alignment = CENTER_ALIGNMENT
        sheet[f"B{row}"] = spec_row["spec"]
        sheet[f"B{row}"].alignment = CENTER_ALIGNMENT
        sheet[f"D{row}"] = "Ton"
        sheet[f"D{row}"].alignment = CENTER_ALIGNMENT
        sheet[f"E{row}"] = spec_row["quantity_ton"]
        sheet[f"F{row}"] = vendor

    sheet["C27"] = today
    sheet["H27"] = today
    sheet["C28"] = f" {sender}    (인)"
    sheet["H28"] = f" {receiver}    (인)"

    sheet["H35"] = delivery_date
    sheet["H36"] = today_korean
    sheet["H37"] = vendor
    total_ton = round(sum(spec_row["quantity_ton"] for spec_row in specs), 3)
    sheet["H38"] = f"{_format_ton(total_ton)} Ton"
    sheet["C39"] = _build_material_spec_summary(material_type, specs)

    for row in CHECKLIST_RESULT_ROWS:
        sheet[f"G{row}"] = None

    sheet["H83"] = delivery_date
    sheet["H86"] = delivery_date

    report_photos.insert_photo_grid(sheet, anchor_row=81, photos=top_photos or [])
    report_photos.insert_photo_grid(sheet, anchor_row=84, photos=bottom_photos or [])

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue(), skipped_specs
