import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { createInvoice } from '../api.js'

const FIELD_DEFS = [
  ['material_type', '자재종류'],
  ['vendor', '거래처'],
  ['delivery_date', '납품일'],
  ['vehicle_no', '차량번호'],
  ['invoice_no', '송장번호'],
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
  const initialFields = location.state?.fields || {}
  const photoFile = location.state?.photoFile || null
  const [fields, setFields] = useState(initialFields)
  const [saving, setSaving] = useState(false)

  function handleChange(key, value) {
    setFields((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await createInvoice(fields, photoFile)
      navigate('/search')
    } catch (err) {
      alert('저장에 실패했습니다. 다시 시도해주세요.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: 16 }}>
      <h1>내용 확인 및 수정</h1>
      {FIELD_DEFS.map(([key, label]) => (
        <div key={key} style={{ marginBottom: 8 }}>
          <label>
            {label}
            <input
              type="text"
              value={fields[key] || ''}
              onChange={(e) => handleChange(key, e.target.value)}
              style={{ display: 'block', width: '100%' }}
            />
          </label>
        </div>
      ))}
      <button onClick={handleSave} disabled={saving || !fields.material_type}>
        {saving ? '저장 중...' : '저장'}
      </button>
    </div>
  )
}
