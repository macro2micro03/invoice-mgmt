from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from . import config, models

pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
FONT_NAME = "HYSMyeongJo-Medium"

FIELD_LABELS = [
    ("거래처", "vendor"),
    ("납품일", "delivery_date"),
    ("차량번호", "vehicle_no"),
    ("송장번호", "invoice_no"),
    ("품명", "item_name"),
    ("규격", "spec"),
    ("단위", "unit"),
    ("수량", "quantity"),
    ("중량", "weight"),
    ("비고", "note"),
]


def is_major_material(material_type: str) -> bool:
    return material_type in config.MAJOR_MATERIALS


def generate_pdf(invoice: models.Invoice) -> str:
    filename = f"invoice_{invoice.id}.pdf"
    dest = config.PDF_DIR / filename
    pdf_canvas = canvas.Canvas(str(dest), pagesize=A4)
    pdf_canvas.setFont(FONT_NAME, 14)
    pdf_canvas.drawString(50, 800, f"주요자재 입고서류 - {invoice.material_type}")
    pdf_canvas.setFont(FONT_NAME, 11)
    y = 760
    for label, attr in FIELD_LABELS:
        value = getattr(invoice, attr)
        pdf_canvas.drawString(50, y, f"{label}: {value if value is not None else ''}")
        y -= 24
    pdf_canvas.save()
    return str(dest.relative_to(config.STORAGE_DIR)).replace("\\", "/")
