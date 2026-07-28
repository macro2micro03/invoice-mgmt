# 촬영 기록 기반 보고서 생성(날짜 선택 방식) — 설계 문서

## 배경

지금까지 "촬영" 탭(개별 송장을 찍어 DB에 레코드로 저장)과 "보고서 생성" 탭(그 자리에서 파일을 올려 OCR로 파싱)은 데이터를 전혀 공유하지 않는 별개의 기능이었다. 사용자가 원하는 실제 업무 흐름은:

1. 자재 반입 시 송장 촬영 (기존 "촬영" 탭)
2. 반입 날짜별로 송장 정보가 DB에 쌓임 (이미 동작 중)
3. **그 쌓인 데이터를 바탕으로 보고서 생성** — 지금은 안 되던 부분

이 문서는 3번을 가능하게 하는 설계다. 기존 "파일 업로드" 방식(OCR로 그 자리에서 파싱)은 그대로 유지하고, "날짜로 생성"이라는 새 방식을 나란히 추가한다.

## 범위

**포함:**
- 자재종류는 이번 기능에서 **"철근"으로 고정**한다 (다른 자재종류 지원은 범위 밖, 나중에 확장 가능한 구조로만 만든다).
- 보고서 생성 탭에 "파일 업로드" / "날짜로 생성" 두 방식 중 선택하는 UI 추가.
- "날짜로 생성" 선택 시: 반입일자(날짜) 하나만 입력받아, DB에서 `material_type="철근"` + 그 날짜에 해당하는 촬영 기록들을 조회해 보고서를 만든다. OCR 호출은 하지 않는다.
- 자재 내역 표의 행은 **규격(spec) + 거래처(vendor) 조합**을 기준으로 구분한다. 같은 조합에 촬영 기록이 여러 건 있으면 중량은 합산하고, 비고(제조사 등 납품회사 정보)는 **쉼표로 나열**한다(예: `동국제강, 한영철강`).

**범위 밖:**
- 사진대지(상단/하단 사진) 자동 연계 — 지금처럼 별도 업로드 유지.
- 철근 외 다른 자재종류 지원.
- 날짜 범위(기간) 선택 — 정확히 하루 단위만 지원.
- 거래처별로 분리된 여러 보고서 생성 — 항상 하나의 보고서로 합쳐서 생성.

## 데이터 집계 규칙

DB에서 조회한 촬영 기록(Invoice)들을 `(spec, vendor)` 조합으로 그룹화한다:

- 같은 조합의 레코드가 여러 개면: `weight`(중량, kg)를 합산하고, 각 레코드의 `note`(비고)를 중복 없이 순서대로 모아 쉼표로 이어붙인다.
- 자재 내역 표의 거래처 칸(F열)에는 기존 관례(`report_parser.build_report_data`의 `f"{vendor}/{manufacturer}"` 패턴)를 그대로 따라 `f"{vendor}/{합쳐진 비고}"` 형태로 표시한다 (비고가 없으면 거래처만).
- 보고서 상단 요약란(H37, 납품회사)에는 이 보고서에 포함된 모든 행의 거래처 표시 문자열을 쉼표로 나열한다.
- 반입일자(H35/H83/H86)는 사용자가 선택한 날짜를 그대로 사용한다.

## 백엔드 변경

### `backend/app/report_excel.py` — 자재 내역 표 거래처 칸을 행별로 채우도록 확장

`fill_material_inspection_form`의 자재 행 채우기 루프에서, 지금은 모든 행에 동일한 `vendor` 파라미터를 채우고 있다:

```python
sheet[f"F{row}"] = vendor
```

이걸 각 `spec_row` 항목이 자신만의 `vendor`를 가질 수 있도록 확장한다(없으면 기존처럼 상위 `vendor` 파라미터로 대체 — 기존 파일 업로드 경로는 항목별 `vendor`를 넣지 않으므로 동작이 전혀 바뀌지 않는다):

```python
sheet[f"F{row}"] = spec_row.get("vendor", vendor)
```

### `backend/app/crud.py` — 자재종류+반입일자로 촬영 기록 조회

```python
def list_invoices_by_material_and_date(db: Session, material_type: str, delivery_date: date) -> list[models.Invoice]:
    return (
        db.query(models.Invoice)
        .filter(models.Invoice.material_type == material_type)
        .filter(models.Invoice.delivery_date == delivery_date)
        .order_by(models.Invoice.id)
        .all()
    )
```

### 신규: `backend/app/report_from_records.py` — DB 레코드를 보고서 데이터로 집계

`report_parser.build_report_data`와 같은 반환 형태(`{"specs": [...], "vendor": ..., "skipped_pages": [], "delivery_date": ...}`)를 만들어, 기존 `report_excel.fill_material_inspection_form` 호출부를 그대로 재사용할 수 있게 한다.

