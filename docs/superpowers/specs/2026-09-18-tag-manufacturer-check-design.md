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
- 제조사 목록 검증(할루시네이션 방지용 표준 목록) — 국내 제조사가 다양하고 목록에 없는 소규모 업체도 있어 이번에는 도입하지 않는다. 검증 없이 LLM 응답을 그대로 사용한다.
- 택-자재 배정(assignment) 로직 변경 — 배정은 기존대로 강종+직경 기준으로만 하고, 제조사는 배정된 뒤 추가 확인 배너로만 표시한다.
- `vendor`(거래처/공장명) 필드와의 대조 — `note` 필드(갑지 파싱 시 실제 제조사명이 들어가는 칸)만 비교 대상으로 한다.

## 비교 대상 필드

송장 레코드의 `note` 필드를 기준으로 삼는다. 갑지(철근 납품 확인서) 파싱 시 표의 "비고" 칸에 실제 제조사명(예: "동국제강")이 들어가는 것이 확인됐다([report_parser.py](../../../backend/app/report_parser.py)의 `build_capture_records`). 일반 촬영 송장은 `note`가 비어있을 수 있으며, 이 경우 판정은 `None`(확인불가)이 된다.

## 인식 방식

기존 강종/직경과 동일한 하이브리드 구조를 따르되, 정규식 폴백 단계는 생략한다(제조사명은 `SD500`처럼 고정된 표기 규칙이 없고, 로고·도장 형태로만 표시되는 경우가 많다):

1. **라벨 매칭**: `ocr.normalize_tag_fields`가 "제조사"/"제강사" 라벨을 찾아 값 추출 (기존 로직 재사용, 라벨 목록만 추가)
2. **LLM 비전 폴백**: 강종·직경·제조사 중 하나라도 비어있으면 Claude 비전에 택 사진을 보내 세 값을 **한 번에** 요청 (기존 강종/직경 폴백 호출에 제조사 추출을 포함시켜, 같은 사진에 대해 API를 두 번 호출하지 않는다)

제조사는 표준 목록 검증 없이 LLM 응답을 trim만 해서 그대로 사용한다.

**참고**: 제조사는 라벨 매칭 성공률이 강종/직경보다 낮을 것으로 예상되어(로고 위주), LLM 폴백 호출 빈도가 강종/직경보다 높아질 가능성이 있다. 호출당 비용 자체가 낮아([2026-09-18-tag-llm-vision-fallback-design.md](2026-09-18-tag-llm-vision-fallback-design.md) 참고) 허용 가능한 수준으로 판단했다.

## 일치 판정 규칙

`(주)`, `㈜`, `주식회사`, 공백을 제거해 정규화한 뒤, 한쪽 문자열이 다른 쪽을 포함(containment)하면 `matched`로 판정한다 (예: `note="동국제강"`, 택="㈜동국제강" → 정규화 후 "동국제강" ⊂ "동국제강" → matched). 정규화 후에도 서로 포함 관계가 아니면 `mismatched`. `tag_manufacturer` 또는 `note` 둘 중 하나라도 비어있으면 `None`(판정 불가).

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

`TAG_FIELDS`는 `TAG_FIELD_LABELS.keys()`에서 자동 파생되므로 별도 변경 불필요.

### `backend/app/llm_tag_fallback.py`

- `_PROMPT`에 `manufacturer` 필드 추가 (강종/직경과 같은 JSON 응답에 포함, 모르면 `null`)
- `extract_tag_grade_diameter(image_bytes, filename, media_type) -> tuple[str, str]`를 `extract_tag_fields(image_bytes, filename, media_type) -> tuple[str, str, str]`(grade, diameter, manufacturer)로 확장
- `call_claude_vision`은 원시 dict를 그대로 반환하므로 변경 없음(호출부에서 `"manufacturer"` 키만 추가로 읽음)
- 제조사는 `_valid_grade`/`_valid_diameter` 같은 검증 없이, 문자열이면 `.strip()`만 적용(빈 문자열/비문자열은 `""`)

### `backend/app/spec_grade.py`

```python
_CORPORATE_MARKERS_PATTERN = re.compile(r"\(주\)|㈜|주식회사|\s+")


def _normalize_manufacturer(value: str | None) -> str | None:
    if not value:
        return None
    normalized = _CORPORATE_MARKERS_PATTERN.sub("", value.strip())
    return normalized or None


def match_manufacturer(tag_manufacturer: str | None, note: str | None) -> str | None:
    norm_tag = _normalize_manufacturer(tag_manufacturer)
    norm_note = _normalize_manufacturer(note)
    if norm_tag is None or norm_note is None:
        return None
    if norm_tag in norm_note or norm_note in norm_tag:
        return "matched"
    return "mismatched"
```

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

- `matchTagToSpec` 옆에 JS 헬퍼 추가 (백엔드 `match_manufacturer`와 동일 로직 이식):

```js
const CORPORATE_MARKERS_PATTERN = /\(주\)|㈜|주식회사|\s+/g

function normalizeManufacturer(value) {
  if (!value) return null
  const normalized = value.trim().replace(CORPORATE_MARKERS_PATTERN, '')
  return normalized || null
}

function matchManufacturer(tagManufacturer, note) {
  const normTag = normalizeManufacturer(tagManufacturer)
  const normNote = normalizeManufacturer(note)
  if (normTag === null || normNote === null) return null
  if (normNote.includes(normTag) || normTag.includes(normNote)) return 'matched'
  return 'mismatched'
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

- `backend/tests/test_spec_grade.py`: `match_manufacturer` — 정상 일치, 법인표기 차이 정규화(`(주)`/`㈜`/`주식회사`/공백), 불일치, `tag_manufacturer`/`note` 중 하나라도 없을 때 `None`
- `backend/tests/test_llm_tag_fallback.py`: 응답에 `manufacturer` 포함 시 추출, `null`일 때 빈 문자열, 기존 grade/diameter 테스트는 3-튜플 반환에 맞게 갱신
- `backend/tests/test_ocr_endpoint.py`: 라벨 매칭만으로 제조사 추출, LLM 폴백으로 제조사만 보완되는 케이스(강종/직경은 라벨로 찾았지만 제조사만 없는 경우도 폴백이 트리거되는지)
- `backend/tests/test_crud.py`: 저장/수정 시 `tag_manufacturer_match_status`가 `note`와 비교해 올바르게 계산되는지 (일치/불일치/판정불가)
- `backend/tests/test_migrations.py` 또는 기존 스키마 마이그레이션 테스트가 있다면 새 컬럼 반영 확인
- 프론트엔드는 기존 패턴대로 자동 테스트 없이 `npm run build` + 브라우저 프리뷰로 입력 필드·배너 동작 확인

## 자체 점검

- 배정(assignment) 로직은 강종+직경 기준 그대로 두고 제조사는 추가 확인 배너로만 표시 — 요구사항대로 반영됨.
- 서버가 저장 시점에 `tag_manufacturer_match_status`를 권위 있게 재계산 — 기존 `tag_match_status` 패턴과 일관됨.
- 제조사는 표준 목록 검증 없이 그대로 사용 — 범위 밖 항목으로 명시됨.
- LLM 폴백은 기존 강종/직경 호출에 통합되어 API 호출이 추가로 늘지 않음.
- `note` 필드가 비어있는 일반 촬영 송장에서는 판정이 `None`(확인불가)으로 자연스럽게 처리됨 — 별도 예외 처리 불필요.
