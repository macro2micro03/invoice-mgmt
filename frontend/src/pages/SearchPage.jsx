import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { bulkDeleteInvoices, searchInvoices } from '../api.js'

const COLUMNS = [
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

export default function SearchPage() {
  const [vendor, setVendor] = useState('')
  const [materialType, setMaterialType] = useState('철근')
  const [results, setResults] = useState([])
  const [selectedIds, setSelectedIds] = useState([])
  const [deleting, setDeleting] = useState(false)
  const navigate = useNavigate()

  async function handleSearch() {
    const data = await searchInvoices({ vendor, material_type: materialType })
    setResults(data)
    setSelectedIds([])
  }

  function toggleSelected(id) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((existing) => existing !== id) : [...prev, id]))
  }

  function toggleSelectAll() {
    setSelectedIds((prev) => (prev.length === results.length ? [] : results.map((item) => item.id)))
  }

  async function handleBulkDelete() {
    if (selectedIds.length === 0) return
    if (!window.confirm(`선택한 ${selectedIds.length}건을 삭제하시겠습니까? 되돌릴 수 없습니다.`)) return
    setDeleting(true)
    try {
      await bulkDeleteInvoices(selectedIds)
      setResults((prev) => prev.filter((item) => !selectedIds.includes(item.id)))
      setSelectedIds([])
    } catch (err) {
      alert('삭제에 실패했습니다. 다시 시도해주세요.')
    } finally {
      setDeleting(false)
    }
  }

  const allSelected = results.length > 0 && selectedIds.length === results.length

  return (
    <div className="page page-wide">
      <h1>검색</h1>
      <div className="search-bar">
        <input className="input" placeholder="거래처" value={vendor} onChange={(e) => setVendor(e.target.value)} />
        <input
          className="input"
          placeholder="자재종류"
          value={materialType}
          onChange={(e) => setMaterialType(e.target.value)}
          disabled
        />
        <button className="btn btn-primary" onClick={handleSearch}>
          검색
        </button>
      </div>
      {selectedIds.length > 0 && (
        <div className="field">
          <button className="btn btn-secondary" onClick={handleBulkDelete} disabled={deleting}>
            {deleting ? '삭제 중...' : `선택 삭제 (${selectedIds.length})`}
          </button>
        </div>
      )}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>
                <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} aria-label="전체 선택" />
              </th>
              {COLUMNS.map(([key, label]) => (
                <th key={key}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((item) => (
              <tr key={item.id} onClick={() => navigate(`/invoices/${item.id}`)}>
                <td onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(item.id)}
                    onChange={() => toggleSelected(item.id)}
                    aria-label={`${item.id}번 선택`}
                  />
                </td>
                {COLUMNS.map(([key]) => (
                  <td key={key}>{item[key] ?? ''}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
