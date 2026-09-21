# 택 카드 판정 단순화 및 인식 강건성 개선 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 편집 화면 택 카드를 "강도/직경/제조사 개별 확인·수정" UI에서 "송장과 일치하는지"만 보여주는 단순 적합/부적합 판정으로 바꾸고, 실제 운영 로그로 확인된 3가지 인식 실패 원인(표 셀 붙음, 영문/축약 제조사명 미인식, 복수 후보 업체 미지원)을 고친다.

**Architecture:** 백엔드 3곳(`ocr.py`의 정규식 폴백, `spec_grade.py`의 제조사 정규화, `llm_tag_fallback.py`의 LLM 프롬프트/검증)을 실제 실패 사례 기반으로 강화하고, 프론트엔드(`EditPage.jsx`)는 입력 필드를 없애고 기존 매칭 헬퍼를 재사용하는 단일 판정 함수로 교체한다.

**Tech Stack:** FastAPI, pytest, React.

## Global Constraints

- 직경은 KS D 3504 표준 호칭경 닫힌 집합만 유효: `{6, 10, 13, 16, 19, 22, 25, 29, 32, 35, 38, 41, 51, 57}`.
- 제조사 풀은 정확히 7개(변경 없음): `HS→현대제철`, `DK→동국제강`, `DH→대한제강`, `HK→한국철강`, `HY→환영철강`, `YK→YK스틸`, `HJ→한국제강`.
- 제조사 별칭은 실제 택에서 확인된 것만 등록: `현대→현대제철`, `DONGKUK→동국제강`, `HYUNDAI→현대제철`. 여러 업체에 공통되는 일반 명사(예: "제강", "철강")는 절대 별칭으로 등록하지 않는다.
- 콤마로 구분된 복수 제조사 후보 입력은 **문자열을 분리하지 않고** 텍스트 전체에서 각 업체(정식명칭/별칭)의 등장 여부를 개별 검사한다 — 영문 법인 표기(`"CO., LTD."`)의 콤마와 충돌하지 않도록.
- 택의 강도+직경+제조사가 송장 내 자재(품목) 중 **하나라도 전부** 일치하면 "적합", 아니면(인식 실패 포함) "부적합".
- 자재 카드의 택 배정 로직(`matchTagsToItems`, 강도+직경 기준)과 저장 로직(`handleSave`)은 변경하지 않는다.
- 이번 범위는 원인 A(표 셀 붙음)·B(영문/축약 제조사명)·D(복수 후보)까지다. 원인 C(애매한 OCR 실패 시 재시도 누락)는 보류.
- 참고 설계 문서: `docs/superpowers/specs/2026-09-18-tag-card-verdict-simplification-design.md`

---

### Task 1: `ocr.py` 정규식 경계 조건 수정 (원인 A)

**Files:**
- Modify: `backend/app/ocr.py`
- Test: `backend/tests/test_ocr.py`

**Interfaces:**
- Consumes: 없음(기존 `spec_grade.parse_spec_grade_diameter`만 계속 사용)
- Produces: `ocr._fallback_tag_grade_diameter(text: str) -> tuple[str, str]`의 동작이 개선됨(시그니처 변경 없음) — `ocr.normalize_tag_fields`가 내부적으로 계속 사용

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_ocr.py` 파일 끝에 추가:

```python
def test_normalize_tag_fields_recovers_diameter_when_glued_to_following_digit_cell():
    # 실제 운영에서 확인된 실패 사례: Upstage가 표 셀을 공백 없이 이어붙여
    # "UHD25" 바로 뒤에 다음 셀("2,800")의 숫자가 붙어버리면, 예전 정규식은
    # "값 뒤에 숫자가 더 없어야 한다"는 경계 조건이 깨져 인식에 실패했다.
    text = "수직1UHD252,800184SD600mmEA"
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_grade"] == "SD600"
    assert fields["tag_diameter"] == "25"


