# 택 카드 판정 단순화 및 인식 강건성 개선 — 설계 문서

## 배경

철근 택 제조사 확인 기능을 배포한 뒤 실사용 테스트 중 두 가지가 확인됐다.

1. 편집 화면의 "철근 Tag 검수" 섹션(택 카드)이 실제 현장 검수 목적과 맞지 않는다. 택 카드는 강도/직경/제조사를 개별적으로 보여주고 수정할 수 있는 입력 폼이었는데, 이 섹션의 실제 용도는 "이 철근 다발(택)이 송장 내용과 일치하는 물건인지"만 확인하면 되는 단순 검수 도구다.
2. 실제 현장 택 사진 여러 장을 테스트하는 과정에서 Render 운영 로그를 근거로 4가지 인식 실패 원인이 확인됐다(원인 C는 이번 범위에서 보류, 아래 "보류된 항목" 참고):
   - **원인 A**: Upstage가 표를 셀 사이 공백 없이 이어붙이면(예: `UHD252,800184SD600mmEA`), 정규식 폴백의 "값 뒤에 숫자가 더 없어야 한다"/"값 앞이 영문·숫자가 아니어야 한다" 경계 조건이 이웃 셀의 숫자 때문에 깨져서 강도/직경 인식이 실패한다.
   - **원인 B**: 실제 택에는 제강사명이 영문으로 찍혀 있는 경우가 있다(`DONGKUK STEEL MILL CO., LTD.`, `HYUNDAI` 등 로그에서 확인됨). 현재 시스템은 한글 표기만 인식하도록 되어 있어 OCR이 텍스트를 정확히 읽어도 인식이 원천적으로 불가능했다.
   - **원인 D**: 일부 택은 현장명 뒤에 승인 업체 후보가 여러 곳(예: `삼성물산-서소문빌딩(동국제강,현대)`) 함께 표기된다. 이건 "이 철근의 제조사"가 아니라 "이 현장에 납품 가능한 업체 목록"으로 보이며, 택 한 장만으로는 후보 중 어느 쪽이 실제 제조사인지 알 수 없다. 사용자 확인 결과, 후보 중 **하나라도** 송장과 일치하면 적합으로 처리하기로 했다.

## 범위

**포함:**
- `EditPage.jsx`의 택 카드(각 촬영된 택 사진마다 나오는 카드)에서 강도/직경/제조사 입력 필드 3개를 제거한다.
- 택의 강도+직경+제조사가 송장 내 자재(품목) 중 **하나라도 전부** 일치하면 "적합", 하나라도 다르거나 애초에 인식이 안 됐으면(빈 값 포함) "부적합"으로 판정하는 단일 배너로 대체한다.
- 인식 자체가 실패한 경우(사진에서 텍스트를 전혀 못 읽음)의 기존 "인식에 실패했습니다" 안내는 그대로 유지한다.
- **(원인 A)** 강도/직경 정규식 폴백(`ocr.py`)이 셀 사이 공백 없이 붙은 텍스트에서도 동작하도록 수정한다.
- **(원인 B)** 확인된 영문 제강사 표기 2건(동국제강/현대제철)을 인식 대상에 추가한다.
- **(원인 D)** 택 하나에서 제강사 후보를 여러 개 인식하고, 송장 `note`가 그 중 하나와만 일치해도 "matched"로 판정하도록 매칭 로직을 확장한다. 라벨 매칭·LLM 비전 폴백 양쪽 모두 반영한다.

**범위 밖 (보류):**
- **원인 C** — 1차 OCR(document-parse)이 완전히 빈 텍스트가 아니라 워터마크 등 쓸모없는 텍스트만 반환했을 때 보조 OCR로 재시도하지 않는 문제. LLM 비전 폴백이 이 경우를 상당 부분 구제하고 있어 이번에는 보류한다.
- 나머지 5개 업체(대한제강/한국철강/환영철강/YK스틸/한국제강)의 영문 표기·축약 표기 — 아직 실제 택에서 확인되지 않았다. 확인되는 대로 `MANUFACTURER_ALIASES`에 추가하면 된다(구조상 항목 추가만으로 확장 가능, 단 여러 업체에 공통되는 일반 명사는 등록하지 않는다).
- 자재 카드(송장 자재 목록 + 택 배정 배너) — 배정 로직(`matchTagsToItems`)과 배정 성공/실패 배너는 강도+직경 기준 그대로 둔다. 다만 배정된 택에 대해 제조사 일치를 표시하는 통합 배너(`"일치하는 철근 Tag을 확인했습니다 : ..."`)는 매칭 로직 확장(원인 D)의 영향을 자동으로 받는다 — 코드 변경은 없지만 동작이 개선된다.
- 저장 로직(`handleSave`) — 배정된 택의 강도/직경/제조사/현장명 등은 지금처럼 그대로 저장된다.

