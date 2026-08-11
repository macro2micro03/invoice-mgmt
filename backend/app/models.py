from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    material_type = Column(String, nullable=False, index=True)
    vendor = Column(String, nullable=True, index=True)
    delivery_date = Column(Date, nullable=True, index=True)
    vehicle_no = Column(String, nullable=True)
    invoice_no = Column(String, nullable=True, index=True)
    item_name = Column(String, nullable=True)
    spec = Column(String, nullable=True)
    unit = Column(String, nullable=True)
    quantity = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)
    note = Column(String, nullable=True)
    photo_path = Column(String, nullable=True)
    tag_photo_path = Column(String, nullable=True)
    tag_site_name = Column(String, nullable=True)
    tag_location = Column(String, nullable=True)
    tag_diameter = Column(String, nullable=True)
    tag_grade = Column(String, nullable=True)
    tag_length = Column(String, nullable=True)
    tag_quantity = Column(String, nullable=True)
    tag_shape = Column(String, nullable=True)
    tag_match_status = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False, unique=True)
    defect_qty = Column(Float, nullable=True)
    defect_reason = Column(String, nullable=True)
    release_date = Column(Date, nullable=True)
    release_qty = Column(Float, nullable=True)
    remaining_qty = Column(Float, nullable=True)
    inspector = Column(String, nullable=True)
    supervisor = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    invoice = relationship("Invoice")


class ReportSequence(Base):
    __tablename__ = "report_sequences"

    id = Column(Integer, primary_key=True)
    last_number = Column(Integer, nullable=False, default=0)
