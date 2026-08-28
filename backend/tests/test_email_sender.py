import base64
from unittest.mock import MagicMock, patch

import pytest

from app import config, email_sender


def _mock_response(ok=True, json_data=None, text=""):
    response = MagicMock()
    response.ok = ok
    response.json.return_value = json_data or {}
    response.text = text
    return response


def test_send_email_with_attachment_posts_to_brevo_api(monkeypatch):
    monkeypatch.setattr(config, "BREVO_API_KEY", "brevo_test_key")
    monkeypatch.setattr(config, "BREVO_FROM_EMAIL", "sender@example.com")

    with patch("app.email_sender.requests.post") as mock_post:
        mock_post.return_value = _mock_response(ok=True)

        email_sender.send_email_with_attachment(
            to_addresses=["receiver@example.com"],
            subject="제목",
            body="본문",
            attachment_filename="report.xlsx",
            attachment_bytes=b"fake-xlsx-bytes",
        )

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == email_sender.BREVO_API_URL
    assert kwargs["headers"]["api-key"] == "brevo_test_key"
    payload = kwargs["json"]
    assert payload["sender"] == {"email": "sender@example.com"}
    assert payload["to"] == [{"email": "receiver@example.com"}]
    assert payload["subject"] == "제목"
    assert payload["textContent"] == "본문"
    assert payload["attachment"][0]["name"] == "report.xlsx"
    assert base64.b64decode(payload["attachment"][0]["content"]) == b"fake-xlsx-bytes"


def test_send_email_with_attachment_sends_to_multiple_recipients(monkeypatch):
    monkeypatch.setattr(config, "BREVO_API_KEY", "brevo_test_key")
    monkeypatch.setattr(config, "BREVO_FROM_EMAIL", "sender@example.com")

    with patch("app.email_sender.requests.post") as mock_post:
        mock_post.return_value = _mock_response(ok=True)

        email_sender.send_email_with_attachment(
            to_addresses=["a@example.com", "b@example.com"],
            subject="제목",
            body="본문",
            attachment_filename="ledger.xlsx",
            attachment_bytes=b"bytes",
        )

    payload = mock_post.call_args.kwargs["json"]
    assert payload["to"] == [{"email": "a@example.com"}, {"email": "b@example.com"}]


def test_send_email_with_attachment_uses_default_body_when_blank(monkeypatch):
    # 본문을 비워 두고 보내면 실패했던 실제 버그(Resend 시절) — Brevo로
    # 바꾼 뒤에도 동일하게 기본 문구를 채워 보내는지 계속 확인한다.
    monkeypatch.setattr(config, "BREVO_API_KEY", "brevo_test_key")
    monkeypatch.setattr(config, "BREVO_FROM_EMAIL", "sender@example.com")

    with patch("app.email_sender.requests.post") as mock_post:
        mock_post.return_value = _mock_response(ok=True)

        email_sender.send_email_with_attachment(
            to_addresses=["receiver@example.com"],
            subject="제목",
            body="",
            attachment_filename="report.xlsx",
            attachment_bytes=b"bytes",
        )

    payload = mock_post.call_args.kwargs["json"]
    assert payload["textContent"] == email_sender.DEFAULT_BODY
    assert payload["textContent"] != ""


def test_send_email_with_attachment_raises_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(config, "BREVO_API_KEY", "")
    monkeypatch.setattr(config, "BREVO_FROM_EMAIL", "sender@example.com")

    with pytest.raises(email_sender.EmailSendError):
        email_sender.send_email_with_attachment(
            to_addresses=["receiver@example.com"],
            subject="제목",
            body="",
            attachment_filename="report.xlsx",
            attachment_bytes=b"bytes",
        )


def test_send_email_with_attachment_raises_when_from_email_missing(monkeypatch):
    monkeypatch.setattr(config, "BREVO_API_KEY", "brevo_test_key")
    monkeypatch.setattr(config, "BREVO_FROM_EMAIL", "")

    with pytest.raises(email_sender.EmailSendError):
        email_sender.send_email_with_attachment(
            to_addresses=["receiver@example.com"],
            subject="제목",
            body="",
            attachment_filename="report.xlsx",
            attachment_bytes=b"bytes",
        )


def test_send_email_with_attachment_raises_on_non_ok_response(monkeypatch):
    monkeypatch.setattr(config, "BREVO_API_KEY", "brevo_test_key")
    monkeypatch.setattr(config, "BREVO_FROM_EMAIL", "sender@example.com")

    with patch("app.email_sender.requests.post") as mock_post:
        mock_post.return_value = _mock_response(ok=False, json_data={"message": "invalid recipient"})

        with pytest.raises(email_sender.EmailSendError, match="invalid recipient"):
            email_sender.send_email_with_attachment(
                to_addresses=["bad-address"],
                subject="제목",
                body="",
                attachment_filename="report.xlsx",
                attachment_bytes=b"bytes",
            )
