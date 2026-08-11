from datetime import date

from app import crud, schemas


def _make_invoice(db_session, spec="SHD10", weight=1.0, delivery_date=date(2026, 4, 20), item_name="철근", material_type="철근"):
    data = schemas.InvoiceCreate(
        material_type=material_type,
        vendor="테스트업체",
        delivery_date=delivery_date,
        item_name=item_name,
        spec=spec,
        unit="Ton",
        quantity=weight,
        weight=weight,
    )
    return crud.create_invoice(db_session, data)


def test_create_ledger_entries_creates_new_entries_and_returns_skipped_count(db_session):
    rebar = _make_invoice(db_session, delivery_date=date(2026, 4, 20))
    coupler = _make_invoice(db_session, item_name="커플러", delivery_date=date(2026, 4, 21))

    entries, skipped = crud.create_ledger_entries(db_session, [rebar.id, coupler.id], "김검수", "박감리")

    assert len(entries) == 1
    assert entries[0].invoice_id == rebar.id
    assert entries[0].inspector == "김검수"
    assert entries[0].supervisor == "박감리"
    assert skipped == 1


def test_create_ledger_entries_skips_already_included_invoices(db_session):
    invoice = _make_invoice(db_session)
    crud.create_ledger_entries(db_session, [invoice.id], "김검수", "박감리")

    entries, skipped = crud.create_ledger_entries(db_session, [invoice.id], "이검수", "최감리")

    assert entries == []
    assert skipped == 1
    all_entries = crud.list_ledger_entries(db_session)
    assert len(all_entries) == 1
    assert all_entries[0].inspector == "김검수"  # 기존 값 유지, 덮어쓰지 않음


def test_list_ledger_entries_sorted_by_invoice_delivery_date(db_session):
    later = _make_invoice(db_session, spec="SHD13", delivery_date=date(2026, 5, 2))
    earlier = _make_invoice(db_session, spec="SHD10", delivery_date=date(2026, 5, 1))
    crud.create_ledger_entries(db_session, [later.id, earlier.id], "", "")

    entries = crud.list_ledger_entries(db_session)

    assert [e.invoice.spec for e in entries] == ["SHD10", "SHD13"]


def test_update_ledger_entry_sets_manual_fields(db_session):
    invoice = _make_invoice(db_session)
    crud.create_ledger_entries(db_session, [invoice.id], "", "")

    updated = crud.update_ledger_entry(
        db_session,
        invoice.id,
        {
            "defect_qty": 0.5,
            "defect_reason": "표면 손상",
            "release_date": date(2026, 5, 10),
            "release_qty": 0.3,
            "remaining_qty": 0.2,
            "inspector": "김검수",
            "supervisor": "박감리",
        },
    )

    assert updated.defect_qty == 0.5
    assert updated.defect_reason == "표면 손상"
    assert updated.release_date == date(2026, 5, 10)
    assert updated.release_qty == 0.3
    assert updated.remaining_qty == 0.2
    assert updated.inspector == "김검수"
    assert updated.supervisor == "박감리"


def test_update_ledger_entry_missing_returns_none(db_session):
    assert crud.update_ledger_entry(db_session, 999999, {"defect_qty": 1.0}) is None


def test_delete_ledger_entry_removes_entry_but_keeps_invoice(db_session):
    invoice = _make_invoice(db_session)
    crud.create_ledger_entries(db_session, [invoice.id], "", "")

    deleted = crud.delete_ledger_entry(db_session, invoice.id)

    assert deleted is True
    assert crud.list_ledger_entries(db_session) == []
    assert crud.get_invoice(db_session, invoice.id) is not None


def test_delete_ledger_entry_missing_returns_false(db_session):
    assert crud.delete_ledger_entry(db_session, 999999) is False
