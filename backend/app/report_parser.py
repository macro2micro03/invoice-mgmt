import html
import re

from . import ocr

COVER_TITLE = "철근납품확인서"

TOTAL_ROW_LABELS = {"총합", "총계", "합계", "계"}

DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
VEHICLE_NO_PATTERN = re.compile(r"[가-힣]{0,3}\d{2,3}[가-힣]\d{4}")
INVOICE_NO_PATTERN = re.compile(r"\d+-\d+")

# Upstage의 category 분류(heading1 vs paragraph)는 동일한 문서 안에서도
# 페이지마다 비결정적으로 갈리는 경우가 실제로 확인되었다. 제목 판별은
# heading1 하나만 신뢰하지 않고 paragraph도 함께 확인한다.
TITLE_CATEGORIES = {"heading1", "paragraph"}

# 라벨 값을 추출할 때 "다음 라벨 직전까지만" 잡기 위한 경계 목록.
# 표/문단이 <br> 없이 한 줄로 뭉쳐 나오는 경우, 탐욕적 정규식은 다음 라벨의
# 값까지 삼켜버리므로 이 목록으로 경계를 정한다.
_INFO_LABELS = (
    "공사명", "공정명", "납품차수", "납품일", "송장번호",
    "착지담당", "착지주소", "연락처", "차량번호", "운전자",
    "공장명", "발송자", "인수처", "인수자", "인수일", "상기",
)


def _collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _label_pattern(label: str) -> str:
    # 실제 문서에서 라벨 글자 사이에 장식적 공백이 들어가는 경우
    # ("납 품 일")를 허용하기 위해 글자 사이에 \s*를 끼워 넣는다.
    return r"\s*".join(re.escape(ch) for ch in label)


_LABEL_LOOKAHEAD = "|".join(
    _label_pattern(label) for label in sorted(_INFO_LABELS, key=len, reverse=True)
)


def _find_labeled_value(text: str, label: str) -> str:
    # re.MULTILINE: extract_text()가 요소들을 "\n"으로 이어붙이기 때문에,
    # 마지막 정보 라벨(예: 공장명) 뒤에 표 등 무관한 내용이 다음 줄로 이어지면
    # 일반 "$"(문자열 끝)는 절대 매치되지 않는다. MULTILINE으로 각 줄 끝에서도
    # "$"가 매치되게 해야 값이 올바르게 끊긴다.
    # 라벨과 값 사이 공백은 [ \t]*로 제한해 줄바꿈을 건너뛰지 않게 하고, 캡처
    # 그룹도 [^\n]+?로 제한한다. 그렇지 않으면 값이 비어있는 라벨(예: "공장명:"
    # 바로 뒤에 줄바꿈)에서 \s*가 그 줄바꿈까지 삼켜버려 다음 줄의 무관한
    # 내용(면책 문구 등)이 값으로 캡처되어 버린다.
    match = re.search(
        rf"{_label_pattern(label)}[ \t]*[:：]?[ \t]*([^\n:：]+?)(?=\s*(?:{_LABEL_LOOKAHEAD})|$)",
        text,
        re.MULTILINE,
    )
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


_VENDOR_COMPANY_MARKERS = ("(주)", "㈜")
_VENDOR_MAX_PLAUSIBLE_LENGTH = 30


def _looks_like_vendor_name(value: str) -> bool:
    if not value:
        return False
    if any(marker in value for marker in _VENDOR_COMPANY_MARKERS):
        return True
    return len(value) <= _VENDOR_MAX_PLAUSIBLE_LENGTH


def _parse_table_rows(table_html: str) -> list[list[str]]:
    rows = []
    for tr_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr_match.group(1), re.DOTALL)
        cleaned = [html.unescape(re.sub(r"<[^>]+>", "", cell)).strip() for cell in cells]
        rows.append(cleaned)
    return rows


def _page_text(raw_response: dict, page: int) -> str:
    elements = raw_response.get("elements", [])
    page_elements = [e for e in elements if e.get("page") == page]
    if not page_elements:
        return ocr.extract_text(raw_response)
    lines = []
    for element in page_elements:
        content = element.get("content", {})
        if isinstance(content, dict):
            element_text = ocr._content_to_text(content)
            if element_text:
                lines.append(element_text)
    return "\n".join(lines)


def find_cover_pages(raw_response: dict) -> list[int]:
    pages = set()
    for element in raw_response.get("elements", []):
        if element.get("category") not in TITLE_CATEGORIES:
            continue
        text = ocr._content_to_text(element.get("content", {}))
        if COVER_TITLE in _collapse_spaces(text.strip()):
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
        if any(any("철근경" in _collapse_spaces(cell) for cell in row) for row in rows):
            return table_html
    return ""


def _normalize_weight_text(text: str) -> str:
    # 실제 Ton 값은 항상 1000 미만의 소수이므로, 쉼표는 천단위 구분자가 아니라
    # OCR이 소수점을 쉼표로 잘못 인식한 경우(예: "0,544")일 가능성이 훨씬 높다.
    match = re.fullmatch(r"(\d+),(\d{1,3})", text)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return text


# 단일 배송 건의 로스감안중량으로 이 값을 넘으면 OCR 오인식(쉼표/자릿수 오류 등)
# 가능성이 훨씬 높다고 보고 조용히 저장하는 대신 행 자체를 건너뛴다.
_MAX_PLAUSIBLE_WEIGHT_TON = 100


