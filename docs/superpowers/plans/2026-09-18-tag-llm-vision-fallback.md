# 철근 택 인식 LLM 비전 폴백 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/ocr/tag` 엔드포인트에서 라벨 매칭 + 정규식 파싱이 실패했을 때(강종/직경 둘 중 하나라도 비어있음), 택 원본 사진을 Claude Haiku 4.5 비전에 직접 보내 강종/직경을 재추출하는 폴백을 추가한다.

**Architecture:** 기존 Upstage OCR → 라벨 매칭 → 정규식 fallback 흐름은 그대로 두고, 그 뒤에 한 단계를 추가한다. 새 모듈 `app/llm_tag_fallback.py`가 (기존 `ocr.py`/`email_sender.py`와 동일하게 SDK 없이) `requests`로 Anthropic Messages API를 직접 호출해 JSON을 받고, 표준 규격 목록으로 검증한 값만 반환한다. 라우터는 이미 채워진 필드는 덮어쓰지 않고 빈 필드만 채운다.

**Tech Stack:** FastAPI, `requests`(신규 의존성 없음), pytest + `unittest.mock`.

## Global Constraints

- 적용 범위는 `/ocr/tag`(철근 Tag 인식)로 한정한다. `/ocr`(일반 송장)은 변경하지 않는다.
- LLM 호출은 기존 파싱(라벨 매칭 + 정규식 fallback) 후에도 `tag_grade` 또는 `tag_diameter`가 비어있을 때만 트리거한다.
- 모델: `claude-haiku-4-5-20251001`
- API 엔드포인트: `https://api.anthropic.com/v1/messages` (헤더 `anthropic-version: 2023-06-01`)
- 강종 검증 목록: `{"SD300", "SD400", "SD500", "SD600"}`
- 직경 검증 목록(mm, 숫자 문자열): `{"6", "10", "13", "16", "19", "22", "25", "29", "32", "35", "38", "41", "51", "57"}`
- `ANTHROPIC_API_KEY` 미설정 시 폴백을 건너뛴다(에러 없이, 기존 동작 유지). Upstage 키와 달리 필수 아님.
- 이미 채워진 필드는 LLM 결과로 절대 덮어쓰지 않는다.
- API 호출 실패/JSON 파싱 실패/목록 밖 값은 모두 예외 없이 빈 문자열로 저하(degrade)한다.
- 새 pip 의존성을 추가하지 않는다(`requests`는 이미 `requirements.txt`에 있음).

---

### Task 1: `llm_tag_fallback` 모듈 (Claude 비전 호출 + 검증)

**Files:**
- Create: `backend/app/llm_tag_fallback.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_llm_tag_fallback.py`