```python
def build_report_data_from_invoices(invoices: list, delivery_date: str) -> dict:
    groups: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []

    for invoice in invoices:
        key = (invoice.spec or "", invoice.vendor or "")
        if key not in groups:
            groups[key] = {"weight_kg": 0.0, "notes": []}
            order.append(key)
        groups[key]["weight_kg"] += invoice.weight or 0.0
        if invoice.note and invoice.note not in groups[key]["notes"]:
            groups[key]["notes"].append(invoice.note)

    specs = []
    vendor_displays = []
    for spec, vendor in order:
        data = groups[(spec, vendor)]
        notes_joined = ", ".join(data["notes"])
        vendor_display = f"{vendor}/{notes_joined}" if vendor and notes_joined else vendor
        specs.append(
            {
                "spec": spec,
                "quantity_ton": round(data["weight_kg"] / 1000, 3),
                "vendor": vendor_display,
            }
        )
        vendor_displays.append(vendor_display)

    return {
        "specs": specs,
        "vendor": ", ".join(dict.fromkeys(v for v in vendor_displays if v)),
        "skipped_pages": [],
        "delivery_date": delivery_date,
    }
```

### `backend/app/routers/reports.py` — 두 방식을 하나의 엔드포인트에서 분기

`POST /reports/material-inspection`에 `delivery_date: Optional[str] = Form(None)`를 추가하고, `files`를 선택 사항(`File(default=[])`)으로 바꾼다:

- `delivery_date`가 주어지면: `crud.list_invoices_by_material_and_date(db, "철근", 날짜)`로 조회 → 비어있으면 400 에러("해당 날짜에 촬영된 철근 기록이 없습니다") → `build_report_data_from_invoices`로 집계 → 이후 `report_excel.fill_material_inspection_form` 호출은 기존과 동일.
- `delivery_date`가 없으면: `files`가 비어있으면 400 에러("파일을 업로드하거나 반입일자를 선택해주세요") → 기존 OCR 기반 흐름 그대로.

## 프론트엔드 변경

`ReportPage.jsx`에 모드 전환(라디오 버튼 또는 탭: "파일 업로드" / "날짜로 생성") 추가:

- **파일 업로드 모드**: 지금과 완전히 동일 (자재종류 입력 가능, 송장 갑지 파일 PhotoPicker 표시).
- **날짜로 생성 모드**: 자재종류 입력란은 "철근"으로 고정(비활성화 표시), 송장 갑지 파일 PhotoPicker는 숨기고 대신 `<input type="date">` 하나만 표시. 사진대지 상단/하단 업로드는 두 모드 모두 동일하게 유지.
- "보고서 생성" 버튼 비활성 조건: 파일 업로드 모드면 지금처럼 `files.length === 0`, 날짜 모드면 날짜가 선택되지 않았을 때.

`api.js`의 `createMaterialInspectionReport`에 선택적 `deliveryDate` 인자를 추가해, 있으면 `delivery_date` 폼 필드로 전송하고 `files`는 전송하지 않는다.

## 테스트 전략

- `build_report_data_from_invoices`: 같은 (규격,거래처) 조합 병합(중량 합산, 비고 쉼표 나열, 거래처 표시 형식) / 다른 거래처는 별도 행 유지 / 상단 요약 거래처 목록 쉼표 나열을 단위 테스트로 검증.
- `routers/reports.py`: `delivery_date`로 요청 시 DB에 미리 만들어둔 촬영 기록들로 올바른 xlsx가 나오는지, 기록이 없으면 400인지, `files`/`delivery_date` 둘 다 없으면 400인지 통합 테스트로 검증. 기존 파일 업로드 경로 테스트는 그대로 통과해야 한다(회귀 없음).
- 프론트엔드는 이 세션의 다른 UI 작업과 동일하게 자동 테스트 없이 `npm run build` + 브라우저 프리뷰로 확인한다.

## 자체 점검

- 기존 파일 업로드 경로(`report_parser.py`, 기존 라우터 로직)는 전혀 수정하지 않고 그대로 재사용 — 확인됨.
- 자재종류 "철근" 고정이 프론트엔드(입력란 비활성화)와 백엔드(DB 쿼리 조건) 양쪽에 명시됨 — 확인됨.
- 행 병합 규칙(규격+거래처 조합, 쉼표 나열)과 상단 요약 거래처 표시 규칙이 구체적인 코드로 명시됨 — 확인됨.
- 범위 밖 항목(사진대지 연계, 다른 자재, 기간 선택, 거래처별 분리)이 명확히 배제됨 — 확인됨.