def test_normalize_tag_fields_recovers_from_real_production_failure_text():
    # 실제 Render 운영 로그에 남은 인식 실패 텍스트를 그대로 회귀 테스트로 쓴다.
    text = (
        "원산지:국내산 1/1 삼성물산-서소문빌딩(동국제강,현대)18차=1=3구간 지하1층 BW2 "
        "수직1UHD252,800184SD600mmEA\n\n2,800\n\n2,050 kg\n001\n2026. 09. 15. 오전 9:32"
    )
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_grade"] == "SD600"
    assert fields["tag_diameter"] == "25"


def test_normalize_tag_fields_grade_recovers_when_preceded_by_digit_cell():
    # "184SD600"처럼 강도 표기 앞에 다른 셀의 숫자가 바로 붙어도 인식돼야 한다.
    text = "184SD600mmEA"
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_grade"] == "SD600"


def test_normalize_tag_fields_sd6_not_confused_with_sd600():
    # "SD" 뒤에 "6"만 오면 직경 6mm(강도 SD400)로 정상 인식돼야 하고,
    # 이게 "SD600"(강도 단독 표기)의 앞부분과 혼동되면 안 된다.
    text = "SD6 X 12m"
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_grade"] == "SD400"
    assert fields["tag_diameter"] == "6"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_ocr.py -v -k "glued_to_following or real_production_failure or preceded_by_digit_cell or sd6_not_confused"`

Expected: 위 4개 중 앞의 3개(`glued_to_following_digit_cell`, `real_production_failure_text`, `preceded_by_digit_cell`)는 FAIL — 현재 정규식은 값 뒤/앞에 숫자가 붙으면 경계 조건이 깨져 `tag_grade`/`tag_diameter`가 빈 문자열로 남는다. 마지막 `sd6_not_confused_with_sd600`은 이번 수정 없이도 이미 통과할 수 있다(기존 정규식도 "SD6" 뒤에 공백이 오는 단순 케이스는 처리한다) — 이 테스트는 새 기능이 아니라 다음 Step에서 추가하는 "SD6/SD600 구분 로직"이 이 정상 케이스를 깨지 않는지 지켜주는 회귀 테스트다.

- [ ] **Step 3: Implement**

`backend/app/ocr.py`의 다음 블록(주석 포함, 현재 57-60번째 줄 근처의 상수 4개):

```python
_PREFIXED_SPEC_PATTERN = re.compile(r"(?<![A-Za-z0-9])(SHD|UHD|SD)(\d{1,2})(?!\d)")
_BARE_GRADE_PATTERN = re.compile(r"(?<![A-Za-z0-9])SD([456]00)(?!\d)")
_DIAMETER_PATTERN = re.compile(r"(?<![A-Za-z0-9])D(\d{1,2})(?!\d)")
_HANGUL_PATTERN = re.compile(r"[가-힣]")
```

를 다음으로 교체한다:

```python
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
```

(`_BARE_GRADE_PATTERN`은 강도 코드가 원래도 고정 3자리라 뒤쪽 `(?!\d)` 경계는 그대로 유지한다 — "SD6001"처럼 4자리면 오매칭 방지용으로 여전히 유효하다. 앞쪽 lookbehind만 나머지 두 패턴과 동일하게 완화한다.)

`_fallback_tag_grade_diameter` 함수 전체를 다음으로 교체한다:

```python
def _fallback_tag_grade_diameter(text: str) -> tuple[str, str]:
    upper_text = text.upper()
    prefixed_match = _PREFIXED_SPEC_PATTERN.search(upper_text)
    if prefixed_match:
        matched_text = prefixed_match.group(0)
        tail = upper_text[prefixed_match.end() : prefixed_match.end() + 2]
        # "SD6"는 유일하게 "SD600"(강도 단독 표기)의 앞부분과 겹친다(직경
        # 값 중 두 자리가 아닌 건 "6"뿐이고, 강도 코드 중에도 "6"으로
        # 시작하는 "600"이 있어서). 바로 뒤에 "00"이 이어지면 직경이 아니라
        # 강도 단독 표기로 보고 아래 bare-grade 패턴으로 넘긴다.
        if not (matched_text == "SD6" and tail == "00"):
            grade, diameter = spec_grade.parse_spec_grade_diameter(matched_text)
            if grade and diameter:
                return grade, diameter
    bare_match = _BARE_GRADE_PATTERN.search(upper_text)
    diameter_match = _DIAMETER_PATTERN.search(upper_text)
    grade = f"SD{bare_match.group(1)}" if bare_match else ""
    diameter = diameter_match.group(1) if diameter_match else ""
    return grade, diameter
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_ocr.py -v`
Expected: PASS (전체 통과 — 기존 케이스 전부 + 신규 4개)

- [ ] **Step 5: Commit**

```bash
git add backend/app/ocr.py backend/tests/test_ocr.py
git commit -m "fix: 표 셀이 공백 없이 붙어도 강도/직경 정규식 폴백이 인식하도록 수정"
```

---

### Task 2: `spec_grade.py` 확장 — 별칭 + 복수 후보 매칭 (원인 B, D)

**Files:**
- Modify: `backend/app/spec_grade.py`
- Test: `backend/tests/test_spec_grade.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `spec_grade.MANUFACTURER_ALIASES: dict[str, str]` — 별칭(영문/한글 축약) → 정식명칭
  - `spec_grade.normalize_manufacturers(value: str | None) -> list[str]` — 텍스트에 등장하는 모든 제조사 후보(정식명칭 리스트, 중복 없음)
  - `spec_grade.normalize_manufacturer(value: str | None) -> str | None` — 대표값 하나(기존 시그니처 유지, `normalize_manufacturers`의 첫 값)
  - `spec_grade.match_manufacturer(tag_manufacturer: str | None, note: str | None) -> str | None` — 후보 중 하나라도 `note`와 일치하면 `"matched"` (기존 시그니처 유지)

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_spec_grade.py` 맨 위 import를 바꾸고:

```python
from app.spec_grade import (
    match_manufacturer,
    match_tag_to_spec,
    normalize_manufacturer,
    normalize_manufacturers,
    parse_spec_grade_diameter,
)
```

파일 끝에 다음 테스트를 추가한다:

```python
def test_normalize_manufacturers_returns_multiple_candidates():
    # "현대"는 "현대제철"의 실제 택에서 확인된 축약 표기다.
    assert normalize_manufacturers("동국제강,현대") == ["동국제강", "현대제철"]


