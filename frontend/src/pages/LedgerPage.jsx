import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { createMaterialLedger } from '../api.js'

export default function LedgerPage() {
  const location = useLocation()
  const invoiceIds = location.state?.invoiceIds ?? []
  const [inspector, setInspector] = useState('')
  const [supervisor, setSupervisor] = useState('')
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setWarning('')
    setGenerating(true)
    try {
      const { blob, warnings, filename } = await createMaterialLedger(invoiceIds, inspector, supervisor)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename || '주요자재검사및수불부.xlsx'
      link.click()
      URL.revokeObjectURL(url)
      if (warnings) {
        setWarning(warnings)
      }
    } catch (err) {
      setError(err.message || '수불부 생성에 실패했습니다')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="page">
      <h1>주요자재 검사 및 수불부 생성</h1>
      <form className="card" onSubmit={handleSubmit}>
        {invoiceIds.length > 0 ? (
          <p className="banner banner-success">검색에서 선택한 {invoiceIds.length}건으로 수불부를 생성합니다.</p>
        ) : (
          <p className="banner banner-warning">
            검색 화면에서 항목을 선택한 뒤 "선택 항목으로 수불부 생성" 버튼으로 들어와주세요.
          </p>
        )}
        <div className="field">
          <label>검수자</label>
          <input className="input" value={inspector} onChange={(e) => setInspector(e.target.value)} />
        </div>
        <div className="field">
          <label>담당감리원</label>
          <input className="input" value={supervisor} onChange={(e) => setSupervisor(e.target.value)} />
        </div>
        <button
          className="btn btn-primary"
          type="submit"
          disabled={generating || invoiceIds.length === 0}
          style={{ width: '100%' }}
        >
          {generating ? '생성 중...' : '수불부 생성'}
        </button>
      </form>
      {error && <p className="banner banner-error">{error}</p>}
      {warning && <p className="banner banner-warning">{warning}</p>}
    </div>
  )
}
