import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { runOcr } from '../api.js'

export default function CapturePage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function handleFileChange(event) {
    const file = event.target.files[0]
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const fields = await runOcr(file)
      navigate('/edit', { state: { fields, photoFile: file } })
    } catch (err) {
      setError('인식에 실패했습니다. 직접 입력해주세요.')
      navigate('/edit', { state: { fields: {}, photoFile: file } })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: 16 }}>
      <h1>송장 촬영</h1>
      <input type="file" accept="image/*,application/pdf" capture="environment" onChange={handleFileChange} />
      {loading && <p>인식 중...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
    </div>
  )
}
