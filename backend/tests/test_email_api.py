from unittest.mock import patch

from fastapi.testclient import TestClient

from app import email_sender
from app.main import app

client = TestClient(app)


def _send(**overrides):
    data = {
        "to": "receiver@example.com",
        "subject": "자재검수요청서",
        "body": "첨부 확인 부탁드립니다",
    }
    data.update(overrides)
    files = {"file": ("report.xlsx", b"fake-bytes", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    return client.post("/email/send", data=data, files=files)


def test_send_email_success():
    with patch("app.routers.email.email_sender.send_email_with_attachment") as mock_send:
        response = _send()

    assert response.status_code == 200
    assert response.json() == {"sent": True, "to": ["receiver@example.com"]}
    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to_addresses"] == ["receiver@example.com"]
    assert kwargs["attachment_filename"] == "report.xlsx"
    assert kwargs["attachment_bytes"] == b"fake-bytes"


def test_send_email_splits_and_trims_multiple_recipients():
    with patch("app.routers.email.email_sender.send_email_with_attachment") as mock_send:
        response = _send(to=" a@example.com ,b@example.com,")

    assert response.status_code == 200
    assert mock_send.call_args.kwargs["to_addresses"] == ["a@example.com", "b@example.com"]


def test_send_email_rejects_blank_recipient():
    response = _send(to="   ")
    assert response.status_code == 400
    assert "받는 사람" in response.json()["detail"]


def test_send_email_reports_send_errors_as_502():
    with patch("app.routers.email.email_sender.send_email_with_attachment") as mock_send:
        mock_send.side_effect = email_sender.EmailSendError("invalid recipient")
        response = _send()

    assert response.status_code == 502
    assert "이메일 발송에 실패했습니다" in response.json()["detail"]
