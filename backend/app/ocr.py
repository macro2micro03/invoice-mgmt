import html
import re

import requests

from . import config, spec_grade

FIELD_LABELS = {
    "material_type": ["자재종류", "자재명"],
    "vendor": ["거래처", "공급자", "상호"],
    "delivery_date": ["납품일", "일자", "날짜"],
    "vehicle_no": ["차량번호", "차량"],
    "invoice_no": ["송장번호", "거래명세서번호", "명세서번호"],
    "item_name": ["품명"],
    "spec": ["규격"],
    "unit": ["단위"],
    "quantity": ["수량"],
    "weight": ["중량"],
    "note": ["비고"],
}

STANDARD_FIELDS = list(FIELD_LABELS.keys())

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

TAG_FIELDS = list(TAG_FIELD_LABELS.keys())

# Upstage document-parse가 택을 표(table)로 인식하면 셀 사이에 <br>이 없어
# HTML 태그를 걷어내고 나면 "직경13강도SD500"처럼 라벨과 값이 공백 없이
# 한 줄로 이어붙는다. 값 캡처를 다음에 나올 라벨 직전까지로 제한해 그 값이
# 다음 라벨의 값까지 삼키지 않도록 한다. 겹치는 라벨(예: "위치"가
# "부재시공위치"의 부분 문자열)이 있으므로 긴 라벨부터 시도한다.
_ALL_TAG_LABELS = sorted(
    {label for labels in TAG_FIELD_LABELS.values() for label in labels},
    key=len,
    reverse=True,
)
_TAG_LABEL_LOOKAHEAD = "|".join(re.escape(label) for label in _ALL_TAG_LABELS)

# 실제 철근 택은 "직경:"/"강도:" 같은 라벨 없이 SD500/SHD13/UHD22 같은 규격·강도
# 표기 자체만 표에 나열되는 경우가 대부분이다(제조사마다 "종류의기호"/"강종" 등
# 서로 다른 항목명을 쓰고, 현장 가공 택은 항목명 자체가 없기도 하다). 라벨 매칭이
# 실패했을 때 이 표기를 직접 찾아 강도/직경을 복구하는 보조 수단이다.

# 실제 철근 직경은 KS D 3504 표준 호칭경으로 닫힌 집합이다. 표 셀이 공백
# 없이 붙으면(예: "UHD252,800") "값 뒤에 숫자가 더 없어야 한다"는 가변
# 길이(\d{1,2}) 방식의 경계 조건이 이웃 셀의 숫자 때문에 깨지므로,
# "1~2자리 숫자 아무거나"가 아니라 "이 목록 중 하나"로 매칭해 가변 길이
# 문제 자체를 없앤다(몇 자리를 캡처할지 목록이 이미 정해준다).
_VALID_DIAMETER_VALUES = ("57", "51", "41", "38", "35", "32", "29", "25", "22", "19", "16", "13", "10", "6")
_DIAMETER_ALTERNATION = "|".join(_VALID_DIAMETER_VALUES)

# 한글은 파이썬 정규식에서 \w(단어 문자)로 취급되어, "강종SD600"처럼 값 바로
# 앞에 한글이 붙어있으면 \b가 경계로 인식되지 않아 매칭에 실패한다. 그래서
# \b 대신 "바로 앞이 영문이 아님"을 명시하는 lookbehind를 쓴다. 표 셀이
# 공백 없이 붙으면 앞뒤로 숫자가 이어질 수도 있어(예: "184SD600") 숫자는
# 경계에서 제외하지 않는다(영문만 제외).
_PREFIXED_SPEC_PATTERN = re.compile(rf"(?<![A-Za-z])(SHD|UHD|SD)({_DIAMETER_ALTERNATION})")
_BARE_GRADE_PATTERN = re.compile(r"(?<![A-Za-z])SD([456]00)(?!\d)")
_DIAMETER_PATTERN = re.compile(rf"(?<![A-Za-z])D({_DIAMETER_ALTERNATION})")
_HANGUL_PATTERN = re.compile(r"[가-힣]")


def _fallback_tag_grade_diameter(text: str) -> tuple[str, str]:
    upper_text = text.upper()
    for prefixed_match in _PREFIXED_SPEC_PATTERN.finditer(upper_text):
        matched_text = prefixed_match.group(0)
        tail = upper_text[prefixed_match.end() : prefixed_match.end() + 2]
        # "SD6"는 유일하게 "SD600"(강도 단독 표기)의 앞부분과 겹친다(직경
        # 값 중 두 자리가 아닌 건 "6"뿐이고, 강도 코드 중에도 "6"으로
        # 시작하는 "600"이 있어서). 바로 뒤에 "00"이 이어지면 직경이 아니라
        # 강도 단독 표기로 보고 이 매치는 건너뛰고 다음 매치를 계속 찾는다
        # — 같은 텍스트 안에 UHD25/SHD13처럼 진짜 매치가 다른 위치(표 셀
        # 순서가 바뀌어 앞이나 뒤에 올 수 있음)에 있을 수 있으므로 첫
        # 매치가 제외 대상이라고 곧바로 포기하면 안 된다.
        if matched_text == "SD6" and tail == "00":
            continue
        grade, diameter = spec_grade.parse_spec_grade_diameter(matched_text)
        if grade and diameter:
            return grade, diameter
    bare_match = _BARE_GRADE_PATTERN.search(upper_text)
    diameter_match = _DIAMETER_PATTERN.search(upper_text)
    grade = f"SD{bare_match.group(1)}" if bare_match else ""
    diameter = diameter_match.group(1) if diameter_match else ""
    return grade, diameter