**Interfaces:**
- Consumes: `app.config.ANTHROPIC_API_KEY: str`, `app.config.CLAUDE_TAG_FALLBACK_MODEL: str`, `app.config.ANTHROPIC_MESSAGES_URL: str` (이 태스크에서 함께 추가)
- Produces:
  - `llm_tag_fallback.call_claude_vision(image_bytes: bytes, filename: str, media_type: str = "image/jpeg") -> dict` — Anthropic API 원시 JSON(`{"grade": ..., "diameter": ...}`) 또는 실패 시 `{}`
  - `llm_tag_fallback.extract_tag_grade_diameter(image_bytes: bytes, filename: str, media_type: str = "image/jpeg") -> tuple[str, str]` — 검증된 `(grade, diameter)`, 실패/무효 시 `("", "")`
  - `llm_tag_fallback.VALID_GRADES: set[str]`, `llm_tag_fallback.VALID_DIAMETERS: set[str]`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_llm_tag_fallback.py`:

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
        mock_post.return_value = _mock_response('{"grade": "SD500", "diameter": "13"}')
        result = llm_tag_fallback.call_claude_vision(b"fake-bytes", "tag.jpg")
    assert result == {"grade": "SD500", "diameter": "13"}
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


def test_extract_tag_grade_diameter_returns_valid_values(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response('{"grade": "SD500", "diameter": "13"}')
        grade, diameter = llm_tag_fallback.extract_tag_grade_diameter(b"fake-bytes", "tag.jpg")
    assert grade == "SD500"
    assert diameter == "13"


def test_extract_tag_grade_diameter_rejects_out_of_range_grade(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response('{"grade": "SD999", "diameter": "13"}')
        grade, diameter = llm_tag_fallback.extract_tag_grade_diameter(b"fake-bytes", "tag.jpg")
    assert grade == ""
    assert diameter == "13"


def test_extract_tag_grade_diameter_rejects_out_of_range_diameter(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response('{"grade": "SD500", "diameter": "99"}')
        grade, diameter = llm_tag_fallback.extract_tag_grade_diameter(b"fake-bytes", "tag.jpg")
    assert grade == "SD500"
    assert diameter == ""


def test_extract_tag_grade_diameter_returns_blank_on_api_failure(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response("", status_ok=False)
        grade, diameter = llm_tag_fallback.extract_tag_grade_diameter(b"fake-bytes", "tag.jpg")
    assert grade == ""
    assert diameter == ""


def test_extract_tag_grade_diameter_returns_blank_when_llm_answers_null(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response('{"grade": null, "diameter": null}')
        grade, diameter = llm_tag_fallback.extract_tag_grade_diameter(b"fake-bytes", "tag.jpg")
    assert grade == ""
    assert diameter == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_llm_tag_fallback.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.llm_tag_fallback'` (or `AttributeError: module 'app.config' has no attribute 'ANTHROPIC_API_KEY'` once the module import itself is fixed) — the module and config constants don't exist yet.

- [ ] **Step 3: Add config constants**

In `backend/app/config.py`, add after the existing `UPSTAGE_TEXT_OCR_URL` line:

```python
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_TAG_FALLBACK_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
```

- [ ] **Step 4: Implement `llm_tag_fallback.py`**

Create `backend/app/llm_tag_fallback.py`:

