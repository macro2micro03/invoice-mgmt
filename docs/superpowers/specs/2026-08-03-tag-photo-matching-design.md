# 철근 택(tag) 촬영·대조 기능 — 설계 문서

## 배경

현재 앱은 운반자가 제출한 송장(갑지)을 촬영해 자재 정보를 저장하는 기능만 있다. 실제 현장 검수 절차는 여기에 더해, 철근다발에 붙어있는 "택"(제조사가 부착하는 꼬리표)을 촬영해 그 정보가 송장 내용과 일치하는지 확인하는 단계를 포함한다. 이 기능은 그 검수 단계를 앱에 반영한다.

## 범위

**포함:**
- 송장 촬영 직후, 같은 편집 화면 흐름에서 레코드(규격)별로 택 사진을 촬영.
- 택 사진에서 현장명, 부재시공위치, 철근 직경, 강도, 길이, 수량, 가공형상을 OCR로 인식.
- 택의 직경+강도를 송장 레코드의 규격(예: `SHD13`)에서 파싱한 직경+강도와 비교해 일치여부 판정.
- 불일치 시 경고 배너를 표시하되 저장은 그대로 허용.
- 상세 화면에서도 택 정보와 일치여부를 확인 가능.

**범위 밖:**
- 현장명/부재시공위치/길이/수량/가공형상은 참고용으로만 저장·표시하고, 자동 대조 판정에는 사용하지 않는다(직경+강도만 판정 기준).
- 택 사진이 없는 기존 레코드에 대한 소급 처리는 다루지 않는다.
- SHD/UHD 외의 접두어(예: 일반 HD)에 대한 강도 매핑은 이번 범위에 포함하지 않되, 확장 가능한 구조로 만든다.

## 규격 표기 규칙

송장의 규격 문자열은 `<강도 접두어><직경 숫자>` 형태다 (예: `SHD13`, `UHD16`).

| 접두어 | 강도 |
|---|---|
| SHD | SD500 |
| UHD | SD600 |

직경은 접두어 뒤에 오는 숫자(mm)다. 접두어가 매핑 딕셔너리에 없으면 강도를 판정하지 않고 대조를 건너뛴다(향후 접두어 추가는 딕셔너리 확장만으로 가능하도록 구현).

## 데이터 모델 변경

`backend/app/models.py`의 `Invoice`에 컬럼 추가 (레코드당 택 1장 대응):

- `tag_photo_path: str | None` — 택 사진 저장 경로
- `tag_site_name: str | None` — 택에서 인식한 현장명
- `tag_location: str | None` — 부재시공위치
- `tag_diameter: str | None` — 택에서 인식한 직경(mm)
- `tag_grade: str | None` — 택에서 인식한 강도(예: SD500)
- `tag_length: str | None` — 길이
- `tag_quantity: str | None` — 수량
- `tag_shape: str | None` — 가공형상
- `tag_match_status: str | None` — `matched` / `mismatched` / `null`(택 미촬영 또는 접두어 미지원으로 판정 불가)

`InvoiceOut`/`InvoiceUpdate` 스키마에 위 필드를 반영한다.

## 백엔드 변경

### `backend/app/spec_grade.py` (신규)

```python
GRADE_BY_PREFIX = {
    "SHD": "SD500",
    "UHD": "SD600",
}

def parse_spec_grade_diameter(spec: str) -> tuple[str | None, str | None]:
    """규격 문자열에서 (강도, 직경)을 추출한다. 접두어를 모르면 (None, None)."""
    for prefix, grade in GRADE_BY_PREFIX.items():
        if spec.upper().startswith(prefix):
            diameter = spec[len(prefix):].strip()
            return grade, diameter or None
    return None, None


def match_tag_to_spec(tag_grade: str | None, tag_diameter: str | None, spec: str) -> str | None:
    """택 정보와 규격을 대조한다. 판정 불가 시 None, 아니면 'matched'/'mismatched'."""
    spec_grade, spec_diameter = parse_spec_grade_diameter(spec)
    if spec_grade is None or tag_grade is None or tag_diameter is None:
        return None
    if spec_grade == tag_grade and spec_diameter == tag_diameter:
        return "matched"
    return "mismatched"
```

