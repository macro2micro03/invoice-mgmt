# 철근 택 제조사 확인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 철근 택 검수에 제조사 확인을 추가한다 — 택 사진에서 제조사를 인식(라벨 매칭 → 실패 시 Claude 비전 폴백)하고, 실제 현장에 납품하는 7개 제강사 풀로 검증한 뒤, 송장 레코드의 `note` 필드와 대조해 일치 여부를 판정한다.

**Architecture:** 기존 강종/직경 검증 파이프라인(라벨 매칭 → 정규식/LLM 폴백 → 서버 저장 시 판정)에 제조사를 세 번째 필드로 통합한다. 라벨 매칭·LLM 응답 모두 `spec_grade.normalize_manufacturer`라는 단일 함수를 거쳐 7개 풀로 정규화되고, 풀 밖 값은 빈 문자열로 처리된다. LLM 호출은 강종/직경 폴백 호출에 통합되어 API 호출이 추가로 늘지 않는다. 저장 시점에 `crud.py`가 `tag_manufacturer_match_status`를 권위 있게 재계산한다(기존 `tag_match_status` 패턴과 동일).

**Tech Stack:** FastAPI, SQLAlchemy(SQLite), React, pytest + `unittest.mock`.

## Global Constraints

- 제조사 풀은 정확히 이 7개: `HS→현대제철`, `DK→동국제강`, `DH→대한제강`, `HK→한국철강`, `HY→환영철강`, `YK→YK스틸`, `HJ→한국제강`.
- 코드(대소문자 무관) 또는 정식명칭(법인 표기·부가정보 포함 가능)으로 인식된 값을 7개 정식명칭 중 하나로 정규화한다. 풀의 7개 중 어디에도 매칭되지 않으면 빈 문자열("")로 처리한다(인식 실패로 간주).
- 라벨 매칭·LLM 비전 두 경로 모두 동일한 `spec_grade.normalize_manufacturer` 함수를 거친다(검증 로직 단일화).
- LLM 폴백 트리거 조건은 강종·직경·제조사 중 **하나라도** 비어있을 때이며, 기존 강종/직경 폴백 호출 한 번에 제조사 추출을 통합한다(API 호출 횟수 불변).
- 이미 값이 채워진 필드는 LLM 결과로 절대 덮어쓰지 않는다.
- `tag_manufacturer_match_status`는 저장 시점에 서버(`crud.py`)가 `tag_manufacturer`와 `note`를 `spec_grade.match_manufacturer`로 비교해 권위 있게 계산한다 — 클라이언트가 보낸 값을 신뢰하지 않는다.
- 배포된 운영 DB(Render, SQLite)에 새 컬럼이 실제로 반영되도록 `migrations.py`의 `TAG_COLUMNS`에 반드시 추가한다.
- 편집 화면의 통합 적합 배너(`"일치하는 철근 Tag을 확인했습니다 : {grade}, D{diameter}, {제조사 코드}"`)는 강종+직경+제조사가 **모두** 일치할 때만 표시하고, 제조사는 **코드**(예: `DK`)로 표기한다. 제조사 판정 불가(미확인) 상태는 경고를 띄우지 않는다.
- 참고 설계 문서: `docs/superpowers/specs/2026-09-18-tag-manufacturer-check-design.md`

---

### Task 1: `spec_grade.py` — 제조사 풀 정의 및 정규화/매칭 함수

**Files:**
- Modify: `backend/app/spec_grade.py`
- Test: `backend/tests/test_spec_grade.py`

**Interfaces:**
- Consumes: 없음 (순수 함수, 신규 의존성 없음 — `re`는 이미 import됨)
- Produces:
  - `spec_grade.MANUFACTURER_POOL: dict[str, str]` — 코드 → 정식명칭
  - `spec_grade.normalize_manufacturer(value: str | None) -> str | None` — 풀의 정식명칭 또는 `None`
  - `spec_grade.match_manufacturer(tag_manufacturer: str | None, note: str | None) -> str | None` — `"matched"`/`"mismatched"`/`None`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_spec_grade.py` 맨 위 import를 바꾸고:

```python
from app.spec_grade import match_manufacturer, match_tag_to_spec, normalize_manufacturer, parse_spec_grade_diameter
```

파일 끝에 다음 테스트를 추가한다:

```python
def test_normalize_manufacturer_matches_code_case_insensitive():
    assert normalize_manufacturer("HS") == "현대제철"
    assert normalize_manufacturer("hs") == "현대제철"
    assert normalize_manufacturer("dk") == "동국제강"


def test_normalize_manufacturer_matches_full_name():
    assert normalize_manufacturer("동국제강") == "동국제강"


def test_normalize_manufacturer_strips_corporate_markers():
    assert normalize_manufacturer("㈜대한제강") == "대한제강"
    assert normalize_manufacturer("주식회사 한국철강") == "한국철강"
    assert normalize_manufacturer("(주)환영철강") == "환영철강"


def test_normalize_manufacturer_matches_with_extra_info():
    assert normalize_manufacturer("동국제강(부산공장)") == "동국제강"


def test_normalize_manufacturer_outside_pool_returns_none():
    assert normalize_manufacturer("알수없는제강") is None


