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

// 촬영한 철근 Tag 여러 장을 자재 목록과 1:1로 대조한다. 각 자재(규격)에
// 대해 아직 배정되지 않은 택 중 규격이 일치하는 것을 하나 찾아 배정하고,
// 끝까지 배정되지 못한 택은 "송장에 없는 규격의 택"으로 따로 반환한다.
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
  const unmatchedTagEntries = tagEntries.filter((entry) => !usedFiles.has(entry.file))
  return { itemAssignments, unmatchedTagEntries }
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

  // OCR이 강도/직경을 잘못 읽었거나 못 읽었을 때 사용자가 직접 고칠 수 있게 한다.
  function handleTagFieldEdit(file, key, value) {
    setTagResultsByFile((prev) => {
      const current = prev.get(file)
      if (!current || current === 'loading' || current === 'error') return prev
      return new Map(prev).set(file, { ...current, [key]: value })
    })
  }

  const tagEntries = tagFiles
    .map((file) => ({ file, result: tagResultsByFile.get(file) }))
    .filter((entry) => entry.result && entry.result !== 'loading' && entry.result !== 'error' && entry.result.tag_grade && entry.result.tag_diameter)
  const { itemAssignments, unmatchedTagEntries } = matchTagsToItems(items, tagEntries)

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
          const { tag_site_name, tag_location, tag_diameter, tag_grade, tag_length, tag_quantity, tag_shape } =
            assignment.result
          tagFields = { tag_site_name, tag_location, tag_diameter, tag_grade, tag_length, tag_quantity, tag_shape }
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
              <p className="banner banner-success">
                일치하는 철근 Tag를 확인했습니다: {itemAssignments[index].result.tag_grade} D
                {itemAssignments[index].result.tag_diameter}
              </p>
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
                </>
              )}
            </div>
          )
        })}
        {unmatchedTagEntries.length > 0 && (
          <p className="banner banner-warning" style={{ marginTop: 12 }}>
            다음 철근 Tag는 이 송장의 규격과 일치하지 않습니다:{' '}
            {unmatchedTagEntries.map((entry) => `${entry.result.tag_grade} D${entry.result.tag_diameter}`).join(', ')}
          </p>
        )}
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
