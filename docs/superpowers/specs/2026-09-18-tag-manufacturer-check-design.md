# 철근 택 제조사 확인 — 설계 문서

## 배경

철근 택 검수는 현재 강종(SD400/500/600)과 직경만 송장 규격과 대조한다([2026-08-03-tag-photo-matching-design.md](2026-08-03-tag-photo-matching-design.md), [2026-09-18-tag-llm-vision-fallback-design.md](2026-09-18-tag-llm-vision-fallback-design.md)). 실제 현장 검수에서는 택에 찍힌 제조사(제강사)가 송장에 기재된 제조사와 일치하는지도 확인해야 한다. 이 문서는 그 확인 절차를 추가하는 설계를 다룬다.

## 범위

**포함:**
- 택 사진에서 제조사를 인식(라벨 매칭 → 실패 시 Claude 비전 폴백, 기존 강종/직경 폴백 호출에 통합).
- 인식한 제조사를 송장 레코드의 `note`(비고) 필드와 대조해 일치 여부 판정.
- 레코드 저장 시 서버에서 권위 있게 판정(프론트 계산값을 신뢰하지 않음) — 기존 `tag_match_status` 계산 방식과 동일한 패턴.
- 편집 화면에서 저장 전 즉시 확인 배너, 상세 화면에서 저장된 판정 결과 표시.

**범위 밖:**
- 택-자재 배정(assignment) 로직 변경 — 배정은 기존대로 강종+직경 기준으로만 하고, 제조사는 배정된 뒤 추가 확인 배너로만 표시한다.
- `vendor`(거래처/공장명) 필드와의 대조 — `note` 필드(갑지 파싱 시 실제 제조사명이 들어가는 칸)만 비교 대상으로 한다.
- 풀(POOL) 자체의 운영 화면(추가/삭제 UI) — 코드에 상수로 고정하고, 제강사 구성이 바뀌면 코드 수정으로 대응한다.

## 제조사 풀 (POOL)

현장에 실제로 납품하는 제강사는 아래 7곳으로 한정된다(사용자 확인). 코드(2자리 약칭)와 정식명칭을 모두 인식 대상으로 삼는다 — 택에는 둘 중 하나로만 표시되는 경우가 많다.

| 코드 | 정식명칭 |
|---|---|
| HS | 현대제철 |
| DK | 동국제강 |
| DH | 대한제강 |
| HK | 한국철강 |
| HY | 환영철강 |
| YK | YK스틸 |
| HJ | 한국제강 |

라벨 매칭이든 LLM 비전이든, 추출된 원문(코드 또는 정식명칭, 법인 표기 포함)은 이 풀로 정규화된다. **풀의 7개 중 어디에도 매칭되지 않으면 인식 실패로 간주해 빈 값으로 처리한다** — 강종/직경의 표준 목록 검증(`VALID_GRADES`/`VALID_DIAMETERS`)과 동일한 원칙이다. 저장되는 `tag_manufacturer` 값은 항상 7개 정식명칭 중 하나이거나 빈 문자열이다.

## 비교 대상 필드

송장 레코드의 `note` 필드를 기준으로 삼는다. 갑지(철근 납품 확인서) 파싱 시 표의 "비고" 칸에 실제 제조사명(예: "동국제강")이 들어가는 것이 확인됐다([report_parser.py](../../../backend/app/report_parser.py)의 `build_capture_records`). 일반 촬영 송장은 `note`가 비어있을 수 있으며, 이 경우 판정은 `None`(확인불가)이 된다. `note`도 같은 풀 정규화 함수를 거쳐 비교하므로, `note`에 부가 정보(예: "동국제강(부산공장)")가 섞여 있어도 정규화 후 매칭된다.

## 인식 방식

기존 강종/직경과 동일한 하이브리드 구조를 따르되, 정규식 폴백 단계는 생략한다(제조사명은 `SD500`처럼 고정된 표기 규칙이 없고, 로고·도장 형태로만 표시되는 경우가 많다):

1. **라벨 매칭**: `ocr.normalize_tag_fields`가 "제조사"/"제강사" 라벨을 찾아 값을 추출한 뒤, **풀로 정규화**(풀 밖이면 빈 값)
2. **LLM 비전 폴백**: 강종·직경·제조사 중 하나라도 비어있으면 Claude 비전에 택 사진을 보내 세 값을 **한 번에** 요청 (기존 강종/직경 폴백 호출에 제조사 추출을 포함시켜, 같은 사진에 대해 API를 두 번 호출하지 않는다). LLM 응답도 동일하게 **풀로 정규화**(풀 밖이면 빈 값)

