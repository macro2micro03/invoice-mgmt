from typing import List
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import crud, ocr, report_docx, report_parser
from ..auth import verify_password
from ..database import get_db

router = APIRouter(dependencies=[Depends(verify_password)])

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.post("/reports/material-inspection")
async def create_material_inspection_report(
    project_name: str = Form(...),
    work_type: str = Form(...),
    material_type: str = Form(...),
    sender: str = Form(...),
    receiver: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    raw_responses = []
    for uploaded_file in files:
        image_bytes = await uploaded_file.read()
        try:
            raw_response = ocr.call_upstage_ocr(image_bytes, filename=uploaded_file.filename or "invoice.jpg")
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"OCR 호출 실패: {error}") from error
        raw_responses.append(raw_response)

    try:
        report_data = report_parser.build_report_data(raw_responses)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    report_number = crud.get_next_report_number(db)
    document_number = f"건축(자검)-{material_type}-{report_number}호"

    docx_bytes = report_docx.generate_material_inspection_docx(
        project_name=project_name,
        work_type=work_type,
        material_type=material_type,
        document_number=document_number,
        sender=sender,
        receiver=receiver,
        specs=report_data["specs"],
        vendor=report_data["vendor"],
    )

    warnings: List[str] = []
    if report_data["skipped_pages"]:
        warnings.append(
            f"{len(report_data['skipped_pages'])}개 페이지에서 자재 내역 표를 찾지 못해 제외했습니다"
        )
    if not report_data["vendor"]:
        warnings.append("거래처(반입업체명)를 자동으로 인식하지 못했습니다 — 문서에서 직접 확인해주세요")

    filename = f"{document_number}.docx"
    encoded_filename = quote(filename)
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"report.docx\"; filename*=UTF-8''{encoded_filename}"
        )
    }
    if warnings:
        headers["X-Report-Warnings"] = quote(" | ".join(warnings))

    return Response(
        content=docx_bytes,
        media_type=DOCX_MEDIA_TYPE,
        headers=headers,
    )
