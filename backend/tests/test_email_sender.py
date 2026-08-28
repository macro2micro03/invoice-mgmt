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


def test_send_email_with_attachment_posts_to_resend_api(monkeypatch):
    monkeypatch.setattr(config, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(config, "RESEND_FROM_EMAIL", "sender@resend.dev")

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
    assert args[0] == email_sender.RESEND_API_URL
    assert kwargs["headers"]["Authorization"] == "Bearer re_test_key"
    payload = kwargs["json"]
    assert payload["from"] == "sender@resend.dev"
    assert payload["to"] == ["receiver@example.com"]
    assert payload["subject"] == "제목"
    assert payload["text"] == "본문"
    assert payload["attachments"][0]["filename"] == "report.xlsx"
    assert base64.b64decode(payload["attachments"][0]["content"]) == b"fake-xlsx-bytes"


def test_send_email_with_attachment_raises_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(config, "RESEND_API_KEY", "")

    with pytest.raises(email_sender.EmailSendError):
        email_sender.send_email_with_attachment(
            to_addresses=["receiver@example.com"],
            subject="제목",
            body="",
            attachment_filename="report.xlsx",
            attachment_bytes=b"bytes",
        )


def test_send_email_with_attachment_raises_on_non_ok_response(monkeypatch):
    monkeypatch.setattr(config, "RESEND_API_KEY", "re_test_key")

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
