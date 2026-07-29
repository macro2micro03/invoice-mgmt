# 사진대지 다중 세트(최대 5세트) 지원 — 설계 문서

## 배경

자재검수요청서 엑셀 서식의 "사진대지" 섹션은 지금 상단 사진 블록(81행)과 하단 사진 블록(84행), 각각 자기 설명(공종명/위치, 내용/날짜) 2줄씩 — 총 6행짜리 블록 하나만 있다. 사진이 많은 현장에서는 이 한 블록(상단+하단 한 쌍)으로 부족해서, 같은 구조를 최대 5세트까지 반복해서 넣고 싶다는 요청이다.

## 범위

**포함:**
- "사진대지 세트"(상단 사진 블록 + 하단 사진 블록, 각자의 설명 2줄 포함 — 총 6행)를 반복 가능한 단위로 취급.
- 사진이 하나라도 있는 세트만 실제로 엑셀에 생성(빈 세트는 건너뜀).
- 최대 5세트까지 지원.
- 프론트엔드는 기본 1세트만 보이고 "+ 세트 추가" 버튼으로 최대 5세트까지 늘어남.

**범위 밖:**
- 세트별로 다른 공종명/위치/내용 텍스트를 사용자가 직접 입력하는 기능 — 지금처럼 템플릿 기본값(철근 콘크리트 공사, 현장 내 야적장, 자재 검수) 그대로 복제.
- 5세트를 초과하는 경우 — 6번째 세트부터는 무시(경고 메시지로 안내).

## 백엔드 변경

### `backend/app/report_excel.py`

**새 상수:**
```python
PHOTO_SET_ROW_START = 81
PHOTO_SET_BLOCK_ROWS = 6
MAX_PHOTO_SETS = 5
```

**새 헬퍼 `_copy_photo_set_block(sheet, source_start, target_start)`:**
템플릿의 81~86행(첫 번째 세트) 서식을 그대로 복제해 `target_start`부터 6행에 값/폰트/테두리/채우기/정렬/행높이/병합범위를 복사한다. `openpyxl.utils.get_column_letter`로 병합 범위를 다시 계산해 새 위치에 `merge_cells`로 재적용한다.

**`fill_material_inspection_form`의 파라미터 변경:**
`top_photos: list[bytes] | None = None, bottom_photos: list[bytes] | None = None` 두 개를 제거하고, 아래로 교체한다:

```python
photo_sets: list[dict] | None = None,
```

각 항목은 `{"top": list[bytes], "bottom": list[bytes]}` 형태. 처리 로직:

```python
photo_sets = photo_sets or []
non_empty_sets = [s for s in photo_sets[:MAX_PHOTO_SETS] if s.get("top") or s.get("bottom")]

for index, photo_set in enumerate(non_empty_sets):
    if index > 0:
        target_start = PHOTO_SET_ROW_START + index * PHOTO_SET_BLOCK_ROWS
        sheet.insert_rows(target_start, amount=PHOTO_SET_BLOCK_ROWS)
        _copy_photo_set_block(sheet, PHOTO_SET_ROW_START, target_start)
    top_anchor = PHOTO_SET_ROW_START + index * PHOTO_SET_BLOCK_ROWS
    bottom_anchor = top_anchor + 3
    report_photos.insert_photo_grid(sheet, anchor_row=top_anchor, photos=photo_set.get("top") or [])
    report_photos.insert_photo_grid(sheet, anchor_row=bottom_anchor, photos=photo_set.get("bottom") or [])
```

세트가 정확히 1개(또는 0개)면 행 삽입이 전혀 일어나지 않아 기존 동작과 완전히 동일하다 — 하위 호환.

`H83`/`H86`(날짜) 채우기는 세트 0(기존 81~86행)에만 적용되던 것을, 생성된 모든 세트의 대응 날짜 셀에 동일하게 적용하도록 확장한다(각 세트의 "내용/날짜" 행, 즉 `top_anchor+2`행의 H열).

### `backend/app/routers/reports.py`

`top_photos`/`bottom_photos` 두 개의 `File(default=[])` 파라미터를 제거하고, 세트별로 이름 붙인 10개의 선택적 파라미터로 교체한다:

```python
photo_set_1_top: List[UploadFile] = File(default=[]),
photo_set_1_bottom: List[UploadFile] = File(default=[]),
photo_set_2_top: List[UploadFile] = File(default=[]),
photo_set_2_bottom: List[UploadFile] = File(default=[]),
photo_set_3_top: List[UploadFile] = File(default=[]),
photo_set_3_bottom: List[UploadFile] = File(default=[]),
photo_set_4_top: List[UploadFile] = File(default=[]),
photo_set_4_bottom: List[UploadFile] = File(default=[]),
photo_set_5_top: List[UploadFile] = File(default=[]),
photo_set_5_bottom: List[UploadFile] = File(default=[]),
```

이 5쌍을 읽어 `photo_sets` 리스트로 조립한 뒤 `fill_material_inspection_form`에 전달한다.

## 프론트엔드 변경

`ReportPage.jsx`:
- `photoSets` 상태를 `[{ top: [], bottom: [] }]`(기본 1개)로 시작.
- "+ 세트 추가" 버튼(현재 세트 수가 5 미만일 때만 표시)을 누르면 빈 세트를 하나 더 추가.
- 각 세트마다 "사진대지 N세트 상단 사진"/"하단 사진" PhotoPicker 한 쌍을 렌더링.
- 제출 시, `top`과 `bottom`이 모두 빈 세트는 제외하고 `photo_set_{n}_top`/`photo_set_{n}_bottom` 폼 필드로 전송한다(비어있지 않은 세트만 순서대로 1번부터 채워서 전송 — 예: 2번째 세트만 채웠으면 `photo_set_1_top`으로 보냄).

`api.js`의 `createMaterialInspectionReport`가 `topPhotos`/`bottomPhotos` 두 인자 대신 `photoSets: [{top: File[], bottom: File[]}]` 배열 하나를 받도록 시그니처를 바꾼다.

## 테스트 전략

- `report_excel.py`: 세트 1개(기존 동작과 동일), 세트 3개(행 삽입 확인 — 각 세트의 사진 개수와 위치), 5개 초과 요청 시 처음 5개만 반영되는지, 빈 세트가 건너뛰어지는지 단위 테스트.
- `routers/reports.py`: 여러 세트를 폼 필드로 보냈을 때 최종 엑셀에 세트 수만큼 이미지가 들어가는지 통합 테스트.
- 프론트엔드는 기존 패턴대로 자동 테스트 없이 `npm run build` + 브라우저 프리뷰로 "+ 세트 추가" 동작 확인.

## 자체 점검

- 세트 1개(가장 흔한 경우)일 때 기존 코드 경로와 동일하게 동작함을 명시 — 확인됨.
- 빈 세트 스킵, 5세트 상한이 구체적으로 명시됨 — 확인됨.
- 세트별 공종명/위치/내용 커스터마이징은 범위 밖으로 명확히 배제됨 — 확인됨.