두 경로 모두 같은 정규화 함수(`spec_grade.normalize_manufacturer`)를 거치므로, 라벨 매칭이든 LLM이든 최종적으로 `tag_manufacturer`에 들어가는 값은 항상 풀 안의 정식명칭이거나 빈 문자열로 일관된다. 프롬프트에도 7개 풀(코드+명칭)을 명시해 LLM이 애매한 표기를 더 정확히 인식하도록 돕는다.

**참고**: 제조사는 라벨 매칭 성공률이 강종/직경보다 낮을 것으로 예상되어(로고 위주), LLM 폴백 호출 빈도가 강종/직경보다 높아질 가능성이 있다. 호출당 비용 자체가 낮아([2026-09-18-tag-llm-vision-fallback-design.md](2026-09-18-tag-llm-vision-fallback-design.md) 참고) 허용 가능한 수준으로 판단했다.

## 일치 판정 규칙

`tag_manufacturer`와 `note`를 각각 풀로 정규화한 뒤, 정규화된 정식명칭이 서로 같으면 `matched`, 다르면 `mismatched`. 둘 중 하나라도 풀에 매칭되지 않으면(빈 값 포함) `None`(판정 불가).

## 백엔드 변경

### `backend/app/ocr.py`

```python
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
```

`TAG_FIELDS`와 라벨 경계 판별용 `_ALL_TAG_LABELS`/`_TAG_LABEL_LOOKAHEAD`는 모두 `TAG_FIELD_LABELS`에서 자동 파생되므로 위 딕셔너리에 항목만 추가하면 되고 별도 변경 불필요.

라벨 매칭 직후, `normalize_tag_fields`에서 `result["tag_manufacturer"]`를 `spec_grade.normalize_manufacturer`에 통과시켜 풀 밖이면 빈 문자열로 되돌린다(`ocr.py`는 이미 `from . import config, spec_grade`로 `spec_grade`를 가져오고 있어 추가 의존성 없음):

```python
    result["tag_manufacturer"] = spec_grade.normalize_manufacturer(result["tag_manufacturer"]) or ""
```

### `backend/app/spec_grade.py`

```python
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
```

### `backend/app/llm_tag_fallback.py`

- `_PROMPT`에 `manufacturer` 필드 추가. 7개 풀(코드+명칭)을 프롬프트에 명시해 LLM이 애매한 표기를 더 정확히 인식하도록 돕는다:

```python
_PROMPT = (
    "이 사진은 철근 택(꼬리표) 사진입니다. 택에 표시된 철근의 강종, 직경, "
    "제조사만 다른 설명 없이 JSON으로 답하세요: "
    '{"grade": "SD300/SD400/SD500/SD600 중 하나, 모르면 null", '
    '"diameter": "13처럼 숫자만, 모르면 null", '
    '"manufacturer": "다음 7개 제강사 중 하나만 — HS(현대제철), DK(동국제강), '
    'DH(대한제강), HK(한국철강), HY(환영철강), YK(YK스틸), HJ(한국제강). '
    '코드나 정식명칭 아무거나로 답해도 됩니다. 이 목록에 없거나 모르면 null"}. '
    "확신이 없으면 null로 답하세요."
)
```

- `extract_tag_grade_diameter(image_bytes, filename, media_type) -> tuple[str, str]`를 `extract_tag_fields(image_bytes, filename, media_type) -> tuple[str, str, str]`(grade, diameter, manufacturer)로 확장
- `call_claude_vision`은 원시 dict를 그대로 반환하므로 변경 없음(호출부에서 `"manufacturer"` 키만 추가로 읽음)
- 제조사는 `import`를 추가해(`from . import config, spec_grade`) `spec_grade.normalize_manufacturer`로 검증한다(모듈 자체 `VALID_GRADES`/`VALID_DIAMETERS`와 별개로, 제조사 풀은 `spec_grade.py`가 단일 소스여서 `note` 비교 쪽과 동일한 정의를 공유한다):

