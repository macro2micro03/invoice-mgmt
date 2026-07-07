from io import BytesIO

from docx import Document

from app import report_docx


def _make_specs():
    return [
        {"spec": "SHD10", "quantity_ton": 3.606},
        {"spec": "SHD13", "quantity_ton": 21.11},
    ]


def _combined_text(doc: Document) -> str:
    paragraph_text = "\n".join(p.text for p in doc.paragraphs)
    table_text = "\n".join(
        cell.text for table in doc.tables for row in table.rows for cell in row.cells
    )
    return paragraph_text + "\n" + table_text


def test_generate_material_inspection_docx_contains_header_fields():
    docx_bytes = report_docx.generate_material_inspection_docx(
        project_name="테스트현장 신축공사",
        work_type="건축",
        material_type="철근",
        document_number="건축(자검)-철근-1호",
        sender="김현장",
        receiver="박감리",
        specs=_make_specs(),
        vendor="동경강업(주)/동국제강",
    )
    doc = Document(BytesIO(docx_bytes))
    combined = _combined_text(doc)
    assert "테스트현장 신축공사" in combined
    assert "건축" in combined
    assert "건축(자검)-철근-1호" in combined
    assert "김현장" in combined
    assert "박감리" in combined


def test_generate_material_inspection_docx_contains_material_rows_and_total():
    docx_bytes = report_docx.generate_material_inspection_docx(
        project_name="테스트현장",
        work_type="건축",
        material_type="철근",
        document_number="건축(자검)-철근-1호",
        sender="김현장",
        receiver="박감리",
        specs=_make_specs(),
        vendor="동경강업(주)/동국제강",
    )
    doc = Document(BytesIO(docx_bytes))
    combined = _combined_text(doc)
    assert "SHD10" in combined
    assert "3.606" in combined
    assert "SHD13" in combined
    assert "21.11" in combined
    assert "동경강업(주)/동국제강" in combined
    assert "24.716" in combined  # 3.606 + 21.11 합계