def call_upstage_ocr(image_bytes: bytes, filename: str = "invoice.jpg") -> dict:
    if not config.UPSTAGE_API_KEY:
        raise RuntimeError("UPSTAGE_API_KEY가 설정되지 않았습니다")
    response = requests.post(
        config.UPSTAGE_OCR_URL,
        headers={"Authorization": f"Bearer {config.UPSTAGE_API_KEY}"},
        files={"document": (filename, image_bytes)},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def call_upstage_text_ocr(image_bytes: bytes, filename: str = "tag.jpg") -> dict:
    """document-parse가 문서 구조를 전혀 인식하지 못했을 때(요소 0개) 보조로
    사용하는 일반 텍스트 인식 API. 표/레이아웃 정보 없이 인식된 글자만 돌려준다."""
    if not config.UPSTAGE_API_KEY:
        raise RuntimeError("UPSTAGE_API_KEY가 설정되지 않았습니다")
    response = requests.post(
        config.UPSTAGE_TEXT_OCR_URL,
        headers={"Authorization": f"Bearer {config.UPSTAGE_API_KEY}"},
        files={"document": (filename, image_bytes)},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _content_to_text(content: dict) -> str:
    """Upstage document-parse는 content.text가 빈 문자열이고 실제 내용은
    content.html에 <br> 태그로 줄바꿈된 HTML로 들어있는 경우가 많다."""
    text = content.get("text", "")
    if text:
        return text
    html_content = content.get("html", "")
    if not html_content:
        return ""
    plain = re.sub(r"<br\s*/?>", "\n", html_content)
    plain = re.sub(r"<[^>]+>", "", plain)
    return html.unescape(plain).strip()


def extract_text(raw_response: dict) -> str:
    flat_text = raw_response.get("text", "")
    if flat_text:
        return flat_text
    top_level_text = _content_to_text(raw_response.get("content", {}))
    if top_level_text:
        return top_level_text
    elements = raw_response.get("elements", [])
    lines = []
    for element in elements:
        content = element.get("content", {})
        if isinstance(content, dict):
            element_text = _content_to_text(content)
            if element_text:
                lines.append(element_text)
    return "\n".join(lines)


def normalize_fields(raw_text: str) -> dict:
    result = {field: "" for field in STANDARD_FIELDS}
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    for line in lines:
        for field, labels in FIELD_LABELS.items():
            if result[field]:
                continue
            for label in labels:
                if label not in line:
                    continue
                match = re.search(rf"{label}\s*[:：]?\s*(.+)", line)
                if match:
                    value = match.group(1).strip()
                    if value and value != label:
                        result[field] = value
                        break

    if not result["material_type"] and result["item_name"]:
        for material in config.SUPPORTED_MATERIALS:
            if material in result["item_name"]:
                result["material_type"] = material
                break

    return result


def normalize_tag_fields(raw_text: str) -> dict:
    result = {field: "" for field in TAG_FIELDS}
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    for line in lines:
        for field, labels in TAG_FIELD_LABELS.items():
            if result[field]:
                continue
            for label in labels:
                if label not in line:
                    continue
                match = re.search(
                    rf"{re.escape(label)}\s*[:：]?\s*(.+?)(?=\s*(?:{_TAG_LABEL_LOOKAHEAD})|$)",
                    line,
                )
                if match:
                    value = match.group(1).strip()
                    if value and value != label:
                        result[field] = value
                        break

    # 표가 <br> 없이 한 줄로 뭉쳐진 경우, 라벨 뒤 캡처가 다음 항목의 한글
    # 라벨/값까지 삼켜 강도·직경 자리에 한글이 섞인 값이 들어갈 수 있다.
    # 이런 오염된 값은 버려서 아래 fallback 패턴 추출로 다시 시도하게 한다.
    if _HANGUL_PATTERN.search(result["tag_grade"]):
        result["tag_grade"] = ""
    if _HANGUL_PATTERN.search(result["tag_diameter"]):
        result["tag_diameter"] = ""

    if not result["tag_grade"] or not result["tag_diameter"]:
        fallback_grade, fallback_diameter = _fallback_tag_grade_diameter(raw_text)
        if not result["tag_grade"] and fallback_grade:
            result["tag_grade"] = fallback_grade
        if not result["tag_diameter"] and fallback_diameter:
            result["tag_diameter"] = fallback_diameter

    result["tag_manufacturer"] = ",".join(spec_grade.normalize_manufacturers(result["tag_manufacturer"]))

    return result