def extract_material_rows(raw_response: dict, page: int) -> list[dict]:
    rows, _skipped = _extract_material_rows_with_skips(raw_response, page)
    return rows


def _extract_material_rows_with_skips(raw_response: dict, page: int) -> tuple[list[dict], int]:
    table_html = _find_material_table_html(raw_response, page)
    if not table_html:
        return [], 0
    rows = _parse_table_rows(table_html)
    try:
        header_idx, header = next(
            (i, row) for i, row in enumerate(rows) if any("철근경" in _collapse_spaces(cell) for cell in row)
        )
    except StopIteration:
        return [], 0
    try:
        spec_idx = next(i for i, cell in enumerate(header) if "철근경" in _collapse_spaces(cell))
        weight_idx = next(i for i, cell in enumerate(header) if "로스감안중량" in _collapse_spaces(cell))
    except StopIteration:
        return [], 0
    note_idx = next((i for i, cell in enumerate(header) if "비고" in _collapse_spaces(cell)), None)

    result = []
    skipped = 0
    for row in rows[header_idx + 1 :]:
        if not row or spec_idx >= len(row):
            continue
        spec = row[spec_idx].strip()
        if not spec or _collapse_spaces(spec) in TOTAL_ROW_LABELS:
            continue
        if weight_idx >= len(row):
            continue
        weight_text = _normalize_weight_text(row[weight_idx].strip())
        if not weight_text:
            continue
        try:
            weight_ton = float(weight_text)
        except ValueError:
            continue
        if weight_ton > _MAX_PLAUSIBLE_WEIGHT_TON:
            skipped += 1
            continue
        note = row[note_idx].strip() if note_idx is not None and note_idx < len(row) else ""
        result.append({"spec": spec, "weight_ton": weight_ton, "note": note})
    return result, skipped


def find_vendor_heading(raw_response: dict, page: int) -> str:
    text = _page_text(raw_response, page)
    value = _collapse_spaces(_find_labeled_value(text, "공장명"))
    return value if _looks_like_vendor_name(value) else ""


def find_delivery_date(raw_response: dict, page: int) -> str:
    text = _page_text(raw_response, page)
    value = _collapse_spaces(_find_labeled_value(text, "납품일"))
    match = DATE_PATTERN.search(value)
    return match.group(0) if match else ""


def find_vehicle_no(raw_response: dict, page: int) -> str:
    text = _page_text(raw_response, page)
    value = _collapse_spaces(_find_labeled_value(text, "차량번호"))
    match = VEHICLE_NO_PATTERN.search(value)
    return match.group(0) if match else ""


def find_invoice_no(raw_response: dict, page: int) -> str:
    text = _page_text(raw_response, page)
    value = _collapse_spaces(_find_labeled_value(text, "송장번호"))
    match = INVOICE_NO_PATTERN.search(value)
    return match.group(0) if match else ""


def build_capture_records(raw_response: dict, material_type: str = "철근") -> list[dict]:
    records: list[dict] = []
    for page in find_cover_pages(raw_response)[:1]:
        rows, _skipped = _extract_material_rows_with_skips(raw_response, page)
        if not rows:
            continue
        vendor = find_vendor_heading(raw_response, page)
        delivery_date = find_delivery_date(raw_response, page)
        vehicle_no = find_vehicle_no(raw_response, page)
        invoice_no = find_invoice_no(raw_response, page)
        for row in rows:
            records.append(
                {
                    "material_type": material_type,
                    "vendor": vendor,
                    "delivery_date": delivery_date,
                    "vehicle_no": vehicle_no,
                    "invoice_no": invoice_no,
                    "item_name": material_type,
                    "spec": row["spec"],
                    "unit": "",
                    "quantity": None,
                    # Invoice.weight 컬럼은 kg 단위(기존 계약) — 표는 Ton이므로 변환한다.
                    "weight": row["weight_ton"] * 1000,
                    "note": row["note"],
                }
            )
    return records


def build_report_data(raw_responses: list[dict]) -> dict:
    totals: dict[str, float] = {}
    vendor = ""
    manufacturer = ""
    skipped_pages: list[int] = []
    skipped_rows = 0
    cover_pages_found = 0
    delivery_dates: list[str] = []

    for raw_response in raw_responses:
        for page in find_cover_pages(raw_response):
            cover_pages_found += 1
            rows, page_skipped_rows = _extract_material_rows_with_skips(raw_response, page)
            skipped_rows += page_skipped_rows
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
                totals[row["spec"]] = totals.get(row["spec"], 0.0) + row["weight_ton"]
                if row["note"] and not manufacturer:
                    manufacturer = row["note"]

    if cover_pages_found == 0:
        raise ValueError("철근 납품 확인서 페이지를 찾을 수 없습니다")

    specs = [
        {"spec": spec, "quantity_ton": round(weight_ton, 3)}
        for spec, weight_ton in sorted(totals.items())
    ]
    vendor_display = f"{vendor}/{manufacturer}" if vendor and manufacturer else vendor

    return {
        "specs": specs,
        "vendor": vendor_display,
        "skipped_pages": skipped_pages,
        "skipped_rows": skipped_rows,
        "delivery_date": max(delivery_dates) if delivery_dates else "",
    }
