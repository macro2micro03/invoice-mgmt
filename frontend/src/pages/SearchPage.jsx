import { useState } from 'react'
import { Link } from 'react-router-dom'
import { searchInvoices } from '../api.js'

export default function SearchPage() {
  const [vendor, setVendor] = useState('')
  const [materialType, setMaterialType] = useState('')
  const [results, setResults] = useState([])

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
      <ul>
        {results.map((item) => (
          <li key={item.id}>
            <Link to={`/invoices/${item.id}`}>
              {item.material_type} / {item.vendor} / {item.invoice_no}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