def test_normalize_manufacturers_returns_multiple_codes_comma_separated():
    # LLM이 "코드나 정식명칭을 콤마로 구분해서" 답할 때의 형태.
    assert normalize_manufacturers("DK,HS") == ["동국제강", "현대제철"]
    assert normalize_manufacturers("DK, HS") == ["동국제강", "현대제철"]


def test_normalize_manufacturers_single_code_returns_one_item_list():
    assert normalize_manufacturers("HS") == ["현대제철"]


def test_normalize_manufacturers_recognizes_korean_abbreviation():
    assert normalize_manufacturers("현대") == ["현대제철"]


def test_normalize_manufacturers_recognizes_english_alias():
    assert normalize_manufacturers("DONGKUK STEEL MILL CO., LTD.") == ["동국제강"]
    assert normalize_manufacturers("STEEL MADE IN KOREA HYUNDAI 인천공장") == ["현대제철"]


def test_normalize_manufacturers_does_not_split_english_corporate_suffix_comma():
    # "CO., LTD."의 콤마 때문에 문자열을 분리하면 안 된다 — 분리했다면
    # "LTD." 쪽 토큰만 남아 DONGKUK을 못 찾았을 것이다.
    assert normalize_manufacturers("DONGKUK STEEL MILL CO., LTD.") == ["동국제강"]


