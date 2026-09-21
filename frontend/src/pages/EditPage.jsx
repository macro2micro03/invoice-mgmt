import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { createInvoice, runTagOcr } from '../api.js'

const COMMON_FIELD_DEFS = [
  ['vendor', '거래처'],
  ['delivery_date', '납품일'],
  ['vehicle_no', '차량번호'],
  ['invoice_no', '송장번호'],
]

const ITEM_FIELD_DEFS = [
  ['item_name', '품명'],
  ['spec', '규격'],
  ['unit', '단위'],
  ['quantity', '수량'],
  ['note', '비고'],
]

const GRADE_BY_PREFIX = { SD: 'SD400', SHD: 'SD500', UHD: 'SD600' }

function parseSpecGradeDiameter(spec) {
  if (!spec) return [null, null]
  const specUpper = spec.trim().toUpperCase()
  for (const [prefix, grade] of Object.entries(GRADE_BY_PREFIX)) {
    if (specUpper.startsWith(prefix)) {
      const diameter = specUpper.slice(prefix.length).replace(/[^0-9]/g, '')
      return [grade, diameter || null]
    }
  }
  return [null, null]
}

function normalizeDiameter(value) {
  if (!value) return null
  const digits = value.replace(/[^0-9]/g, '')
  return digits || null
}

function normalizeGrade(value) {
  if (!value) return null
  const normalized = value.trim().toUpperCase().replace(/[^A-Z0-9]/g, '')
  return normalized || null
}

// backend app/spec_grade.py의 match_tag_to_spec와 동일한 로직을 프런트에서도
// 재계산할 수 있도록 이식한 헬퍼.
function matchTagToSpec(tagGrade, tagDiameter, spec) {
  const [specGrade, specDiameter] = parseSpecGradeDiameter(spec)
  const normTagGrade = normalizeGrade(tagGrade)
  const normTagDiameter = normalizeDiameter(tagDiameter)
  if (specGrade === null || normTagGrade === null || normTagDiameter === null) return null
  if (specGrade === normTagGrade && specDiameter === normTagDiameter) return 'matched'
  return 'mismatched'
}

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

// 부적합 배지 옆에 사유를 보여주기 위한 설명 문구. isTagVerifiedAgainstInvoice가
// false일 때만 호출한다고 가정하고, 어느 단계에서 막혔는지 우선순위대로
// 확인한다: ①택 인식 자체 실패 → ②규격이 일치하는 품목 없음 → ③규격은
// 맞는데 제조사가 안 맞음(송장 비고에 제조사 정보 자체가 없는 경우와
// 다른 제조사가 적힌 경우를 구분).
function explainTagRejection(tagResult, items) {
  if (!tagResult.tag_grade || !tagResult.tag_diameter) {
    return '택에서 강도/직경을 인식하지 못했습니다'
  }
  if (!tagResult.tag_manufacturer) {
    return '택에서 제조사를 인식하지 못했습니다'
  }
  const specMatchedItems = items.filter(
    (item) => matchTagToSpec(tagResult.tag_grade, tagResult.tag_diameter, item.spec) === 'matched',
  )
  if (specMatchedItems.length === 0) {
    return '송장에 이 규격과 일치하는 품목이 없습니다'
  }
  const hasRecognizedNote = specMatchedItems.some((item) => normalizeManufacturer(item.note) !== null)
  if (!hasRecognizedNote) {
    return '규격은 일치하지만 송장 비고에서 제조사를 확인할 수 없습니다'
  }
  return '규격은 일치하지만 택 제조사가 송장 비고와 다릅니다'
}

// 촬영한 철근 Tag 여러 장을 자재 목록과 1:1로 대조한다. 각 자재(규격)에
// 대해 아직 배정되지 않은 택 중 규격이 일치하는 것을 하나 찾아 배정한다.
// 같은 규격의 택이 여러 장 남더라도(패킹 단위별로 택이 따로 있는 게
// 정상이다) 그건 문제가 아니므로 경고하지 않는다 — 저장 시 그 자재에
// 첨부할 택을 정하는 용도로만 쓰인다. 개별 택이 이 송장 규격에
// 포함되는지 여부는 각 택 카드에서 matchTagToSpec으로 직접 표시한다.
function matchTagsToItems(items, tagEntries) {
  const usedFiles = new Set()
  const itemAssignments = items.map((item) => {
    const found = tagEntries.find(
      (entry) => !usedFiles.has(entry.file) && matchTagToSpec(entry.result.tag_grade, entry.result.tag_diameter, item.spec) === 'matched',
    )
    if (!found) return null
    usedFiles.add(found.file)
    return found
  })

  return { itemAssignments }
}