```python
def _valid_manufacturer(value) -> str:
    if not isinstance(value, str):
        return ""
    return spec_grade.normalize_manufacturer(value) or ""
```

  `extract_tag_fields`에서 `_valid_grade`/`_valid_diameter`와 같은 자리에 `_valid_manufacturer(raw.get("manufacturer"))`를 호출해 세 번째 값으로 반환한다. 목록 밖 값에 대한 경고 로그도 `tag_grade`/`tag_diameter`와 동일한 패턴으로 추가한다.

### `backend/app/routers/ocr.py`

`run_tag_ocr`의 폴백 트리거 조건에 `tag_manufacturer` 빈 값 여부를 추가:

```python
    fields = ocr.normalize_tag_fields(text)
    if not fields["tag_grade"] or not fields["tag_diameter"] or not fields["tag_manufacturer"]:
        logger.warning(...)  # 기존 로그 메시지에 tag_manufacturer 추가
        if config.ANTHROPIC_API_KEY:
            media_type = ...  # 기존과 동일
            llm_grade, llm_diameter, llm_manufacturer = llm_tag_fallback.extract_tag_fields(
                image_bytes, file.filename or "tag.jpg", media_type
            )
            if not fields["tag_grade"] and llm_grade:
                fields["tag_grade"] = llm_grade
            if not fields["tag_diameter"] and llm_diameter:
                fields["tag_diameter"] = llm_diameter
            if not fields["tag_manufacturer"] and llm_manufacturer:
                fields["tag_manufacturer"] = llm_manufacturer
```

응답 형식(`{**fields, "tag_match_status": ...}`)은 `fields`에 `tag_manufacturer`가 자동으로 포함되므로 별도 변경 없이 확장된다. `tag_manufacturer_match_status`는 이 엔드포인트에서 계산하지 않는다(강종/직경의 `tag_match_status`와 달리 `spec` 같은 비교 대상 파라미터를 받지 않음 — 저장 시점에 `crud.py`가 `note`와 비교해 권위 있게 계산).

### `backend/app/models.py`

```python
    tag_manufacturer = Column(String, nullable=True)
    tag_manufacturer_match_status = Column(String, nullable=True)
```

### `backend/app/migrations.py`

**필수** — Render에 이미 배포된 운영 DB(SQLite, `STORAGE_DIR/invoices.db`)에는 이 두 컬럼이 없다. `models.py`만 고치면 로컬 새 DB에는 반영되지만, 기존 운영 DB는 앱 시작 시 이 마이그레이션이 돌지 않으면 컬럼이 없어 저장/조회 시 에러가 난다. `TAG_COLUMNS`에 추가:

```python
TAG_COLUMNS = {
    "tag_photo_path": "VARCHAR",
    "tag_site_name": "VARCHAR",
    "tag_location": "VARCHAR",
    "tag_diameter": "VARCHAR",
    "tag_grade": "VARCHAR",
    "tag_length": "VARCHAR",
    "tag_quantity": "VARCHAR",
    "tag_shape": "VARCHAR",
    "tag_match_status": "VARCHAR",
    "tag_manufacturer": "VARCHAR",
    "tag_manufacturer_match_status": "VARCHAR",
}
```

### `backend/app/schemas.py`

- `InvoiceBase`(→ `InvoiceCreate`/`InvoiceUpdate`/`InvoiceOut`에 모두 상속)에 `tag_grade`와 같은 자리에 `tag_manufacturer: Optional[str] = None` 추가 — 클라이언트가 OCR 인식값(또는 사용자가 직접 수정한 값)을 보내는 일반 필드다.
- `tag_manufacturer_match_status`는 `tag_match_status`와 달리 클라이언트가 명시적으로 override할 이유가 없으므로(배정 로직과 무관, 항상 서버 계산) **`InvoiceBase`/`InvoiceCreate`/`InvoiceUpdate`에는 추가하지 않는다.** `InvoiceOut`에만 `tag_manufacturer_match_status: Optional[str] = None`을 `tag_match_status` 옆에 추가해 응답에는 포함되지만 요청 바디로는 받지 않게 한다.

### `backend/app/crud.py`

`create_invoice`: `tag_manufacturer`는 `InvoiceBase`에 있으므로 `payload`(← `data.model_dump()`)에 이미 포함되어 있다. `tag_manufacturer_match_status`는 `payload`에 없으므로(스키마에 선언하지 않았으므로) pop 없이 바로 계산해 `models.Invoice(...)` 생성자에 명시적으로 전달한다:

