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
    db.delete(invoice)
    db.commit()
    return True


def delete_invoices(db: Session, invoice_ids: list[int]) -> int:
    if not invoice_ids:
        return 0
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


def get_next_report_number(db: Session) -> int:
    sequence = db.query(models.ReportSequence).filter(models.ReportSequence.id == 1).first()
    if sequence is None:
        sequence = models.ReportSequence(id=1, last_number=0)
        db.add(sequence)
    sequence.last_number += 1
    db.commit()
    db.refresh(sequence)
    return sequence.last_number
