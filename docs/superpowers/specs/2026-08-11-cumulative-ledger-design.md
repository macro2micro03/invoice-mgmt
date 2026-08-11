# 누적 수불부 관리 — 설계 문서

## 배경

`2026-08-10-material-ledger-design.md`에서 구현한 수불부 생성 기능은 매번 완전히 새 파일을 만들고, 그때 검색에서 선택한 송장만 채운다 — 이전에 생성했던 수불부의 내용을 기억하지 않는다. 실제 현장에서는 수불부를 "계속 쌓이는 하나의 장부"로 관리하고 싶어 한다: 새 송장이 등록될 때마다 기존 수불부 아래에 이어붙여지고, 예전 항목의 값을 고치면 다음 생성 시 반영되고, 특정 건을 장부에서 빼고 싶을 때 뺄 수 있어야 한다.

또한 수불부에는 송장(Invoice)에는 없는 항목(불합격량/사유/반출일/반출량/잔량)이 있고, 현장에서는 이 항목들을 실제로 채워 넣고 계속 유지해야 한다. 이 항목들은 **엑셀 파일에 직접 타이핑하면 다음 재생성 때 사라진다** — 파일을 매번 새로 만들기 때문이다. 따라서 이 항목들도 앱이 값을 저장하고 있어야 하고, 사용자는 **엑셀 파일이 아니라 앱 화면에서** 값을 입력/수정해야 한다.

## 핵심 설계 결정

1. **파일을 저장하지 않고 매번 재생성한다.** 서버에 실제 엑셀 파일을 두고 이어붙이는 대신, DB에 저장된 값으로 다운로드할 때마다 템플릿을 처음부터(7행부터) 다시 채운다. 파일 손상 위험이 없고, 수정/제외가 DB 값 변경만으로 자연스럽게 처리된다.
2. **수불부 전용 항목은 별도 테이블에 저장한다.** 송장 자체 값(반입일/규격/반입량)은 기존 `Invoice`에서 가져오지만, 수불부에서만 쓰는 값(불합격량/사유/반출일/반출량/잔량/검수자/담당감리원)은 새 테이블 `LedgerEntry`에 저장한다.
3. **앱 화면이 곧 수불부다.** `/ledger` 화면에 현재 포함된 전체 목록을 표로 보여주고, 자동 채움 컬럼(연번/반입일/규격/반입량)은 읽기 전용으로, 수동 컬럼(불합격량/사유/반출일/반출량/잔량/검수자/담당감리원)은 표 안에서 직접 입력/수정한다. 이 화면에 보이는 내용이 그대로 "수불부 생성" 시 엑셀로 떨어진다.

## 데이터 모델

새 테이블 `LedgerEntry` (`backend/app/models.py`):

```python
class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), unique=True, nullable=False)
    defect_qty = Column(Float, nullable=True)       # 불합격량
    defect_reason = Column(String, nullable=True)    # 사유
    release_date = Column(Date, nullable=True)       # 반출일
    release_qty = Column(Float, nullable=True)       # 반출량
    remaining_qty = Column(Float, nullable=True)     # 잔량
    inspector = Column(String, nullable=True)        # 검수자
    supervisor = Column(String, nullable=True)       # 담당감리원

    invoice = relationship("Invoice")
```

- `invoice_id`가 `unique=True`인 것 자체가 "이 송장이 수불부에 포함되어 있다"는 표시를 겸한다 — 별도 boolean 플래그는 두지 않는다. `LedgerEntry` 행이 있으면 포함된 것, 없으면(또는 삭제되면) 포함 안 된 것.
- 이 앱은 Alembic 등 마이그레이션 도구를 쓰지 않고 `Base.metadata.create_all`로 스키마를 관리한다 — 새 테이블이므로 기존 테이블처럼 컬럼 추가 마이그레이션이 필요 없고, `create_all`이 자동으로 만들어준다(기존 SQLite/Postgres 배포에 안전하게 적용됨).

## 백엔드 API

### `POST /reports/material-ledger` (기존 엔드포인트 수정)

1. 선택한 `invoice_ids` 중 커플러/비철근은 기존과 동일하게 제외
2. 남은 것 중 이미 `LedgerEntry`가 있는 건은 건너뛰고 개수를 경고에 포함 ("이미 수불부에 포함된 N건은 건너뛰었습니다")
3. 나머지(신규)는 `LedgerEntry`를 새로 만든다 — `inspector`/`supervisor`는 이번 요청의 폼 값으로 채우고, 나머지(불합격량/사유/반출일/반출량/잔량)는 빈 값으로 시작
4. **파일은 현재 존재하는 모든 `LedgerEntry`**(방금 추가한 것 + 기존 것 전부)를 연결된 `Invoice`의 반입일 순으로 정렬해 채운다
5. 채울 `LedgerEntry`가 하나도 없으면 400

### `GET /reports/material-ledger/entries` (신규)

현재 존재하는 모든 `LedgerEntry`를 `Invoice`와 조인해 반입일 순으로 반환한다. 응답에 연번(정렬 순서), 반입일/규격/반입량(Invoice에서), 불합격량/사유/반출일/반출량/잔량/검수자/담당감리원(LedgerEntry에서)을 모두 포함.

