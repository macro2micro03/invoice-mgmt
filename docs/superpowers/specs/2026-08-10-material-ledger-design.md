# 검색 항목 → 주요자재 검사 및 수불부 자동 생성 — 설계 문서

## 배경

현장에서 반입 자재를 관리할 때 "주요자재 검사 및 수불부"라는 엑셀 장부를 별도로 수기 작성하고 있다. 이 앱에는 이미 검색 화면에서 송장 기록을 여러 건 선택해 "자재검수요청서"를 생성하는 기능(`선택 항목으로 보고서 생성`)이 있으므로, 같은 선택 흐름으로 수불부도 자동으로 채워 넣을 수 있게 한다.

사용자가 첨부한 실제 양식 파일 `(철근)(건축)주요자재 검사 및 수불부.xlsx`을 분석한 결과는 아래와 같다.

## 템플릿 구조 (실제 파일 검증됨)

두 시트로 구성: `철근`, `커플러`. 레이아웃은 동일하다.

- `B2`: 제목 "주요자재 검사 및 수불부" (고정, 건드리지 않음)
- 4~6행: 컬럼 헤더 및 자동 합산 수식(`T5:AB6` 등 규격별 SUMIF 합계) — 건드리지 않음
- **7행부터 데이터 행 시작**. 각 행 = 반입 1건. 열 구성:
  - `B`: 연번
  - `C`: 반입일
  - `D`: 규격
  - `E`: 단위 — 템플릿에 이미 `"ton"`(철근 시트) 고정값으로 채워져 있음, 건드리지 않음
  - `F`~`P`: 설계량/합격량(금회·누계)/불합격/사용일/사용량/반출일/반출량/잔량 — **템플릿에 이미 수식·기본값이 574행까지 미리 채워져 있음**. 예: `F7='=G7'`, `H7='=IF(G7="","",(G7-J7))'`. 우리가 건드릴 필요 없음.
  - `G`: 반입량 — **유일하게 실제 반입 수량을 넣어야 하는 입력 컬럼**
  - `Q`: 검수자
  - `R`: 담당감리원

이번 기능에서 실제로 쓰는 셀은 시트당 `B`, `C`, `D`, `G`, `Q`, `R` 뿐이다. 나머지는 템플릿에 이미 있는 수식이 반입량(G열)을 참조해 자동 계산한다.

이 파일을 그대로 `backend/app/templates/material_ledger.xlsx`로 저장소에 포함하고, 매 요청마다 열어(원본 불변) 사본에 값을 채워 반환한다.

## 이번 범위: 철근 시트만

앱은 현재 커플러의 EA(개) 수량을 별도로 저장하지 않는다 — 촬영 시 커플러 여부는 품명을 `"커플러"`로 표시하는 데만 쓰이고, 저장되는 수량/중량은 항상 Ton 단위 값(철근과 동일 필드)이라 커플러 시트(단위: EA)에 그대로 넣을 수 없다. 이번 기능은 **`철근` 시트만 채우고, 커플러 시트는 건드리지 않는다.**

선택한 기록 중 다음은 채우기 대상에서 제외하고, 제외된 건수를 경고 메시지로 알려준다(기존 `X-Report-Warnings` 패턴 재사용):
- `item_name == "커플러"`인 기록
- `material_type != "철근"`인 기록

## 데이터 흐름

```
[검색 화면] 체크박스로 여러 건 선택
      |
      v  "선택 항목으로 수불부 생성" 버튼 클릭 (기존 "선택 항목으로 보고서 생성" 버튼 옆)
[/ledger 화면] 검수자·담당감리원 입력 (한 번만 입력, 모든 행에 공통 적용)
      |
      v  POST /reports/material-ledger  (invoice_ids, inspector, supervisor)
[백엔드]
  1. invoice_ids로 DB에서 송장 조회 (crud.list_invoices_by_ids 재사용)
  2. item_name=="커플러" 또는 material_type!="철근"인 건 제외, 나머지는 delivery_date 오름차순 정렬
  3. report_ledger.fill_material_ledger(template_path, invoices, inspector, supervisor) -> (bytes, excluded_count)
     - openpyxl로 템플릿 로드, "철근" 시트의 7행부터 순서대로 B/C/D/G/Q/R만 채움
     - BytesIO로 바이트 반환
      |
      v  응답: .xlsx 다운로드, 제외 건수가 있으면 X-Report-Warnings 헤더 포함
```