## 백엔드 변경 (원인 A — 정규식 경계 조건)

`backend/app/ocr.py`의 강도/직경 폴백 정규식은 "직경 숫자 뒤에 더 이상 숫자가 없어야 한다"(`\d{1,2}(?!\d)`)는 가변 길이 캡처 방식이라, 표 셀이 공백 없이 붙으면(다음 셀이 숫자로 시작) 경계 조건이 깨진다. 실제 철근 직경은 KS D 3504 표준 호칭경(6/10/13/16/19/22/25/29/32/35/38/41/51/57)으로 **닫힌 집합**이므로, "1~2자리 숫자 아무거나"가 아니라 "이 목록 중 하나"로 매칭하도록 바꾸면 가변 길이 문제 자체가 없어진다(뒤에 숫자가 더 있어도 상관없이, 정확히 이 값들 중 하나가 왔는지만 보면 되므로).

```python
# ocr.py — 기존 상수를 다음으로 교체
_VALID_DIAMETER_VALUES = ("57", "51", "41", "38", "35", "32", "29", "25", "22", "19", "16", "13", "10", "6")
_DIAMETER_ALTERNATION = "|".join(_VALID_DIAMETER_VALUES)

# 한글은 파이썬 정규식에서 \w(단어 문자)로 취급돼 \b가 경계로 인식되지 않고,
# 표 셀이 공백 없이 붙으면 앞뒤로 숫자가 이어질 수도 있어(예: "184SD600",
# "UHD252,800") "영문 앞뒤가 아님"만 경계로 삼는다 — 숫자가 붙어도 허용한다.
_PREFIXED_SPEC_PATTERN = re.compile(rf"(?<![A-Za-z])(SHD|UHD|SD)({_DIAMETER_ALTERNATION})")
_BARE_GRADE_PATTERN = re.compile(r"(?<![A-Za-z])SD([456]00)(?!\d)")
_DIAMETER_PATTERN = re.compile(rf"(?<![A-Za-z])D({_DIAMETER_ALTERNATION})")
```

- `_PREFIXED_SPEC_PATTERN`/`_DIAMETER_PATTERN`: 뒤쪽 `(?!\d)` 제거(닫힌 집합이 이미 몇 자리를 캡처할지 결정하므로 불필요), 앞쪽 lookbehind에서 `0-9` 제외 — 숫자가 바로 앞에 붙어도 매칭 허용.
- `_BARE_GRADE_PATTERN`: 강도(`[456]00`)는 원래도 고정 3자리라 뒤쪽 경계는 그대로 유지(여전히 유효 — "SD6001"처럼 4자리면 오매칭 방지용으로 의미 있음). 앞쪽 lookbehind만 동일하게 완화.
- 실제 로그에서 확인된 실패 텍스트(`...수직1UHD252,800184SD600mmEA...`)를 그대로 회귀 테스트 픽스처로 쓴다.
- **트레이드오프**: 뒤쪽 숫자 경계를 없애면서, "D13"처럼 우연히 유효 직경 값으로 시작하는 무관한 숫자열(예: 어떤 일련번호가 "D1350"처럼 찍혀있는 경우)을 오매칭할 가능성이 이론적으로 생긴다. 다만 이건 실제로 발생 중인 인식 실패(원인 A)보다 드물고 위험이 낮다고 판단했다 — 값을 아예 못 읽는 것보다, 드물게 잘못 읽는 편이 검수 목적에 더 낫다는 판단. 회귀 우려가 크면 추후 재논의 가능.

