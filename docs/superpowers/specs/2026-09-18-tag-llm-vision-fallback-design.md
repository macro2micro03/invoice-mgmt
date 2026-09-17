# 철근 택 인식 LLM 비전 폴백 — 설계 문서

## 배경

`/ocr/tag`는 Upstage document-parse(+필요시 일반 텍스트 OCR) 결과를 라벨 매칭과 정규식 fallback(`_fallback_tag_grade_diameter`)으로 파싱해 강종(`tag_grade`)·직경(`tag_diameter`)을 추출한다. 현장에서 핸드폰으로 촬영한 택 사진은 제강사마다 항목명(예: "종류의기호" vs "강종")과 레이아웃이 달라, 규칙 기반 파싱이 실패하는 경우가 있다. 이 문서는 규칙 기반 파싱이 실패했을 때만 비전 LLM(Claude)을 폴백으로 호출해 인식률을 높이는 설계를 다룬다.

## 범위

**포함:**
- `/ocr/tag`에서 기존 파싱(라벨 매칭 + 정규식 fallback) 후에도 `tag_grade` 또는 `tag_diameter`가 비어있으면, 택 원본 이미지를 Claude Haiku 4.5(비전)에 전달해 강종/직경만 재추출.
- LLM 응답을 표준 규격 목록으로 검증한 뒤에만 채택.
- `ANTHROPIC_API_KEY` 미설정 시 폴백을 건너뛰고 기존 동작 그대로 유지(선택적 기능).

**범위 밖:**
- 일반 송장(`/ocr`, 갑지 파싱 포함)에는 이번 폴백을 적용하지 않는다.
- 현장명·부재시공위치·길이·수량·가공형상 등 강종/직경 외 택 필드는 LLM 폴백 대상이 아니다(기존 규칙 기반 결과 그대로 사용).
- 기존에 저장된 레코드에 대한 소급 재인식은 다루지 않는다.

## 표준 규격 목록 (검증용)

LLM 응답이 아래 목록을 벗어나면 폴백 실패로 간주하고 해당 필드를 빈 값으로 둔다(할루시네이션 방지).

- 강종: `SD300`, `SD400`, `SD500`, `SD600`
- 직경(mm, 숫자만): `6, 10, 13, 16, 19, 22, 25, 29, 32, 35, 38, 41, 51, 57` (KS D 3504 표준 호칭경)

## 백엔드 변경

### `backend/app/config.py`

```python
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_TAG_FALLBACK_MODEL = "claude-haiku-4-5-20251001"
```

### `backend/app/llm_tag_fallback.py` (신규)

```python
VALID_GRADES = {"SD300", "SD400", "SD500", "SD600"}
VALID_DIAMETERS = {"6", "10", "13", "16", "19", "22", "25", "29", "32", "35", "38", "41", "51", "57"}

def call_claude_vision(image_bytes: bytes, filename: str, media_type: str) -> dict:
    """Anthropic API를 호출해 원시 JSON({"grade":..., "diameter":...} 또는 필드가 null)을 반환.
    호출/파싱 실패 시 예외를 던지지 않고 {} 반환."""
    ...

def extract_tag_grade_diameter(image_bytes: bytes, filename: str, media_type: str = "image/jpeg") -> tuple[str, str]:
    """call_claude_vision 결과를 VALID_GRADES/VALID_DIAMETERS로 검증해
    (grade, diameter)를 반환. 검증 실패한 필드는 빈 문자열."""
    ...
```

- 프롬프트: "이 사진은 철근 택(꼬리표) 사진입니다. 택에 표시된 철근의 강종과 직경만 다른 설명 없이 JSON으로 답하세요: `{"grade": "SD500 또는 null", "diameter": "13처럼 숫자만, 또는 null"}`. 확신이 없으면 null로 답하세요."
- `max_tokens`는 작게(예: 100) 설정.
- Anthropic 클라이언트 호출 실패(네트워크/인증/레이트리밋), JSON 파싱 실패는 모두 `call_claude_vision` 내부에서 잡아 로그(`logger.exception`/`logger.warning`)만 남기고 `{}` 반환.
- `extract_tag_grade_diameter`는 `{}` 또는 목록 밖 값에 대해 해당 필드를 빈 문자열로 채우고, 목록 밖 값이 왔을 때는 원래 값과 함께 경고 로그를 남긴다(`"LLM이 표준 목록 밖의 값을 반환함: grade=%r diameter=%r"`).

