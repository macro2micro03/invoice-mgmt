import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import {
  createMaterialLedger,
  deleteLedgerEntry,
  getLedgerEntries,
  updateLedgerEntry,
} from '../api.js'
import EmailSendCard from '../components/EmailSendCard.jsx'

const MANUAL_FIELDS = [
  ['defect_qty', '불합격량'],
  ['defect_reason', '사유'],
  ['release_date', '반출일'],
  ['release_qty', '반출량'],
  ['remaining_qty', '잔량'],
  ['inspector', '검수자'],
  ['supervisor', '담당감리원'],
]

export default function LedgerPage() {
  const location = useLocation()
  const invoiceIds = location.state?.invoiceIds ?? []
  const [inspector, setInspector] = useState('')
  const [supervisor, setSupervisor] = useState('')
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [entries, setEntries] = useState([])
  const [loadingEntries, setLoadingEntries] = useState(true)
  const [generatedFile, setGeneratedFile] = useState(null)

  async function loadEntries() {
    setLoadingEntries(true)
    try {
      const data = await getLedgerEntries()
      setEntries(data)
    } catch (err) {
      setError(err.message || '수불부 목록을 불러오지 못했습니다')
    } finally {
      setLoadingEntries(false)
    }
  }

  useEffect(() => {
    loadEntries()
  }, [])

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setWarning('')
    setGenerating(true)
    setGeneratedFile(null)
    try {
      const { blob, warnings, filename } = await createMaterialLedger(invoiceIds, inspector, supervisor)
      const resolvedFilename = filename || '주요자재검사및수불부.xlsx'
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = resolvedFilename
      link.click()
      URL.revokeObjectURL(url)
      setGeneratedFile({ blob, filename: resolvedFilename })
      if (warnings) {
        setWarning(warnings)
      }
      await loadEntries()
    } catch (err) {
      setError(err.message || '수불부 생성에 실패했습니다')
    } finally {
      setGenerating(false)
    }
  }

  function handleFieldChange(invoiceId, key, value) {
    setEntries((prev) =>
      prev.map((entry) => (entry.invoice_id === invoiceId ? { ...entry, [key]: value } : entry))
    )
  }

  async function handleFieldBlur(invoiceId) {
    const entry = entries.find((row) => row.invoice_id === invoiceId)
    if (!entry) return
    try {
      await updateLedgerEntry(invoiceId, {
        defect_qty: entry.defect_qty === '' || entry.defect_qty == null ? null : Number(entry.defect_qty),
        defect_reason: entry.defect_reason || null,
        release_date: entry.release_date || null,
        release_qty: entry.release_qty === '' || entry.release_qty == null ? null : Number(entry.release_qty),
        remaining_qty:
          entry.remaining_qty === '' || entry.remaining_qty == null ? null : Number(entry.remaining_qty),
        inspector: entry.inspector || null,
        supervisor: entry.supervisor || null,
      })
    } catch (err) {
      setError(err.message || '수불부 항목 저장에 실패했습니다')
    }
  }

  async function handleExclude(invoiceId) {
    if (!window.confirm('이 항목을 수불부에서 제외하시겠습니까? 송장 기록 자체는 삭제되지 않습니다.')) return
    try {
      await deleteLedgerEntry(invoiceId)
      setEntries((prev) => prev.filter((entry) => entry.invoice_id !== invoiceId))
    } catch (err) {
      setError(err.message || '제외에 실패했습니다')
    }
  }

  return (
    <div className="page page-wide">
      <h1>주요자재 검사 및 수불부</h1>
      <form className="card" onSubmit={handleSubmit}>
        {invoiceIds.length > 0 ? (
          <p className="banner banner-success">검색에서 선택한 {invoiceIds.length}건을 수불부에 추가합니다.</p>
        ) : (
          <p className="banner banner-warning">
            검색 화면에서 항목을 선택한 뒤 "선택 항목으로 수불부 생성" 버튼으로 들어오면 새 항목을 추가할 수
            있습니다. 아래 목록만 보거나 내려받는 것은 지금도 가능합니다.
          </p>
        )}
        <div className="field">
          <label>검수자 (신규 추가 항목 기본값)</label>
          <input className="input" value={inspector} onChange={(e) => setInspector(e.target.value)} />
        </div>
        <div className="field">
          <label>담당감리원 (신규 추가 항목 기본값)</label>
          <input className="input" value={supervisor} onChange={(e) => setSupervisor(e.target.value)} />
        </div>
        <button
          className="btn btn-primary"
          type="submit"
          disabled={generating || invoiceIds.length === 0}
          style={{ width: '100%' }}
        >
          {generating ? '생성 중...' : '수불부 생성 (선택 항목 추가 + 다운로드)'}
        </button>
      </form>
      {error && <p className="banner banner-error">{error}</p>}
      {warning && <p className="banner banner-warning">{warning}</p>}
      {generatedFile && (
        <EmailSendCard blob={generatedFile.blob} filename={generatedFile.filename} defaultSubject="주요자재 검사 및 수불부" />
      )}

      <h2 style={{ fontSize: 16, margin: '24px 0 8px' }}>현재 수불부 포함 목록 ({entries.length}건)</h2>
      {loadingEntries ? (
        <p>불러오는 중...</p>
      ) : entries.length === 0 ? (
        <p className="banner banner-warning">아직 수불부에 포함된 기록이 없습니다.</p>
      ) : (
        <div className="table-wrap">
          <table className="table" style={{ textAlign: 'center' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'center' }}>연번</th>
                <th style={{ textAlign: 'center' }}>반입일</th>
                <th style={{ textAlign: 'center' }}>규격</th>
                <th style={{ textAlign: 'center' }}>반입량</th>
                {MANUAL_FIELDS.map(([key, label]) => (
                  <th
                    key={key}
                    style={{
                      textAlign: 'center',
                      ...(key === 'inspector' || key === 'supervisor' ? { minWidth: 130 } : {}),
                    }}
                  >
                    {label}
                  </th>
                ))}
                <th style={{ textAlign: 'center' }}>제외</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, index) => (
                <tr key={entry.invoice_id}>
                  <td style={{ textAlign: 'center' }}>{index + 1}</td>
                  <td style={{ textAlign: 'center' }}>{entry.delivery_date ?? ''}</td>
                  <td style={{ textAlign: 'center' }}>{entry.spec ?? ''}</td>
                  <td style={{ textAlign: 'center' }}>{entry.weight ?? ''}</td>
                  {MANUAL_FIELDS.map(([key]) => (
                    <td
                      key={key}
                      style={key === 'inspector' || key === 'supervisor' ? { minWidth: 130 } : undefined}
                    >
                      <input
                        className="input"
                        type={key.includes('date') ? 'date' : key.includes('qty') ? 'number' : 'text'}
                        value={entry[key] ?? ''}
                        onChange={(e) => handleFieldChange(entry.invoice_id, key, e.target.value)}
                        onBlur={() => handleFieldBlur(entry.invoice_id)}
                        style={{ textAlign: 'center', width: '100%' }}
                      />
                    </td>
                  ))}
                  <td style={{ textAlign: 'center' }}>
                    <button type="button" className="btn btn-danger" onClick={() => handleExclude(entry.invoice_id)}>
                      제외
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
