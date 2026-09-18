from unittest.mock import MagicMock, patch

from app import config, llm_tag_fallback


def _mock_response(text_value, status_ok=True):
    response = MagicMock()
    if status_ok:
        response.raise_for_status.return_value = None
    else:
        response.raise_for_status.side_effect = Exception("http error")
    response.json.return_value = {"content": [{"type": "text", "text": text_value}]}
    response.text = text_value
    return response


def test_call_claude_vision_skips_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        result = llm_tag_fallback.call_claude_vision(b"fake-bytes", "tag.jpg")
    mock_post.assert_not_called()
    assert result == {}


def test_call_claude_vision_posts_image_and_returns_parsed_json(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response('{"grade": "SD500", "diameter": "13", "manufacturer": "DK"}')
        result = llm_tag_fallback.call_claude_vision(b"fake-bytes", "tag.jpg")
    assert result == {"grade": "SD500", "diameter": "13", "manufacturer": "DK"}
    args, kwargs = mock_post.call_args
    assert args[0] == config.ANTHROPIC_MESSAGES_URL
    assert kwargs["headers"]["x-api-key"] == "test-key"
    assert kwargs["headers"]["anthropic-version"] == "2023-06-01"
    assert kwargs["json"]["model"] == config.CLAUDE_TAG_FALLBACK_MODEL
    content = kwargs["json"]["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["media_type"] == "image/jpeg"
    assert content[1]["type"] == "text"


def test_call_claude_vision_returns_empty_dict_on_http_failure(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response("", status_ok=False)
        result = llm_tag_fallback.call_claude_vision(b"fake-bytes", "tag.jpg")
    assert result == {}


def test_call_claude_vision_returns_empty_dict_on_non_json_response(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response("죄송합니다, 답변할 수 없습니다.")
        result = llm_tag_fallback.call_claude_vision(b"fake-bytes", "tag.jpg")
    assert result == {}


def test_extract_tag_fields_returns_valid_values(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response('{"grade": "SD500", "diameter": "13", "manufacturer": "DK"}')
        grade, diameter, manufacturer = llm_tag_fallback.extract_tag_fields(b"fake-bytes", "tag.jpg")
    assert grade == "SD500"
    assert diameter == "13"
    assert manufacturer == "동국제강"


def test_extract_tag_fields_accepts_manufacturer_as_full_name(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response('{"grade": "SD500", "diameter": "13", "manufacturer": "현대제철"}')
        _, _, manufacturer = llm_tag_fallback.extract_tag_fields(b"fake-bytes", "tag.jpg")
    assert manufacturer == "현대제철"


def test_extract_tag_fields_rejects_out_of_range_grade(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response('{"grade": "SD999", "diameter": "13", "manufacturer": "DK"}')
        grade, diameter, manufacturer = llm_tag_fallback.extract_tag_fields(b"fake-bytes", "tag.jpg")
    assert grade == ""
    assert diameter == "13"
    assert manufacturer == "동국제강"


def test_extract_tag_fields_rejects_out_of_range_diameter(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response('{"grade": "SD500", "diameter": "99", "manufacturer": "DK"}')
        grade, diameter, manufacturer = llm_tag_fallback.extract_tag_fields(b"fake-bytes", "tag.jpg")
    assert grade == "SD500"
    assert diameter == ""
    assert manufacturer == "동국제강"


def test_extract_tag_fields_rejects_manufacturer_outside_pool(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response(
            '{"grade": "SD500", "diameter": "13", "manufacturer": "알수없는제강"}'
        )
        grade, diameter, manufacturer = llm_tag_fallback.extract_tag_fields(b"fake-bytes", "tag.jpg")
    assert grade == "SD500"
    assert diameter == "13"
    assert manufacturer == ""


def test_extract_tag_fields_returns_blank_on_api_failure(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response("", status_ok=False)
        grade, diameter, manufacturer = llm_tag_fallback.extract_tag_fields(b"fake-bytes", "tag.jpg")
    assert grade == ""
    assert diameter == ""
    assert manufacturer == ""


def test_extract_tag_fields_returns_blank_when_llm_answers_null(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response('{"grade": null, "diameter": null, "manufacturer": null}')
        grade, diameter, manufacturer = llm_tag_fallback.extract_tag_fields(b"fake-bytes", "tag.jpg")
    assert grade == ""
    assert diameter == ""
    assert manufacturer == ""
