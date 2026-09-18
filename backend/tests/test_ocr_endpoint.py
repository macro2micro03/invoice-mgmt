from fastapi.testclient import TestClient

from app import ocr as ocr_module
from app.main import app
from app.routers import ocr as ocr_router

client = TestClient(app)


def _cover_table_html():
    return (
        "<table><thead><tr><td>철근경</td><td>가공중량,Ton</td><td>할증(%)</td>"
        "<td>로스감안중량,Ton</td><td>커플러</td><td>비고</td></tr></thead><tbody>"
        "<tr><td>SHD10</td><td>0.528</td><td>3</td><td>0.544</td><td>0</td><td>동국제강</td></tr>"
        "<tr><td>SHD13</td><td>1.486</td><td>3</td><td>1.531</td><td>0</td><td>동국제강</td></tr>"
        "<tr><td>계</td><td>2.014</td><td></td><td>2.075</td><td></td><td></td></tr>"
        "</tbody></table>"
    )


def _cover_page_response():
    return {
        "elements": [
            {"page": 1, "category": "heading1", "content": {"html": "<h1>철근 납품 확인서</h1>", "text": ""}},
            {"page": 1, "category": "table", "content": {"html": _cover_table_html(), "text": ""}},
            {
                "page": 1,
                "category": "paragraph",
                "content": {"html": "<p>공장명: 동경강업(주)</p>", "text": ""},
            },
        ]
    }


