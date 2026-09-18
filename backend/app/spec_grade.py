import re

GRADE_BY_PREFIX = {
    "SD": "SD400",
    "SHD": "SD500",
    "UHD": "SD600",
}


def parse_spec_grade_diameter(spec: str) -> tuple[str | None, str | None]:
    if not spec:
        return None, None
    spec_upper = spec.strip().upper()
    for prefix, grade in GRADE_BY_PREFIX.items():
        if spec_upper.startswith(prefix):
            diameter = re.sub(r"[^0-9]", "", spec_upper[len(prefix):])
            return grade, diameter or None
    return None, None


def _normalize_diameter(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"[^0-9]", "", value)
    return digits or None


def _normalize_grade(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^A-Z0-9]", "", value.strip().upper())
    return normalized or None


def match_tag_to_spec(tag_grade: str | None, tag_diameter: str | None, spec: str) -> str | None:
    spec_grade, spec_diameter = parse_spec_grade_diameter(spec)
    norm_tag_grade = _normalize_grade(tag_grade)
    norm_tag_diameter = _normalize_diameter(tag_diameter)
    if spec_grade is None or norm_tag_grade is None or norm_tag_diameter is None:
        return None
    if spec_grade == norm_tag_grade and spec_diameter == norm_tag_diameter:
        return "matched"
    return "mismatched"


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
