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
    <div className="page">
      <h1>송장 촬영</h1>
      <div className="card">
        <div className="field">
          <label>송장 사진 또는 PDF</label>
          <input
            className="input"
            type="file"
            accept="image/*,application/pdf"
            capture="environment"
            onChange={handleFileChange}
          />
        </div>
        {loading && <p className="banner banner-success">인식 중...</p>}
        {error && <p className="banner banner-error">{error}</p>}
      </div>
    </div>
  )
}
