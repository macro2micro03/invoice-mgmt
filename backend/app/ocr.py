import html
import re

import requests

from . import config

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
    return result
