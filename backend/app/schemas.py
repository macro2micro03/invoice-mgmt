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
    # 철근 Tag 일괄 검수(여러 장 대조)에서 이 규격에 일치하는 택을 하나도
    # 찾지 못한 경우, 그 사실을 "missing"으로 명시적으로 저장하기 위한
    # 값이다. 보통은 비워두면 서버가 tag_grade/tag_diameter/spec으로
    # 자동 계산한다(기존 동작 그대로 유지).
    tag_match_status: Optional[str] = None


class InvoiceUpdate(InvoiceBase):
    pass


class BulkDeleteRequest(BaseModel):
    ids: list[int]


class LedgerEntryUpdate(BaseModel):
    defect_qty: Optional[float] = None
    defect_reason: Optional[str] = None
    release_date: Optional[date] = None
    release_qty: Optional[float] = None
    remaining_qty: Optional[float] = None
    inspector: Optional[str] = None
    supervisor: Optional[str] = None


class LedgerEntryOut(BaseModel):
    invoice_id: int
    delivery_date: Optional[date] = None
    spec: Optional[str] = None
    weight: Optional[float] = None
    defect_qty: Optional[float] = None
    defect_reason: Optional[str] = None
    release_date: Optional[date] = None
    release_qty: Optional[float] = None
    remaining_qty: Optional[float] = None
    inspector: Optional[str] = None
    supervisor: Optional[str] = None


class InvoiceOut(InvoiceBase):
    id: int
    photo_path: Optional[str] = None
    tag_photo_path: Optional[str] = None
    tag_match_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
