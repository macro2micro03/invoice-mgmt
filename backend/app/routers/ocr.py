from fastapi import APIRouter, Depends, File, UploadFile

from .. import ocr, report_parser
from ..auth import verify_password

router = APIRouter(dependencies=[Depends(verify_password)])


@router.post("/ocr")
async def run_ocr(file: UploadFile = File(...)):
    image_bytes = await file.read()
    try:
        raw_response = ocr.call_upstage_ocr(image_bytes, filename=file.filename or "invoice.jpg")
    except Exception:
        return {"records": [{field: "" for field in ocr.STANDARD_FIELDS}]}

    if report_parser.find_cover_pages(raw_response):
        records = report_parser.build_capture_records(raw_response)
        if records:
            return {"records": records}

    text = ocr.extract_text(raw_response)
    return {"records": [ocr.normalize_fields(text)]}