def test_ocr_endpoint_returns_normalized_fields_for_free_form_document(monkeypatch):
    monkeypatch.setattr(ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": {"text": "거래처: 대한제강"})
    response = client.post("/ocr", files={"file": ("test.jpg", b"fake-image-bytes", "image/jpeg")})
    assert response.status_code == 200
    body = response.json()
    assert len(body["records"]) == 1
    assert body["records"][0]["vendor"] == "대한제강"


def test_ocr_endpoint_returns_blank_fields_on_failure(monkeypatch):
    def raise_error(*args, **kwargs):
        raise RuntimeError("network error")

    monkeypatch.setattr(ocr_module, "call_upstage_ocr", raise_error)
    response = client.post("/ocr", files={"file": ("test.jpg", b"fake-image-bytes", "image/jpeg")})
    assert response.status_code == 200
    body = response.json()
    assert len(body["records"]) == 1
    for field in ocr_module.STANDARD_FIELDS:
        assert body["records"][0][field] == ""


def test_ocr_endpoint_returns_multiple_records_for_cover_page_document(monkeypatch):
    monkeypatch.setattr(ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": _cover_page_response())
    response = client.post("/ocr", files={"file": ("cover.jpg", b"fake-image-bytes", "image/jpeg")})
    assert response.status_code == 200
    body = response.json()
    assert len(body["records"]) == 2
    specs = {record["spec"] for record in body["records"]}
    assert specs == {"SHD10", "SHD13"}
    for record in body["records"]:
        assert record["vendor"] == "동경강업(주)"
        assert record["material_type"] == "철근"


def test_tag_ocr_endpoint_returns_parsed_fields_and_match_status(monkeypatch):
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_ocr",
        lambda image_bytes, filename="x": {"text": "직경: 13\n강도: SD500\n"},
    )
    response = client.post(
        "/ocr/tag",
        data={"spec": "SHD13"},
        files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tag_diameter"] == "13"
    assert body["tag_grade"] == "SD500"
    assert body["tag_match_status"] == "matched"


def test_tag_ocr_endpoint_without_spec_skips_match_status(monkeypatch):
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_ocr",
        lambda image_bytes, filename="x": {"text": "직경: 13\n강도: SD500\n"},
    )
    response = client.post("/ocr/tag", files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")})
    assert response.status_code == 200
    assert response.json()["tag_match_status"] is None


def _tag_table_html():
    return (
        "<table><tbody>"
        "<tr><td>현장명</td><td>서소문 재개발</td><td>직경</td><td>13</td></tr>"
        "<tr><td>강도</td><td>SD500</td><td>길이</td><td>12000</td></tr>"
        "</tbody></table>"
    )


def _tag_table_response():
    return {
        "elements": [
            {"page": 1, "category": "table", "content": {"html": _tag_table_html(), "text": ""}},
        ]
    }


def test_tag_ocr_endpoint_parses_table_shaped_response_without_concatenation(monkeypatch):
    # 실제 택 사진은 Upstage에서 표(table)로 분류되기 쉽고, 표 셀은 <br> 없이
    # 이어붙여져 "직경13강도SD500"처럼 한 줄로 뭉쳐진다. 탐욕적 정규식이면
    # 직경 값이 "13강도SD500"처럼 다음 라벨의 값까지 삼켜버릴 수 있다.
    monkeypatch.setattr(ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": _tag_table_response())
    response = client.post(
        "/ocr/tag",
        data={"spec": "SHD13"},
        files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tag_diameter"] == "13"
    assert body["tag_grade"] == "SD500"
    assert body["tag_match_status"] == "matched"


def test_tag_ocr_endpoint_falls_back_to_text_ocr_when_document_parse_finds_no_text(monkeypatch):
    # 문서 구조가 없는 사물 사진(택 근접 촬영 등)은 document-parse가 요소를
    # 하나도 인식하지 못해 빈 텍스트를 반환할 수 있다. 이 경우 일반 텍스트
    # 인식 API를 보조로 호출해 복구를 시도해야 한다.
    monkeypatch.setattr(ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": {"elements": []})
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_text_ocr",
        lambda image_bytes, filename="x": {"text": "직경: 13\n강도: SD500\n"},
    )
    response = client.post(
        "/ocr/tag",
        data={"spec": "SHD13"},
        files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tag_diameter"] == "13"
    assert body["tag_grade"] == "SD500"
    assert body["tag_match_status"] == "matched"


def test_tag_ocr_endpoint_does_not_fall_back_when_document_parse_succeeds(monkeypatch):
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_ocr",
        lambda image_bytes, filename="x": {"text": "직경: 13\n강도: SD500\n"},
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("fallback text OCR should not be called when document-parse already found text")

    monkeypatch.setattr(ocr_module, "call_upstage_text_ocr", fail_if_called)
    response = client.post(
        "/ocr/tag",
        data={"spec": "SHD13"},
        files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["tag_grade"] == "SD500"


def test_tag_ocr_endpoint_returns_blank_fields_when_fallback_also_finds_nothing(monkeypatch):
    monkeypatch.setattr(ocr_module, "call_upstage_ocr", lambda image_bytes, filename="x": {"elements": []})
    monkeypatch.setattr(ocr_module, "call_upstage_text_ocr", lambda image_bytes, filename="x": {"elements": []})
    response = client.post("/ocr/tag", files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")})
    assert response.status_code == 200
    body = response.json()
    for field in ocr_module.TAG_FIELDS:
        assert body[field] == ""


def test_tag_ocr_endpoint_returns_blank_fields_on_ocr_failure(monkeypatch):
    def raise_error(*args, **kwargs):
        raise RuntimeError("network error")

    monkeypatch.setattr(ocr_module, "call_upstage_ocr", raise_error)
    response = client.post("/ocr/tag", files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")})
    assert response.status_code == 200
    body = response.json()
    for field in ocr_module.TAG_FIELDS:
        assert body[field] == ""
    assert body["tag_match_status"] is None


def test_tag_ocr_endpoint_falls_back_to_llm_vision_when_regex_parsing_fails(monkeypatch):
    # "종류"/"치수"처럼 라벨 매칭(직경/호칭경/강도/강종)에도, 정규식 fallback
    # 패턴(SD/SHD/UHD+숫자, D+숫자)에도 걸리지 않는 제조사별 표기를 흉내낸다.
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_ocr",
        lambda image_bytes, filename="x": {"text": "종류: 5호강\n치수: 13mm\n제조사: 현대제철"},
    )
    monkeypatch.setattr(ocr_router.config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        ocr_router.llm_tag_fallback,
        "extract_tag_grade_diameter",
        lambda image_bytes, filename: ("SD500", "13"),
    )
    response = client.post(
        "/ocr/tag",
        data={"spec": "SHD13"},
        files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tag_grade"] == "SD500"
    assert body["tag_diameter"] == "13"
    assert body["tag_match_status"] == "matched"


def test_tag_ocr_endpoint_skips_llm_vision_fallback_when_regex_parsing_succeeds(monkeypatch):
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_ocr",
        lambda image_bytes, filename="x": {"text": "직경: 13\n강도: SD500\n"},
    )
    monkeypatch.setattr(ocr_router.config, "ANTHROPIC_API_KEY", "test-key")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("regex parsing already succeeded — LLM fallback should not be called")

    monkeypatch.setattr(ocr_router.llm_tag_fallback, "extract_tag_grade_diameter", fail_if_called)
    response = client.post(
        "/ocr/tag",
        data={"spec": "SHD13"},
        files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["tag_grade"] == "SD500"


def test_tag_ocr_endpoint_skips_llm_vision_fallback_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_ocr",
        lambda image_bytes, filename="x": {"text": "종류: 5호강\n치수: 13mm\n제조사: 현대제철"},
    )
    monkeypatch.setattr(ocr_router.config, "ANTHROPIC_API_KEY", "")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("ANTHROPIC_API_KEY unset — LLM fallback should not be called")

    monkeypatch.setattr(ocr_router.llm_tag_fallback, "extract_tag_grade_diameter", fail_if_called)
    response = client.post(
        "/ocr/tag",
        data={"spec": "SHD13"},
        files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tag_grade"] == ""
    assert body["tag_diameter"] == ""