function makeItem(record) {
  return {
    material_type: record.material_type || '',
    item_name: record.item_name || '',
    spec: record.spec || '',
    unit: record.unit || '',
    quantity: record.quantity ?? '',
    weight: record.weight ?? '',
    note: record.note || '',
  }
}

export default function EditPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const initialRecords = location.state?.records?.length ? location.state.records : [{}]
  const photoFile = location.state?.photoFile || null

  const [common, setCommon] = useState(() => ({
    vendor: initialRecords[0]?.vendor || '',
    delivery_date: initialRecords[0]?.delivery_date || '',
    vehicle_no: initialRecords[0]?.vehicle_no || '',
    invoice_no: initialRecords[0]?.invoice_no || '',
  }))
  const [items, setItems] = useState(() => initialRecords.map(makeItem))
  // 철근 Tag는 한 번에 여러 장 촬영/선택할 수 있다. 파일 자체를 key로 써서
  // (인덱스 대신) 추가/삭제 순서가 뒤섞여도 결과가 엇갈리지 않게 한다.
  const [tagFiles, setTagFiles] = useState([])
  const [tagResultsByFile, setTagResultsByFile] = useState(new Map())
  const [saving, setSaving] = useState(false)

  function handleCommonChange(key, value) {
    setCommon((prev) => ({ ...prev, [key]: value }))
  }

  function handleItemChange(index, key, value) {
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, [key]: value } : item)))
  }

  function handleRemoveItem(index) {
    setItems((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleAddTagFiles(event) {
    const newFiles = Array.from(event.target.files)
    event.target.value = ''
    if (newFiles.length === 0) return
    setTagFiles((prev) => [...prev, ...newFiles])
    setTagResultsByFile((prev) => {
      const next = new Map(prev)
      newFiles.forEach((file) => next.set(file, 'loading'))
      return next
    })
    for (const file of newFiles) {
      try {
        const result = await runTagOcr(file)
        setTagResultsByFile((prev) => new Map(prev).set(file, result))
      } catch (err) {
        setTagResultsByFile((prev) => new Map(prev).set(file, 'error'))
      }
    }
  }

  function handleRemoveTagFile(file) {
    setTagFiles((prev) => prev.filter((f) => f !== file))
    setTagResultsByFile((prev) => {
      const next = new Map(prev)
      next.delete(file)
      return next
    })
  }

  const tagEntries = tagFiles
    .map((file) => ({ file, result: tagResultsByFile.get(file) }))
    .filter((entry) => entry.result && entry.result !== 'loading' && entry.result !== 'error' && entry.result.tag_grade && entry.result.tag_diameter)
  const { itemAssignments } = matchTagsToItems(items, tagEntries)

  async function handleSave() {
    setSaving(true)
    let saved = 0
    try {
      for (let i = 0; i < items.length; i += 1) {
        const item = items[i]
        const assignment = itemAssignments[i]
        let tagFields = {}
        let tagPhotoFile = null
        if (assignment) {
          const {
            tag_site_name,
            tag_location,
            tag_diameter,
            tag_grade,
            tag_length,
            tag_quantity,
            tag_shape,
            tag_manufacturer,
          } = assignment.result
          tagFields = {
            tag_site_name,
            tag_location,
            tag_diameter,
            tag_grade,
            tag_length,
            tag_quantity,
            tag_shape,
            tag_manufacturer,
          }
          tagPhotoFile = assignment.file
        } else if (tagFiles.length > 0) {
          // 택은 촬영했지만 이 규격과 일치하는 게 하나도 없었던 경우 —
          // "확인은 했지만 대응하는 택이 없었다"를 명시적으로 저장해 둔다.
          tagFields = { tag_match_status: 'missing' }
        }
        await createInvoice({ ...common, ...item, ...tagFields }, photoFile, tagPhotoFile)
        saved += 1
      }
      navigate('/search')
    } catch (err) {
      setItems((prev) => prev.slice(saved))
      alert(`${saved}건 저장 후 실패했습니다. 남은 ${items.length - saved}건을 다시 시도해주세요.`)
    } finally {
      setSaving(false)
    }
  }

  const canSave = items.length > 0 && items.every((item) => item.material_type)

  return (
    <div className="page">
      <h1>내용 확인 및 수정</h1>
      <div className="card">
        <p className="field-group-label">공통 정보</p>
        {COMMON_FIELD_DEFS.map(([key, label]) => (
          <div key={key} className="field">
            <label>{label}</label>
            <input
              className="input"
              type="text"
              value={common[key] || ''}
              onChange={(e) => handleCommonChange(key, e.target.value)}
            />
          </div>
        ))}
      </div>
      {items.map((item, index) => (
        <div key={index} className="card item-card">
          <div className="item-card-header">
            <p className="field-group-label">자재 {index + 1}</p>
            {items.length > 1 && (
              <button
                type="button"
                className="item-remove"
                onClick={() => handleRemoveItem(index)}
                aria-label={`자재 ${index + 1} 삭제`}
              >
                ×
              </button>
            )}
          </div>
          {ITEM_FIELD_DEFS.map(([key, label]) => (
            <div key={key} className="field">
              <label>{label}</label>
              <input
                className="input"
                type="text"
                value={item[key] ?? ''}
                onChange={(e) => handleItemChange(index, key, e.target.value)}
              />
            </div>
          ))}
          {tagFiles.length > 0 &&
            (itemAssignments[index] ? (
              (() => {
                const tag = itemAssignments[index].result
                const manufacturerStatus = matchManufacturer(tag.tag_manufacturer, item.note)
                if (manufacturerStatus === 'matched') {
                  const code = CODE_BY_MANUFACTURER[normalizeManufacturer(item.note)] || tag.tag_manufacturer
                  return (
                    <p className="banner banner-success">
                      일치하는 철근 Tag을 확인했습니다 : {tag.tag_grade}, D{tag.tag_diameter}, {code}
                    </p>
                  )
                }
                return (
                  <>
                    <p className="banner banner-success">
                      일치하는 철근 Tag를 확인했습니다: {tag.tag_grade} D{tag.tag_diameter}
                    </p>
                    {manufacturerStatus === 'mismatched' && (
                      <p className="banner banner-warning">
                        택 제조사({tag.tag_manufacturer})가 송장 비고({item.note})와 다릅니다
                      </p>
                    )}
                  </>
                )
              })()
            ) : (
              <p className="banner banner-warning">이 규격에 해당하는 철근 Tag를 찾지 못했습니다</p>
            ))}
        </div>
      ))}
      <div className="card">
        <p className="field-group-label">철근 Tag 검수</p>
        <div style={{ display: 'flex', gap: 8 }}>
          <label className="btn btn-primary photo-picker-add">
            📷 촬영 (여러 장 가능)
            <input
              className="photo-picker-input"
              type="file"
              accept="image/*"
              capture="environment"
              multiple
              onChange={handleAddTagFiles}
            />
          </label>
          <label className="btn btn-secondary photo-picker-add">
            📁 파일 선택
            <input
              className="photo-picker-input"
              type="file"
              accept="image/*"
              multiple
              onChange={handleAddTagFiles}
            />
          </label>
        </div>
        {tagFiles.map((file, index) => {
          const result = tagResultsByFile.get(file)
          return (
            <div key={`${file.name}-${index}`} className="card item-card" style={{ marginTop: 12 }}>
              <div className="item-card-header">
                <p className="field-group-label">{file.name}</p>
                <button
                  type="button"
                  className="item-remove"
                  onClick={() => handleRemoveTagFile(file)}
                  aria-label={`${file.name} 삭제`}
                >
                  ×
                </button>
              </div>
              {result === 'loading' && <p>인식 중...</p>}
              {result === 'error' && <p className="banner banner-error">인식에 실패했습니다.</p>}
              {result && result !== 'loading' && result !== 'error' &&
                (isTagVerifiedAgainstInvoice(result, items) ? (
                  <p className="banner banner-success">적합</p>
                ) : (
                  <p className="banner banner-warning">
                    부적합
                    <span className="banner-reason"> — {explainTagRejection(result, items)}</span>
                  </p>
                ))}
            </div>
          )
        })}
      </div>
      <button
        className="btn btn-primary"
        onClick={handleSave}
        disabled={saving || !canSave}
        style={{ width: '100%', marginTop: 16 }}
      >
        {saving ? '저장 중...' : `저장 (${items.length}건)`}
      </button>
    </div>
  )
}