def test_normalize_manufacturer_empty_or_none_returns_none():
    assert normalize_manufacturer("") is None
    assert normalize_manufacturer(None) is None


def test_match_manufacturer_matched_across_code_and_name():
    assert match_manufacturer("HS", "현대제철") == "matched"


def test_match_manufacturer_matched_with_corporate_marker_difference():
    assert match_manufacturer("㈜동국제강", "동국제강") == "matched"


def test_match_manufacturer_mismatched():
    assert match_manufacturer("HS", "동국제강") == "mismatched"


def test_match_manufacturer_returns_none_when_tag_manufacturer_missing():
    assert match_manufacturer(None, "동국제강") is None
    assert match_manufacturer("", "동국제강") is None


def test_match_manufacturer_returns_none_when_note_missing():
    assert match_manufacturer("HS", None) is None
    assert match_manufacturer("HS", "") is None


def test_match_manufacturer_returns_none_when_note_outside_pool():
    assert match_manufacturer("HS", "이상한업체") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_spec_grade.py -v`
Expected: FAIL with `ImportError: cannot import name 'normalize_manufacturer' from 'app.spec_grade'` (또는 `match_manufacturer`) — 아직 정의되지 않았다.

- [ ] **Step 3: Implement**

`backend/app/spec_grade.py` 파일 끝에 추가 (기존 `import re`, `GRADE_BY_PREFIX`, `parse_spec_grade_diameter`, `_normalize_diameter`, `_normalize_grade`, `match_tag_to_spec`는 그대로 둔다):

```python
MANUFACTURER_POOL = {
    "HS": "현대제철",
    "DK": "동국제강",
    "DH": "대한제강",
    "HK": "한국철강",
    "HY": "환영철강",
    "YK": "YK스틸",
    "HJ": "한국제강",
}

_CORPORATE_MARKERS_PATTERN = re.compile(r"\(주\)|㈜|주식회사|\s+")


def normalize_manufacturer(value: str | None) -> str | None:
    """원문 표기(코드 또는 정식명칭, 법인 표기 포함)를 MANUFACTURER_POOL의
    정식명칭으로 정규화한다. 풀의 7개 중 어디에도 매칭되지 않으면 None
    (인식 실패로 간주 — 강종/직경의 표준 목록 검증과 동일한 원칙)."""
    if not value:
        return None
    stripped = value.strip()
    if stripped.upper() in MANUFACTURER_POOL:
        return MANUFACTURER_POOL[stripped.upper()]
    cleaned = _CORPORATE_MARKERS_PATTERN.sub("", stripped)
    if not cleaned:
        return None
    for canonical_name in MANUFACTURER_POOL.values():
        if canonical_name in cleaned or cleaned in canonical_name:
            return canonical_name
    return None


def match_manufacturer(tag_manufacturer: str | None, note: str | None) -> str | None:
    norm_tag = normalize_manufacturer(tag_manufacturer)
    norm_note = normalize_manufacturer(note)
    if norm_tag is None or norm_note is None:
        return None
    return "matched" if norm_tag == norm_note else "mismatched"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_spec_grade.py -v`
Expected: PASS (기존 11개 + 신규 12개 = 23개)

- [ ] **Step 5: Commit**

```bash
git add backend/app/spec_grade.py backend/tests/test_spec_grade.py
git commit -m "feat: 철근 택 제조사 풀 정규화·매칭 함수 추가"
```

---

### Task 2: `ocr.py` — 라벨 매칭에 제조사 통합

**Files:**
- Modify: `backend/app/ocr.py`
- Test: `backend/tests/test_ocr.py`

**Interfaces:**
- Consumes: Task 1의 `spec_grade.normalize_manufacturer(value: str | None) -> str | None`
- Produces: `ocr.normalize_tag_fields(raw_text: str) -> dict`의 반환값에 `"tag_manufacturer"` 키 추가(항상 풀의 정식명칭 또는 빈 문자열). `ocr.TAG_FIELDS`에도 `"tag_manufacturer"`가 자동 포함됨.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_ocr.py` 파일 끝에 추가:

```python
def test_normalize_tag_fields_extracts_manufacturer_label_and_normalizes_to_pool():
    text = "직경: 13\n강도: SD500\n제조사: ㈜현대제철\n"
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_manufacturer"] == "현대제철"


def test_normalize_tag_fields_manufacturer_label_code_normalizes_to_full_name():
    text = "직경: 13\n강도: SD500\n제강사: DK\n"
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_manufacturer"] == "동국제강"


def test_normalize_tag_fields_manufacturer_outside_pool_returns_empty_string():
    text = "직경: 13\n강도: SD500\n제조사: 알수없는제강\n"
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_manufacturer"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_ocr.py -v -k manufacturer`
Expected: FAIL with `KeyError: 'tag_manufacturer'` — `TAG_FIELD_LABELS`에 아직 `tag_manufacturer` 항목이 없어 `normalize_tag_fields`가 반환하는 dict에 그 키 자체가 없다.

- [ ] **Step 3: Implement**

`backend/app/ocr.py`의 `TAG_FIELD_LABELS`를 다음으로 교체:

```python
TAG_FIELD_LABELS = {
    "tag_site_name": ["현장명", "현장"],
    "tag_location": ["부재시공위치", "시공위치", "위치"],
    "tag_diameter": ["직경", "호칭경"],
    "tag_grade": ["강도", "강종"],
    "tag_length": ["길이"],
    "tag_quantity": ["수량"],
    "tag_shape": ["가공형상", "형상"],
    "tag_manufacturer": ["제조사", "제강사"],
}
```

(`TAG_FIELDS`, `_ALL_TAG_LABELS`, `_TAG_LABEL_LOOKAHEAD`는 모두 `TAG_FIELD_LABELS`에서 자동 파생되므로 이 딕셔너리 외에 다른 곳은 손댈 필요 없다.)

`normalize_tag_fields` 함수의 `return result` 직전(기존 강종/직경 fallback 보정 블록 다음)에 추가:

```python
    result["tag_manufacturer"] = spec_grade.normalize_manufacturer(result["tag_manufacturer"]) or ""

    return result
```

(`ocr.py`는 이미 파일 상단에서 `from . import config, spec_grade`로 `spec_grade`를 가져오고 있으므로 추가 import 불필요.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_ocr.py -v`
Expected: PASS (전체 통과, 신규 3개 포함)

- [ ] **Step 5: Commit**

```bash
git add backend/app/ocr.py backend/tests/test_ocr.py
git commit -m "feat: 택 라벨 매칭에 제조사 인식 및 풀 검증 추가"
```

---

### Task 3: `llm_tag_fallback.py` + `routers/ocr.py` — LLM 비전 추출 확장 및 라우터 배선

이 태스크는 두 파일을 하나로 묶는다: `extract_tag_grade_diameter`를 `extract_tag_fields`로 이름을 바꾸는 순간, 그 함수를 호출하는 라우터도 같이 바뀌지 않으면 라우터가 존재하지 않는 함수를 호출하게 된다. 두 변경을 한 태스크(한 커밋)로 묶어 그런 깨진 중간 상태가 커밋되지 않게 한다.

**Files:**
- Modify: `backend/app/llm_tag_fallback.py`, `backend/app/routers/ocr.py`
- Test: `backend/tests/test_llm_tag_fallback.py` (전체 재작성), `backend/tests/test_ocr_endpoint.py`

**Interfaces:**
- Consumes: Task 1의 `spec_grade.normalize_manufacturer(value: str | None) -> str | None`, Task 2의 `ocr.normalize_tag_fields(...)["tag_manufacturer"]`
- Produces:
  - `llm_tag_fallback.extract_tag_fields(image_bytes: bytes, filename: str, media_type: str = "image/jpeg") -> tuple[str, str, str]` (grade, diameter, manufacturer) — **기존 `extract_tag_grade_diameter`를 대체하며 이름이 바뀐다.** `call_claude_vision`의 시그니처/동작은 변경 없음.
  - `/ocr/tag` 응답에 `tag_manufacturer` 필드가 항상 포함됨(다른 필드와 동일하게 `fields`에서 자동 전개). 응답 형식(`{**fields, "tag_match_status": ...}`) 자체는 변경 없음.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_llm_tag_fallback.py`를 다음 내용으로 전체 교체한다:

```python
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
```

`backend/tests/test_ocr_endpoint.py`에서 아래 4개 기존 테스트를 **정확히 이 내용으로 교체**한다 (함수명은 그대로, 본문만 교체):

```python
def test_tag_ocr_endpoint_falls_back_to_llm_vision_when_regex_parsing_fails(monkeypatch):
    # "종류"/"치수"처럼 라벨 매칭(직경/호칭경/강도/강종/제조사/제강사)에도,
    # 정규식 fallback 패턴(SD/SHD/UHD+숫자, D+숫자)에도 걸리지 않는 제조사별
    # 표기를 흉내낸다. "생산업체"는 "제조사"/"제강사" 라벨과 겹치지 않도록
    # 일부러 고른 표현이다.
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_ocr",
        lambda image_bytes, filename="x": {"text": "종류: 5호강\n치수: 13mm\n생산업체: 현대제철"},
    )
    monkeypatch.setattr(ocr_router.config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        ocr_router.llm_tag_fallback,
        "extract_tag_fields",
        lambda image_bytes, filename, media_type: ("SD500", "13", "현대제철"),
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
    assert body["tag_manufacturer"] == "현대제철"
    assert body["tag_match_status"] == "matched"


def test_tag_ocr_endpoint_skips_llm_vision_fallback_when_regex_parsing_succeeds(monkeypatch):
    # 강도/직경/제조사가 모두 라벨로 이미 채워지면 폴백 트리거 조건
    # (셋 중 하나라도 비어있음)이 성립하지 않아 LLM이 호출되지 않는다.
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_ocr",
        lambda image_bytes, filename="x": {"text": "직경: 13\n강도: SD500\n제조사: 현대제철\n"},
    )
    monkeypatch.setattr(ocr_router.config, "ANTHROPIC_API_KEY", "test-key")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("regex parsing already succeeded — LLM fallback should not be called")

    monkeypatch.setattr(ocr_router.llm_tag_fallback, "extract_tag_fields", fail_if_called)
    response = client.post(
        "/ocr/tag",
        data={"spec": "SHD13"},
        files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tag_grade"] == "SD500"
    assert body["tag_manufacturer"] == "현대제철"


def test_tag_ocr_endpoint_skips_llm_vision_fallback_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_ocr",
        lambda image_bytes, filename="x": {"text": "종류: 5호강\n치수: 13mm\n생산업체: 현대제철"},
    )
    monkeypatch.setattr(ocr_router.config, "ANTHROPIC_API_KEY", "")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("ANTHROPIC_API_KEY unset — LLM fallback should not be called")

    monkeypatch.setattr(ocr_router.llm_tag_fallback, "extract_tag_fields", fail_if_called)
    response = client.post(
        "/ocr/tag",
        data={"spec": "SHD13"},
        files={"file": ("tag.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tag_grade"] == ""
    assert body["tag_diameter"] == ""
    assert body["tag_manufacturer"] == ""


def test_tag_ocr_endpoint_never_overwrites_field_already_found_by_regex(monkeypatch):
    # 정규식이 직경만 찾고 강도/제조사는 못 찾은 경우, LLM이 세 필드 모두에
    # 값을 반환해도 이미 찾은 직경은 절대 덮어쓰면 안 된다.
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_ocr",
        lambda image_bytes, filename="x": {"text": "직경: 13\n종류: 5호강"},
    )
    monkeypatch.setattr(ocr_router.config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        ocr_router.llm_tag_fallback,
        "extract_tag_fields",
        lambda image_bytes, filename, media_type: ("SD500", "99", "동국제강"),
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
    assert body["tag_manufacturer"] == "동국제강"
```

파일 끝에 새 테스트를 추가한다:

```python
def test_tag_ocr_endpoint_falls_back_to_llm_vision_when_only_manufacturer_missing(monkeypatch):
    # 강도/직경은 라벨로 찾았지만 제조사 라벨이 없는 경우에도 폴백이
    # 트리거되어야 하고, 이미 찾은 강도/직경은 LLM이 (일부러 틀린 값을)
    # 반환해도 덮어쓰이면 안 된다.
    monkeypatch.setattr(
        ocr_module,
        "call_upstage_ocr",
        lambda image_bytes, filename="x": {"text": "직경: 13\n강도: SD500\n"},
    )
    monkeypatch.setattr(ocr_router.config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        ocr_router.llm_tag_fallback,
        "extract_tag_fields",
        lambda image_bytes, filename, media_type: ("SD600", "22", "동국제강"),
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
    assert body["tag_manufacturer"] == "동국제강"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_llm_tag_fallback.py tests/test_ocr_endpoint.py -v`
Expected: FAIL — `test_llm_tag_fallback.py`에서 `call_claude_vision`만 다루는 4개 테스트(`test_call_claude_vision_*`)는 이 함수 자체가 아직 안 바뀌었으므로 그대로 통과하고, `extract_tag_fields`를 호출하는 나머지 8개는 `AttributeError: module 'app.llm_tag_fallback' has no attribute 'extract_tag_fields'`로 실패한다(아직 `extract_tag_grade_diameter`만 존재). `test_ocr_endpoint.py`는 (역시 `extract_tag_fields`가 아직 없으므로) `monkeypatch.setattr(ocr_router.llm_tag_fallback, "extract_tag_fields", ...)` 호출 자체가 `AttributeError`를 내며 실패한다.

- [ ] **Step 3: Implement `llm_tag_fallback.py`**

`backend/app/llm_tag_fallback.py`를 다음과 같이 수정한다.

import에 `spec_grade` 추가:

```python
from . import config, spec_grade
```

`_PROMPT`를 다음으로 교체:

```python
_PROMPT = (
    "이 사진은 철근 택(꼬리표) 사진입니다. 택에 표시된 철근의 강종, 직경, "
    "제조사만 다른 설명 없이 JSON으로 답하세요: "
    '{"grade": "SD300/SD400/SD500/SD600 중 하나, 모르면 null", '
    '"diameter": "13처럼 숫자만, 모르면 null", '
    '"manufacturer": "다음 7개 제강사 중 하나만 — HS(현대제철), DK(동국제강), '
    'DH(대한제강), HK(한국철강), HY(환영철강), YK(YK스틸), HJ(한국제강). '
    '코드나 정식명칭 아무거나로 답해도 됩니다. 이 목록에 없거나 모르면 null"}. '
    "확신이 없으면 null로 답하세요."
)
```

`_valid_diameter` 함수 바로 다음에 `_valid_manufacturer` 추가:

```python
def _valid_manufacturer(value) -> str:
    if not isinstance(value, str):
        return ""
    return spec_grade.normalize_manufacturer(value) or ""
```

`extract_tag_grade_diameter` 함수 전체를 다음으로 교체(이름 변경 포함):

```python
def extract_tag_fields(image_bytes: bytes, filename: str, media_type: str = "image/jpeg") -> tuple[str, str, str]:
    """call_claude_vision 결과를 검증해 (grade, diameter, manufacturer)를 반환한다.
    API 실패, 파싱 실패, 표준 목록/제조사 풀 밖의 값 — 어떤 경우든 해당 필드는
    예외 없이 빈 문자열("")이 된다."""
    raw = call_claude_vision(image_bytes, filename, media_type)
    raw_grade = raw.get("grade")
    raw_diameter = raw.get("diameter")
    raw_manufacturer = raw.get("manufacturer")
    grade = _valid_grade(raw_grade)
    diameter = _valid_diameter(raw_diameter)
    manufacturer = _valid_manufacturer(raw_manufacturer)
    if raw_grade and not grade:
        logger.warning(
            "Claude 비전 폴백이 표준 강종 목록 밖의 값을 반환함 (filename=%s): grade=%r",
            filename,
            raw_grade,
        )
    if raw_diameter and not diameter:
        logger.warning(
            "Claude 비전 폴백이 표준 직경 목록 밖의 값을 반환함 (filename=%s): diameter=%r",
            filename,
            raw_diameter,
        )
    if raw_manufacturer and not manufacturer:
        logger.warning(
            "Claude 비전 폴백이 제조사 풀 밖의 값을 반환함 (filename=%s): manufacturer=%r",
            filename,
            raw_manufacturer,
        )
    return grade, diameter, manufacturer
```

- [ ] **Step 4: Implement `routers/ocr.py`**

`backend/app/routers/ocr.py`의 `run_tag_ocr` 함수 내 다음 블록:

```python
    fields = ocr.normalize_tag_fields(text)
    if not fields["tag_grade"] or not fields["tag_diameter"]:
        logger.warning(
            "택에서 강도/직경 인식 실패 (filename=%s, tag_grade=%r, tag_diameter=%r) — 텍스트 미리보기: %r",
            file.filename,
            fields["tag_grade"],
            fields["tag_diameter"],
            text[:500],
        )
        if config.ANTHROPIC_API_KEY:
            media_type = (
                file.content_type
                if file.content_type in llm_tag_fallback.SUPPORTED_MEDIA_TYPES
                else "image/jpeg"
            )
            llm_grade, llm_diameter = llm_tag_fallback.extract_tag_grade_diameter(
                image_bytes, file.filename or "tag.jpg", media_type
            )
            if not fields["tag_grade"] and llm_grade:
                fields["tag_grade"] = llm_grade
            if not fields["tag_diameter"] and llm_diameter:
                fields["tag_diameter"] = llm_diameter
    tag_match_status = None
```

를 다음으로 교체한다:

```python
    fields = ocr.normalize_tag_fields(text)
    if not fields["tag_grade"] or not fields["tag_diameter"] or not fields["tag_manufacturer"]:
        logger.warning(
            "택에서 강도/직경/제조사 인식 실패 (filename=%s, tag_grade=%r, tag_diameter=%r, tag_manufacturer=%r)"
            " — 텍스트 미리보기: %r",
            file.filename,
            fields["tag_grade"],
            fields["tag_diameter"],
            fields["tag_manufacturer"],
            text[:500],
        )
        if config.ANTHROPIC_API_KEY:
            media_type = (
                file.content_type
                if file.content_type in llm_tag_fallback.SUPPORTED_MEDIA_TYPES
                else "image/jpeg"
            )
            llm_grade, llm_diameter, llm_manufacturer = llm_tag_fallback.extract_tag_fields(
                image_bytes, file.filename or "tag.jpg", media_type
            )
            if not fields["tag_grade"] and llm_grade:
                fields["tag_grade"] = llm_grade
            if not fields["tag_diameter"] and llm_diameter:
                fields["tag_diameter"] = llm_diameter
            if not fields["tag_manufacturer"] and llm_manufacturer:
                fields["tag_manufacturer"] = llm_manufacturer
    tag_match_status = None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_llm_tag_fallback.py tests/test_ocr_endpoint.py -v`
Expected: PASS (`test_llm_tag_fallback.py` 12개, `test_ocr_endpoint.py` 15개 — 기존 14개 + 신규 1개, 전체 통과)

- [ ] **Step 6: Commit**

```bash
git add backend/app/llm_tag_fallback.py backend/app/routers/ocr.py backend/tests/test_llm_tag_fallback.py backend/tests/test_ocr_endpoint.py
git commit -m "feat: Claude 비전 폴백과 /ocr/tag 엔드포인트에 제조사 인식 통합"
```

---

### Task 4: 데이터 계층 — `models.py` / `migrations.py` / `schemas.py` / `crud.py`

**Files:**
- Modify: `backend/app/models.py`, `backend/app/migrations.py`, `backend/app/schemas.py`, `backend/app/crud.py`
- Test: `backend/tests/test_crud.py`

**Interfaces:**
- Consumes: Task 1의 `spec_grade.match_manufacturer(tag_manufacturer, note) -> str | None`
- Produces: `models.Invoice.tag_manufacturer`, `models.Invoice.tag_manufacturer_match_status` 컬럼. `schemas.InvoiceBase.tag_manufacturer: Optional[str]`, `schemas.InvoiceOut.tag_manufacturer_match_status: Optional[str]`. `crud.create_invoice`/`crud.update_invoice`가 저장 시 `tag_manufacturer_match_status`를 권위 있게 계산.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_crud.py` 파일 끝에 추가:

```python
def test_create_invoice_computes_matched_manufacturer_status(db_session):
    created = crud.create_invoice(
        db_session, make_invoice_data(note="동국제강", tag_manufacturer="동국제강")
    )
    assert created.tag_manufacturer_match_status == "matched"


def test_create_invoice_computes_matched_manufacturer_status_across_code_and_name(db_session):
    created = crud.create_invoice(
        db_session, make_invoice_data(note="현대제철", tag_manufacturer="HS")
    )
    assert created.tag_manufacturer_match_status == "matched"


def test_create_invoice_computes_mismatched_manufacturer_status(db_session):
    created = crud.create_invoice(
        db_session, make_invoice_data(note="동국제강", tag_manufacturer="현대제철")
    )
    assert created.tag_manufacturer_match_status == "mismatched"


def test_create_invoice_without_manufacturer_info_leaves_status_none(db_session):
    created = crud.create_invoice(db_session, make_invoice_data(note="", tag_manufacturer=""))
    assert created.tag_manufacturer_match_status is None


def test_update_invoice_recomputes_manufacturer_match_status(db_session):
    created = crud.create_invoice(db_session, make_invoice_data(note="동국제강"))
    update_data = schemas.InvoiceUpdate(
        **{**make_invoice_data(note="동국제강").model_dump(), "tag_manufacturer": "동국제강"}
    )
    updated = crud.update_invoice(db_session, created.id, update_data)
    assert updated.tag_manufacturer_match_status == "matched"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_crud.py -v -k manufacturer`
Expected: FAIL with `AttributeError: 'Invoice' object has no attribute 'tag_manufacturer_match_status'`. (Pydantic v2 스키마는 기본적으로 선언되지 않은 kwarg를 조용히 무시하므로 `InvoiceCreate(**base, tag_manufacturer=...)` 생성 자체는 에러 없이 통과하고, `tag_manufacturer` 값도 그냥 버려진다 — `models.Invoice`에 아직 그 컬럼이 없어서 저장된 레코드의 속성에 접근할 때 실패한다.)

- [ ] **Step 3: Implement**

**`backend/app/models.py`** — `tag_match_status = Column(String, nullable=True)` 줄 바로 다음에 추가:

```python
    tag_manufacturer = Column(String, nullable=True)
    tag_manufacturer_match_status = Column(String, nullable=True)
```

**`backend/app/migrations.py`** — `TAG_COLUMNS`를 다음으로 교체(운영 DB에 실제로 컬럼이 추가되도록 반드시 포함):

```python
TAG_COLUMNS = {
    "tag_photo_path": "VARCHAR",
    "tag_site_name": "VARCHAR",
    "tag_location": "VARCHAR",
    "tag_diameter": "VARCHAR",
    "tag_grade": "VARCHAR",
    "tag_length": "VARCHAR",
    "tag_quantity": "VARCHAR",
    "tag_shape": "VARCHAR",
    "tag_match_status": "VARCHAR",
    "tag_manufacturer": "VARCHAR",
    "tag_manufacturer_match_status": "VARCHAR",
}
```

**`backend/app/schemas.py`** — `InvoiceBase`의 `tag_shape: Optional[str] = None` 줄 바로 다음에 추가:

```python
    tag_manufacturer: Optional[str] = None
```

`InvoiceOut`의 `tag_match_status: Optional[str] = None` 줄 바로 다음에 추가:

```python
    tag_manufacturer_match_status: Optional[str] = None
```

(클라이언트가 명시적으로 override할 이유가 없으므로 `InvoiceCreate`/`InvoiceUpdate`에는 `tag_manufacturer_match_status`를 추가하지 않는다 — `tag_manufacturer`는 `InvoiceBase`를 통해 이미 두 스키마에 상속된다.)

**`backend/app/crud.py`** — `create_invoice` 함수를 다음으로 교체:

```python
def create_invoice(
    db: Session,
    data: schemas.InvoiceCreate,
    photo_path: Optional[str] = None,
    tag_photo_path: Optional[str] = None,
) -> models.Invoice:
    payload = data.model_dump()
    explicit_tag_match_status = payload.pop("tag_match_status", None)
    # 명시적으로 넘어온 값(예: 철근 Tag 일괄 검수에서 이 규격에 대응하는
    # 택을 찾지 못해 "missing"으로 표시)이 있으면 그대로 쓰고, 없으면
    # 기존과 동일하게 tag_grade/tag_diameter/spec으로 자동 계산한다.
    tag_match_status = explicit_tag_match_status or spec_grade.match_tag_to_spec(
        data.tag_grade, data.tag_diameter, data.spec or ""
    )
    tag_manufacturer_match_status = spec_grade.match_manufacturer(data.tag_manufacturer, data.note)
    invoice = models.Invoice(
        **payload,
        photo_path=photo_path,
        tag_photo_path=tag_photo_path,
        tag_match_status=tag_match_status,
        tag_manufacturer_match_status=tag_manufacturer_match_status,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice
```

`update_invoice` 함수를 다음으로 교체:

```python
def update_invoice(db: Session, invoice_id: int, data: schemas.InvoiceUpdate) -> Optional[models.Invoice]:
    invoice = get_invoice(db, invoice_id)
    if invoice is None:
        return None
    for key, value in data.model_dump().items():
        setattr(invoice, key, value)
    invoice.tag_match_status = spec_grade.match_tag_to_spec(invoice.tag_grade, invoice.tag_diameter, invoice.spec or "")
    invoice.tag_manufacturer_match_status = spec_grade.match_manufacturer(invoice.tag_manufacturer, invoice.note)
    db.commit()
    db.refresh(invoice)
    return invoice
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_crud.py tests/test_migrations.py -v`
Expected: PASS — `test_crud.py` 전체(기존 + 신규 5개), `test_migrations.py`는 `TAG_COLUMNS`를 순회하는 기존 테스트가 새 컬럼 2개까지 자동으로 검증한다(테스트 코드 변경 불필요).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/app/migrations.py backend/app/schemas.py backend/app/crud.py backend/tests/test_crud.py
git commit -m "feat: 제조사 컬럼·스키마·마이그레이션 추가 및 저장 시 판정 계산"
```

---

### Task 5: 프론트엔드 — `EditPage.jsx` / `DetailPage.jsx`

**Files:**
- Modify: `frontend/src/pages/EditPage.jsx`, `frontend/src/pages/DetailPage.jsx`

**Interfaces:**
- Consumes: `/ocr/tag` 응답의 `tag_manufacturer` 필드(Task 3), `/invoices` 응답의 `tag_manufacturer`/`tag_manufacturer_match_status` 필드(Task 4)
- Produces: 없음(최종 UI 계층)

이 프로젝트의 프론트엔드는 자동 테스트가 없으므로(기존 패턴), 이 태스크는 TDD 대신 구현 후 빌드 확인으로 검증한다.

- [ ] **Step 1: `EditPage.jsx`에 제조사 풀·정규화·매칭 헬퍼 추가**

`frontend/src/pages/EditPage.jsx`의 다음 블록:

```js
// backend app/spec_grade.py의 match_tag_to_spec와 동일한 로직을 프런트에서도
// 재계산할 수 있도록 이식한 헬퍼.
function matchTagToSpec(tagGrade, tagDiameter, spec) {
  const [specGrade, specDiameter] = parseSpecGradeDiameter(spec)
  const normTagGrade = normalizeGrade(tagGrade)
  const normTagDiameter = normalizeDiameter(tagDiameter)
  if (specGrade === null || normTagGrade === null || normTagDiameter === null) return null
  if (specGrade === normTagGrade && specDiameter === normTagDiameter) return 'matched'
  return 'mismatched'
}
```

바로 다음에 추가:

```js
// backend app/spec_grade.py의 MANUFACTURER_POOL과 동일하게 유지할 것.
const MANUFACTURER_POOL = {
  HS: '현대제철',
  DK: '동국제강',
  DH: '대한제강',
  HK: '한국철강',
  HY: '환영철강',
  YK: 'YK스틸',
  HJ: '한국제강',
}
const CORPORATE_MARKERS_PATTERN = /\(주\)|㈜|주식회사|\s+/g

// backend app/spec_grade.py의 normalize_manufacturer와 동일한 로직을 프런트에서도
// 재계산할 수 있도록 이식한 헬퍼.
function normalizeManufacturer(value) {
  if (!value) return null
  const stripped = value.trim()
  const code = stripped.toUpperCase()
  if (MANUFACTURER_POOL[code]) return MANUFACTURER_POOL[code]
  const cleaned = stripped.replace(CORPORATE_MARKERS_PATTERN, '')
  if (!cleaned) return null
  const found = Object.values(MANUFACTURER_POOL).find(
    (name) => cleaned.includes(name) || name.includes(cleaned),
  )
  return found || null
}

function matchManufacturer(tagManufacturer, note) {
  const normTag = normalizeManufacturer(tagManufacturer)
  const normNote = normalizeManufacturer(note)
  if (normTag === null || normNote === null) return null
  return normTag === normNote ? 'matched' : 'mismatched'
}

// 배너 표시용 — 저장되는 tag_manufacturer는 정식명칭이지만, 적합 배너에는
// 코드로 표기하기 위한 정식명칭 → 코드 역변환 테이블.
const CODE_BY_MANUFACTURER = Object.fromEntries(
  Object.entries(MANUFACTURER_POOL).map(([code, name]) => [name, code]),
)
```

- [ ] **Step 2: 자재 카드의 성공 배너를 강종+직경+제조사 통합 배너로 교체**

다음 블록:

```jsx
          {tagFiles.length > 0 &&
            (itemAssignments[index] ? (
              <p className="banner banner-success">
                일치하는 철근 Tag를 확인했습니다: {itemAssignments[index].result.tag_grade} D
                {itemAssignments[index].result.tag_diameter}
              </p>
            ) : (
              <p className="banner banner-warning">이 규격에 해당하는 철근 Tag를 찾지 못했습니다</p>
            ))}
```

를 다음으로 교체:

```jsx
          {tagFiles.length > 0 &&
            (itemAssignments[index] ? (
              (() => {
                const tag = itemAssignments[index].result
                const manufacturerStatus = matchManufacturer(tag.tag_manufacturer, item.note)
                if (manufacturerStatus === 'matched') {
                  const code = CODE_BY_MANUFACTURER[tag.tag_manufacturer] || tag.tag_manufacturer
                  return (
                    <p className="banner banner-success">
                      일치하는 철근 Tag을 확인했습니다 : {tag.tag_grade}, D{tag.tag_diameter}, {code}
                    </p>
                  )
                }
                return (
                  <>
                    <p className="banner banner-success">
                      일치하는 철근 Tag를 확인했습니다: {tag.tag_grade} D{tag.tag_diameter}
                    </p>
                    {manufacturerStatus === 'mismatched' && (
                      <p className="banner banner-warning">
                        택 제조사({tag.tag_manufacturer})가 송장 비고({item.note})와 다릅니다
                      </p>
                    )}
                  </>
                )
              })()
            ) : (
              <p className="banner banner-warning">이 규격에 해당하는 철근 Tag를 찾지 못했습니다</p>
            ))}
```

- [ ] **Step 3: 택 카드에 제조사 입력 필드 추가**

다음 블록:

```jsx
                  <div className="field">
                    <label>직경 (자동 인식, 다르면 직접 수정)</label>
                    <input
                      className="input"
                      type="text"
                      value={result.tag_diameter || ''}
                      onChange={(e) => handleTagFieldEdit(file, 'tag_diameter', e.target.value)}
                      placeholder="예: 10, 13, 16"
                    />
                  </div>
                  {result.tag_grade &&
```

를 다음으로 교체:

```jsx
                  <div className="field">
                    <label>직경 (자동 인식, 다르면 직접 수정)</label>
                    <input
                      className="input"
                      type="text"
                      value={result.tag_diameter || ''}
                      onChange={(e) => handleTagFieldEdit(file, 'tag_diameter', e.target.value)}
                      placeholder="예: 10, 13, 16"
                    />
                  </div>
                  <div className="field">
                    <label>제조사 (자동 인식, 다르면 직접 수정)</label>
                    <input
                      className="input"
                      type="text"
                      value={result.tag_manufacturer || ''}
                      onChange={(e) => handleTagFieldEdit(file, 'tag_manufacturer', e.target.value)}
                      placeholder="예: 현대제철, DK, 동국제강"
                    />
                  </div>
                  {result.tag_grade &&
```

- [ ] **Step 4: 저장 시 `tag_manufacturer` 포함**

`handleSave` 함수 안의 다음 블록:

```js
        if (assignment) {
          const { tag_site_name, tag_location, tag_diameter, tag_grade, tag_length, tag_quantity, tag_shape } =
            assignment.result
          tagFields = { tag_site_name, tag_location, tag_diameter, tag_grade, tag_length, tag_quantity, tag_shape }
          tagPhotoFile = assignment.file
```

를 다음으로 교체:

```js
        if (assignment) {
          const {
            tag_site_name,
            tag_location,
            tag_diameter,
            tag_grade,
            tag_length,
            tag_quantity,
            tag_shape,
            tag_manufacturer,
          } = assignment.result
          tagFields = {
            tag_site_name,
            tag_location,
            tag_diameter,
            tag_grade,
            tag_length,
            tag_quantity,
            tag_shape,
            tag_manufacturer,
          }
          tagPhotoFile = assignment.file
```

- [ ] **Step 5: `DetailPage.jsx`에 제조사 필드·배너 추가**

`frontend/src/pages/DetailPage.jsx`의 `TAG_FIELD_DEFS`를 다음으로 교체:

```js
const TAG_FIELD_DEFS = [
  ['tag_site_name', '택 현장명'],
  ['tag_location', '택 부재시공위치'],
  ['tag_diameter', '택 직경'],
  ['tag_grade', '택 강도'],
  ['tag_manufacturer', '택 제조사'],
  ['tag_length', '택 길이'],
  ['tag_quantity', '택 수량'],
  ['tag_shape', '택 가공형상'],
]
```

다음 블록:

```jsx
        {invoice.tag_match_status === 'missing' && (
          <p className="banner banner-warning">
            이 규격({invoice.spec})에 해당하는 철근 Tag를 찾지 못했습니다 — 촬영한 택 중 일치하는 것이
            없습니다
          </p>
        )}
```

바로 다음에 추가:

```jsx
        {invoice.tag_manufacturer_match_status === 'mismatched' && (
          <p className="banner banner-warning">
            택 제조사({invoice.tag_manufacturer})가 송장 비고({invoice.note})와 다릅니다
          </p>
        )}
```

- [ ] **Step 6: 빌드 확인**

Run: `cd frontend && npm run build`
Expected: 에러 없이 빌드 성공 (`dist/` 생성)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/EditPage.jsx frontend/src/pages/DetailPage.jsx
git commit -m "feat: 편집/상세 화면에 철근 택 제조사 확인 UI 추가"
```

**참고(구현 완료 후 수동 확인 권장):** 개발 서버(`npm run dev`)를 띄워 실제로 택 사진을 촬영/선택했을 때 제조사 입력 필드가 표시되고, `note`가 있는 자재에 강종+직경+제조사가 모두 맞는 택을 배정했을 때 `"일치하는 철근 Tag을 확인했습니다 : SD600, D22, DK"` 형식의 통합 배너가 뜨는지, 제조사만 다를 때 별도 경고 배너가 뜨는지 브라우저에서 확인한다.

---

## 배포 참고 (구현 범위 밖, 기록용)

Render에 배포된 백엔드는 다음 배포 시 `migrations.py`가 자동으로 새 컬럼(`tag_manufacturer`, `tag_manufacturer_match_status`)을 기존 운영 DB에 추가한다(앱 시작 시 `run_migrations` 실행, 별도 수동 작업 불필요). 프론트엔드(Vercel)는 이 브랜치가 병합되면 자동 재배포된다.
