from datetime import date

from app import config, models, pdf


def make_invoice(**overrides):
    defaults = dict(
        id=1,
        material_type="철근",
        vendor="대한제강",
        delivery_date=date(2026, 7, 1),
        vehicle_no="12가3456",
        invoice_no="INV-001",
        item_name="철근 D10",
        spec="D10",
        unit="TON",
        quantity=10.5,
        weight=10500,
        note="",
    )
    defaults.update(overrides)
    return models.Invoice(**defaults)


def test_is_major_material_true_for_configured_types():
    assert pdf.is_major_material("철근") is True
    assert pdf.is_major_material("레미콘") is True


def test_is_major_material_false_for_others():
    assert pdf.is_major_material("마감재") is False


def test_generate_pdf_creates_nonempty_file():
    rel_path = pdf.generate_pdf(make_invoice())
    full_path = config.STORAGE_DIR / rel_path
    assert full_path.exists()
    assert full_path.stat().st_size > 0
    assert rel_path.startswith("pdf")
