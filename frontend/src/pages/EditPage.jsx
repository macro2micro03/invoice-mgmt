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

// 불일치 시, 직경/강도 중 어느 쪽이 원인인지 구분해 안내 문구를 만든다.
function describeMismatch(tagGrade, tagDiameter, items) {
  const normTagGrade = normalizeGrade(tagGrade)
  const normTagDiameter = normalizeDiameter(tagDiameter)

  if (!normTagGrade && !normTagDiameter) {
    return '자재 일치 여부를 판단할 수 없습니다 — 택 사진에서 강도와 직경 글자를 읽어내지 못했습니다(자재 목록과는 무관). 택 사진이 선명하게 나오도록 다시 촬영해주세요.'
  }
  if (!normTagGrade) {
    return `자재 일치 여부를 판단할 수 없습니다 — 택 사진에서 강도(SD/SHD/UHD) 글자를 읽어내지 못했습니다(직경 D${normTagDiameter}만 인식됨, 등록된 자재와는 무관한 사진 인식 문제입니다). 택 사진이 선명하게 나오도록 다시 촬영해주세요.`
  }
  if (!normTagDiameter) {
    return `자재 일치 여부를 판단할 수 없습니다 — 택 사진에서 직경 숫자를 읽어내지 못했습니다(강도 ${normTagGrade}만 인식됨, 등록된 자재와는 무관한 사진 인식 문제입니다). 택 사진이 선명하게 나오도록 다시 촬영해주세요.`
  }

  const registered = items
    .map((item) => ({ spec: item.spec, grade: parseSpecGradeDiameter(item.spec)[0], diameter: parseSpecGradeDiameter(item.spec)[1] }))
    .filter((entry) => entry.grade !== null)

  const sameDiameter = registered.filter((entry) => entry.diameter === normTagDiameter)
  const sameGrade = registered.filter((entry) => entry.grade === normTagGrade)

  if (sameDiameter.length > 0) {
    const grades = [...new Set(sameDiameter.map((entry) => entry.grade))].join(', ')
    return `직경(D${normTagDiameter})은 일치하는 자재가 있지만 강도(${normTagGrade})가 다릅니다. 등록된 강도: ${grades}`
  }
  if (sameGrade.length > 0) {
    const diameters = [...new Set(sameGrade.map((entry) => `D${entry.diameter}`))].join(', ')
    return `강도(${normTagGrade})는 일치하는 자재가 있지만 직경(D${normTagDiameter})이 다릅니다. 등록된 직경: ${diameters}`
  }
  return `직경(D${normTagDiameter})과 강도(${normTagGrade})가 모두 일치하는 등록 자재가 없습니다.`
}