```python
def create_invoice(
    db: Session,
    data: schemas.InvoiceCreate,
    photo_path: Optional[str] = None,
    tag_photo_path: Optional[str] = None,
) -> models.Invoice:
    payload = data.model_dump()
    explicit_tag_match_status = payload.pop("tag_match_status", None)
    tag_match_status = explicit_tag_match_status or spec_grade.match_tag_to_spec(
        data.tag_grade, data.tag_diameter, data.spec or ""
    )
    tag_manufacturer_match_status = spec_grade.match_manufacturer(data.tag_manufacturer, data.note)
    invoice = models.Invoice(
        **payload,
        photo_path=photo_path,
        tag_photo_path=tag_photo_path,
        tag_match_status=tag_match_status,
        tag_manufacturer_match_status=tag_manufacturer_match_status,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice
```

`update_invoice`: 기존 `tag_match_status` 재계산 바로 다음 줄에 추가 (`data.model_dump()`의 `tag_manufacturer` 값이 이미 `setattr`로 `invoice.tag_manufacturer`에 반영된 뒤이므로, `invoice.tag_manufacturer`/`invoice.note`를 읽으면 된다):

```python
    invoice.tag_match_status = spec_grade.match_tag_to_spec(invoice.tag_grade, invoice.tag_diameter, invoice.spec or "")
    invoice.tag_manufacturer_match_status = spec_grade.match_manufacturer(invoice.tag_manufacturer, invoice.note)
```

## 프론트엔드 변경

### `frontend/src/pages/EditPage.jsx`

- `matchTagToSpec` 옆에 JS 헬퍼 추가 (백엔드 `spec_grade.py`의 `MANUFACTURER_POOL`/`normalize_manufacturer`/`match_manufacturer`와 동일 로직 이식 — 풀 목록이 두 곳에 중복되므로, 나중에 풀이 바뀌면 백엔드·프론트 양쪽 다 고쳐야 함을 주석으로 남긴다):

```js
// backend/app/spec_grade.py의 MANUFACTURER_POOL과 동일하게 유지할 것.
const MANUFACTURER_POOL = {
  HS: '현대제철',
  DK: '동국제강',
  DH: '대한제강',
  HK: '한국철강',
  HY: '환영철강',
  YK: 'YK스틸',
  HJ: '한국제강',
}
const CORPORATE_MARKERS_PATTERN = /\(주\)|㈜|주식회사|\s+/g

function normalizeManufacturer(value) {
  if (!value) return null
  const stripped = value.trim()
  const code = stripped.toUpperCase()
  if (MANUFACTURER_POOL[code]) return MANUFACTURER_POOL[code]
  const cleaned = stripped.replace(CORPORATE_MARKERS_PATTERN, '')
  if (!cleaned) return null
  const found = Object.values(MANUFACTURER_POOL).find(
    (name) => cleaned.includes(name) || name.includes(cleaned),
  )
  return found || null
}

function matchManufacturer(tagManufacturer, note) {
  const normTag = normalizeManufacturer(tagManufacturer)
  const normNote = normalizeManufacturer(note)
  if (normTag === null || normNote === null) return null
  return normTag === normNote ? 'matched' : 'mismatched'
}
```

- 택 카드에 "제조사(자동 인식, 다르면 직접 수정)" 입력 필드 추가 (`tag_grade`/`tag_diameter` 입력 필드와 같은 패턴, `handleTagFieldEdit(file, 'tag_manufacturer', ...)`)
- 배정된 자재 카드 아래, 기존 강종/직경 일치 배너와 별도로 제조사 확인 배너 추가:

```jsx
{itemAssignments[index] && (() => {
  const status = matchManufacturer(itemAssignments[index].result.tag_manufacturer, item.note)
  if (status === 'matched') return <p className="banner banner-success">제조사가 일치합니다: {itemAssignments[index].result.tag_manufacturer}</p>
  if (status === 'mismatched') return <p className="banner banner-warning">택 제조사({itemAssignments[index].result.tag_manufacturer})가 송장 비고({item.note})와 다릅니다</p>
  return null
})()}
```

- `handleSave`의 `tagFields` 구조분해에 `tag_manufacturer` 추가

### `frontend/src/pages/DetailPage.jsx`

