from sqlalchemy import Column, Integer, String, Float, Date, DateTime
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
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
