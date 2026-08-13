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

# 라벨과 값이 서로 다른 줄로 나뉜 레이아웃(round 2)에서 "바로 다음 줄"을 값
# 후보로 받아들이기 전에 검증하는 데 쓰는 패턴들.
# - _NEXT_LINE_LABEL_START_PATTERN: 다음 줄이 그 자체로 또 다른 서식 라벨(예:
#   "납품일: ...")로 시작하면, 그 줄은 절대 값이 될 수 없다(1b).
# - _SENTENCE_FINAL_PATTERN: 다음 줄이 "...확인함"/"...한다." 처럼 문장으로
#   끝나면 면책 문구 등 무관한 문단일 가능성이 높다(1a).
# 짧은 라벨 값(회사명/날짜/차량번호 등)은 공백으로 나뉜 단어가 많아야 1~2개인
# 반면, 표 헤더 행이나 안내 문장은 공백으로 구분된 단어가 여러 개인 경우가
# 대부분이므로 단어 수도 함께 확인한다.
_NEXT_LINE_LABEL_START_PATTERN = re.compile(rf"^(?:{_LABEL_LOOKAHEAD})")
_SENTENCE_FINAL_PATTERN = re.compile(r"(다|함)[.]?$")
_LABEL_VALUE_MAX_PLAUSIBLE_LENGTH = 30
_LABEL_VALUE_MAX_PLAUSIBLE_WORDS = 2


def _looks_like_plausible_label_value(value: str) -> bool:
    if not value:
        return False
    if len(value) > _LABEL_VALUE_MAX_PLAUSIBLE_LENGTH:
        return False
    if _SENTENCE_FINAL_PATTERN.search(value):
        return False
    if _NEXT_LINE_LABEL_START_PATTERN.match(value):
        return False
    if len(value.split()) > _LABEL_VALUE_MAX_PLAUSIBLE_WORDS:
        return False
    return True


def _find_labeled_value(text: str, label: str) -> str:
    # re.MULTILINE: extract_text()가 요소들을 "\n"으로 이어붙이기 때문에,
    # 마지막 정보 라벨(예: 공장명) 뒤에 표 등 무관한 내용이 다음 줄로 이어지면
    # 일반 "$"(문자열 끝)는 절대 매치되지 않는다. MULTILINE으로 각 줄 끝에서도
    # "$"가 매치되게 해야 값이 올바르게 끊긴다.
    # 라벨과 값 사이 공백은 [ \t]*로 제한해 줄바꿈을 건너뛰지 않게 하고, 캡처
    # 그룹도 [^\n]*?로 제한한다(같은 줄만 본다).
    # colon 매치 여부를 별도 그룹으로 남겨두는 이유: 라벨 뒤에 콜론까지 명시돼
    # 있는데 값이 비어 있다면(예: "공장명:" 바로 뒤에 줄바꿈) 의도적으로 값이
    # 비어 있는 것으로 보고 다음 줄로 넘어가지 않는다 — 그렇지 않으면 다음 줄의
    # 무관한 내용(면책 문구 등)이 값으로 캡처되어 버린다(Important #4).
    # 반대로 콜론조차 없이 라벨만 있고 같은 줄에 아무 값도 없다면, 라벨과 값이
    # 서로 다른 줄/요소로 나뉜 레이아웃(예: Upstage가 라벨/값을 별개 요소로
    # 반환해 "\n"으로만 이어붙는 경우)일 가능성이 높으므로, 바로 다음 한 줄만
    # 확인해 값으로 사용한다. 그 이상은 절대 스캔하지 않는다.
    match = re.search(
        rf"{_label_pattern(label)}[ \t]*(?P<colon>[:：])?[ \t]*(?P<value>[^\n:：]*?)(?=\s*(?:{_LABEL_LOOKAHEAD})|$)",
        text,
        re.MULTILINE,
    )
    if not match:
        return ""
    value = match.group("value").strip()
    if value:
        return re.sub(r"\s+", " ", value).strip()
    # 콜론이 있어도(예: "납품일:" 바로 뒤 줄바꿈) 값이 폭 제한으로 다음 줄에
    # 줄바꿈되어 들어오는 실제 문서 레이아웃이 있다(Round 4). 콜론 유무와
    # 무관하게 다음 줄 후보를 동일한 그럴듯함 검사로 걸러내면, 진짜로 값이
    # 비어 있는 경우(다음 줄이 무관한 문단/라벨)는 여전히 빈 문자열을 반환하고,
    # 실제로 줄바꿈된 값만 올바르게 집어낸다.
    next_line_match = re.match(r"[ \t]*\r?\n([^\n]*)", text[match.end():])
    if not next_line_match:
        return ""
    next_line = next_line_match.group(1).strip()
    if not next_line:
        return ""
    next_line = re.sub(r"\s+", " ", next_line).strip()
    if not _looks_like_plausible_label_value(next_line):
        return ""
    return next_line


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
    # page 키가 아예 없거나 None인 요소(예: Upstage가 특정 페이지에 귀속시키지
    # 못한 요약/폼 요소)는 어떤 페이지를 조회하든 함께 포함시킨다. 이 값들은
    # 이 스코핑 기능(Important #5) 이전에는 문서 전체 텍스트 검색 대상이었으므로,
    # page 번호가 명시적으로 다른 요소만 제외하고 나머지는 계속 포함해야 한다.
    page_elements = [e for e in elements if e.get("page") in (page, None)]
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


