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

const GRADE_BY_PREFIX = { SHD: 'SD500', UHD: 'SD600' }

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
// 재계산할 수 있도록 이식한 헬퍼. 저장 시 최종 판정은 서버가 다시 계산하지만,
// 화면에 보이는 배너가 최신 spec/택 값을 반영하도록 로컬에서도 즉시 재계산한다.
function matchTagToSpec(tagGrade, tagDiameter, spec) {
  const [specGrade, specDiameter] = parseSpecGradeDiameter(spec)
  const normTagGrade = normalizeGrade(tagGrade)
  const normTagDiameter = normalizeDiameter(tagDiameter)
  if (specGrade === null || normTagGrade === null || normTagDiameter === null) return null
  if (specGrade === normTagGrade && specDiameter === normTagDiameter) return 'matched'
  return 'mismatched'
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
    tag_site_name: '',
    tag_location: '',
    tag_diameter: '',
    tag_grade: '',
    tag_length: '',
    tag_quantity: '',
    tag_shape: '',
    tag_match_status: null,
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
  const [saving, setSaving] = useState(false)
  const [tagLoadingIndex, setTagLoadingIndex] = useState(null)

  function handleCommonChange(key, value) {
    setCommon((prev) => ({ ...prev, [key]: value }))
  }

  function handleItemChange(index, key, value) {
    setItems((prev) =>
      prev.map((item, i) => {
        if (i !== index) return item
        const updated = { ...item, [key]: value }
        if (key === 'spec' || key === 'tag_grade' || key === 'tag_diameter') {
          updated.tag_match_status = matchTagToSpec(updated.tag_grade, updated.tag_diameter, updated.spec)
        }
        return updated
      }),
    )
  }

  function handleRemoveItem(index) {
    setItems((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleTagPhotoChange(index, event) {
    const file = event.target.files[0]
    if (!file) return
    setTagLoadingIndex(index)
    // 재촬영이 실패하거나 결과가 도착하기 전까지 이전 사진의 판정 결과가
    // 화면에 남아있지 않도록 즉시 초기화한다.
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, tag_match_status: null } : item)))
    try {
      const result = await runTagOcr(file, items[index].spec)
      setItems((prev) =>
        prev.map((item, i) =>
          i === index
            ? {
                ...item,
                tag_site_name: result.tag_site_name || '',
                tag_location: result.tag_location || '',
                tag_diameter: result.tag_diameter || '',
                tag_grade: result.tag_grade || '',
                tag_length: result.tag_length || '',
                tag_quantity: result.tag_quantity || '',
                tag_shape: result.tag_shape || '',
                tag_match_status: result.tag_match_status,
                tagPhotoFile: file,
              }
            : item,
        ),
      )
    } catch (err) {
      alert('택 인식에 실패했습니다.')
    } finally {
      setTagLoadingIndex(null)
    }
  }

  async function handleSave() {
    setSaving(true)
    let saved = 0
    try {
      for (const item of items) {
        const { tagPhotoFile, tag_match_status, ...fields } = item
        await createInvoice({ ...common, ...fields }, photoFile, tagPhotoFile)
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
          <div className="field">
            <label>택 촬영</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <label className="btn btn-primary photo-picker-add">
                {tagLoadingIndex === index ? '인식 중...' : item.tagPhotoFile ? '📷 택 다시 촬영' : '📷 촬영'}
                <input
                  className="photo-picker-input"
                  type="file"
                  accept="image/*"
                  capture="environment"
                  onChange={(e) => handleTagPhotoChange(index, e)}
                />
              </label>
              <label className="btn btn-secondary photo-picker-add">
                📁 파일 선택
                <input
                  className="photo-picker-input"
                  type="file"
                  accept="image/*"
                  onChange={(e) => handleTagPhotoChange(index, e)}
                />
              </label>
            </div>
          </div>
          {item.tag_match_status === 'mismatched' && (
            <p className="banner banner-warning">
              택 규격({item.tag_grade} D{item.tag_diameter})이 송장 규격({item.spec})과 다릅니다
            </p>
          )}
        </div>
      ))}
      <button className="btn btn-primary" onClick={handleSave} disabled={saving || !canSave} style={{ width: '100%' }}>
        {saving ? '저장 중...' : `저장 (${items.length}건)`}
      </button>
    </div>
  )
}
