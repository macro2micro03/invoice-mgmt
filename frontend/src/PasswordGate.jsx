import { useEffect, useState } from 'react'

export default function PasswordGate({ children }) {
  const [checking, setChecking] = useState(true)
  const [unlocked, setUnlocked] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [verifying, setVerifying] = useState(false)

  useEffect(() => {
    setUnlocked(!!sessionStorage.getItem('appPassword'))
    setChecking(false)
  }, [])

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setVerifying(true)
    const API_BASE = import.meta.env.VITE_API_BASE || ''
    try {
      const response = await fetch(`${API_BASE}/invoices`, {
        headers: { 'X-App-Password': password },
      })
      if (response.ok) {
        sessionStorage.setItem('appPassword', password)
        setUnlocked(true)
      } else {
        setError('비밀번호가 올바르지 않습니다')
      }
    } catch (err) {
      setError('서버에 연결할 수 없습니다')
    } finally {
      setVerifying(false)
    }
  }

  if (checking) return null
  if (unlocked) return children

  return (
    <div className="page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ width: '100%', maxWidth: 320 }}>
        <h1 style={{ textAlign: 'center' }}>비밀번호 입력</h1>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="비밀번호"
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={verifying} style={{ width: '100%' }}>
            {verifying ? '확인 중...' : '확인'}
          </button>
        </form>
        {error && <p className="banner banner-error">{error}</p>}
      </div>
    </div>
  )
}