```python
import base64
import json
import logging
import re

import requests

from . import config

logger = logging.getLogger(__name__)

VALID_GRADES = {"SD300", "SD400", "SD500", "SD600"}
VALID_DIAMETERS = {"6", "10", "13", "16", "19", "22", "25", "29", "32", "35", "38", "41", "51", "57"}

_PROMPT = (
    "이 사진은 철근 택(꼬리표) 사진입니다. 택에 표시된 철근의 강종과 직경만 "
    "다른 설명 없이 JSON으로 답하세요: "
    '{"grade": "SD300/SD400/SD500/SD600 중 하나, 모르면 null", '
    '"diameter": "13처럼 숫자만, 모르면 null"}. 확신이 없으면 null로 답하세요.'
)

# 지시에도 불구하고 응답 앞뒤에 설명 문장이나 코드펜스가 붙는 경우가 있어,
# 텍스트 전체가 아니라 그 안의 {...} 블록만 골라 파싱한다.
_JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def call_claude_vision(image_bytes: bytes, filename: str, media_type: str = "image/jpeg") -> dict:
    if not config.ANTHROPIC_API_KEY:
        return {}
    try:
        response = requests.post(
            config.ANTHROPIC_MESSAGES_URL,
            headers={
                "x-api-key": config.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": config.CLAUDE_TAG_FALLBACK_MODEL,
                "max_tokens": 100,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64.b64encode(image_bytes).decode("ascii"),
                                },
                            },
                            {"type": "text", "text": _PROMPT},
                        ],
                    }
                ],
            },
            timeout=30,
        )
        response.raise_for_status()
    except Exception:
        logger.exception("Claude 비전 폴백 API 호출 실패 (filename=%s)", filename)
        return {}

    try:
        body = response.json()
        text = body["content"][0]["text"]
        match = _JSON_BLOCK_PATTERN.search(text)
        if not match:
            raise ValueError(f"응답에서 JSON 블록을 찾지 못함: {text!r}")
        return json.loads(match.group(0))
    except Exception:
        logger.warning(
            "Claude 비전 폴백 응답을 JSON으로 파싱하지 못함 (filename=%s) — 원본: %r",
            filename,
            response.text[:500],
        )
        return {}


def _valid_grade(value) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.strip().upper()
    return normalized if normalized in VALID_GRADES else ""


def _valid_diameter(value) -> str:
    if isinstance(value, (int, float)):
        value = str(int(value))
    if not isinstance(value, str):
        return ""
    normalized = re.sub(r"[^0-9]", "", value)
    return normalized if normalized in VALID_DIAMETERS else ""


def extract_tag_grade_diameter(image_bytes: bytes, filename: str, media_type: str = "image/jpeg") -> tuple[str, str]:
    raw = call_claude_vision(image_bytes, filename, media_type)
    raw_grade = raw.get("grade")
    raw_diameter = raw.get("diameter")
    grade = _valid_grade(raw_grade)
    diameter = _valid_diameter(raw_diameter)
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
    return grade, diameter
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_llm_tag_fallback.py -v`
Expected: PASS (9 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/llm_tag_fallback.py backend/app/config.py backend/tests/test_llm_tag_fallback.py
git commit -m "feat: 철근 택 인식용 Claude 비전 폴백 모듈 추가"
```

---

### Task 2: `/ocr/tag` 라우터에 폴백 연결

**Files:**
- Modify: `backend/app/routers/ocr.py:1-9` (imports), `backend/app/routers/ocr.py:64-72` (`run_tag_ocr` 본문)
- Test: `backend/tests/test_ocr_endpoint.py`

**Interfaces:**
- Consumes: Task 1의 `llm_tag_fallback.extract_tag_grade_diameter(image_bytes, filename) -> tuple[str, str]`, `config.ANTHROPIC_API_KEY: str`
- Produces: `/ocr/tag` 응답 필드는 변경 없음(`{**fields, "tag_match_status": ...}`), 동작만 확장됨

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_ocr_endpoint.py` 상단 import에 라우터 모듈 참조를 추가한다:

```python
from fastapi.testclient import TestClient

from app import ocr as ocr_module
from app.main import app
from app.routers import ocr as ocr_router
```

파일 끝에 다음 3개 테스트를 추가한다:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_ocr_endpoint.py -v -k llm_vision`
Expected: FAIL with `AttributeError: module 'app.routers.ocr' has no attribute 'config'` (또는 `'llm_tag_fallback'`) — 라우터가 아직 이 모듈들을 import하지 않았고 폴백 로직도 없다.

- [ ] **Step 3: Wire the fallback into the router**

`backend/app/routers/ocr.py`의 import 구문을 바꾼다:

```python
# 변경 전
from .. import ocr, report_parser, spec_grade
```
```python
# 변경 후
from .. import config, llm_tag_fallback, ocr, report_parser, spec_grade
```

`run_tag_ocr` 안의 다음 블록:

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
    tag_match_status = None
```

를 다음으로 교체한다:

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
            llm_grade, llm_diameter = llm_tag_fallback.extract_tag_grade_diameter(
                image_bytes, file.filename or "tag.jpg"
            )
            if not fields["tag_grade"] and llm_grade:
                fields["tag_grade"] = llm_grade
            if not fields["tag_diameter"] and llm_diameter:
                fields["tag_diameter"] = llm_diameter
    tag_match_status = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_ocr_endpoint.py -v`
Expected: PASS (모든 기존 테스트 포함 전체 통과 — 새 3개 + 기존 9개)

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && python -m pytest -v`
Expected: PASS (전체 테스트 그린 — 회귀 없음)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/ocr.py backend/tests/test_ocr_endpoint.py
git commit -m "feat: 택 강도/직경 파싱 실패 시 Claude 비전 폴백 연결"
```

---

## 배포 참고 (구현 범위 밖, 기록용)

Render에 배포된 백엔드를 실제로 쓰려면 `ANTHROPIC_API_KEY` 환경변수를 Render 대시보드에 추가해야 폴백이 동작한다(README의 배포 섹션에 있는 `UPSTAGE_API_KEY` 등록 방식과 동일). 이 문서의 태스크 범위에는 포함하지 않았으니, 구현 완료 후 별도로 등록이 필요하다.
