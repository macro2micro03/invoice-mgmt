import { useState } from 'react'
import { sendEmailWithAttachment } from '../api.js'

// 발신 Gmail 주소/받는 사람은 다음에 또 입력하기 번거로우니 브라우저에
// 기억해 둔다. 앱 비밀번호는 민감한 값이라 저장하지 않고 매번 새로 입력받는다.
const STORAGE_KEY = 'emailSendDefaults'

function loadDefaults() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

export default function EmailSendCard({ blob, filename, defaultSubject }) {
  const defaults = loadDefaults()
  const [to, setTo] = useState(defaults.to || '')
  const [smtpEmail, setSmtpEmail] = useState(defaults.smtpEmail || '')
  const [smtpAppPassword, setSmtpAppPassword] = useState('')
  const [subject, setSubject] = useState(defaultSubject)
  const [body, setBody] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)

  if (!blob) return null

  async function handleSend(event) {
    event.preventDefault()
    setError('')
    setSent(false)
    setSending(true)
    try {
      await sendEmailWithAttachment({ blob, filename, to, smtpEmail, smtpAppPassword, subject, body })
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ to, smtpEmail }))
      setSent(true)
    } catch (err) {
      setError(err.message || '이메일 발송에 실패했습니다')
    } finally {
      setSending(false)
    }
  }

  return (
    <form className="card" onSubmit={handleSend} style={{ marginTop: 16 }}>
      <p className="field-group-label">이메일로 보내기</p>
      <div className="field">
        <label>받는 사람 (여러 명은 쉼표로 구분)</label>
        <input className="input" value={to} onChange={(e) => setTo(e.target.value)} required />
      </div>
      <div className="field">
        <label>보내는 Gmail 주소</label>
        <input
          className="input"
          type="email"
          value={smtpEmail}
          onChange={(e) => setSmtpEmail(e.target.value)}
          required
        />
      </div>
      <div className="field">
        <label>Gmail 앱 비밀번호</label>
        <input
          className="input"
          type="password"
          value={smtpAppPassword}
          onChange={(e) => setSmtpAppPassword(e.target.value)}
          placeholder="계정 비밀번호가 아닌, Google 계정에서 발급받은 앱 비밀번호"
          required
        />
      </div>
      <div className="field">
        <label>제목</label>
        <input className="input" value={subject} onChange={(e) => setSubject(e.target.value)} required />
      </div>
      <div className="field">
        <label>본문 (선택)</label>
        <textarea className="input" value={body} onChange={(e) => setBody(e.target.value)} rows={3} />
      </div>
      <button className="btn btn-primary" type="submit" disabled={sending} style={{ width: '100%' }}>
        {sending ? '보내는 중...' : `${filename} 첨부해서 보내기`}
      </button>
      {sent && <p className="banner banner-success">발송했습니다.</p>}
      {error && <p className="banner banner-error">{error}</p>}
    </form>
  )
}