## 백엔드 변경 (원인 B, D — 제강사 인식 확장)

### `backend/app/spec_grade.py`

별칭 테이블(영문 표기 + 흔한 한글 축약 표기)을 추가하고, "택 하나에서 여러 제강사 후보를 모두 인식"하는 함수를 새로 만든다. 기존 `normalize_manufacturer`(단일값)는 이 함수의 얇은 래퍼로 바꿔 로직을 한 곳에만 둔다.

실제 택 텍스트로 설계를 검증하는 과정에서, "동국제강,현대"처럼 **현대제철이 "현대"로 축약**돼 있는 걸 확인했다(정식명칭 "현대제철"이 그대로 나오지 않음). 이건 앞서(원인 D 발견 전) 고친 "제강"/"철강" 같은 일반 명사 오판정 방지 로직과 같은 종류의 문제(정식명칭의 일부만 있는 표기를 인정할지)라서, 별도의 "고유하게 식별되는 축약형만 등록"하는 별칭 테이블로 통합해 해결한다 — 영문 표기와 완전히 같은 방식으로 다룬다.

콤마로 여러 후보가 나열된 입력을 처리할 때 문제가 하나 있다: `"CO., LTD."`처럼 **영문 법인 표기 자체에 콤마가 들어있는 경우**, 콤마로 무조건 분리하면 잘못 쪼개진다. 그렇다고 전혀 분리하지 않으면 `"DK,HS"`처럼(LLM이 코드를 콤마로 나열한 경우) 코드 하나하나를 정확히 인식하기 어렵다. 그래서 두 단계로 나눠 처리한다: ① 콤마로 나눈 각 토큰이 "코드"(또는 법인 표기 제거 후 코드)인 경우만 먼저 인정하고, ② 그걸로 못 찾은 나머지는 원문 전체(분리하지 않음)에서 정식명칭/별칭이 부분 문자열로 등장하는지 확인한다 — 이 두 번째 단계가 `"CO., LTD."`의 콤마와도, `"동국제강,현대"`처럼 라벨 없이 붙은 한글 축약형과도 문제없이 맞물린다.

```python
# 실제 택에서 확인된 표기만 등록한다 — "현대"는 "현대제철"의 흔한 줄임
# 표기(택에 "(동국제강,현대)"처럼 나옴), DONGKUK/HYUNDAI는 영문 표기.
# 아직 확인 안 된 나머지 5개 업체(대한제강/한국철강/환영철강/YK스틸/
# 한국제강)의 축약형·영문 표기는 실제 택을 받는 대로 추가한다.
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

    두 단계로 찾는다: 1) 콤마로 나눈 각 토큰이 "코드"(또는 법인 표기 제거
    후 코드)인 경우 — LLM이 "DK,HS"처럼 깔끔하게 답한 경우를 위해. 2) 원문
    전체(콤마로 나누지 않음)에서 정식명칭/별칭이 부분 문자열로 등장하는지
    확인 — 영문 법인 표기("CO., LTD.")의 콤마와 충돌하지 않도록, 그리고
    "현대"처럼 라벨 없이 붙은 축약형을 위해 콤마로 나누지 않는다."""
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
    """원문 표기를 MANUFACTURER_POOL의 정식명칭 하나(대표값)로 정규화한다.
    여러 업체가 함께 표기된 경우는 normalize_manufacturers를 쓸 것.
    풀의 7개 중 어디에도 매칭되지 않으면 None."""
    found = normalize_manufacturers(value)
    return found[0] if found else None


def match_manufacturer(tag_manufacturer: str | None, note: str | None) -> str | None:
    """택에서 인식된 제강사 후보들 중 하나라도 송장 note와 일치하면 matched."""
    tag_candidates = normalize_manufacturers(tag_manufacturer)
    norm_note = normalize_manufacturer(note)
    if not tag_candidates or norm_note is None:
        return None
    return "matched" if norm_note in tag_candidates else "mismatched"
```

