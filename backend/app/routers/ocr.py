from fastapi import APIRouter, File, UploadFile

from .. import ocr

router = APIRouter()


@router.post("/ocr")
async def run_ocr(file: UploadFile = File(...)):
    image_bytes = await file.read()
    try:
        raw_response = ocr.call_upstage_ocr(image_bytes, filename=file.filename or "invoice.jpg")
    except Exception:
        return {field: "" for field in ocr.STANDARD_FIELDS}
    text = ocr.extract_text(raw_response)
    return ocr.normalize_fields(text)
