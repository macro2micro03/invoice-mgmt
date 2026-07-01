from app import ocr


def test_extract_text_from_flat_text_response():
    raw = {"text": "거래처: 대한제강"}
    assert ocr.extract_text(raw) == "거래처: 대한제강"


def test_extract_text_from_elements_response():
    raw = {"elements": [{"content": {"text": "line1"}}, {"content": {"text": "line2"}}]}
    assert ocr.extract_text(raw) == "line1\nline2"


def test_normalize_fields_extracts_labeled_values():
    text = (
        "거래처: 대한제강\n"
        "납품일: 2026-07-01\n"
        "차량번호: 12가3456\n"
        "송장번호: INV-001\n"
        "품명: 철근 D10\n"
        "규격: D10\n"
        "단위: TON\n"
        "수량: 10.5\n"
    )
    fields = ocr.normalize_fields(text)
    assert fields["vendor"] == "대한제강"
    assert fields["delivery_date"] == "2026-07-01"
    assert fields["vehicle_no"] == "12가3456"
    assert fields["invoice_no"] == "INV-001"
    assert fields["item_name"] == "철근 D10"
    assert fields["unit"] == "TON"


def test_normalize_fields_missing_label_returns_empty_strings():
    fields = ocr.normalize_fields("아무 관련 없는 텍스트")
    for field in ocr.STANDARD_FIELDS:
        assert fields[field] == ""


def test_call_upstage_ocr_sends_auth_header(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"text": "ok"}

    def fake_post(url, headers=None, files=None, timeout=None):
        captured["headers"] = headers
        captured["url"] = url
        return FakeResponse()

    monkeypatch.setattr(ocr, "requests", type("R", (), {"post": staticmethod(fake_post)}))
    monkeypatch.setattr(ocr.config, "UPSTAGE_API_KEY", "test-key")

    result = ocr.call_upstage_ocr(b"fake-bytes")
    assert result == {"text": "ok"}
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_call_upstage_ocr_raises_without_api_key(monkeypatch):
    monkeypatch.setattr(ocr.config, "UPSTAGE_API_KEY", "")
    try:
        ocr.call_upstage_ocr(b"fake-bytes")
        assert False, "should have raised"
    except RuntimeError:
        pass
