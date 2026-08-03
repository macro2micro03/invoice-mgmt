from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class InvoiceBase(BaseModel):
    material_type: str
    vendor: Optional[str] = None
    delivery_date: Optional[date] = None
    vehicle_no: Optional[str] = None
    invoice_no: Optional[str] = None
    item_name: Optional[str] = None
    spec: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = None
    weight: Optional[float] = None
    note: Optional[str] = None
    tag_site_name: Optional[str] = None
    tag_location: Optional[str] = None
    tag_diameter: Optional[str] = None
    tag_grade: Optional[str] = None
    tag_length: Optional[str] = None
    tag_quantity: Optional[str] = None
    tag_shape: Optional[str] = None


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(InvoiceBase):
    pass


class InvoiceOut(InvoiceBase):
    id: int
    photo_path: Optional[str] = None
    tag_photo_path: Optional[str] = None
    tag_match_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