### `backend/app/routers/ocr.py` (또는 기존 OCR 라우터 확장)

새 엔드포인트 `POST /ocr/tag`:
- 요청: 택 사진 파일 1장(`multipart/form-data`), 선택적으로 대조 대상 규격 문자열(`spec`).
- 처리: 기존 Upstage OCR 클라이언트로 텍스트를 추출하고, 정규식/휴리스틱으로 현장명, 부재시공위치, 직경, 강도, 길이, 수량, 가공형상을 파싱한다.
- `spec`이 함께 전달되면 `match_tag_to_spec`으로 대조해 `tag_match_status`를 함께 반환한다.
- 응답 예:
```json
{
  "site_name": "서소문 재개발",
  "location": "지하 2층 슬라브",
  "diameter": "13",
  "grade": "SD500",
  "length": "12000",
  "quantity": "50",
  "shape": "직선",
  "tag_match_status": "matched"
}
```

### `backend/app/routers/invoices.py`

`PUT /invoices/{id}` 업데이트 바디에 택 관련 필드(`tag_photo_path` 등)를 추가로 받아 저장할 수 있도록 확장한다. 택 사진 파일 자체의 저장은 기존 `report_photos`/사진 저장 로직과 동일한 방식을 재사용한다.

## 프론트엔드 변경

### `frontend/src/pages/EditPage.jsx`

- 각 레코드 카드에 "택 촬영" 버튼 추가 (레코드별로 독립).
- 클릭 시 사진 촬영/선택 → `POST /ocr/tag`에 사진과 해당 레코드의 `spec`을 함께 전송.
- 응답의 택 필드를 레코드 상태에 반영하고, `tag_match_status === 'mismatched'`이면 카드 상단에 경고 배너를 표시한다: `택 규격(${tag_grade} D${tag_diameter})이 송장 규격(${spec})과 다릅니다`.
- 저장 시 택 필드를 포함해 `PUT /invoices/{id}`로 전송한다(저장 자체는 불일치 여부와 무관하게 항상 허용).

### `frontend/src/pages/DetailPage.jsx`

- 택 사진(있는 경우)과 인식된 택 정보, 일치여부 배지(`일치`/`불일치`/`택 미촬영`)를 표시하는 섹션을 추가한다.

### `frontend/src/api.js`

- `runTagOcr(file, spec)` 함수 추가 — `POST /ocr/tag` 호출.
- 기존 `updateInvoice` 호출에 택 필드를 포함하도록 페이로드를 확장한다.

## 테스트 전략

- `backend/tests/test_spec_grade.py`: `parse_spec_grade_diameter`와 `match_tag_to_spec`의 정상/불일치/미지원 접두어 케이스.
- `backend/tests/test_ocr_tag.py` (또는 기존 OCR 테스트 확장): `/ocr/tag` 엔드포인트가 목(mock) OCR 응답을 파싱해 올바른 필드와 `tag_match_status`를 반환하는지.
- `backend/tests/test_invoices_api.py` 확장: 택 필드를 포함한 업데이트가 정상 저장되는지.
- 프론트엔드는 기존 패턴대로 자동 테스트 없이 `npm run build` + 브라우저 프리뷰로 택 촬영·경고 배너 동작을 확인한다.

## 자체 점검

- 직경+강도만 자동 대조 기준으로 사용하고, 나머지 필드는 참고용임을 명시 — 확인됨.
- 불일치 시에도 저장을 막지 않는다는 요구사항이 반영됨 — 확인됨.
- SHD/UHD 외 접두어 확장이 쉬운 구조(딕셔너리 기반)로 설계됨 — 확인됨.
- 레코드별 택 1장 촬영이라는 요구사항이 데이터 모델(레코드당 컬럼)과 UI(레코드 카드별 버튼)에 일관되게 반영됨 — 확인됨.