### `backend/app/routers/ocr.py` — `run_tag_ocr` 확장

기존 흐름(Upstage OCR → `normalize_tag_fields` → 정규식 fallback) 이후:

```python
if (not fields["tag_grade"] or not fields["tag_diameter"]) and config.ANTHROPIC_API_KEY:
    llm_grade, llm_diameter = llm_tag_fallback.extract_tag_grade_diameter(
        image_bytes, file.filename or "tag.jpg"
    )
    if not fields["tag_grade"] and llm_grade:
        fields["tag_grade"] = llm_grade
    if not fields["tag_diameter"] and llm_diameter:
        fields["tag_diameter"] = llm_diameter
```

- 이미 값이 있는 필드는 LLM 결과로 덮어쓰지 않는다.
- `tag_match_status` 계산은 기존 로직(필드 채움 이후 `spec_grade.match_tag_to_spec` 호출)을 그대로 재사용하므로 변경 없음.

### `backend/requirements.txt`

`anthropic` SDK 버전을 고정해 추가.

## 데이터 흐름

```
택 사진 업로드
  → Upstage document-parse (표/라벨 인식)
      → 요소 0개면 Upstage 일반 텍스트 OCR로 재시도
  → normalize_tag_fields (라벨 매칭) + 정규식 fallback (SD/SHD/UHD 패턴)
  → tag_grade 또는 tag_diameter 비어있음 AND ANTHROPIC_API_KEY 설정됨?
        → Claude Haiku 4.5에 원본 이미지 전달 → JSON 응답 파싱
        → VALID_GRADES/VALID_DIAMETERS로 검증된 값만 빈 필드에 채움
  → spec_grade.match_tag_to_spec으로 송장 규격과 대조 → tag_match_status
```

## 에러 처리

| 상황 | 동작 |
|---|---|
| `ANTHROPIC_API_KEY` 미설정 | 폴백 자체를 건너뜀. 기존 동작과 동일. |
| Anthropic API 호출 실패(네트워크/인증/레이트리밋) | 로그 남기고 `{}` 반환 → 해당 필드 빈 값 유지. |
| 응답이 JSON으로 파싱 안 됨 | 로그 남기고 `{}` 반환 → 해당 필드 빈 값 유지. |
| 응답 값이 표준 목록 밖 | 경고 로그 남기고 해당 필드만 무시(다른 필드는 유효하면 채택). |

모든 실패 경로는 현재의 "인식 실패 시 빈 필드" 동작으로 자연스럽게 저하(degrade)되며, 엔드포인트 응답 형식(`{**fields, "tag_match_status": ...}`)은 변경되지 않는다.

## 테스트 전략

- `backend/tests/test_llm_tag_fallback.py` (신규):
  - 정상 응답(`{"grade": "SD500", "diameter": "13"}`) → 그대로 반환
  - 표준 목록 밖 값(예: `grade: "SD999"`) → 해당 필드 빈 문자열
  - Anthropic 클라이언트 예외 발생 → `("", "")` 반환, 예외가 밖으로 전파되지 않음
  - JSON이 아닌 응답(자유 텍스트) → `("", "")` 반환
- `backend/tests/test_ocr_endpoint.py` 확장:
  - 정규식 파싱 실패(`tag_grade`/`tag_diameter` 둘 다 빈 값) + `ANTHROPIC_API_KEY` 설정 시 `llm_tag_fallback.extract_tag_grade_diameter`가 호출되어 값을 채우는지
  - 정규식 파싱이 이미 성공하면 LLM 폴백이 호출되지 않는지(`fail_if_called` 패턴 재사용)
  - `ANTHROPIC_API_KEY` 미설정 시 정규식 실패해도 폴백이 호출되지 않고 빈 필드로 남는지

## 자체 점검

- 적용 범위를 `/ocr/tag`로 한정하고 일반 송장(`/ocr`)은 건드리지 않음 — 확인됨.
- LLM 호출은 규칙 기반 파싱 실패 시에만 트리거되어 비용을 최소화하는 하이브리드 구조 — 확인됨.
- 할루시네이션 방지를 위해 표준 규격 목록 검증을 거치도록 설계됨 — 확인됨.
- 모든 실패 경로(키 미설정/API 오류/파싱 실패/목록 밖 값)가 예외 없이 기존 "빈 필드" 동작으로 저하됨 — 확인됨.
- 이미 인식된 필드는 LLM 결과로 덮어쓰지 않음 — 확인됨.