## 셀 매핑

| 필드 | 셀 (7행 기준, 이후 행마다 +1) | 값 |
|---|---|---|
| 연번 | `B7`, `B8`, … | 1부터 순서대로 |
| 반입일 | `C7`, `C8`, … | `invoice.delivery_date` (YYYY-MM-DD) |
| 규격 | `D7`, `D8`, … | `invoice.spec` |
| 반입량 | `G7`, `G8`, … | `invoice.weight` (Ton) |
| 검수자 | `Q7`, `Q8`, … | 입력받은 `inspector` 값, 모든 행 동일 |
| 담당감리원 | `R7`, `R8`, … | 입력받은 `supervisor` 값, 모든 행 동일 |

## API

`POST /reports/material-ledger`
- Form 필드: `invoice_ids`(콤마 구분 문자열, 필수), `inspector`(문자열, 선택), `supervisor`(문자열, 선택)
- 응답: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, 파일명 `주요자재검사및수불부_YYMMDD.xlsx` (Content-Disposition, 기존 보고서 파일명 처리 방식과 동일하게 `filename*=UTF-8''` 인코딩)
- `invoice_ids`가 비어있거나 조회된 기록이 없으면 400
- 제외 대상만 있고 채울 기록이 하나도 없으면 400 ("철근 자재 기록이 없습니다" 류 메시지)
- 제외된 기록이 있지만 채울 기록도 있으면 200 + `X-Report-Warnings`에 제외 건수 안내

## 프론트엔드

- `SearchPage.jsx`: 선택 항목 액션 바에 "선택 항목으로 수불부 생성" 버튼 추가. 클릭 시 `navigate('/ledger', { state: { invoiceIds: selectedIds } })`
- `App.jsx`: `/ledger` 라우트 추가, nav에 "수불부 생성" 링크 추가
- 새 `LedgerPage.jsx`:
  - `location.state?.invoiceIds`가 없으면 (직접 URL 진입 등) 안내 문구만 보여주고 생성 버튼 비활성화
  - 검수자/담당감리원 입력 필드 2개
  - "수불부 생성" 버튼 → `api.js`에 새 함수 `createMaterialLedger(invoiceIds, inspector, supervisor)` 추가, blob 다운로드는 `ReportPage.jsx`와 동일한 패턴(서버가 보낸 Content-Disposition 파일명을 그대로 사용)
  - 경고(X-Report-Warnings)가 있으면 배너로 표시

## 에러 처리

- `invoice_ids` 파싱 실패 시 400
- 대상 기록이 하나도 없으면 400
- 그 외 원칙은 기존 `/reports/material-inspection`과 동일

## 테스트 전략

- `report_ledger.py` 단위 테스트: 여러 invoice를 넣었을 때 B/C/D/G/Q/R이 정확한 셀에 순서대로 들어가는지, 커플러/타 자재종류가 제외되는지, 날짜순 정렬이 되는지, 기존 수식 셀(F7 등)이 그대로 보존되는지(덮어쓰지 않았는지) 확인
- `routers/reports.py` 통합 테스트: 응답이 유효한 xlsx인지, 제외 건수가 있을 때 경고 헤더가 오는지, 대상이 하나도 없을 때 400인지
- 프론트: 로컬 브라우저로 검색 → 선택 → 수불부 생성 → 실제 다운로드 파일명/셀 값 확인 (기존 세션에서 써온 브라우저 기반 수동 검증 방식)

## 범위 밖

- 커플러 시트 자동 채움 (EA 수량 미저장으로 이번 범위 제외 — 추후 촬영 시 커플러 EA 수량을 별도 필드로 저장하는 작업이 선행되어야 함)
- 불합격량/불합격 사유, 반출일/반출량 등 수동 입력 영역 자동화
- 이 템플릿 구조가 아닌 다른 레이아웃의 수불부 지원