- `TAG_FIELD_DEFS` 배열에 `['tag_manufacturer', '택 제조사']` 추가
- `tagMatchLabel`과 별도로 `tag_manufacturer_match_status`용 배너 추가 (기존 강종/직경 불일치 배너와 같은 스타일):

```jsx
{invoice.tag_manufacturer_match_status === 'mismatched' && (
  <p className="banner banner-warning">
    택 제조사({invoice.tag_manufacturer})가 송장 비고({invoice.note})와 다릅니다
  </p>
)}
```

### `frontend/src/api.js`

변경 없음 (`createInvoice`는 이미 임의의 필드를 `fields` 객체로 받아 그대로 전송하므로 `tag_manufacturer` 포함은 호출부에서만 처리하면 됨).

## 테스트 전략

- `backend/tests/test_spec_grade.py`:
  - `normalize_manufacturer` — 코드로 매칭(`"HS"`, 소문자 `"hs"`), 정식명칭으로 매칭, 법인표기 포함 매칭(`"㈜동국제강"`, `"주식회사 대한제강"`), 부가정보 포함 매칭(`"동국제강(부산공장)"`), 풀 밖 값은 `None`, 빈 값은 `None`
  - `match_manufacturer` — 정상 일치(코드 vs 정식명칭처럼 표기가 달라도 정규화 후 같으면 matched), 불일치(서로 다른 풀 항목), `tag_manufacturer`/`note` 중 하나라도 풀 밖이거나 비어있으면 `None`
- `backend/tests/test_llm_tag_fallback.py`: 응답에 풀 안의 `manufacturer`(코드 또는 정식명칭) 포함 시 정식명칭으로 정규화되어 추출, 풀 밖 값이나 `null`일 때 빈 문자열, 기존 grade/diameter 테스트는 3-튜플 반환에 맞게 갱신
- `backend/tests/test_ocr_endpoint.py`: 라벨 매칭만으로 제조사 추출(풀 안의 값), 라벨로 찾았지만 풀 밖이라 빈 값 처리되는 케이스, LLM 폴백으로 제조사만 보완되는 케이스(강종/직경은 라벨로 찾았지만 제조사만 없는 경우도 폴백이 트리거되는지)
- `backend/tests/test_crud.py`: 저장/수정 시 `tag_manufacturer_match_status`가 `note`와 비교해 올바르게 계산되는지 (일치/불일치/판정불가)
- `backend/tests/test_migrations.py`: `tag_manufacturer`/`tag_manufacturer_match_status` 컬럼이 없는 기존 DB에 `run_migrations` 실행 시 컬럼이 추가되는지
- 프론트엔드는 기존 패턴대로 자동 테스트 없이 `npm run build` + 브라우저 프리뷰로 입력 필드·배너 동작 확인

## 자체 점검

- 배정(assignment) 로직은 강종+직경 기준 그대로 두고 제조사는 추가 확인 배너로만 표시 — 요구사항대로 반영됨.
- 서버가 저장 시점에 `tag_manufacturer_match_status`를 권위 있게 재계산 — 기존 `tag_match_status` 패턴과 일관됨.
- 실제 현장에 납품하는 7개 제강사로 풀을 구성하고, 풀 밖 값은 인식 실패로 간주(빈값) — 사용자 확인 사항 반영됨.
- 라벨 매칭·LLM 비전 양쪽 경로 모두 동일한 `spec_grade.normalize_manufacturer`를 거치므로 검증 로직이 한 곳에만 있음(DRY).
- LLM 폴백은 기존 강종/직경 호출에 통합되어 API 호출이 추가로 늘지 않음.
- `note` 필드가 비어있거나 풀 밖 값인 경우 판정이 `None`(확인불가)으로 자연스럽게 처리됨 — 별도 예외 처리 불필요.
- 운영 DB(Render, 기존 데이터 보유)에 대한 컬럼 마이그레이션(`migrations.py`)을 누락 없이 포함 — 이전 LLM 폴백 설계에는 없던 항목이라 별도로 점검함.
- 풀 목록이 백엔드(`spec_grade.py`)와 프론트엔드(`EditPage.jsx`)에 중복 정의되는 것은 알려진 트레이드오프로 명시함(공유 설정 파일로 뺄 만큼 이 프로젝트에 프론트-백엔드 공유 모듈 체계가 없어 YAGNI로 판단).
