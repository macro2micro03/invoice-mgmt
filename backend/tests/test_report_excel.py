from datetime import date
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

from app import report_excel

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "app" / "templates" / "material_inspection_form.xlsx"


def _make_specs():
    return [
        {"spec": "SHD10", "quantity_ton": 3.606},
        {"spec": "SHD13", "quantity_ton": 21.11},
    ]


def _fill(**overrides):
    kwargs = dict(
        template_path=TEMPLATE_PATH,
        project_name="테스트현장 신축공사",
        work_type="건축",
        material_type="철근",
        document_number="건축(자검)-철근-1호",
        sender="김현장",
        receiver="박감리",
        specs=_make_specs(),
        vendor="동경강업(주)/동국제강",
        delivery_date="2026-03-31",
    )
    kwargs.update(overrides)
    return report_excel.fill_material_inspection_form(**kwargs)


def test_fill_material_inspection_form_sets_header_fields():
    xlsx_bytes, skipped = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["B2"].value == "테스트현장 신축공사"
    assert sheet["B4"].value == "건축(자검)-철근-1호"
    assert sheet["C28"].value == " 김현장    (인)"
    assert sheet["H28"].value == " 박감리    (인)"
    assert skipped == []


def test_fill_material_inspection_form_marks_selected_work_type_checkbox():
    xlsx_bytes, _ = _fill(work_type="토목")
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert "토목 ■" in sheet["B3"].value
    assert "건축 □" in sheet["B3"].value


def test_fill_material_inspection_form_fills_material_rows():
    xlsx_bytes, _ = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["A9"].value == "철근"
    assert sheet["B9"].value == "SHD10"
    assert sheet["D9"].value == "Ton"
    assert sheet["E9"].value == 3.606
    assert sheet["F9"].value == "동경강업(주)/동국제강"
    assert sheet["B10"].value == "SHD13"
    assert sheet["E10"].value == 21.11


def test_fill_material_inspection_form_computes_summary_fields():
    xlsx_bytes, _ = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["H35"].value == "2026-03-31"
    assert sheet["H37"].value == "동경강업(주)/동국제강"
    assert sheet["H38"].value == "24.716 Ton"
    assert sheet["C39"].value == "철근 SHD10 외 1"
    assert sheet["H83"].value == "2026-03-31"
    assert sheet["H86"].value == "2026-03-31"


def test_fill_material_inspection_form_single_spec_summary_omits_count():
    xlsx_bytes, _ = _fill(specs=[{"spec": "SHD10", "quantity_ton": 3.606}])
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["C39"].value == "철근 SHD10"


def test_fill_material_inspection_form_clears_checklist_result_column():
    xlsx_bytes, _ = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    for row in range(63, 80):
        assert sheet[f"G{row}"].value is None


def test_fill_material_inspection_form_leaves_inspection_result_columns_blank():
    xlsx_bytes, _ = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["H9"].value is None
    assert sheet["I9"].value is None
    assert sheet["J9"].value is None


def test_fill_material_inspection_form_centers_material_name_and_spec_columns():
    xlsx_bytes, _ = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    for row in (9, 10):
        assert sheet[f"A{row}"].alignment.horizontal == "center"
        assert sheet[f"B{row}"].alignment.horizontal == "center"


def test_fill_material_inspection_form_uses_korean_date_format_for_receipt_and_inspection_dates():
    xlsx_bytes, _ = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    today = date.today()
    expected = f"{today:%Y}년 {today:%m}월 {today:%d}일"
    assert sheet["G4"].value == expected
    assert sheet["G5"].value == expected
    assert sheet["H36"].value == expected


def test_fill_material_inspection_form_reports_skipped_specs_beyond_capacity():
    many_specs = [{"spec": f"SPEC{i}", "quantity_ton": 1.0} for i in range(20)]
    xlsx_bytes, skipped = _fill(specs=many_specs)
    assert len(skipped) == 4
    assert skipped[0]["spec"] == "SPEC16"
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert sheet["A24"].value == "철근"
    assert sheet["B24"].value == "SPEC15"


def test_fill_material_inspection_form_inserts_top_and_bottom_photos():
    from io import BytesIO as _BytesIO

    from PIL import Image as _PILImage

    def _photo_bytes():
        img = _PILImage.new("RGB", (100, 100), (0, 255, 0))
        buf = _BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    xlsx_bytes, _ = _fill(top_photos=[_photo_bytes(), _photo_bytes()], bottom_photos=[_photo_bytes()])
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert len(sheet._images) == 3


def test_fill_material_inspection_form_no_photos_means_no_images():
    xlsx_bytes, _ = _fill()
    wb = load_workbook(BytesIO(xlsx_bytes))
    sheet = wb.active
    assert len(sheet._images) == 0
