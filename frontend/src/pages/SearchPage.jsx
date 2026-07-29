import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchInvoices } from '../api.js'

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
  const navigate = useNavigate()

  async function handleSearch() {
    const data = await searchInvoices({ vendor, material_type: materialType })
    setResults(data)
  }

  return (
    <div className="page" style={{ maxWidth: 720 }}>
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
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              {COLUMNS.map(([key, label]) => (
                <th key={key}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((item) => (
              <tr key={item.id} onClick={() => navigate(`/invoices/${item.id}`)}>
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
