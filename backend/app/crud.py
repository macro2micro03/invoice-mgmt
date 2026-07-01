from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from . import models, schemas


def create_invoice(db: Session, data: schemas.InvoiceCreate, photo_path: Optional[str] = None) -> models.Invoice:
    invoice = models.Invoice(**data.model_dump(), photo_path=photo_path)
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
    db.commit()
    db.refresh(invoice)
    return invoice
