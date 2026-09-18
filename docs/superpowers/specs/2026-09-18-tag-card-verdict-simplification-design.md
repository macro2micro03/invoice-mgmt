# 택 카드 판정 단순화 — 설계 문서

## 배경

철근 택 제조사 확인 기능을 배포한 뒤 실사용 테스트 중, 편집 화면의 "철근 Tag 검수" 섹션(택 카드)이 실제 현장 검수 목적과 맞지 않는 것으로 확인됐다. 택 카드는 강도/직경/제조사를 개별적으로 보여주고 수정할 수 있는 입력 폼이었는데, 이 섹션의 실제 용도는 "이 철근 다발(택)이 송장 내용과 일치하는 물건인지"만 확인하면 되는 단순 검수 도구다. 현재 UI는 필드별 값을 노출·수정하게 해서 불필요하게 복잡하고, 강도/직경만 보는 기존 배너("이 규격은 송장에 포함되어 있습니다")는 제조사를 고려하지 않아 오해를 준다.

## 범위

**포함:**
- `EditPage.jsx`의 택 카드(각 촬영된 택 사진마다 나오는 카드)에서 강도/직경/제조사 입력 필드 3개를 제거한다.
- 택의 강도+직경+제조사가 송장 내 자재(품목) 중 **하나라도 전부** 일치하면 "적합", 하나라도 다르거나 애초에 인식이 안 됐으면(빈 값 포함) "부적합"으로 판정하는 단일 배너로 대체한다.
- 인식 자체가 실패한 경우(사진에서 텍스트를 전혀 못 읽음)의 기존 "인식에 실패했습니다" 안내는 그대로 유지한다.

**범위 밖:**
- 자재 카드(송장 자재 목록 + 택 배정 배너) — 배정 로직(`matchTagsToItems`)과 배정 성공/실패 배너는 이번 변경 대상이 아니다. 그대로 둔다.
- 저장 로직(`handleSave`) — 배정된 택의 강도/직경/제조사/현장명 등은 지금처럼 그대로 저장된다. 택 카드에서 값을 보여주고 수정하는 UI만 없앨 뿐, 데이터 자체나 저장 흐름은 바뀌지 않는다.
- 백엔드 — 변경 없음. `/ocr/tag` 응답 형식, DB 스키마 모두 그대로다.

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

- 자재 카드의 배정 배너(`"일치하는 철근 Tag을 확인했습니다 : ..."` 등)는 그대로다.
- `handleSave`가 배정된 택의 `tag_grade`/`tag_diameter`/`tag_manufacturer`/기타 필드를 저장하는 로직은 그대로다 — 택 카드에서 입력 필드로 값을 보여주고 고치던 것만 없앨 뿐, OCR로 인식된 값 자체는 (수정 없이) 그대로 저장된다.
- `DetailPage.jsx` — 저장된 값을 보여주는 화면이라 이번 변경과 무관하다.

## 테스트 전략

프론트엔드는 기존 패턴대로 자동 테스트 없이 `npm run build` + 브라우저 프리뷰로 확인한다. 확인 항목:
- 택 사진 업로드 후 강도/직경/제조사 입력 필드가 더 이상 보이지 않는지
- 강도+직경+제조사가 송장 자재 중 하나와 모두 일치하면 "적합" 배너가 뜨는지
- 하나라도 다르면(또는 인식이 안 됐으면) "부적합" 배너가 뜨는지
- 자재 카드 쪽 배정 배너와 저장 동작은 기존과 동일하게 유지되는지

## 자체 점검

- 판정 로직이 기존 `matchTagToSpec`/`matchManufacturer` 헬퍼를 재사용해 중복 로직을 만들지 않음 — 확인됨.
- 인식 실패(빈 값)가 자동으로 "부적합"으로 처리됨(`null !== 'matched'`) — 별도 분기 없이 요구사항 반영됨.
- 자재 카드/저장 로직 비변경 — 요구사항대로 명시됨.
- 죽은 코드(`handleTagFieldEdit`)를 함께 정리 — 범위에 포함.
