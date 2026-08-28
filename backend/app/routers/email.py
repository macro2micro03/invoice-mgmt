import logging
import smtplib

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from .. import email_sender
from ..auth import verify_password

router = APIRouter(dependencies=[Depends(verify_password)])
logger = logging.getLogger(__name__)


@router.post("/email/send")
async def send_email(
    to: str = Form(...),
    smtp_email: str = Form(...),
    smtp_app_password: str = Form(...),
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
            smtp_email=smtp_email,
            smtp_app_password=smtp_app_password,
            to_addresses=to_addresses,
            subject=subject,
            body=body,
            attachment_filename=file.filename or "attachment.xlsx",
            attachment_bytes=attachment_bytes,
        )
    except smtplib.SMTPAuthenticationError as error:
        raise HTTPException(
            status_code=400, detail="Gmail 로그인에 실패했습니다 — 주소와 앱 비밀번호를 확인해주세요"
        ) from error
    except smtplib.SMTPException as error:
        logger.exception("이메일 발송 실패")
        raise HTTPException(status_code=502, detail=f"이메일 발송에 실패했습니다: {error}") from error

    return {"sent": True, "to": to_addresses}
