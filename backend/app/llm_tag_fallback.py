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