- `MANUFACTURER_ALIASES`는 "제강"/"철강" 같은 일반 명사를 절대 포함하지 않는다 — 등록되는 건 실제 택에서 확인되고 풀 안에서 유일하게 한 업체만 가리키는 표기(축약형/영문)뿐이다. 새 별칭을 추가할 때도 이 원칙(여러 업체에 공통으로 들어맞지 않는 표기인지)을 지켜야 한다.
- 시그니처는 그대로이므로(`match_manufacturer`) `crud.py` 호출부는 변경 불필요 — 저장된 `tag_manufacturer` 값에 복수 후보가 콤마로 들어있어도 내부에서 알아서 다시 파싱한다.

### `backend/app/ocr.py`

라벨 매칭으로 캡처한 원문을 **모든 후보를 콤마로 이어붙여** 저장하도록 바꾼다(기존엔 대표값 하나만 저장):

```python
    result["tag_manufacturer"] = ",".join(spec_grade.normalize_manufacturers(result["tag_manufacturer"]))
```

### `backend/app/llm_tag_fallback.py`

프롬프트가 "7개 중 하나만" 답하도록 되어 있던 걸 "해당하는 걸 모두 콤마로" 답하도록 바꾼다:

```python
_PROMPT = (
    "이 사진은 철근 택(꼬리표) 사진입니다. 택에 표시된 철근의 강종, 직경, "
    "제조사만 다른 설명 없이 JSON으로 답하세요: "
    '{"grade": "SD300/SD400/SD500/SD600 중 하나, 모르면 null", '
    '"diameter": "13처럼 숫자만, 모르면 null", '
    '"manufacturer": "다음 7개 제강사 중 택에 표기된 것을 모두 콤마로 구분해서 — '
    'HS(현대제철), DK(동국제강), DH(대한제강), HK(한국철강), HY(환영철강), YK(YK스틸), '
    'HJ(한국제강). 코드나 정식명칭 아무거나로 답해도 됩니다. 이 목록에 없거나 모르면 null"}. '
    "확신이 없으면 null로 답하세요."
)
```

`_valid_manufacturer`도 복수 후보를 받아 콤마로 이어붙이도록 바꾼다:

```python
def _valid_manufacturer(value) -> str:
    if not isinstance(value, str):
        return ""
    return ",".join(spec_grade.normalize_manufacturers(value))
```

`extract_tag_fields`/`routers/ocr.py`의 나머지 로직(그레이드·직경과 동일하게 "이미 값이 있으면 LLM 결과로 덮어쓰지 않음")은 그대로 — `tag_manufacturer`가 이제 콤마 구분 문자열이 될 수 있다는 것만 반영되면 된다.

## 판정 로직

기존에 이미 있는 두 헬퍼(`matchTagToSpec`, `matchManufacturer`)를 그대로 재사용해, "송장 내 자재 중 하나라도 강도+직경+제조사가 모두 일치하는가"를 판정하는 함수를 새로 추가한다:

```js
function isTagVerifiedAgainstInvoice(tagResult, items) {
  return items.some(
    (item) =>
      matchTagToSpec(tagResult.tag_grade, tagResult.tag_diameter, item.spec) === 'matched' &&
      matchManufacturer(tagResult.tag_manufacturer, item.note) === 'matched',
  )
}
```

- `matchTagToSpec`/`matchManufacturer` 둘 다 인식 실패(빈 값) 시 `null`을 반환하므로, `=== 'matched'` 비교로 자연스럽게 "인식 안 됨"도 부적합으로 처리된다 — 별도 분기 불필요.
- 자재가 여러 개인 송장에서, 그 중 하나(품목)라도 3가지 조건이 모두 맞으면 적합.

## 프론트엔드 변경

### `frontend/src/pages/EditPage.jsx`

백엔드 `normalizeManufacturer`/`matchManufacturer` JS 포트도 원인 B(영문 별칭)·원인 D(복수 후보)에 맞춰 함께 갱신한다 — 이미 알려진 트레이드오프(풀 목록이 Python/JS 양쪽에 중복 정의됨)를 그대로 유지한다.

기존 `MANUFACTURER_POOL` 바로 다음에 별칭 테이블 추가(영문 표기 + 흔한 한글 축약 표기, 백엔드와 동일한 원칙 — "제강"/"철강" 같은 일반 명사는 절대 넣지 않고, 풀 안에서 유일하게 한 업체만 가리키는 표기만 등록):