// 촬영한 택 하나를 전체 규격 목록과 비교해, 일치하는 규격이 하나라도 있으면
// 'matched'(그 규격 문자열과 함께), 하나도 없으면 'mismatched'와 불일치 사유를 반환한다.
function matchTagAgainstItems(tagGrade, tagDiameter, items) {
  const matchedSpec = items.find((item) => matchTagToSpec(tagGrade, tagDiameter, item.spec) === 'matched')
  if (matchedSpec) return { status: 'matched', spec: matchedSpec.spec, reason: null }
  return { status: 'mismatched', spec: null, reason: describeMismatch(tagGrade, tagDiameter, items) }
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

function makeTagInfo() {
  return {
    tag_site_name: '',
    tag_location: '',
    tag_diameter: '',
    tag_grade: '',
    tag_length: '',
    tag_quantity: '',
    tag_shape: '',
    tag_match_status: null,
    matchedSpec: null,
    mismatchReason: null,
    tagPhotoFile: null,
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
  const [tagInfo, setTagInfo] = useState(makeTagInfo)
  const [saving, setSaving] = useState(false)
  const [tagLoading, setTagLoading] = useState(false)

  function handleCommonChange(key, value) {
    setCommon((prev) => ({ ...prev, [key]: value }))
  }

  function handleItemChange(index, key, value) {
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, [key]: value } : item)))
    // 규격을 수정한 경우, 이미 촬영해 둔 택이 있다면 새 규격 목록 기준으로 재판정한다.
    if (key === 'spec' && tagInfo.tag_grade) {
      setItems((prev) => {
        const updated = prev.map((item, i) => (i === index ? { ...item, spec: value } : item))
        const { status, spec, reason } = matchTagAgainstItems(tagInfo.tag_grade, tagInfo.tag_diameter, updated)
        setTagInfo((prevTag) => ({ ...prevTag, tag_match_status: status, matchedSpec: spec, mismatchReason: reason }))
        return updated
      })
    }
  }

  function handleRemoveItem(index) {
    setItems((prev) => prev.filter((_, i) => i !== index))
  }

  // OCR이 강도/직경을 잘못 읽었거나 못 읽었을 때 사용자가 직접 고칠 수 있게 하고,
  // 수정 즉시 새 값 기준으로 재판정한다.
  function handleTagFieldChange(key, value) {
    setTagInfo((prev) => {
      const updated = { ...prev, [key]: value }
      const { status, spec, reason } = matchTagAgainstItems(updated.tag_grade, updated.tag_diameter, items)
      return { ...updated, tag_match_status: status, matchedSpec: spec, mismatchReason: reason }
    })
  }

  async function handleTagPhotoChange(event) {
    const file = event.target.files[0]
    if (!file) return
    setTagLoading(true)
    // 재촬영이 실패하거나 결과가 도착하기 전까지 이전 판정 결과가 남아있지 않도록 초기화한다.
    setTagInfo((prev) => ({ ...prev, tag_match_status: null, matchedSpec: null, mismatchReason: null }))
    try {
      const result = await runTagOcr(file)
      const { status, spec, reason } = matchTagAgainstItems(result.tag_grade, result.tag_diameter, items)
      setTagInfo({
        tag_site_name: result.tag_site_name || '',
        tag_location: result.tag_location || '',
        tag_diameter: result.tag_diameter || '',
        tag_grade: result.tag_grade || '',
        tag_length: result.tag_length || '',
        tag_quantity: result.tag_quantity || '',
        tag_shape: result.tag_shape || '',
        tag_match_status: status,
        matchedSpec: spec,
        mismatchReason: reason,
        tagPhotoFile: file,
      })
    } catch (err) {
      alert('택 인식에 실패했습니다.')
    } finally {
      setTagLoading(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    let saved = 0
    try {
      const { matchedSpec, tag_match_status, mismatchReason, ...tagFields } = tagInfo
      for (const item of items) {
        await createInvoice({ ...common, ...item, ...tagFields }, photoFile, tagInfo.tagPhotoFile)
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
        </div>
      ))}
      <div className="card">
        <p className="field-group-label">택 촬영</p>
        <div style={{ display: 'flex', gap: 8 }}>
          <label className="btn btn-primary photo-picker-add">
            {tagLoading ? '인식 중...' : tagInfo.tagPhotoFile ? '📷 택 다시 촬영' : '📷 촬영'}
            <input
              className="photo-picker-input"
              type="file"
              accept="image/*"
              capture="environment"
              onChange={handleTagPhotoChange}
            />
          </label>
          <label className="btn btn-secondary photo-picker-add">
            📁 파일 선택
            <input className="photo-picker-input" type="file" accept="image/*" onChange={handleTagPhotoChange} />
          </label>
        </div>
        <div className="field" style={{ marginTop: 24 }}>
          <label>강도 (자동 인식, 다르면 직접 수정)</label>
          <input
            className="input"
            type="text"
            value={tagInfo.tag_grade}
            onChange={(e) => handleTagFieldChange('tag_grade', e.target.value)}
            placeholder="예: SD400, SD500, SD600"
          />
        </div>
        <div className="field">
          <label>직경 (자동 인식, 다르면 직접 수정)</label>
          <input
            className="input"
            type="text"
            value={tagInfo.tag_diameter}
            onChange={(e) => handleTagFieldChange('tag_diameter', e.target.value)}
            placeholder="예: 10, 13, 16"
          />
        </div>
        {tagInfo.tag_match_status === 'matched' && (
          <p className="banner banner-success">
            택 규격({tagInfo.tag_grade} D{tagInfo.tag_diameter})이 일치하는 자재를 확인했습니다: {tagInfo.matchedSpec}
          </p>
        )}
        {tagInfo.tag_match_status === 'mismatched' && (
          <p className="banner banner-warning">{tagInfo.mismatchReason}</p>
        )}
      </div>
      <button className="btn btn-primary" onClick={handleSave} disabled={saving || !canSave} style={{ width: '100%' }}>
        {saving ? '저장 중...' : `저장 (${items.length}건)`}
      </button>
    </div>
  )
}
