from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from . import models, schemas, spec_grade


def create_invoice(
    db: Session,
    data: schemas.InvoiceCreate,
    photo_path: Optional[str] = None,
    tag_photo_path: Optional[str] = None,
) -> models.Invoice:
    invoice = models.Invoice(
        **data.model_dump(),
        photo_path=photo_path,
        tag_photo_path=tag_photo_path,
        tag_match_status=spec_grade.match_tag_to_spec(data.tag_grade, data.tag_diameter, data.spec or ""),
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def get_invoice(db: Session, invoice_id: int) -> Optional[models.Invoice]:
    return db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()


def list_invoices(
    db: Session,
    vendor: Optional[str] = None,
    material_type: Optional[str] = None,
    invoice_no: Optional[str] = None,
    delivery_date: Optional[date] = None,
) -> list[models.Invoice]:
    query = db.query(models.Invoice)
    if vendor:
        query = query.filter(models.Invoice.vendor == vendor)
    if material_type:
        query = query.filter(models.Invoice.material_type == material_type)
    if invoice_no:
        query = query.filter(models.Invoice.invoice_no == invoice_no)
    if delivery_date:
        query = query.filter(models.Invoice.delivery_date == delivery_date)
    return query.order_by(models.Invoice.id.desc()).all()


def update_invoice(db: Session, invoice_id: int, data: schemas.InvoiceUpdate) -> Optional[models.Invoice]:
    invoice = get_invoice(db, invoice_id)
    if invoice is None:
        return None
    for key, value in data.model_dump().items():
        setattr(invoice, key, value)
    invoice.tag_match_status = spec_grade.match_tag_to_spec(invoice.tag_grade, invoice.tag_diameter, invoice.spec or "")
    db.commit()
    db.refresh(invoice)
    return invoice


def delete_invoice(db: Session, invoice_id: int) -> bool:
    invoice = get_invoice(db, invoice_id)
    if invoice is None:
        return False
    db.query(models.LedgerEntry).filter(models.LedgerEntry.invoice_id == invoice_id).delete(
        synchronize_session=False
    )
    db.delete(invoice)
    db.commit()
    return True


def delete_invoices(db: Session, invoice_ids: list[int]) -> int:
    if not invoice_ids:
        return 0
    db.query(models.LedgerEntry).filter(models.LedgerEntry.invoice_id.in_(invoice_ids)).delete(
        synchronize_session=False
    )
    deleted_count = (
        db.query(models.Invoice)
        .filter(models.Invoice.id.in_(invoice_ids))
        .delete(synchronize_session="fetch")
    )
    db.commit()
    return deleted_count


def list_invoices_by_ids(db: Session, invoice_ids: list[int]) -> list[models.Invoice]:
    if not invoice_ids:
        return []
    return (
        db.query(models.Invoice)
        .filter(models.Invoice.id.in_(invoice_ids))
        .order_by(models.Invoice.id)
        .all()
    )


def list_invoices_by_material_and_date(db: Session, material_type: str, delivery_date: date) -> list[models.Invoice]:
    return (
        db.query(models.Invoice)
        .filter(models.Invoice.material_type == material_type)
        .filter(models.Invoice.delivery_date == delivery_date)
        .order_by(models.Invoice.id)
        .all()
    )


def create_ledger_entries(
    db: Session, invoice_ids: list[int], inspector: str, supervisor: str
) -> tuple[list[models.LedgerEntry], int]:
    if not invoice_ids:
        return [], 0
    invoices = list_invoices_by_ids(db, invoice_ids)
    existing_ids = {
        row[0]
        for row in db.query(models.LedgerEntry.invoice_id)
        .filter(models.LedgerEntry.invoice_id.in_(invoice_ids))
        .all()
    }
    skipped = 0
    created: list[models.LedgerEntry] = []
    for invoice in invoices:
        if invoice.item_name == "커플러" or invoice.material_type != "철근":
            skipped += 1
            continue
        if invoice.id in existing_ids:
            skipped += 1
            continue
        entry = models.LedgerEntry(invoice_id=invoice.id, inspector=inspector, supervisor=supervisor)
        db.add(entry)
        created.append(entry)
    db.commit()
    for entry in created:
        db.refresh(entry)
    return created, skipped


def list_ledger_entries(db: Session) -> list[models.LedgerEntry]:
    return (
        db.query(models.LedgerEntry)
        .join(models.Invoice)
        .order_by(models.Invoice.delivery_date)
        .all()
    )


def update_ledger_entry(db: Session, invoice_id: int, fields: dict) -> Optional[models.LedgerEntry]:
    entry = db.query(models.LedgerEntry).filter(models.LedgerEntry.invoice_id == invoice_id).first()
    if entry is None:
        return None
    for key, value in fields.items():
        setattr(entry, key, value)
    db.commit()
    db.refresh(entry)
    return entry


def delete_ledger_entry(db: Session, invoice_id: int) -> bool:
    entry = db.query(models.LedgerEntry).filter(models.LedgerEntry.invoice_id == invoice_id).first()
    if entry is None:
        return False
    db.delete(entry)
    db.commit()
    return True


def get_next_report_number(db: Session) -> int:
    today = date.today()
    sequence = db.query(models.ReportSequence).filter(models.ReportSequence.id == 1).first()
    if sequence is None:
        sequence = models.ReportSequence(id=1, last_number=0, last_date=today)
        db.add(sequence)
    # 날짜가 바뀌면 번호를 1부터 다시 시작한다 — 예전에는 계속 누적돼서
    # 파일명 뒤 번호가 날짜와 무관하게 끝없이 커졌다.
    if sequence.last_date != today:
        sequence.last_number = 0
        sequence.last_date = today
    sequence.last_number += 1
    db.commit()
    db.refresh(sequence)
    return sequence.last_number