```js
// backend app/spec_grade.py의 MANUFACTURER_ALIASES와 동일하게 유지할 것.
const MANUFACTURER_ALIASES = {
  현대: '현대제철',
  DONGKUK: '동국제강',
  HYUNDAI: '현대제철',
}
```

`normalizeManufacturer`를 `normalizeManufacturers`(복수 후보 배열 반환)로 바꾸고, 기존 `normalizeManufacturer`는 그 위에 얇게 래핑한다. 백엔드와 동일한 2단계 방식 — ① 콤마로 나눈 각 토큰이 코드인 경우 먼저 인정, ② 원문 전체(분리하지 않음)에서 정식명칭/별칭이 부분 문자열로 등장하는지 확인 — 을 그대로 이식한다:

```js
// backend app/spec_grade.py의 normalize_manufacturers와 동일한 로직을 프런트에서도
// 재계산할 수 있도록 이식한 헬퍼. "동국제강,현대"처럼 후보가 여러 곳 함께
// 표기된 택을 위해 배열을 반환한다.
function normalizeManufacturers(value) {
  if (!value) return []
  const found = []
  for (const token of value.split(',')) {
    const strippedToken = token.trim()
    if (!strippedToken) continue
    const code = strippedToken.toUpperCase()
    if (MANUFACTURER_POOL[code]) {
      const name = MANUFACTURER_POOL[code]
      if (!found.includes(name)) found.push(name)
      continue
    }
    const cleanedToken = strippedToken.replace(CORPORATE_MARKERS_PATTERN, '')
    const cleanedCode = cleanedToken.toUpperCase()
    if (MANUFACTURER_POOL[cleanedCode]) {
      const name = MANUFACTURER_POOL[cleanedCode]
      if (!found.includes(name)) found.push(name)
    }
  }

  const cleanedWhole = value.trim().replace(CORPORATE_MARKERS_PATTERN, '')
  for (const name of Object.values(MANUFACTURER_POOL)) {
    if (cleanedWhole.includes(name) && !found.includes(name)) found.push(name)
  }
  const cleanedWholeUpper = cleanedWhole.toUpperCase()
  for (const [alias, name] of Object.entries(MANUFACTURER_ALIASES)) {
    if (cleanedWholeUpper.includes(alias.toUpperCase()) && !found.includes(name)) found.push(name)
  }
  return found
}

function normalizeManufacturer(value) {
  const found = normalizeManufacturers(value)
  return found.length > 0 ? found[0] : null
}

function matchManufacturer(tagManufacturer, note) {
  const tagCandidates = normalizeManufacturers(tagManufacturer)
  const normNote = normalizeManufacturer(note)
  if (tagCandidates.length === 0 || normNote === null) return null
  return tagCandidates.includes(normNote) ? 'matched' : 'mismatched'
}
```

(기존 `normalizeManufacturer`/`matchManufacturer` 정의를 위 내용으로 교체하는 것 — 함수 이름과 호출부는 그대로라 `isTagVerifiedAgainstInvoice`나 자재 카드의 통합 배너 쪽 코드는 수정 없이 새 동작을 그대로 물려받는다.)

`isTagVerifiedAgainstInvoice` 함수를 `matchManufacturer` 정의 바로 다음(기존 `CODE_BY_MANUFACTURER` 앞)에 추가한다.

택 카드 렌더링 블록(현재 강도/직경/제조사 입력 필드 3개 + "이 규격은 송장에 포함되어 있습니다" 배너가 있는 부분)을 다음으로 교체한다:

```jsx
              {result === 'loading' && <p>인식 중...</p>}
              {result === 'error' && <p className="banner banner-error">인식에 실패했습니다. 강도/직경을 직접 입력해주세요.</p>}
              {result && result !== 'loading' && result !== 'error' &&
                (isTagVerifiedAgainstInvoice(result, items) ? (
                  <p className="banner banner-success">적합</p>
                ) : (
                  <p className="banner banner-warning">부적합</p>
                ))}
```

