from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile

from .. import ocr, report_parser, spec_grade
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


@router.post("/ocr/tag")
async def run_tag_ocr(file: UploadFile = File(...), spec: Optional[str] = Form(None)):
    image_bytes = await file.read()
    try:
        raw_response = ocr.call_upstage_ocr(image_bytes, filename=file.filename or "tag.jpg")
    except Exception:
        return {**{field: "" for field in ocr.TAG_FIELDS}, "tag_match_status": None}

    text = ocr.extract_text(raw_response)
    fields = ocr.normalize_tag_fields(text)
    tag_match_status = None
    if spec:
        tag_match_status = spec_grade.match_tag_to_spec(
            fields["tag_grade"] or None, fields["tag_diameter"] or None, spec
        )
    return {**fields, "tag_match_status": tag_match_status}
