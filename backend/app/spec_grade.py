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


# 실제 택에서 확인된 표기만 등록한다 — "현대"는 "현대제철"의 흔한 줄임
# 표기(택에 "(동국제강,현대)"처럼 나옴), DONGKUK/HYUNDAI는 영문 표기.
# 아직 확인 안 된 나머지 5개 업체(대한제강/한국철강/환영철강/YK스틸/
# 한국제강)의 축약형·영문 표기는 실제 택을 받는 대로 추가한다. "제강"/
# "철강"처럼 여러 업체에 공통되는 일반 명사는 절대 등록하지 않는다 — 그러면
# 어느 업체인지 특정할 수 없는데도 사전 순서상 먼저 오는 업체로 오판정된다.
MANUFACTURER_ALIASES = {
    "현대": "현대제철",
    "DONGKUK": "동국제강",
    "HYUNDAI": "현대제철",
}


def normalize_manufacturers(value: str | None) -> list[str]:
    """value 안에 등장하는 모든 제강사(코드/한글 정식명칭/별칭)를 정규화해
    중복 없이 나열한다. "동국제강,현대"처럼 현장 승인 업체가 여러 곳 함께
    표기된 택을 위해 존재한다 — 단일 대표값만 필요하면 normalize_manufacturer를
    쓴다. 하나도 없으면 빈 리스트.

    두 단계로 찾는다:
    1) 콤마로 나눈 각 토큰이 "코드" 또는 "법인 표기 제거 후 완전한
       코드"인 경우(LLM이 "DK,HS"처럼 깔끔하게 답한 경우를 위해).
    2) 원문 전체(콤마로 나누지 않음)에서 정식명칭/별칭이 부분 문자열로
       등장하는지 확인("동국제강(부산공장)"처럼 부가정보가 붙은 경우,
       "현대"처럼 라벨 없이 붙은 축약형을 위해). 여기서 콤마로 나누지
       않는 이유는 영문 법인 표기("CO., LTD.")의 콤마와 충돌하기
       때문이다 — 나누면 "LTD." 쪽 토큰만 남아 앞부분을 놓친다."""
    if not value:
        return []
    found = []
    for token in value.split(","):
        stripped_token = token.strip()
        if not stripped_token:
            continue
        if stripped_token.upper() in MANUFACTURER_POOL:
            canonical_name = MANUFACTURER_POOL[stripped_token.upper()]
            if canonical_name not in found:
                found.append(canonical_name)
            continue
        cleaned_token = _CORPORATE_MARKERS_PATTERN.sub("", stripped_token)
        if cleaned_token.upper() in MANUFACTURER_POOL:
            canonical_name = MANUFACTURER_POOL[cleaned_token.upper()]
            if canonical_name not in found:
                found.append(canonical_name)

    cleaned_whole = _CORPORATE_MARKERS_PATTERN.sub("", value.strip())
    for canonical_name in MANUFACTURER_POOL.values():
        if canonical_name in cleaned_whole and canonical_name not in found:
            found.append(canonical_name)
    cleaned_whole_upper = cleaned_whole.upper()
    for alias, canonical_name in MANUFACTURER_ALIASES.items():
        if alias.upper() in cleaned_whole_upper and canonical_name not in found:
            found.append(canonical_name)
    return found


def normalize_manufacturer(value: str | None) -> str | None:
    """원문 표기(코드 또는 정식명칭, 법인 표기 포함)를 MANUFACTURER_POOL의
    정식명칭 하나(대표값)로 정규화한다. 여러 업체가 함께 표기된 경우는
    normalize_manufacturers를 쓸 것. 풀의 7개 중 어디에도 매칭되지 않으면
    None(인식 실패로 간주 — 강종/직경의 표준 목록 검증과 동일한 원칙)."""
    found = normalize_manufacturers(value)
    return found[0] if found else None


def match_manufacturer(tag_manufacturer: str | None, note: str | None) -> str | None:
    """택에서 인식된 제강사 후보들과 송장 note에서 인식된 제강사 후보들 중
    하나라도 겹치면 matched. note도 택과 마찬가지로 여러 업체가 함께
    표기될 수 있어("동국제강,현대" 등) 양쪽 다 normalize_manufacturers로
    후보 집합을 구해 교집합 여부로 판정한다."""
    tag_candidates = normalize_manufacturers(tag_manufacturer)
    note_candidates = normalize_manufacturers(note)
    if not tag_candidates or not note_candidates:
        return None
    return "matched" if set(tag_candidates) & set(note_candidates) else "mismatched"