def test_normalize_manufacturers_outside_pool_returns_empty_list():
    assert normalize_manufacturers("알수없는업체") == []


def test_normalize_manufacturers_empty_or_none_returns_empty_list():
    assert normalize_manufacturers("") == []
    assert normalize_manufacturers(None) == []


def test_normalize_manufacturers_still_rejects_generic_substring():
    # 기존에 고친 "제강"/"철강" 오판정 방지가 별칭 로직 추가로 깨지지 않아야 한다.
    assert normalize_manufacturers("제강") == []
    assert normalize_manufacturers("철강") == []


def test_normalize_manufacturer_single_value_unchanged():
    assert normalize_manufacturer("HS") == "현대제철"
    assert normalize_manufacturer("현대") == "현대제철"
    assert normalize_manufacturer("알수없는업체") is None


def test_match_manufacturer_matches_when_note_equals_any_candidate():
    assert match_manufacturer("동국제강,현대", "현대제철") == "matched"
    assert match_manufacturer("동국제강,현대", "동국제강") == "matched"


def test_match_manufacturer_mismatched_when_note_matches_none_of_candidates():
    assert match_manufacturer("동국제강,현대", "대한제강") == "mismatched"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_spec_grade.py -v`
Expected: FAIL with `ImportError: cannot import name 'normalize_manufacturers' from 'app.spec_grade'` — 아직 정의되지 않았다.

- [ ] **Step 3: Implement**

`backend/app/spec_grade.py`에서 기존 `normalize_manufacturer`/`match_manufacturer` 함수(현재 `_CORPORATE_MARKERS_PATTERN` 정의 다음, `MANUFACTURER_POOL` 정의 다음에 있는 부분) 전체를 다음으로 교체한다:

```python
# 실제 택에서 확인된 표기만 등록한다 — "현대"는 "현대제철"의 흔한 줄임
# 표기(택에 "(동국제강,현대)"처럼 나옴), DONGKUK/HYUNDAI는 영문 표기.
# 아직 확인 안 된 나머지 5개 업체(대한제강/한국철강/환영철강/YK스틸/
# 한국제강)의 축약형·영문 표기는 실제 택을 받는 대로 추가한다. "제강"/
# "철강"처럼 여러 업체에 공통되는 일반 명사는 절대 등록하지 않는다 — 그러면
# 어느 업체인지 특정할 수 없는데도 사전 순서상 먼저 오는 업체로 오판정된다.
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

    두 단계로 찾는다:
    1) 콤마로 나눈 각 토큰이 "코드" 또는 "법인 표기 제거 후 완전한
       코드"인 경우(LLM이 "DK,HS"처럼 깔끔하게 답한 경우를 위해).
    2) 원문 전체(콤마로 나누지 않음)에서 정식명칭/별칭이 부분 문자열로
       등장하는지 확인("동국제강(부산공장)"처럼 부가정보가 붙은 경우,
       "현대"처럼 라벨 없이 붙은 축약형을 위해). 여기서 콤마로 나누지
       않는 이유는 영문 법인 표기("CO., LTD.")의 콤마와 충돌하기
       때문이다 — 나누면 "LTD." 쪽 토큰만 남아 앞부분을 놓친다."""
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
    """원문 표기(코드 또는 정식명칭, 법인 표기 포함)를 MANUFACTURER_POOL의
    정식명칭 하나(대표값)로 정규화한다. 여러 업체가 함께 표기된 경우는
    normalize_manufacturers를 쓸 것. 풀의 7개 중 어디에도 매칭되지 않으면
    None(인식 실패로 간주 — 강종/직경의 표준 목록 검증과 동일한 원칙)."""
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

(`_CORPORATE_MARKERS_PATTERN`, `MANUFACTURER_POOL` 정의는 그대로 둔다.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_spec_grade.py -v`
Expected: PASS (전체 통과)

- [ ] **Step 5: Commit**

```bash
git add backend/app/spec_grade.py backend/tests/test_spec_grade.py
git commit -m "feat: 제조사 별칭(영문/축약) 및 복수 후보 매칭 지원"
```

---

### Task 3: `ocr.py` 제조사 저장 포맷 변경 (원인 B, D 반영)

**Files:**
- Modify: `backend/app/ocr.py`
- Test: `backend/tests/test_ocr.py`

**Interfaces:**
- Consumes: Task 2의 `spec_grade.normalize_manufacturers(value: str | None) -> list[str]`
- Produces: `ocr.normalize_tag_fields(...)["tag_manufacturer"]`가 이제 **콤마로 구분된 모든 인식 후보**를 담을 수 있다(기존엔 대표값 하나만 저장). 후보가 없으면 여전히 빈 문자열.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_ocr.py` 파일 끝에 추가:

```python
def test_normalize_tag_fields_manufacturer_stores_all_candidates_as_comma_joined():
    text = "직경: 13\n강도: SD500\n제조사: 동국제강,현대\n"
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_manufacturer"] == "동국제강,현대제철"


def test_normalize_tag_fields_manufacturer_recognizes_korean_abbreviation_label():
    text = "직경: 13\n강도: SD500\n제조사: 현대\n"
    fields = ocr.normalize_tag_fields(text)
    assert fields["tag_manufacturer"] == "현대제철"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_ocr.py -v -k manufacturer_stores_all_candidates`
Expected: FAIL — 현재 `normalize_tag_fields`는 `spec_grade.normalize_manufacturer`(단일값)만 저장하므로, `"동국제강,현대"`에서 제조사 후보를 하나만(또는 매칭 순서에 따라 다르게) 저장하고 `"동국제강,현대제철"`처럼 둘 다 콤마로 합쳐 반환하지 않는다.

- [ ] **Step 3: Implement**

`backend/app/ocr.py`의 `normalize_tag_fields` 함수 안, 다음 줄:

```python
    result["tag_manufacturer"] = spec_grade.normalize_manufacturer(result["tag_manufacturer"]) or ""
```

를 다음으로 교체한다:

```python
    result["tag_manufacturer"] = ",".join(spec_grade.normalize_manufacturers(result["tag_manufacturer"]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_ocr.py -v`
Expected: PASS (전체 통과)

- [ ] **Step 5: Commit**

```bash
git add backend/app/ocr.py backend/tests/test_ocr.py
git commit -m "feat: 라벨 매칭 제조사 인식이 복수 후보를 모두 저장하도록 변경"
```

---

### Task 4: `llm_tag_fallback.py` 프롬프트/검증 변경 (원인 B, D 반영)

**Files:**
- Modify: `backend/app/llm_tag_fallback.py`
- Test: `backend/tests/test_llm_tag_fallback.py`

**Interfaces:**
- Consumes: Task 2의 `spec_grade.normalize_manufacturers(value: str | None) -> list[str]`
- Produces: `llm_tag_fallback.extract_tag_fields(...)`가 반환하는 3번째 값(`manufacturer`)이 이제 콤마로 구분된 복수 후보를 담을 수 있다(시그니처 변경 없음, 여전히 `tuple[str, str, str]`).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_llm_tag_fallback.py` 파일 끝에 추가:

```python
def test_extract_tag_fields_returns_multiple_manufacturer_candidates(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response(
            '{"grade": "SD500", "diameter": "13", "manufacturer": "DK,HS"}'
        )
        _, _, manufacturer = llm_tag_fallback.extract_tag_fields(b"fake-bytes", "tag.jpg")
    assert manufacturer == "동국제강,현대제철"


def test_extract_tag_fields_accepts_korean_abbreviation_manufacturer(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    with patch("app.llm_tag_fallback.requests.post") as mock_post:
        mock_post.return_value = _mock_response(
            '{"grade": "SD500", "diameter": "13", "manufacturer": "현대"}'
        )
        _, _, manufacturer = llm_tag_fallback.extract_tag_fields(b"fake-bytes", "tag.jpg")
    assert manufacturer == "현대제철"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_llm_tag_fallback.py -v -k "multiple_manufacturer_candidates or korean_abbreviation"`
Expected: FAIL — 현재 `_valid_manufacturer`는 `spec_grade.normalize_manufacturer`(단일값)만 써서 `"DK,HS"` 같은 복수 응답을 하나로도 제대로 못 살리고, `"현대"` 같은 축약형도 아직 `spec_grade.py`가 인식하지 못한다(Task 2에서 이미 고쳤다면 이 두 번째 부분은 통과할 수 있음 — 그래도 복수 후보 테스트는 여전히 실패한다).

- [ ] **Step 3: Implement**

`_PROMPT`를 다음으로 교체한다:

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

`_valid_manufacturer` 함수를 다음으로 교체한다:

```python
def _valid_manufacturer(value) -> str:
    if not isinstance(value, str):
        return ""
    return ",".join(spec_grade.normalize_manufacturers(value))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_llm_tag_fallback.py -v`
Expected: PASS (전체 통과)

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm_tag_fallback.py backend/tests/test_llm_tag_fallback.py
git commit -m "feat: Claude 비전 폴백이 복수 제조사 후보를 모두 인식하도록 변경"
```

---

### Task 5: 프론트엔드 — 택 카드 단순화 및 제조사 매칭 로직 갱신

**Files:**
- Modify: `frontend/src/pages/EditPage.jsx`

**Interfaces:**
- Consumes: `/ocr/tag` 응답의 `tag_manufacturer` 필드(Task 3, 4 — 이제 콤마 구분 복수 후보일 수 있음)
- Produces: 없음(최종 UI 계층)

이 프로젝트의 프론트엔드는 자동 테스트가 없으므로(기존 패턴), 이 태스크는 TDD 대신 구현 후 빌드 확인으로 검증한다.

- [ ] **Step 1: 제조사 별칭 테이블 + 복수 후보 인식 함수로 교체**

`frontend/src/pages/EditPage.jsx`의 다음 블록:

```js
// backend app/spec_grade.py의 MANUFACTURER_POOL과 동일하게 유지할 것.
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

// backend app/spec_grade.py의 normalize_manufacturer와 동일한 로직을 프런트에서도
// 재계산할 수 있도록 이식한 헬퍼.
function normalizeManufacturer(value) {
  if (!value) return null
  const stripped = value.trim()
  const code = stripped.toUpperCase()
  if (MANUFACTURER_POOL[code]) return MANUFACTURER_POOL[code]
  const cleaned = stripped.replace(CORPORATE_MARKERS_PATTERN, '')
  if (!cleaned) return null
  // "제강"/"철강"처럼 여러 풀 항목에 공통으로 들어있는 일반 명사 조각만으로
  // 특정 업체로 오판정되지 않도록, cleaned가 정식명칭에 포함되는 방향만
  // 허용한다(정식명칭이 cleaned에 포함되는 방향만 — 반대 방향은 금지).
  const found = Object.values(MANUFACTURER_POOL).find((name) => cleaned.includes(name))
  return found || null
}

function matchManufacturer(tagManufacturer, note) {
  const normTag = normalizeManufacturer(tagManufacturer)
  const normNote = normalizeManufacturer(note)
  if (normTag === null || normNote === null) return null
  return normTag === normNote ? 'matched' : 'mismatched'
}

// 배너 표시용 — 저장되는 tag_manufacturer는 정식명칭이지만, 적합 배너에는
// 코드로 표기하기 위한 정식명칭 → 코드 역변환 테이블.
const CODE_BY_MANUFACTURER = Object.fromEntries(
  Object.entries(MANUFACTURER_POOL).map(([code, name]) => [name, code]),
)
```

를 다음으로 교체한다:

```js
// backend app/spec_grade.py의 MANUFACTURER_POOL과 동일하게 유지할 것.
const MANUFACTURER_POOL = {
  HS: '현대제철',
  DK: '동국제강',
  DH: '대한제강',
  HK: '한국철강',
  HY: '환영철강',
  YK: 'YK스틸',
  HJ: '한국제강',
}
// backend app/spec_grade.py의 MANUFACTURER_ALIASES와 동일하게 유지할 것.
const MANUFACTURER_ALIASES = {
  현대: '현대제철',
  DONGKUK: '동국제강',
  HYUNDAI: '현대제철',
}
const CORPORATE_MARKERS_PATTERN = /\(주\)|㈜|주식회사|\s+/g

// backend app/spec_grade.py의 normalize_manufacturers와 동일한 로직을 프런트에서도
// 재계산할 수 있도록 이식한 헬퍼. "동국제강,현대"처럼 후보가 여러 곳 함께
// 표기된 택을 위해 배열을 반환한다. 두 단계로 찾는다: ① 콤마로 나눈 각
// 토큰이 코드(또는 법인 표기 제거 후 코드)인 경우 먼저 인정 — LLM이
// "DK,HS"처럼 답한 경우를 위해. ② 원문 전체(콤마로 나누지 않음)에서
// 정식명칭/별칭이 부분 문자열로 등장하는지 확인 — 영문 법인 표기
// ("CO., LTD.")의 콤마와 충돌하지 않도록 분리하지 않는다.
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

// 배너 표시용 — 저장되는 tag_manufacturer는 정식명칭이지만, 적합 배너에는
// 코드로 표기하기 위한 정식명칭 → 코드 역변환 테이블.
const CODE_BY_MANUFACTURER = Object.fromEntries(
  Object.entries(MANUFACTURER_POOL).map(([code, name]) => [name, code]),
)
```

- [ ] **Step 2: `isTagVerifiedAgainstInvoice` 판정 함수 추가**

`CODE_BY_MANUFACTURER` 정의 바로 다음(기존 `matchTagsToItems` 함수 앞)에 추가:

```js
// 택의 강도+직경+제조사가 송장 내 자재(품목) 중 하나라도 전부 일치하는지
// 판정한다. matchTagToSpec/matchManufacturer 둘 다 인식 실패(빈 값) 시
// null을 반환하므로, 'matched' 비교로 인식 안 된 경우도 자동으로
// 부적합 처리된다.
function isTagVerifiedAgainstInvoice(tagResult, items) {
  return items.some(
    (item) =>
      matchTagToSpec(tagResult.tag_grade, tagResult.tag_diameter, item.spec) === 'matched' &&
      matchManufacturer(tagResult.tag_manufacturer, item.note) === 'matched',
  )
}
```

- [ ] **Step 3: 택 카드 렌더링을 입력 필드 3개 + 기존 배너에서 단순 적합/부적합 배너로 교체**

`frontend/src/pages/EditPage.jsx`에서 다음 블록:

```jsx
              {result === 'loading' && <p>인식 중...</p>}
              {result === 'error' && <p className="banner banner-error">인식에 실패했습니다. 강도/직경을 직접 입력해주세요.</p>}
              {result && result !== 'loading' && result !== 'error' && (
                <>
                  {(!result.tag_grade || !result.tag_diameter) && (
                    <p className="banner banner-warning">강도/직경을 읽지 못했습니다 — 직접 입력해주세요.</p>
                  )}
                  <div className="field">
                    <label>강도 (자동 인식, 다르면 직접 수정)</label>
                    <input
                      className="input"
                      type="text"
                      value={result.tag_grade || ''}
                      onChange={(e) => handleTagFieldEdit(file, 'tag_grade', e.target.value)}
                      placeholder="예: SD400, SD500, SD600"
                    />
                  </div>
                  <div className="field">
                    <label>직경 (자동 인식, 다르면 직접 수정)</label>
                    <input
                      className="input"
                      type="text"
                      value={result.tag_diameter || ''}
                      onChange={(e) => handleTagFieldEdit(file, 'tag_diameter', e.target.value)}
                      placeholder="예: 10, 13, 16"
                    />
                  </div>
                  <div className="field">
                    <label>제조사 (자동 인식, 다르면 직접 수정)</label>
                    <input
                      className="input"
                      type="text"
                      value={result.tag_manufacturer || ''}
                      onChange={(e) => handleTagFieldEdit(file, 'tag_manufacturer', e.target.value)}
                      placeholder="예: 현대제철, DK, 동국제강"
                    />
                  </div>
                  {result.tag_grade &&
                    result.tag_diameter &&
                    (items.some((item) => matchTagToSpec(result.tag_grade, result.tag_diameter, item.spec) === 'matched') ? (
                      <p className="banner banner-success">이 규격은 송장에 포함되어 있습니다 — 이상 없습니다.</p>
                    ) : (
                      <p className="banner banner-warning">이 규격은 이 송장의 규격 어디에도 없습니다.</p>
                    ))}
                </>
              )}
```

를 다음으로 교체한다:

```jsx
              {result === 'loading' && <p>인식 중...</p>}
              {result === 'error' && <p className="banner banner-error">인식에 실패했습니다.</p>}
              {result && result !== 'loading' && result !== 'error' &&
                (isTagVerifiedAgainstInvoice(result, items) ? (
                  <p className="banner banner-success">적합</p>
                ) : (
                  <p className="banner banner-warning">부적합</p>
                ))}
```

- [ ] **Step 4: `handleTagFieldEdit` 함수 제거**

`handleTagFieldEdit` 함수(현재 다음 코드)를 삭제한다 — Step 3에서 없앤 입력 필드 3개가 유일한 호출처였고, 다른 곳에서 쓰이지 않는다:

```js
  // OCR이 강도/직경을 잘못 읽었거나 못 읽었을 때 사용자가 직접 고칠 수 있게 한다.
  function handleTagFieldEdit(file, key, value) {
    setTagResultsByFile((prev) => {
      const current = prev.get(file)
      if (!current || current === 'loading' || current === 'error') return prev
      return new Map(prev).set(file, { ...current, [key]: value })
    })
  }
```

- [ ] **Step 5: 빌드 확인**

Run: `cd frontend && npm run build`
Expected: 에러 없이 빌드 성공 (`dist/` 생성). `handleTagFieldEdit` 제거 후 미사용 함수/미사용 import가 남지 않았는지도 이 빌드로 확인된다.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/EditPage.jsx
git commit -m "feat: 택 카드를 적합/부적합 단일 판정으로 단순화하고 제조사 별칭·복수 후보 인식 반영"
```

**참고(구현 완료 후 수동 확인 권장):** 개발 서버(`npm run dev`)를 띄워 실제로 택 사진을 촬영/선택했을 때 강도/직경/제조사 입력 필드가 더 이상 보이지 않고, 강도+직경+제조사가 송장 자재 중 하나와 모두 일치하면 "적합", 아니면 "부적합" 배너만 뜨는지 확인한다. 자재 카드 쪽 배정 배너(`"일치하는 철근 Tag을 확인했습니다 : ..."`)와 저장 동작은 기존과 동일하게 유지돼야 한다.

---

## 배포 참고 (구현 범위 밖, 기록용)

이 브랜치는 새 DB 컬럼이나 마이그레이션을 추가하지 않는다 — 기존 `tag_manufacturer` 컬럼(문자열)에 콤마로 구분된 값이 들어갈 뿐이라 스키마 변경이 불필요하다. Render/Vercel 모두 push 후 자동 재배포된다.
