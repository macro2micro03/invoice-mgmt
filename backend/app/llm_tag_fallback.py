import base64
import json
import logging
import re

import requests

from . import config, spec_grade

logger = logging.getLogger(__name__)

VALID_GRADES = {"SD300", "SD400", "SD500", "SD600"}
VALID_DIAMETERS = {"6", "10", "13", "16", "19", "22", "25", "29", "32", "35", "38", "41", "51", "57"}
SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

_PROMPT = (
    "이 사진은 철근 택(꼬리표) 사진입니다. 택에 표시된 철근의 강종, 직경, "
    "제조사만 다른 설명 없이 JSON으로 답하세요: "
    '{"grade": "SD300/SD400/SD500/SD600 중 하나, 모르면 null", '
    '"diameter": "13처럼 숫자만, 모르면 null", '
    '"manufacturer": "다음 7개 제강사 중 택에 표기된 것을 모두 콤마로 구분해서 — '
    'HS(현대제철), DK(동국제강), DH(대한제강), HK(한국철강), HY(환영철강), YK(YK스틸), '
    'HJ(한국제강). 제조사 로고나 "제조사"/"제강사" 같은 별도 라벨 없이, 현장명/주소 '
    '바로 뒤 괄호 안에 "(동국제강,현대)"처럼 축약된 회사명으로만 표기되는 경우도 '
    '있으니 택 상단의 작은 글씨까지 놓치지 말고 살펴보세요. 코드나 정식명칭 아무거나로 '
    '답해도 됩니다. 이 목록에 없거나 모르면 null"}. '
    "확신이 없으면 null로 답하세요."
)

# 지시에도 불구하고 응답 앞뒤에 설명 문장이나 코드펜스가 붙는 경우가 있어,
# 텍스트 전체가 아니라 그 안의 {...} 블록만 골라 파싱한다.
_JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def call_claude_vision(image_bytes: bytes, filename: str, media_type: str = "image/jpeg") -> dict:
    """Anthropic Messages API를 호출해 원시 응답 JSON을 dict로 반환한다.
    API 키 미설정, 호출 실패, 응답 파싱 실패 등 어떤 이유로든 실패하면 예외를
    던지지 않고 항상 {}를 반환한다."""
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
                "max_tokens": 200,
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
        logger.exception(
            "Claude 비전 폴백 API 호출 실패 (filename=%s, bytes=%d)", filename, len(image_bytes)
        )
        return {}

    stop_reason = None
    try:
        body = response.json()
        stop_reason = body.get("stop_reason")
        text = body["content"][0]["text"]
        match = _JSON_BLOCK_PATTERN.search(text)
        if not match:
            raise ValueError(f"응답에서 JSON 블록을 찾지 못함: {text!r}")
        return json.loads(match.group(0))
    except Exception:
        logger.warning(
            "Claude 비전 폴백 응답을 JSON으로 파싱하지 못함 (filename=%s, stop_reason=%r) — 원본: %r",
            filename,
            stop_reason,
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


def _valid_manufacturer(value) -> str:
    if not isinstance(value, str):
        return ""
    return ",".join(spec_grade.normalize_manufacturers(value))


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
