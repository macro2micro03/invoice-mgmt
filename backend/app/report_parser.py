import html
import re

from . import ocr

COVER_TITLE = "송장별 총괄 내역서"

TOTAL_ROW_LABELS = {"총합", "총계", "합계"}

DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")

# Upstage의 category 분류(heading1 vs paragraph)는 동일한 문서 안에서도
# 페이지마다 비결정적으로 갈리는 경우가 실제로 확인되었다(실제 반입송장
# 21페이지 중 갑지 제목과 회사명이 어떤 페이지에서는 heading1로, 다른
# 페이지에서는 paragraph로 분류됨). 그래서 제목/회사명 판별 모두 heading1
# 하나만 신뢰하지 않고 paragraph도 함께 확인한다.
TITLE_CATEGORIES = {"heading1", "paragraph"}
COMPANY_NAME_MARKERS = ("(주)", "㈜")


def _collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _parse_table_rows(table_html: str) -> list[list[str]]:
    rows = []
    for tr_match in re.finditer(r"<tr>(.*?)</tr>", table_html, re.DOTALL):
        cells = re.findall(r"<td>(.*?)</td>", tr_match.group(1), re.DOTALL)
        cleaned = [html.unescape(re.sub(r"<[^>]+>", "", cell)).strip() for cell in cells]
        rows.append(cleaned)
    return rows


def find_cover_pages(raw_response: dict) -> list[int]:
    pages = set()
    for element in raw_response.get("elements", []):
        if element.get("category") not in TITLE_CATEGORIES:
            continue
        text = ocr._content_to_text(element.get("content", {}))
        if text.strip() == COVER_TITLE:
            page = element.get("page")
            if page is not None:
                pages.add(page)
    return sorted(pages)


def _find_material_table_html(raw_response: dict, page: int) -> str:
    for element in raw_response.get("elements", []):
        if element.get("category") != "table" or element.get("page") != page:
            continue
        table_html = element.get("content", {}).get("html", "")
        rows = _parse_table_rows(table_html)
        if rows and rows[0] and "직경" in rows[0][0]:
            return table_html
    return ""


def extract_material_rows(raw_response: dict, page: int) -> list[dict]:
    table_html = _find_material_table_html(raw_response, page)
    if not table_html:
        return []
    rows = _parse_table_rows(table_html)
    header = rows[0]
    try:
        spec_idx = header.index("직경")
        weight_idx = next(i for i, cell in enumerate(header) if "발송중량" in cell)
    except (ValueError, StopIteration):
        return []
    note_idx = header.index("비고") if "비고" in header else None

    result = []
    for row in rows[1:]:
        if not row or spec_idx >= len(row):
            continue
        spec = row[spec_idx].strip()
        if not spec or _collapse_spaces(spec) in TOTAL_ROW_LABELS:
            continue
        if weight_idx >= len(row):
            continue
        weight_text = row[weight_idx].strip().replace(",", "")
        if not weight_text:
            continue
        try:
            weight_kg = float(weight_text)
        except ValueError:
            continue
        note = row[note_idx].strip() if note_idx is not None and note_idx < len(row) else ""
        result.append({"spec": spec, "weight_kg": weight_kg, "note": note})
    return result


def find_vendor_heading(raw_response: dict, page: int) -> str:
    candidate = ""
    for element in raw_response.get("elements", []):
        category = element.get("category")
        if element.get("page") != page:
            continue
        if category not in TITLE_CATEGORIES:
            continue
        text = ocr._content_to_text(element.get("content", {})).strip()
        if not text or text == COVER_TITLE or text.startswith("송장중량"):
            continue
        collapsed = _collapse_spaces(text)
        # heading1은 그대로 신뢰하되, paragraph로 분류된 경우는 회사명
        # 형태("(주)"/"㈜" 포함, 글자 사이 공백은 무시)일 때만 후보로 인정해
        # 다른 문단(면책 문구, 서명란 안내 등)이 거래처로 잘못 잡히는 것을 막는다.
        if category == "paragraph" and not any(marker in collapsed for marker in COMPANY_NAME_MARKERS):
            continue
        candidate = collapsed
    return candidate


def find_delivery_date(raw_response: dict, page: int) -> str:
    for element in raw_response.get("elements", []):
        if element.get("category") != "table" or element.get("page") != page:
            continue
        table_html = element.get("content", {}).get("html", "")
        for row in _parse_table_rows(table_html):
            joined = _collapse_spaces("".join(row))
            if joined.startswith("도착일"):
                match = DATE_PATTERN.search(joined)
                if match:
                    return match.group(0)
    return ""


def build_report_data(raw_responses: list[dict]) -> dict:
    totals: dict[str, float] = {}
    vendor = ""
    manufacturer = ""
    skipped_pages: list[int] = []
    cover_pages_found = 0
    delivery_dates: list[str] = []

    for raw_response in raw_responses:
        for page in find_cover_pages(raw_response):
            cover_pages_found += 1
            rows = extract_material_rows(raw_response, page)
            if not rows:
                skipped_pages.append(page)
                continue
            page_vendor = find_vendor_heading(raw_response, page)
            if page_vendor:
                vendor = page_vendor
            delivery_date = find_delivery_date(raw_response, page)
            if delivery_date:
                delivery_dates.append(delivery_date)
            for row in rows:
                totals[row["spec"]] = totals.get(row["spec"], 0.0) + row["weight_kg"]
                if row["note"] and not manufacturer:
                    manufacturer = row["note"]

    if cover_pages_found == 0:
        raise ValueError("송장별 총괄 내역서 페이지를 찾을 수 없습니다")

    specs = [
        {"spec": spec, "quantity_ton": round(weight_kg / 1000, 3)}
        for spec, weight_kg in sorted(totals.items())
    ]
    vendor_display = f"{vendor}/{manufacturer}" if vendor and manufacturer else vendor

    return {
        "specs": specs,
        "vendor": vendor_display,
        "skipped_pages": skipped_pages,
        "delivery_date": max(delivery_dates) if delivery_dates else "",
    }
