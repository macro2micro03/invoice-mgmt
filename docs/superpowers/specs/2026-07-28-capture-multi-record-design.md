# 촬영 탭 갑지(표 형식) 다중 레코드 생성 — 설계 문서

## 배경

촬영 탭(`/`)은 "사진 1장 = 송장 레코드 1개"를 전제로 설계되어 있다. `backend/app/ocr.py`의 `normalize_fields()`는 OCR 텍스트를 줄 단위로 훑으며 `단위`, `중량`, `비고` 같은 라벨 뒤의 텍스트를 정규식 `(.+)`로 **그 줄 끝까지** 통째로 캡처한다.

실제로 현장에서 촬영하는 문서는 "보고서 생성" 기능이 파싱하는 것과 **동일한 "송장별 총괄 내역서" 갑지 표 양식**이다. 이 문서는:
- 자재 규격(SHD10/SHD13/UHD16 등) 여러 개가 표 하나에 함께 들어있다 (사진 1장에 자재 정보가 여러 건).
- 표 헤더에 "단위중량(kg/m)"이라는 문구가 있어, "단위"라는 라벨만 찾는 기존 로직이 그 줄 전체(단위중량+발송중량+할증중량+비고 값까지)를 "단위" 필드 값으로 잘못 캡처한다.

이 문서 형식을 촬영했을 때 사용자가 승인한 처리 방식은: **사진 1장 → 자재 규격별로 레코드를 여러 개 생성**, 거래처/납품일/차량번호/송장번호는 공통값으로 모든 레코드에 채우고, 규격/중량은 레코드마다 다르게 채운다.

## 범위

**변경 대상:**
- `backend/app/report_parser.py` — 차량번호/송장번호 추출 함수, 촬영용 다중 레코드 빌더 추가
- `backend/app/routers/ocr.py` — 갑지 감지 시 다중 레코드 반환, 아니면 기존 단일 레코드 방식 유지
- `frontend/src/pages/CapturePage.jsx` — OCR 응답이 레코드 배열임을 반영
- `frontend/src/pages/EditPage.jsx` — 공통 정보 영역 + 자재별 카드 여러 개로 재구성, 카드별 삭제, 저장 시 레코드 수만�큼 DB 생성
- `frontend/src/styles.css` — 카드 그룹 라벨/삭제 버튼 스타일 추가

**범위 밖:**
- `backend/app/ocr.py`의 `normalize_fields()`(자유 양식 문서용 기존 로직)는 그대로 유지 — 갑지가 아닌 문서는 기존 방식으로 계속 동작
- 자재종류 자동 추론 고도화 — 이번 문서 특성상 규격이 전부 철근 규격(SHD/UHD)이므로 기본값 "철근"으로 채우고, 다른 자재라면 사용자가 직접 수정
- "수량"(개수/미터 등) 자동 채움 — 이 문서 형식에는 수량 컬럼 자체가 없으므로 공란으로 두고 사용자가 필요 시 입력

## 백엔드 변경

### `report_parser.py`에 신규 함수 2개 추가

기존 `find_delivery_date`와 동일한 패턴(정보표 행을 훑어 라벨로 시작하는 행을 찾고, 그 행 전체에서 정규식으로 값을 추출)을 그대로 따른다.

```python
VEHICLE_NO_PATTERN = re.compile(r"[가-힣]{0,3}\d{2,3}[가-힣]\d{4}")
INVOICE_NO_PATTERN = re.compile(r"\d{8}-\d{3}")


def find_vehicle_no(raw_response: dict, page: int) -> str:
    # find_delivery_date와 동일한 방식: "차량번호"로 시작하는 행에서 정규식 매치
    ...


def find_invoice_no(raw_response: dict, page: int) -> str:
    # "송장번호"로 시작하는 행에서 정규식 매치
    ...
```

실제 예시 문서 기준 검증:
- `차 량 번 호 : 서울85바3204 안영일 010-3664-8672` → `VEHICLE_NO_PATTERN`이 "서울85바3204" 매치
- `송 장 번 호 : 20260420-024 ( 114 회차 )` → `INVOICE_NO_PATTERN`이 "20260420-024" 매치

### `build_capture_records()` 신규 함수

```python
def build_capture_records(raw_response: dict, material_type: str = "철근") -> list[dict]:
```