`handleTagFieldEdit` 함수는 제거한다 — 강도/직경/제조사 입력 필드가 그 함수의 유일한 호출처였고, 다른 곳에서 쓰이지 않는다.

`result === 'error'` 배너의 문구("인식에 실패했습니다. 강도/직경을 직접 입력해주세요.")는 이제 "직접 입력"할 UI가 없으므로 다음으로 바꾼다: `"인식에 실패했습니다."`

## 영향받지 않는 부분

- 자재 카드의 배정 로직(`matchTagsToItems`, 강도+직경 기준) 자체는 그대로다 — 다만 그 아래 통합 적합 배너는 `matchManufacturer` 확장을 통해 복수 후보/영문 표기를 자동으로 인식하게 된다(코드 변경 없이 동작만 개선).
- `handleSave`가 배정된 택의 `tag_grade`/`tag_diameter`/`tag_manufacturer`/기타 필드를 저장하는 로직은 그대로다 — 택 카드에서 입력 필드로 값을 보여주고 고치던 것만 없앨 뿐, OCR로 인식된 값 자체는 (수정 없이) 그대로 저장된다.
- `DetailPage.jsx` — 코드 변경은 없다. 다만 `tag_manufacturer`가 이제 `"동국제강,현대제철"`처럼 콤마로 여러 값이 들어올 수 있어 읽기전용 필드에 그대로 표시된다(정보 전달에는 문제없음).
- `crud.py` — `spec_grade.match_manufacturer` 호출 시그니처가 그대로라 코드 변경 불필요.

## 테스트 전략

**백엔드** (TDD로 진행):
- `test_spec_grade.py`: `normalize_manufacturers` — 복수 후보 인식(`"동국제강,현대"` → 2개), 영문 별칭(`"DONGKUK STEEL MILL CO., LTD."` → 동국제강, `"HYUNDAI"` → 현대제철), 기존 단일 후보 케이스 회귀. `match_manufacturer` — 복수 후보 중 하나만 일치해도 matched.
- `test_ocr.py`: 실제 로그에서 확인된 셀 붙음 텍스트(`UHD252,800184SD600mmEA` 등)를 그대로 픽스처로 사용해 강도/직경 폴백 회귀 테스트. 기존 통과 테스트(정상 케이스)들도 계속 통과하는지 확인.
- `test_llm_tag_fallback.py`: 프롬프트 응답이 콤마로 여러 값을 포함할 때 모두 파싱되는지.
- `test_ocr_endpoint.py`, `test_crud.py`: 필요 시 복수 후보가 엔드투엔드로 저장·판정되는 케이스 추가.

**프론트엔드**: 기존 패턴대로 자동 테스트 없이 `npm run build` + 브라우저 프리뷰로 확인. 추가 확인 항목:
- 택 사진 업로드 후 강도/직경/제조사 입력 필드가 더 이상 보이지 않는지
- 강도+직경+제조사가 송장 자재 중 하나와 모두 일치하면 "적합" 배너가 뜨는지
- 하나라도 다르면(또는 인식이 안 됐으면) "부적합" 배너가 뜨는지
- 자재 카드 쪽 배정 배너와 저장 동작은 기존과 동일하게 유지되는지

## 자체 점검

- 판정 로직이 기존 `matchTagToSpec`/`matchManufacturer` 헬퍼를 재사용해 중복 로직을 만들지 않음 — 확인됨.
- 인식 실패(빈 값)가 자동으로 "부적합"으로 처리됨(`null !== 'matched'`) — 별도 분기 없이 요구사항 반영됨.
- 자재 카드/저장 로직 비변경 — 요구사항대로 명시됨.
- 죽은 코드(`handleTagFieldEdit`)를 함께 정리 — 범위에 포함.
- 원인 A 수정이 실제 운영 로그의 실패 텍스트로 검증됨 — 추측이 아니라 재현된 증거 기반.
- 원인 D(복수 후보) 반영 시 `crud.py`/라우터 호출부 변경이 불필요하도록 설계해 영향 범위를 최소화함.
- 나머지 5개 업체 영문 표기는 보류하고 확장 가능한 구조(딕셔너리 항목 추가)로만 남겨둠 — 없는 정보를 추측해서 채우지 않음.
