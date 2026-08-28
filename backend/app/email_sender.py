"""사용자 본인의 Gmail 계정(앱 비밀번호)으로 생성된 서류를 첨부해 보내는 기능.

이 앱은 사용자 여러 명이 하나의 공유 비밀번호로 접속하는 구조라, 발신
계정을 서버에 고정해 두지 않는다 — 매 요청마다 호출자가 자신의 Gmail
주소와 앱 비밀번호를 함께 보내고, 그 값은 이 SMTP 전송 한 번에만 쓰고
저장하지 않는다.
"""
import smtplib
from email.message import EmailMessage

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_email_with_attachment(
    *,
    smtp_email: str,
    smtp_app_password: str,
    to_addresses: list[str],
    subject: str,
    body: str,
    attachment_filename: str,
    attachment_bytes: bytes,
) -> None:
    message = EmailMessage()
    message["From"] = smtp_email
    message["To"] = ", ".join(to_addresses)
    message["Subject"] = subject
    message.set_content(body or "")
    message.add_attachment(
        attachment_bytes,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=attachment_filename,
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(smtp_email, smtp_app_password)
        server.send_message(message)