### `PUT /reports/material-ledger/entries/{invoice_id}` (신규)

해당 `LedgerEntry`의 수동 입력 필드(불합격량/사유/반출일/반출량/잔량/검수자/담당감리원)를 갱신한다. 존재하지 않으면 404.

### `DELETE /reports/material-ledger/entries/{invoice_id}` (신규)

해당 `LedgerEntry`를 삭제한다 = 수불부에서 제외. `Invoice` 자체는 건드리지 않는다. 존재하지 않아도(이미 제외된 상태) 204로 멱등 처리.

## 프론트엔드 변경

### `LedgerPage.jsx`

- 상단: 기존 "검수자/담당감리원 입력 + 수불부 생성" 폼 유지 (검색에서 선택해서 들어왔을 때 신규 항목을 추가하는 용도)
- 생성 버튼 아래: 페이지 진입 시 `GET /reports/material-ledger/entries`로 전체 목록을 불러와 표로 표시
  - 컬럼: 연번, 반입일, 규격, 반입량 (읽기 전용) / 불합격량, 사유, 반출일, 반출량, 잔량, 검수자, 담당감리원 (입력 필드) / 제외 버튼
  - 입력 필드 변경 시 `PUT .../entries/{invoice_id}`로 저장 (검색 화면의 검수자/담당감리원 입력 패턴과 동일하게 즉시 반영 또는 blur 시 저장 — 구현 단계에서 blur 시 저장으로 확정)
  - "제외" 버튼 → 확인창 → `DELETE .../entries/{invoice_id}` → 목록에서 제거
- "수불부 생성" 성공 후 목록을 다시 불러와 새로 추가된 항목을 표에 반영
- 목록이 비어있으면 "아직 수불부에 포함된 기록이 없습니다" 안내

### `api.js`

- `getLedgerEntries()`: `GET /reports/material-ledger/entries`
- `updateLedgerEntry(invoiceId, fields)`: `PUT /reports/material-ledger/entries/{invoiceId}`
- `deleteLedgerEntry(invoiceId)`: `DELETE /reports/material-ledger/entries/{invoiceId}`

## 셀 매핑 갱신

기존 매핑(B/C/D/G/Q/R)에 아래를 추가한다 — `report_ledger.fill_material_ledger`가 이제 `LedgerEntry` 리스트를 받아 채운다:

| 필드 | 열 | 출처 |
|---|---|---|
| 연번 | B | 정렬 순서 |
| 반입일 | C | Invoice |
| 규격 | D | Invoice |
| 반입량 | G | Invoice |
| 불합격량 | J | LedgerEntry |
| 사유 | K | LedgerEntry |
| 반출일 | N | LedgerEntry |
| 반출량 | O | LedgerEntry |
| 잔량 | P | LedgerEntry |
| 검수자 | Q | LedgerEntry |
| 담당감리원 | R | LedgerEntry |

(사용일(L)/사용량(M)은 템플릿의 기존 수식 `=C`, `=G`을 그대로 두고 건드리지 않는다 — 별도 요구사항이 없었음)

## 에러 처리

- 신규로 추가할 것도 없고 기존 `LedgerEntry`도 없으면 400 ("수불부에 포함할 철근 자재 기록이 없습니다")
- `PUT`/`DELETE` 대상이 존재하지 않으면 404 (DELETE는 예외적으로 이미 없어도 204 — 멱등)
- 그 외 기존 원칙(공유 비밀번호 인증 등) 동일하게 유지

## 테스트 전략

- `crud.py`: `LedgerEntry` 생성/조회/수정/삭제 단위 테스트 — 반입일 순 정렬, 중복 생성 방지(이미 있으면 건너뜀), 삭제 후 목록에서 빠지는지, `Invoice`는 삭제되지 않는지
- `report_ledger.py`: `LedgerEntry` 리스트(Invoice 조인 값 포함)를 받아 B/C/D/G/J/K/N/O/P/Q/R이 정확한 셀에 들어가는지, 값이 없는 필드(None)는 빈 셀로 남는지
- `/reports/material-ledger` 통합 테스트: 1차 생성(2건) → 2차 생성(신규 1건 + 기존 1건 재선택) → 파일에 총 3건, 경고 문구("이미 포함된 1건") 확인
- `/reports/material-ledger/entries` GET/PUT/DELETE 테스트: 목록 조회, 수동 필드 수정 후 재조회 시 반영, 삭제 후 목록에서 사라지고 `Invoice`는 `GET /invoices/{id}`로 계속 조회됨, 존재하지 않는 항목 PUT/DELETE 시 404
- 프론트: 로컬 브라우저로 1차 생성 → 목록 표시 → 불합격량/사유 등 입력 후 저장 확인 → 2차 생성 시 파일에 그 값이 그대로 들어있는지 → 하나 제외 후 목록/파일에서 빠지는지 수동 검증

## 범위 밖

- 여러 개의 독립된 수불부(프로젝트별/연도별 분리 관리)
- 커플러 수불부의 동일 기능 (기존과 마찬가지로 철근 시트만 대상)
- 목록의 수동 재정렬 (항상 반입일 순 자동 정렬)
- 사용일(L)/사용량(M)의 수동 오버라이드 (현재 수식 그대로 유지)
