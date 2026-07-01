import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getInvoice, updateInvoice } from '../api.js'

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

export default function DetailPage() {
  const { id } = useParams()
  const [invoice, setInvoice] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getInvoice(id).then(setInvoice)
  }, [id])

  if (!invoice) return <p style={{ padding: 16 }}>불러오는 중...</p>

  function handleChange(key, value) {
    setInvoice((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await updateInvoice(id, invoice)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: 16 }}>
      <h1>상세/수정</h1>
      {invoice.photo_path && (
        <img src={`/storage/${invoice.photo_path}`} alt="원본 사진" style={{ maxWidth: '100%' }} />
      )}
      {FIELD_DEFS.map(([key, label]) => (
        <div key={key} style={{ marginBottom: 8 }}>
          <label>
            {label}
            <input
              type="text"
              value={invoice[key] || ''}
              onChange={(e) => handleChange(key, e.target.value)}
              style={{ display: 'block', width: '100%' }}
            />
          </label>
        </div>
      ))}
      <button onClick={handleSave} disabled={saving}>
        {saving ? '저장 중...' : '수정 저장'}
      </button>
    </div>
  )
}