# 제목 포함(containment) 매치를 허용하되, 너무 느슨하면 제목 문구를 그저
# 인용하는 무관한 문단(예: "본 철근 납품 확인서는 2부 작성한다.")까지 표지
# 페이지로 오인한다. 길이 기준선(예: "제목 길이의 N배")은 짧은 상투적 문장이
# 긴 정당한 제목 주석보다 더 짧을 수 있어 어느 쪽으로도 잘못될 수 있으므로,
# 길이 대신 "모양"으로 판별한다: 실제 제목 요소는 항상 제목으로 "시작"하고,
# 제목 뒤에는 짧은 괄호/날짜 주석 정도만 붙는다 — 마침표나 "...다."/"...함"
# 처럼 문장으로 끝나는 어미가 붙지 않는다. 반면 제목을 그저 인용하는 문장은
# 제목이 문두에 오지 않거나(예: "본 철근 납품 확인서는...") 문장 어미로
# 끝난다.
_SENTENCE_FINAL_ANNOTATION_PATTERN = re.compile(r"(다|함)$")


def _looks_like_cover_title_annotation(collapsed: str) -> bool:
    if not collapsed.startswith(COVER_TITLE):
        return False
    remainder = collapsed[len(COVER_TITLE):]
    if "." in remainder:
        return False
    if _SENTENCE_FINAL_ANNOTATION_PATTERN.search(remainder):
        return False
    return True


def find_cover_pages(raw_response: dict) -> list[int]:
    pages = set()
    all_pages = set()
    for element in raw_response.get("elements", []):
        page = element.get("page")
        if page is not None:
            all_pages.add(page)
        if element.get("category") not in TITLE_CATEGORIES:
            continue
        text = ocr._content_to_text(element.get("content", {}))
        collapsed = _collapse_spaces(text.strip())
        if _looks_like_cover_title_annotation(collapsed):
            if page is not None:
                pages.add(page)
    # 사진 각도/글레어 등으로 Upstage가 표지 제목 영역 자체를 표(table)로
    # 잘못 인식해 제목 글자가 무관한 표 셀들로 조각나 흩어지는 경우가 실제
    # 촬영 사진에서 확인됐다 — 이때는 제목 텍스트로는 표지를 찾을 수 없다.
    # "철근경" 헤더를 가진 자재 내역 표가 있다는 것 자체가 이 문서가 철근
    # 납품 확인서라는 훨씬 더 구체적이고 오탐 가능성이 낮은 증거이므로,
    # 제목 인식에 실패한 페이지도 이 표가 있으면 표지로 인정한다.
    for page in all_pages - pages:
        if _find_material_table_html(raw_response, page):
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
    coupler_idx = next((i for i, cell in enumerate(header) if "커플러" in _collapse_spaces(cell)), None)

    # rowspan으로 세로 병합된 맨 앞 칸(예: 빈 안내 칸)은 헤더 행에만 <td>가
    # 남고 그 아래 데이터 행들에는 나타나지 않는다(정상적인 HTML rowspan
    # 동작). _parse_table_rows는 rowspan을 인식하지 못해 셀 목록을 그대로
    # 만들기 때문에, 데이터 행이 헤더보다 칸이 하나 적어 좌측 기준 인덱스가
    # 통째로 밀려 엉뚱한 칸(예: 가공중량 칸)을 철근경으로 읽는 문제가 실제
    # 촬영 사진에서 확인됐다. 표 끝에서부터의 위치(오프셋)는 이런 경우에도
    # 안정적이므로, 각 열의 위치를 "끝에서부터 몇 번째"로 저장해 두고 매
    # 데이터 행마다 그 행의 실제 길이를 기준으로 다시 계산한다.
    header_len = len(header)
    spec_offset = header_len - 1 - spec_idx
    weight_offset = header_len - 1 - weight_idx
    note_offset = header_len - 1 - note_idx if note_idx is not None else None
    coupler_offset = header_len - 1 - coupler_idx if coupler_idx is not None else None

    result = []
    skipped = 0
    for row in rows[header_idx + 1 :]:
        if not row:
            continue
        row_len = len(row)
        spec_pos = row_len - 1 - spec_offset
        if not 0 <= spec_pos < row_len:
            continue
        spec = row[spec_pos].strip()
        if not spec or _collapse_spaces(spec) in TOTAL_ROW_LABELS:
            continue
        weight_pos = row_len - 1 - weight_offset
        if not 0 <= weight_pos < row_len:
            continue
        weight_text = _normalize_weight_text(row[weight_pos].strip())
        if not weight_text:
            continue
        try:
            weight_ton = float(weight_text)
        except ValueError:
            continue
        if weight_ton > _MAX_PLAUSIBLE_WEIGHT_TON:
            skipped += 1
            continue
        note_pos = row_len - 1 - note_offset if note_offset is not None else None
        note = row[note_pos].strip() if note_pos is not None and 0 <= note_pos < row_len else ""
        coupler_pos = row_len - 1 - coupler_offset if coupler_offset is not None else None
        coupler_count = 0.0
        if coupler_pos is not None and 0 <= coupler_pos < row_len:
            try:
                coupler_count = float(row[coupler_pos].strip())
            except ValueError:
                coupler_count = 0.0
        result.append({"spec": spec, "weight_ton": weight_ton, "note": note, "coupler_count": coupler_count})
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
            item_name = "커플러" if row.get("coupler_count", 0) > 0 else material_type
            records.append(
                {
                    "material_type": material_type,
                    "vendor": vendor,
                    "delivery_date": delivery_date,
                    "vehicle_no": vehicle_no,
                    "invoice_no": invoice_no,
                    "item_name": item_name,
                    "spec": row["spec"],
                    "unit": "Ton",
                    # quantity는 화면에 보이는 수량 칸(Ton) — 중량과 동일한 값을 보여준다.
                    "quantity": row["weight_ton"],
                    # Invoice.weight 컬럼도 Ton 단위로 저장한다(기존 계약) — 변환 없이 그대로.
                    "weight": row["weight_ton"],
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
