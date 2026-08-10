from datetime import date
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import crud, ocr, report_excel, report_from_records, report_ledger, report_parser
from ..auth import verify_password
from ..database import get_db

router = APIRouter(dependencies=[Depends(verify_password)])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CAPTURE_REPORT_MATERIAL_TYPE = "철근"


@router.post("/reports/material-inspection")
async def create_material_inspection_report(
    project_name: str = Form(...),
    work_type: str = Form(...),
    material_type: str = Form(...),
    sender: str = Form(...),
    receiver: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    delivery_date: Optional[str] = Form(None),
    invoice_ids: Optional[str] = Form(None),
    photo_set_1_top: List[UploadFile] = File(default=[]),
    photo_set_1_bottom: List[UploadFile] = File(default=[]),
    photo_set_2_top: List[UploadFile] = File(default=[]),
    photo_set_2_bottom: List[UploadFile] = File(default=[]),
    photo_set_3_top: List[UploadFile] = File(default=[]),
    photo_set_3_bottom: List[UploadFile] = File(default=[]),
    photo_set_4_top: List[UploadFile] = File(default=[]),
    photo_set_4_bottom: List[UploadFile] = File(default=[]),
    photo_set_5_top: List[UploadFile] = File(default=[]),
    photo_set_5_bottom: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    if invoice_ids:
        try:
            ids = [int(part) for part in invoice_ids.split(",") if part.strip()]
        except ValueError as error:
            raise HTTPException(status_code=400, detail="선택 항목 형식이 올바르지 않습니다") from error
        invoices = crud.list_invoices_by_ids(db, ids)
        if not invoices:
            raise HTTPException(status_code=400, detail="선택한 송장 기록을 찾을 수 없습니다")
        report_data = report_from_records.build_report_data_from_invoices(invoices)
    elif delivery_date:
        try:
            parsed_date = date.fromisoformat(delivery_date)
        except ValueError as error:
            raise HTTPException(
                status_code=400, detail="반입일자 형식이 올바르지 않습니다 (YYYY-MM-DD)"
            ) from error
        material_type = CAPTURE_REPORT_MATERIAL_TYPE
        invoices = crud.list_invoices_by_material_and_date(db, CAPTURE_REPORT_MATERIAL_TYPE, parsed_date)
        if not invoices:
            raise HTTPException(status_code=400, detail="해당 날짜에 촬영된 철근 기록이 없습니다")
        report_data = report_from_records.build_report_data_from_invoices(invoices, delivery_date=delivery_date)
    else:
        if not files:
            raise HTTPException(status_code=400, detail="파일을 업로드하거나 반입일자를 선택해주세요")
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

    photo_set_fields = [
        (photo_set_1_top, photo_set_1_bottom),
        (photo_set_2_top, photo_set_2_bottom),
        (photo_set_3_top, photo_set_3_bottom),
        (photo_set_4_top, photo_set_4_bottom),
        (photo_set_5_top, photo_set_5_bottom),
    ]
    photo_sets = []
    for top_files, bottom_files in photo_set_fields:
        top_bytes = [await photo.read() for photo in top_files]
        bottom_bytes = [await photo.read() for photo in bottom_files]
        photo_sets.append({"top": top_bytes, "bottom": bottom_bytes})

    report_number = crud.get_next_report_number(db)
    document_number = f"건축(자검) - {material_type} - {report_number}호"

    xlsx_bytes, skipped_specs = report_excel.fill_material_inspection_form(
        report_excel.TEMPLATE_PATH,
        project_name=project_name,
        work_type=work_type,
        material_type=material_type,
        document_number=document_number,
        sender=sender,
        receiver=receiver,
        specs=report_data["specs"],
        vendor=report_data["vendor"],
        delivery_date=report_data["delivery_date"],
        photo_sets=photo_sets,
    )

    warnings: List[str] = []
    if report_data["skipped_pages"]:
        warnings.append(
            f"{len(report_data['skipped_pages'])}개 페이지에서 자재 내역 표를 찾지 못해 제외했습니다"
        )
    if report_data.get("skipped_rows"):
        warnings.append(
            f"중량 값이 비정상적으로 큰 자재 행 {report_data['skipped_rows']}건을 제외했습니다 — 원본 문서를 확인해주세요"
        )
    if not report_data["vendor"]:
        warnings.append("거래처(반입업체명)를 자동으로 인식하지 못했습니다 — 문서에서 직접 확인해주세요")
    if not report_data["delivery_date"]:
        warnings.append("반입일자를 자동으로 인식하지 못했습니다 — 문서에서 직접 확인해주세요")
    if skipped_specs:
        warnings.append(
            f"자재 규격이 {len(skipped_specs)}개 더 있었지만 표 용량을 초과해 제외했습니다"
        )

    filename = f"자재검수요청서_{date.today():%y%m%d}_{report_number}.xlsx"
    encoded_filename = quote(filename)
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"report.xlsx\"; filename*=UTF-8''{encoded_filename}"
        )
    }
    if warnings:
        headers["X-Report-Warnings"] = quote(" | ".join(warnings))

    return Response(
        content=xlsx_bytes,
        media_type=XLSX_MEDIA_TYPE,
        headers=headers,
    )


@router.post("/reports/material-ledger")
async def create_material_ledger(
    invoice_ids: Optional[str] = Form(None),
    inspector: str = Form(""),
    supervisor: str = Form(""),
    db: Session = Depends(get_db),
):
    if not invoice_ids:
        raise HTTPException(status_code=400, detail="선택 항목이 없습니다")
    try:
        ids = [int(part) for part in invoice_ids.split(",") if part.strip()]
    except ValueError as error:
        raise HTTPException(status_code=400, detail="선택 항목 형식이 올바르지 않습니다") from error

    invoices = crud.list_invoices_by_ids(db, ids)
    if not invoices:
        raise HTTPException(status_code=400, detail="선택한 송장 기록을 찾을 수 없습니다")

    excluded_count = sum(
        1 for invoice in invoices if invoice.item_name == "커플러" or invoice.material_type != "철근"
    )
    rebar_invoices = sorted(
        (
            invoice
            for invoice in invoices
            if invoice.item_name != "커플러" and invoice.material_type == "철근"
        ),
        key=lambda invoice: invoice.delivery_date or date.min,
    )
    if not rebar_invoices:
        raise HTTPException(status_code=400, detail="선택한 기록 중 철근 자재 기록이 없습니다")

    xlsx_bytes = report_ledger.fill_material_ledger(
        report_ledger.TEMPLATE_PATH, rebar_invoices, inspector, supervisor
    )

    filename = f"주요자재검사및수불부_{date.today():%y%m%d}.xlsx"
    encoded_filename = quote(filename)
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"ledger.xlsx\"; filename*=UTF-8''{encoded_filename}"
        )
    }
    if excluded_count:
        headers["X-Report-Warnings"] = quote(
            f"커플러 또는 철근이 아닌 자재 {excluded_count}건은 수불부에서 제외했습니다"
        )

    return Response(
        content=xlsx_bytes,
        media_type=XLSX_MEDIA_TYPE,
        headers=headers,
    )
