import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { runOcr } from '../api.js'

export default function CapturePage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [failedFile, setFailedFile] = useState(null)
  const navigate = useNavigate()

  async function handleFileChange(event) {
    const file = event.target.files[0]
    if (!file) return
    setLoading(true)
    setError('')
    setFailedFile(null)
    try {
      const { records } = await runOcr(file)
      navigate('/edit', { state: { records, photoFile: file } })
    } catch (err) {
      // 실패 시 안내 없이 빈 화면으로 바로 넘어가면 사용자가 무슨 일이
      // 있었는지 알 수 없다 — 여기 머물러서 원인을 보여주고, 필요하면
      // 직접 입력 화면으로 넘어갈지 사용자가 선택하게 한다.
      setError(err.message === 'OCR 요청 실패' || err.message?.includes('Failed to fetch')
        ? '서버에 연결하지 못했습니다. 네트워크(사내망 차단 등)를 확인하거나 잠시 후 다시 시도해주세요.'
        : `인식에 실패했습니다: ${err.message || '알 수 없는 오류'}`)
      setFailedFile(file)
    } finally {
      setLoading(false)
    }
  }

  function handleManualEntry() {
    navigate('/edit', { state: { records: [{}], photoFile: failedFile } })
  }

  return (
    <div className="page">
      <h1>송장 촬영</h1>
      <div className="card">
        <div className="field">
          <label>송장 사진 또는 PDF</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <label className="btn btn-primary photo-picker-add">
              📷 촬영
              <input
                className="photo-picker-input"
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleFileChange}
              />
            </label>
            <label className="btn btn-secondary photo-picker-add">
              📁 파일 선택
              <input
                className="photo-picker-input"
                type="file"
                accept="image/*,application/pdf"
                onChange={handleFileChange}
              />
            </label>
          </div>
        </div>
        {loading && <p className="banner banner-success">인식 중...</p>}
        {error && <p className="banner banner-error">{error}</p>}
        {failedFile && (
          <button type="button" className="btn btn-secondary" style={{ width: '100%', marginTop: 8 }} onClick={handleManualEntry}>
            직접 입력하기
          </button>
        )}
      </div>
    </div>
  )
}