- 갑지 페이지마다 `extract_material_rows()`로 규격별 행을 가져오고, 페이지 공통값(`find_vendor_heading`, `find_delivery_date`, `find_vehicle_no`, `find_invoice_no`)을 모든 레코드에 동일하게 채운다.
- 반환 형식은 `InvoiceCreate` 스키마와 1:1 대응하는 dict 리스트: `material_type`, `vendor`, `delivery_date`, `vehicle_no`, `invoice_no`, `item_name`(=material_type), `spec`, `unit`(빈 문자열), `quantity`(None), `weight`(=weight_kg), `note`
- 갑지를 못 찾거나 표 파싱에 실패하면 빈 리스트 반환

## `routers/ocr.py` 변경

```python
@router.post("/ocr")
async def run_ocr(file: UploadFile = File(...)):
    image_bytes = await file.read()
    try:
        raw_response = ocr.call_upstage_ocr(image_bytes, filename=file.filename or "invoice.jpg")
    except Exception:
        return {"records": [{field: "" for field in ocr.STANDARD_FIELDS}]}

    if report_parser.find_cover_pages(raw_response):
        records = report_parser.build_capture_records(raw_response)
        if records:
            return {"records": records}

    text = ocr.extract_text(raw_response)
    return {"records": [ocr.normalize_fields(text)]}
```

**API 응답 형식이 바뀐다**: 기존 `{자재종류: "", ...}` 평평한 dict → `{"records": [...]}` 배열 래핑. 프론트엔드도 함께 수정한다(하위 호환 유지 안 함 — 프론트/백엔드를 같이 배포하므로 문제 없음).

## 프론트엔드 변경

### `CapturePage.jsx`

`runOcr(file)`의 반환값에서 `records` 배열을 꺼내 `/edit`으로 그대로 전달한다. 실패 시에도 빈 값 1건짜리 배열(`[{}]`)을 전달해 기존처럼 수동 입력이 가능하게 한다.

### `EditPage.jsx` — 전면 재구성

- **공통 정보 카드**: 거래처, 납품일, 차량번호, 송장번호 — 한 번만 입력/수정하며, 저장 시 모든 레코드에 동일하게 적용
- **자재별 카드 (배열)**: 자재종류, 품명, 규격, 단위, 수량, 중량, 비고 — 레코드마다 별도 카드, 카드 우측 상단에 삭제(X) 버튼 (레코드가 1개만 남으면 삭제 버튼 숨김)
- **저장**: 카드 개수만큼 `createInvoice(공통+레코드, photoFile)`를 순차 호출 — 사진은 모든 레코드가 동일 원본 공유
- 저장 버튼 비활성 조건: 저장 중이거나, 카드가 0개이거나, 카드 중 자재종류가 빈 값인 게 있을 때
- 버튼 라벨에 저장될 건수 표시 (`저장 (3건)`)

### `styles.css` 추가 클래스

`.field-group-label`(카드 그룹 제목), `.item-card`(자재별 카드 간격), `.item-card-header`(제목+삭제 버튼 가로 배치), `.item-remove`(작은 원형 삭제 버튼)

## 테스트 전략

- `report_parser.py`: `find_vehicle_no`/`find_invoice_no`에 대한 단위 테스트(실제 예시 형식 기반 합성 데이터, 못 찾는 경우 빈 문자열), `build_capture_records`가 자재 규격 수만큼 레코드를 만들고 공통 필드가 모든 레코드에 동일하게 채워지는지 검증
- `routers/ocr.py`: 갑지 문서 업로드 시 `{"records": [...]}`(여러 건)를 반환하는지, 자유 양식 문서(갑지 아님)는 기존처럼 `{"records": [단일 dict]}`를 반환하는지 통합 테스트
- 프론트엔드는 이 세션의 다른 순수 UI 변경과 동일하게 자동 테스트 없이 `npm run build` + 실제 브라우저 프리뷰로 확인

## 자체 점검

- 자유 양식 문서의 기존 동작(`normalize_fields`)이 전혀 바뀌지 않음을 명시 — 확인됨
- API 응답 형식 변경이 프론트/백엔드 양쪽에 명시되어 누락 없음 — 확인됨
- 실제 첨부 문서 예시로 정규식 패턴 검증(차량번호/송장번호) — 확인됨
- 범위 밖 항목(자재종류 고도화, 수량 자동 채움)이 명확히 배제됨 — 확인됨
