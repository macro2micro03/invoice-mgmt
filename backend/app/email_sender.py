"""생성된 서류를 이메일로 보내는 기능.

처음에는 사용자 각자의 Gmail 계정(SMTP + 앱 비밀번호)으로 보내려
했으나, Render는 스팸 방지를 위해 SMTP 포트(587 등) 아웃바운드 연결
자체를 막고 있어(실제로 재현·확인됨) 서버에서 직접 SMTP 접속이 불가능
하다. 대신 HTTPS(막히지 않는 포트)로 통신하는 Resend 이메일 API를
쓴다. 발신 계정은 서버에 한 번 설정해 둔 공용 발신 주소를 쓰고,
개별 사용자가 계정을 만들 필요는 없다.
"""
import base64

import requests

from . import config

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_BODY = "첨부된 서류를 확인해주세요."


class EmailSendError(Exception):
    pass


def send_email_with_attachment(
    *,
    to_addresses: list[str],
    subject: str,
    body: str,
    attachment_filename: str,
    attachment_bytes: bytes,
) -> None:
    if not config.RESEND_API_KEY:
        raise EmailSendError("이메일 발송 기능이 아직 설정되지 않았습니다 (RESEND_API_KEY 미설정)")

    response = requests.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
        json={
            "from": config.RESEND_FROM_EMAIL,
            "to": to_addresses,
            "subject": subject,
            # Resend는 html/text 둘 다 없으면(빈 문자열도 "없음"으로 취급)
            # 요청 자체를 거부한다 — 본문을 비워 두고 보내면 "Missing 'html'
            # or 'text' field" 오류가 났다. 항상 비어있지 않은 기본 문구를 넣는다.
            "text": body.strip() if body and body.strip() else DEFAULT_BODY,
            "attachments": [
                {
                    "filename": attachment_filename,
                    "content": base64.b64encode(attachment_bytes).decode("ascii"),
                }
            ],
        },
        timeout=30,
    )
    if not response.ok:
        detail = response.text
        try:
            detail = response.json().get("message", detail)
        except Exception:
            pass
        raise EmailSendError(detail)
