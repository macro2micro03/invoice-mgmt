from app import ocr


def test_extract_text_from_flat_text_response():
    raw = {"text": "거래처: 대한제강"}
    assert ocr.extract_text(raw) == "거래처: 대한제강"


def test_extract_text_from_elements_response():
    raw = {"elements": [{"content": {"text": "line1"}}, {"content": {"text": "line2"}}]}
    assert ocr.extract_text(raw) == "line1\nline2"


def test_extract_text_from_real_upstage_document_parse_response():
    # 실제 Upstage document-parse API는 content.text/elements[].content.text가
    # 항상 빈 문자열이고, 실제 내용은 content.html / elements[].content.html에
    # <br> 태그로 줄바꿈된 HTML로 들어있다.
    raw = {
        "content": {
            "html": "<h1 id='0'>거래명세서</h1>\n<p id='1'>거래처: 대한제강<br>송장번호: INV-001</p>",
            "markdown": "",
            "text": "",
        },
        "elements": [
            {"content": {"html": "<h1 id='0'>거래명세서</h1>", "markdown": "", "text": ""}},
            {
                "content": {
                    "html": "<p id='1'>거래처: 대한제강<br>송장번호: INV-001</p>",
                    "markdown": "",
                    "text": "",
                }
            },
        ],
    }
    text = ocr.extract_text(raw)
    assert "거래처: 대한제강" in text
    assert "송장번호: INV-001" in text


def test_extract_text_html_entities_are_unescaped():
    raw = {"content": {"html": "<p>규격: 10&amp;20</p>", "text": ""}}
    assert ocr.extract_text(raw) == "규격: 10&20"


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


def test_normalize_fields_infers_material_type_from_item_name():
    # 실제 송장에는 "자재종류"라는 라벨이 따로 없는 경우가 많다.
    # 품명에 지원 자재 목록 중 하나가 포함되어 있으면 그것으로 채운다.
    text = "품명: 철근 D10\n단위: TON\n"
    fields = ocr.normalize_fields(text)
    assert fields["material_type"] == "철근"


def test_normalize_fields_prefers_explicit_material_type_label_over_inference():
    text = "자재종류: 시멘트\n품명: 철근 D10\n"
    fields = ocr.normalize_fields(text)
    assert fields["material_type"] == "시멘트"


def test_normalize_fields_leaves_material_type_empty_when_item_name_has_no_known_material():
    text = "품명: 알 수 없는 자재\n"
    fields = ocr.normalize_fields(text)
    assert fields["material_type"] == ""


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


def test_normalize_tag_fields_extracts_labeled_values():
    text = (
        "현장명: 서소문 재개발\n"
        "부재시공위치: 지하 2층 슬라브\n"
        "직경: 13\n"
        "강도: SD500\n"
        "길이: 12000\n"
        "수량: 50\n"
        "가공형상: 직선\n"
    )
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_site_name"] == "서소문 재개발"
    assert fields["tag_location"] == "지하 2층 슬라브"
    assert fields["tag_diameter"] == "13"
    assert fields["tag_grade"] == "SD500"
    assert fields["tag_length"] == "12000"
    assert fields["tag_quantity"] == "50"
    assert fields["tag_shape"] == "직선"


def test_normalize_tag_fields_recovers_grade_diameter_from_manufacturer_style_a():
    # 동국제강 스타일: "종류의기호"란에 SD500, "호칭및길이"란에 "D10 X 8.0m"처럼
    # 직경/강도 라벨이 전혀 없다.
    text = (
        "종 류\n이 형 봉 강\n"
        "종류의기호\nSD500\n"
        "호칭및길이\nD10 X 8.0m\n"
        "수 량\n210PCS / 941kg\n"
    )
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_grade"] == "SD500"
    assert fields["tag_diameter"] == "10"


def test_normalize_tag_fields_recovers_grade_diameter_from_manufacturer_style_b():
    # 현대제철 스타일: "강종"란에 SD600, "규격"란에 "D16 X 8 M".
    text = "강 종\nSD600\n규 격\nD16 X 8 M\n제강번호\nK 347001 027\n"
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_grade"] == "SD600"
    assert fields["tag_diameter"] == "16"


def test_normalize_tag_fields_recovers_grade_diameter_from_bare_spec_code():
    # 현장 가공 택: 라벨 없이 UHD22, SD600 같은 값만 표에 나열된다.
    text = "삼성물산-서소문빌딩재개발 현장\nUHD22    7,700    52\nSD600    mm    EA\n"
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_grade"] == "SD600"
    assert fields["tag_diameter"] == "22"


def test_normalize_tag_fields_fallback_does_not_override_labeled_values():
    # 라벨로 이미 값을 찾았으면 보조 추출로 덮어쓰지 않는다.
    text = "직경: 13\n강도: SD500\nUHD22\n"
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_diameter"] == "13"
    assert fields["tag_grade"] == "SD500"


def test_normalize_tag_fields_missing_label_returns_empty_strings():
    fields = ocr.normalize_tag_fields("아무 관련 없는 텍스트")
    for field in ocr.TAG_FIELDS:
        assert fields[field] == ""


def test_normalize_tag_fields_handles_table_concatenated_line():
    # Upstage document-parse는 표(table) 요소를 <br> 없이 셀만 이어붙여
    # HTML 태그를 제거하면 한 줄로 뭉쳐진다. 예: "현장명서소문 재개발직경13강도SD500"
    # 이 경우 라벨 뒤 값이 다음 라벨의 값까지 탐욕적으로 삼키면 안 된다.
    text = "현장명서소문 재개발직경13강도SD500길이12000"
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_site_name"] == "서소문 재개발"
    assert fields["tag_diameter"] == "13"
    assert fields["tag_grade"] == "SD500"
    assert fields["tag_length"] == "12000"
