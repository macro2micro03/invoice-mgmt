"""생성된 서류를 이메일로 보내는 기능.

처음에는 사용자 각자의 Gmail 계정(SMTP + 앱 비밀번호)으로 보내려
했으나, Render는 스팸 방지를 위해 SMTP 포트(587 등) 아웃바운드 연결
자체를 막고 있어(실제로 재현·확인됨) 서버에서 직접 SMTP 접속이 불가능
하다. HTTPS로 통신하는 Resend API로 바꿨지만, Resend는 도메인 전체를
인증해야만 발신 계정 소유자 외의 수신자에게 보낼 수 있어(실제로
"you can only send testing emails to your own email address" 오류로
확인됨) 개인이 도메인을 따로 갖고 있지 않은 이 상황에는 맞지 않았다.
Brevo는 이메일 주소 하나만 인증(확인 메일 클릭)하면 임의의 수신자에게
보낼 수 있어 이걸로 최종 정착했다.
"""
import base64

import requests

from . import config

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
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
    if not config.BREVO_API_KEY:
        raise EmailSendError("이메일 발송 기능이 아직 설정되지 않았습니다 (BREVO_API_KEY 미설정)")
    if not config.BREVO_FROM_EMAIL:
        raise EmailSendError("이메일 발송 기능이 아직 설정되지 않았습니다 (BREVO_FROM_EMAIL 미설정)")

    response = requests.post(
        BREVO_API_URL,
        headers={
            "api-key": config.BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json={
            "sender": {"email": config.BREVO_FROM_EMAIL},
            "to": [{"email": addr} for addr in to_addresses],
            "subject": subject,
            # 본문이 비어 있으면(일부 API는 빈 문자열도 "없음"으로 취급해
            # 거부한다) 항상 비어있지 않은 기본 문구를 넣는다.
            "textContent": body.strip() if body and body.strip() else DEFAULT_BODY,
            "attachment": [
                {
                    "name": attachment_filename,
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
