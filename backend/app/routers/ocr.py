import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile

from .. import config, llm_tag_fallback, ocr, report_parser, spec_grade
from ..auth import verify_password

router = APIRouter(dependencies=[Depends(verify_password)])
logger = logging.getLogger(__name__)


@router.post("/ocr")
async def run_ocr(file: UploadFile = File(...)):
    image_bytes = await file.read()
    try:
        raw_response = ocr.call_upstage_ocr(image_bytes, filename=file.filename or "invoice.jpg")
    except Exception:
        logger.exception("Upstage OCR 호출 실패 (filename=%s, bytes=%d)", file.filename, len(image_bytes))
        return {"records": [{field: "" for field in ocr.STANDARD_FIELDS}]}

    cover_pages = report_parser.find_cover_pages(raw_response)
    if cover_pages:
        records = report_parser.build_capture_records(raw_response)
        if records:
            return {"records": records}
        logger.warning(
            "갑지 페이지(%s)는 찾았지만 자재 내역을 추출하지 못함 (filename=%s)", cover_pages, file.filename
        )
    else:
        logger.warning(
            "갑지 제목을 인식하지 못함 (filename=%s) — 텍스트 미리보기: %r",
            file.filename,
            ocr.extract_text(raw_response)[:500],
        )

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
    if not text:
        logger.warning(
            "택 이미지에서 텍스트를 전혀 추출하지 못함 (filename=%s, bytes=%d) — 응답 키: %s, elements 개수: %d"
            " — 일반 텍스트 인식 API로 재시도",
            file.filename,
            len(image_bytes),
            list(raw_response.keys()),
            len(raw_response.get("elements", [])),
        )
        try:
            fallback_response = ocr.call_upstage_text_ocr(image_bytes, filename=file.filename or "tag.jpg")
            text = ocr.extract_text(fallback_response)
        except Exception:
            logger.exception("일반 텍스트 인식 API 호출 실패 (filename=%s)", file.filename)
    fields = ocr.normalize_tag_fields(text)
    if not fields["tag_grade"] or not fields["tag_diameter"] or not fields["tag_manufacturer"]:
        logger.warning(
            "택에서 강도/직경/제조사 인식 실패 (filename=%s, tag_grade=%r, tag_diameter=%r, tag_manufacturer=%r)"
            " — 텍스트 미리보기: %r",
            file.filename,
            fields["tag_grade"],
            fields["tag_diameter"],
            fields["tag_manufacturer"],
            text[:500],
        )
        if config.ANTHROPIC_API_KEY:
            media_type = (
                file.content_type
                if file.content_type in llm_tag_fallback.SUPPORTED_MEDIA_TYPES
                else "image/jpeg"
            )
            llm_grade, llm_diameter, llm_manufacturer = llm_tag_fallback.extract_tag_fields(
                image_bytes, file.filename or "tag.jpg", media_type
            )
            if not fields["tag_grade"] and llm_grade:
                fields["tag_grade"] = llm_grade
            if not fields["tag_diameter"] and llm_diameter:
                fields["tag_diameter"] = llm_diameter
            if not fields["tag_manufacturer"] and llm_manufacturer:
                fields["tag_manufacturer"] = llm_manufacturer
    tag_match_status = None
    if spec:
        tag_match_status = spec_grade.match_tag_to_spec(
            fields["tag_grade"] or None, fields["tag_diameter"] or None, spec
        )
    return {**fields, "tag_match_status": tag_match_status}
