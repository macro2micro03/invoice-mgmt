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

const cellStyle = { border: '1px solid #ccc', padding: '4px 8px', whiteSpace: 'nowrap' }

export default function SearchPage() {
  const [vendor, setVendor] = useState('')
  const [materialType, setMaterialType] = useState('')
  const [results, setResults] = useState([])
  const navigate = useNavigate()

  async function handleSearch() {
    const data = await searchInvoices({ vendor, material_type: materialType })
    setResults(data)
  }

  return (
    <div style={{ padding: 16 }}>
      <h1>검색</h1>
      <input placeholder="거래처" value={vendor} onChange={(e) => setVendor(e.target.value)} />
      <input placeholder="자재종류" value={materialType} onChange={(e) => setMaterialType(e.target.value)} />
      <button onClick={handleSearch}>검색</button>
      <div style={{ overflowX: 'auto', marginTop: 12 }}>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              {COLUMNS.map(([key, label]) => (
                <th key={key} style={{ ...cellStyle, textAlign: 'left', background: '#f2f2f2' }}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((item) => (
              <tr key={item.id} onClick={() => navigate(`/invoices/${item.id}`)} style={{ cursor: 'pointer' }}>
                {COLUMNS.map(([key]) => (
                  <td key={key} style={cellStyle}>
                    {item[key] ?? ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
