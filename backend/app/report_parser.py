import html
import re

from . import ocr

COVER_TITLE = "송장별 총괄 내역서"


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
        if element.get("category") != "heading1":
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
        if not row or not row[0].strip() or "총" in row[0]:
            continue
        spec = row[0].strip()
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
        if element.get("category") != "heading1" or element.get("page") != page:
            continue
        text = ocr._content_to_text(element.get("content", {})).strip()
        if not text or text == COVER_TITLE or text.startswith("송장중량"):
            continue
        candidate = _collapse_spaces(text)
    return candidate


def build_report_data(raw_responses: list[dict]) -> dict:
    totals: dict[str, float] = {}
    vendor = ""
    manufacturer = ""
    skipped_pages: list[int] = []
    cover_pages_found = 0

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

    return {"specs": specs, "vendor": vendor_display, "skipped_pages": skipped_pages}
