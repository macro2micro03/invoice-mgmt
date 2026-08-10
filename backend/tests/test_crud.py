from datetime import date

from app import crud, schemas


def make_invoice_data(**overrides):
    base = dict(
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
        note="비고 없음",
    )
    base.update(overrides)
    return schemas.InvoiceCreate(**base)


def test_create_and_get_invoice(db_session):
    created = crud.create_invoice(db_session, make_invoice_data(), photo_path="photos/1.jpg")
    assert created.id is not None
    fetched = crud.get_invoice(db_session, created.id)
    assert fetched.vendor == "대한제강"
    assert fetched.photo_path == "photos/1.jpg"


def test_get_invoice_missing_returns_none(db_session):
    assert crud.get_invoice(db_session, 999999) is None


def test_list_invoices_filter_by_vendor(db_session):
    crud.create_invoice(db_session, make_invoice_data(vendor="A업체"))
    crud.create_invoice(db_session, make_invoice_data(vendor="B업체"))
    results = crud.list_invoices(db_session, vendor="A업체")
    assert len(results) == 1
    assert results[0].vendor == "A업체"


def test_update_invoice(db_session):
    created = crud.create_invoice(db_session, make_invoice_data())
    update_data = schemas.InvoiceUpdate(**{**make_invoice_data().model_dump(), "vendor": "수정된업체"})
    updated = crud.update_invoice(db_session, created.id, update_data)
    assert updated.vendor == "수정된업체"


def test_update_invoice_missing_returns_none(db_session):
    update_data = make_invoice_data()
    assert crud.update_invoice(db_session, 999999, schemas.InvoiceUpdate(**update_data.model_dump())) is None


def test_get_next_report_number_starts_at_one_and_increments(db_session):
    first = crud.get_next_report_number(db_session)
    second = crud.get_next_report_number(db_session)
    third = crud.get_next_report_number(db_session)
    assert first == 1
    assert second == 2
    assert third == 3


def test_create_invoice_computes_matched_tag_status(db_session):
    created = crud.create_invoice(
        db_session,
        make_invoice_data(spec="SHD13", tag_grade="SD500", tag_diameter="13"),
        tag_photo_path="photos/tag1.jpg",
    )
    assert created.tag_match_status == "matched"
    assert created.tag_photo_path == "photos/tag1.jpg"


def test_create_invoice_computes_mismatched_tag_status(db_session):
    created = crud.create_invoice(
        db_session, make_invoice_data(spec="SHD13", tag_grade="SD600", tag_diameter="13")
    )
    assert created.tag_match_status == "mismatched"


def test_create_invoice_without_tag_info_leaves_status_none(db_session):
    created = crud.create_invoice(db_session, make_invoice_data(spec="SHD13"))
    assert created.tag_match_status is None


def test_update_invoice_recomputes_tag_match_status(db_session):
    created = crud.create_invoice(db_session, make_invoice_data(spec="SHD13"))
    update_data = schemas.InvoiceUpdate(
        **{**make_invoice_data(spec="SHD13").model_dump(), "tag_grade": "SD500", "tag_diameter": "13"}
    )
    updated = crud.update_invoice(db_session, created.id, update_data)
    assert updated.tag_match_status == "matched"


def test_delete_invoice_removes_record_and_returns_true(db_session):
    created = crud.create_invoice(db_session, make_invoice_data())
    assert crud.delete_invoice(db_session, created.id) is True
    assert crud.get_invoice(db_session, created.id) is None


def test_delete_invoice_missing_returns_false(db_session):
    assert crud.delete_invoice(db_session, 999999) is False
