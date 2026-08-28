from unittest.mock import MagicMock, patch

from app import email_sender


def test_send_email_with_attachment_logs_in_and_sends_via_starttls():
    with patch("app.email_sender.smtplib.SMTP") as mock_smtp_class:
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        email_sender.send_email_with_attachment(
            smtp_email="sender@gmail.com",
            smtp_app_password="app-password",
            to_addresses=["receiver@example.com"],
            subject="제목",
            body="본문",
            attachment_filename="report.xlsx",
            attachment_bytes=b"fake-xlsx-bytes",
        )

    mock_smtp_class.assert_called_once_with(email_sender.SMTP_HOST, email_sender.SMTP_PORT, timeout=30)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("sender@gmail.com", "app-password")
    assert mock_server.send_message.call_count == 1

    sent_message = mock_server.send_message.call_args[0][0]
    assert sent_message["From"] == "sender@gmail.com"
    assert sent_message["To"] == "receiver@example.com"
    assert sent_message["Subject"] == "제목"

    attachments = list(sent_message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "report.xlsx"
    assert attachments[0].get_payload(decode=True) == b"fake-xlsx-bytes"


def test_send_email_with_attachment_joins_multiple_recipients():
    with patch("app.email_sender.smtplib.SMTP") as mock_smtp_class:
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        email_sender.send_email_with_attachment(
            smtp_email="sender@gmail.com",
            smtp_app_password="app-password",
            to_addresses=["a@example.com", "b@example.com"],
            subject="제목",
            body="",
            attachment_filename="ledger.xlsx",
            attachment_bytes=b"bytes",
        )

    sent_message = mock_server.send_message.call_args[0][0]
    assert sent_message["To"] == "a@example.com, b@example.com"
