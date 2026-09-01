import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { deleteInvoice, getInvoice, updateInvoice } from '../api.js'

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

const TAG_FIELD_DEFS = [
  ['tag_site_name', '택 현장명'],
  ['tag_location', '택 부재시공위치'],
  ['tag_diameter', '택 직경'],
  ['tag_grade', '택 강도'],
  ['tag_length', '택 길이'],
  ['tag_quantity', '택 수량'],
  ['tag_shape', '택 가공형상'],
]

function tagMatchLabel(status) {
  if (status === 'matched') return '일치'
  if (status === 'mismatched') return '불일치'
  if (status === 'missing') return '대응 택 없음'
  return '택 미촬영'
}

export default function DetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [invoice, setInvoice] = useState(null)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    getInvoice(id).then(setInvoice)
  }, [id])

  if (!invoice)
    return (
      <div className="page">
        <p>불러오는 중...</p>
      </div>
    )

  function handleChange(key, value) {
    setInvoice((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await updateInvoice(id, invoice)
      navigate('/search')
    } catch (err) {
      alert('저장에 실패했습니다. 다시 시도해주세요.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm('이 송장 기록을 삭제하시겠습니까? 되돌릴 수 없습니다.')) return
    setDeleting(true)
    try {
      await deleteInvoice(id)
      navigate('/search')
    } catch (err) {
      alert('삭제에 실패했습니다. 다시 시도해주세요.')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="page">
      <h1>상세/수정</h1>
      <div className="card">
        {invoice.photo_path && (
          <img className="photo-preview" src={`/storage/${invoice.photo_path}`} alt="원본 사진" />
        )}
        {invoice.tag_photo_path && (
          <img className="photo-preview" src={`/storage/${invoice.tag_photo_path}`} alt="택 사진" />
        )}
        <p className="field-group-label">
          택 대조 결과: {tagMatchLabel(invoice.tag_match_status)}
        </p>
        {invoice.tag_match_status === 'mismatched' && (
          <p className="banner banner-warning">
            택 규격({invoice.tag_grade} D{invoice.tag_diameter})이 송장 규격({invoice.spec})과 다릅니다
          </p>
        )}
        {invoice.tag_match_status === 'missing' && (
          <p className="banner banner-warning">
            이 규격({invoice.spec})에 해당하는 철근 Tag를 찾지 못했습니다 — 촬영한 택 중 일치하는 것이
            없습니다
          </p>
        )}
        {TAG_FIELD_DEFS.map(([key, label]) => (
          <div key={key} className="field">
            <label>{label}</label>
            <input className="input" type="text" value={invoice[key] || ''} readOnly disabled />
          </div>
        ))}
        {FIELD_DEFS.map(([key, label]) => (
          <div key={key} className="field">
            <label>{label}</label>
            <input
              className="input"
              type="text"
              value={invoice[key] || ''}
              onChange={(e) => handleChange(key, e.target.value)}
            />
          </div>
        ))}
        <button className="btn btn-primary" onClick={handleSave} disabled={saving} style={{ width: '100%' }}>
          {saving ? '저장 중...' : '수정 저장'}
        </button>
        <button
          className="btn btn-secondary"
          onClick={handleDelete}
          disabled={deleting}
          style={{ width: '100%', marginTop: 8 }}
        >
          {deleting ? '삭제 중...' : '삭제'}
        </button>
      </div>
    </div>
  )
}
