import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { createInvoice } from '../api.js'

const COMMON_FIELD_DEFS = [
  ['vendor', '거래처'],
  ['delivery_date', '납품일'],
  ['vehicle_no', '차량번호'],
  ['invoice_no', '송장번호'],
]

const ITEM_FIELD_DEFS = [
  ['material_type', '자재종류'],
  ['item_name', '품명'],
  ['spec', '규격'],
  ['unit', '단위'],
  ['quantity', '수량'],
  ['weight', '중량'],
  ['note', '비고'],
]

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
  const [items, setItems] = useState(() =>
    initialRecords.map((record) => ({
      material_type: record.material_type || '',
      item_name: record.item_name || '',
      spec: record.spec || '',
      unit: record.unit || '',
      quantity: record.quantity ?? '',
      weight: record.weight ?? '',
      note: record.note || '',
    })),
  )
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

  async function handleSave() {
    setSaving(true)
    let saved = 0
    try {
      for (const item of items) {
        await createInvoice({ ...common, ...item }, photoFile)
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
      <button className="btn btn-primary" onClick={handleSave} disabled={saving || !canSave} style={{ width: '100%' }}>
        {saving ? '저장 중...' : `저장 (${items.length}건)`}
      </button>
    </div>
  )
}
