import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import crud, excel, pdf, photos, schemas
from ..database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/invoices", response_model=schemas.InvoiceOut)
async def create_invoice(
    material_type: str = Form(...),
    vendor: Optional[str] = Form(None),
    delivery_date: Optional[date] = Form(None),
    vehicle_no: Optional[str] = Form(None),
    invoice_no: Optional[str] = Form(None),
    item_name: Optional[str] = Form(None),
    spec: Optional[str] = Form(None),
    unit: Optional[str] = Form(None),
    quantity: Optional[float] = Form(None),
    weight: Optional[float] = Form(None),
    note: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    data = schemas.InvoiceCreate(
        material_type=material_type,
        vendor=vendor,
        delivery_date=delivery_date,
        vehicle_no=vehicle_no,
        invoice_no=invoice_no,
        item_name=item_name,
        spec=spec,
        unit=unit,
        quantity=quantity,
        weight=weight,
        note=note,
    )
    invoice = crud.create_invoice(db, data)

    if photo is not None:
        try:
            image_bytes = await photo.read()
            photo_path = photos.save_photo(image_bytes, photo.filename or "invoice.jpg")
            invoice.photo_path = photo_path
            db.commit()
            db.refresh(invoice)
        except Exception:
            logger.exception("사진 저장 실패")

    try:
        excel.append_invoice(invoice)
    except Exception:
        logger.exception("엑셀 저장 실패")

    if pdf.is_major_material(invoice.material_type):
        try:
            pdf.generate_pdf(invoice)
        except Exception:
            logger.exception("PDF 생성 실패")

    return invoice


@router.get("/invoices", response_model=list[schemas.InvoiceOut])
def search_invoices(
    vendor: Optional[str] = None,
    material_type: Optional[str] = None,
    invoice_no: Optional[str] = None,
    delivery_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return crud.list_invoices(
        db,
        vendor=vendor,
        material_type=material_type,
        invoice_no=invoice_no,
        delivery_date=delivery_date,
    )


@router.get("/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = crud.get_invoice(db, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="송장을 찾을 수 없습니다")
    return invoice


@router.put("/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def update_invoice(invoice_id: int, data: schemas.InvoiceUpdate, db: Session = Depends(get_db)):
    invoice = crud.update_invoice(db, invoice_id, data)
    if invoice is None:
        raise HTTPException(status_code=404, detail="송장을 찾을 수 없습니다")
    return invoice
