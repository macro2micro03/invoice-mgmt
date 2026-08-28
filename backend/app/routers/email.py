import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from .. import email_sender
from ..auth import verify_password

router = APIRouter(dependencies=[Depends(verify_password)])
logger = logging.getLogger(__name__)


@router.post("/email/send")
async def send_email(
    to: str = Form(...),
    subject: str = Form(...),
    body: str = Form(""),
    file: UploadFile = File(...),
):
    to_addresses = [addr.strip() for addr in to.split(",") if addr.strip()]
    if not to_addresses:
        raise HTTPException(status_code=400, detail="받는 사람을 입력해주세요")

    attachment_bytes = await file.read()
    try:
        email_sender.send_email_with_attachment(
            to_addresses=to_addresses,
            subject=subject,
            body=body,
            attachment_filename=file.filename or "attachment.xlsx",
            attachment_bytes=attachment_bytes,
        )
    except email_sender.EmailSendError as error:
        logger.exception("이메일 발송 실패")
        raise HTTPException(status_code=502, detail=f"이메일 발송에 실패했습니다: {error}") from error

    return {"sent": True, "to": to_addresses}
