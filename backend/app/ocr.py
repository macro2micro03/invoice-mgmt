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


def extract_text(raw_response: dict) -> str:
    text = raw_response.get("text", "")
    if text:
        return text
    elements = raw_response.get("elements", [])
    lines = []
    for element in elements:
        content = element.get("content", {})
        if isinstance(content, dict) and content.get("text"):
            lines.append(content["text"])
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
