# 모바일 앱 스타일 시각 리디자인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 프론트엔드의 모든 페이지(`App`, `PasswordGate`, `CapturePage`, `EditPage`, `SearchPage`, `DetailPage`, `ReportPage`)를 순수 CSS 전역 스타일시트 하나로 통일해, 페이지 구조/라우팅/로직 변경 없이 깔끔하고 미니멀한 모바일 앱 느낌으로 바꾼다.

**Architecture:** `frontend/src/styles.css` 하나에 CSS 변수(디자인 토큰)와 공통 클래스(`.btn`, `.input`, `.card`, `.page`, `.nav`, `.banner-*`, `.table`)를 정의하고, 각 페이지 컴포넌트의 inline `style={{...}}`를 이 클래스들로 교체한다. 새 npm 의존성은 추가하지 않는다.

**Tech Stack:** React, Vite, 순수 CSS (변수 기반, 프레임워크 없음)

## Global Constraints

- 브랜드 색상은 기존 PWA manifest의 `#1f6feb`(파란색)를 그대로 사용한다 (`frontend/vite.config.js`의 `theme_color`).
- 페이지 구조, 라우팅, 상태 관리, API 호출 로직은 전혀 변경하지 않는다 — 오직 JSX의 `className`/마크업 구조와 CSS만 바꾼다.
- 하단 탭 네비게이션 추가, 다크모드, 아이콘 세트, Tailwind 등 새 패키지 도입은 범위 밖이다.
- 버튼/입력란의 터치 영역은 최소 높이 44px을 확보한다.
- 이 작업은 순수 CSS/마크업 변경이라 자동화된 단위 테스트를 추가하지 않는다 — 대신 매 태스크마다 `npm run build`로 빌드 통과를 확인하고, 마지막 태스크에서 모바일 뷰포트 스크린샷으로 전체 페이지를 시각 검증한다.

---

### Task 1: 전역 스타일시트 작성 및 로드

**Files:**
- Create: `frontend/src/styles.css`
- Modify: `frontend/src/main.jsx`

**Interfaces:**
- Produces: CSS 변수 (`--color-primary`, `--color-bg`, `--color-surface`, `--color-text`, `--color-text-muted`, `--color-border`, `--color-success-bg`, `--color-success-text`, `--color-warning-bg`, `--color-warning-text`, `--color-error-bg`, `--color-error-text`, `--radius-sm`, `--radius-md`, `--radius-lg`, `--space-xs`, `--space-sm`, `--space-md`, `--space-lg`, `--shadow-sm`, `--shadow-md`, `--font-family`)와 공통 클래스(`.page`, `.nav`, `.card`, `.field`, `.input`, `.select`, `.textarea`, `.btn`, `.btn-primary`, `.btn-secondary`, `.banner`, `.banner-error`, `.banner-warning`, `.banner-success`, `.table-wrap`, `.table`, `.search-bar`, `.photo-preview`) — 이후 모든 태스크가 이 클래스들을 그대로 사용한다.

- [ ] **Step 1: `frontend/src/styles.css` 생성**

```css
:root {
  --color-primary: #1f6feb;
  --color-primary-dark: #1a5cc4;
  --color-bg: #f5f6f8;
  --color-surface: #ffffff;
  --color-text: #1a1d23;
  --color-text-muted: #6b7280;
  --color-border: #e2e5ea;
  --color-success-bg: #e6f4ea;
  --color-success-text: #1e7a34;
  --color-warning-bg: #fdf3d9;
  --color-warning-text: #8a6100;
  --color-error-bg: #fde8e8;
  --color-error-text: #b91c1c;

  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;

  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;

  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.08);
  --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.1);

  --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    "Malgun Gothic", sans-serif;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: var(--font-family);
  background: var(--color-bg);
  color: var(--color-text);
}

.page {
  min-height: 100vh;
  padding: var(--space-md);
  max-width: 480px;
  margin: 0 auto;
}

.page h1 {
  font-size: 20px;
  margin: 0 0 var(--space-md);
}

.nav {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  gap: var(--space-sm);
  padding: var(--space-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.nav a {
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  text-decoration: none;
  font-weight: 600;
  font-size: 14px;
}

.nav a:hover {
  background: var(--color-bg);
  color: var(--color-primary);
}

.card {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: var(--space-md);
}

.field {
  margin-bottom: var(--space-md);
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.field label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-muted);
}

.input,
.select,
.textarea {
  min-height: 44px;
  padding: 0 var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 15px;
  background: var(--color-surface);
  color: var(--color-text);
  width: 100%;
}

.textarea {
  min-height: 88px;
  padding: var(--space-sm) var(--space-md);
}

.input:focus,
.select:focus,
.textarea:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(31, 111, 235, 0.15);
}

.btn {
  min-height: 44px;
  padding: 0 var(--space-lg);
  border-radius: var(--radius-sm);
  font-size: 15px;
  font-weight: 700;
  border: 1px solid transparent;
  cursor: pointer;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--color-primary);
  color: #ffffff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-dark);
}

.btn-secondary {
  background: var(--color-surface);
  border-color: var(--color-border);
  color: var(--color-text);
}

.banner {
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-sm);
  margin-top: var(--space-md);
  font-size: 14px;
}

.banner-error {
  background: var(--color-error-bg);
  color: var(--color-error-text);
}

.banner-warning {
  background: var(--color-warning-bg);
  color: var(--color-warning-text);
}

.banner-success {
  background: var(--color-success-bg);
  color: var(--color-success-text);
}

.table-wrap {
  overflow-x: auto;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  background: var(--color-surface);
}

.table {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
}

.table th,
.table td {
  padding: var(--space-sm) var(--space-md);
  white-space: nowrap;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
}

.table th {
  background: var(--color-bg);
  color: var(--color-text-muted);
  font-weight: 600;
}

.table tbody tr {
  cursor: pointer;
}

.table tbody tr:hover {
  background: var(--color-bg);
}

.search-bar {
  display: flex;
  gap: var(--space-sm);
  margin-bottom: var(--space-md);
  flex-wrap: wrap;
}

.search-bar .input {
  flex: 1;
  min-width: 120px;
}

.photo-preview {
  max-width: 100%;
  border-radius: var(--radius-md);
  margin-bottom: var(--space-md);
  display: block;
}
```

- [ ] **Step 2: `frontend/src/main.jsx`에서 전역 스타일시트 로드**

`frontend/src/main.jsx`의 현재 전체 내용:

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
```

아래 내용으로 교체 (`import './styles.css'` 한 줄 추가):

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
```

- [ ] **Step 3: 빌드 확인**

Run: `cd frontend && npm run build`
Expected: 에러 없이 빌드 성공 (아직 페이지들은 새 클래스를 안 쓰므로 화면은 기존과 동일하게 보임 — 이 태스크는 스타일시트 준비만)

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/styles.css frontend/src/main.jsx
git commit -m "feat: 모바일 앱 스타일 디자인 토큰 및 공통 CSS 클래스 추가"
```

---

### Task 2: `App.jsx` 네비게이션 + `PasswordGate.jsx` 리디자인

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/PasswordGate.jsx`

**Interfaces:**
- Consumes: Task 1에서 만든 `.nav`, `.page`, `.card`, `.field`, `.input`, `.btn`, `.btn-primary`, `.banner`, `.banner-error` 클래스 (전역 로드되어 있으므로 import 불필요)

- [ ] **Step 1: `App.jsx`의 상단 네비게이션을 `.nav` 클래스로 교체**

`frontend/src/App.jsx`의 현재 전체 내용:

```jsx
import { Link, Route, Routes } from 'react-router-dom'
import CapturePage from './pages/CapturePage.jsx'
import DetailPage from './pages/DetailPage.jsx'
import EditPage from './pages/EditPage.jsx'
import PasswordGate from './PasswordGate.jsx'
import ReportPage from './pages/ReportPage.jsx'
import SearchPage from './pages/SearchPage.jsx'

export default function App() {
  return (
    <PasswordGate>
      <div>
        <nav style={{ display: 'flex', gap: 12, padding: 12 }}>
          <Link to="/">촬영</Link>
          <Link to="/search">검색</Link>
          <Link to="/report">보고서 생성</Link>
        </nav>
        <Routes>
          <Route path="/" element={<CapturePage />} />
          <Route path="/edit" element={<EditPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/invoices/:id" element={<DetailPage />} />
          <Route path="/report" element={<ReportPage />} />
        </Routes>
      </div>
    </PasswordGate>
  )
}
```

아래 내용으로 교체 (nav의 `style` → `className="nav"`):

```jsx
import { Link, Route, Routes } from 'react-router-dom'
import CapturePage from './pages/CapturePage.jsx'
import DetailPage from './pages/DetailPage.jsx'
import EditPage from './pages/EditPage.jsx'
import PasswordGate from './PasswordGate.jsx'
import ReportPage from './pages/ReportPage.jsx'
import SearchPage from './pages/SearchPage.jsx'

export default function App() {
  return (
    <PasswordGate>
      <div>
        <nav className="nav">
          <Link to="/">촬영</Link>
          <Link to="/search">검색</Link>
          <Link to="/report">보고서 생성</Link>
        </nav>
        <Routes>
          <Route path="/" element={<CapturePage />} />
          <Route path="/edit" element={<EditPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/invoices/:id" element={<DetailPage />} />
          <Route path="/report" element={<ReportPage />} />
        </Routes>
      </div>
    </PasswordGate>
  )
}
```

- [ ] **Step 2: `PasswordGate.jsx`를 카드형 중앙 정렬 레이아웃으로 교체**

`frontend/src/PasswordGate.jsx`의 현재 전체 내용:

```jsx
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
    <div style={{ padding: 16 }}>
      <h1>비밀번호 입력</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="비밀번호"
        />
        <button type="submit" disabled={verifying}>
          {verifying ? '확인 중...' : '확인'}
        </button>
      </form>
      {error && <p style={{ color: 'red' }}>{error}</p>}
    </div>
  )
}
```

아래 내용으로 전체 교체:

```jsx
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
```

- [ ] **Step 3: 빌드 확인**

Run: `cd frontend && npm run build`
Expected: 에러 없이 빌드 성공

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/App.jsx frontend/src/PasswordGate.jsx
git commit -m "feat: 상단 네비게이션과 비밀번호 화면을 모바일 앱 스타일로 리디자인"
```

---

### Task 3: `CapturePage.jsx` + `EditPage.jsx` 리디자인

**Files:**
- Modify: `frontend/src/pages/CapturePage.jsx`
- Modify: `frontend/src/pages/EditPage.jsx`

**Interfaces:**
- Consumes: Task 1의 `.page`, `.card`, `.field`, `.input`, `.btn`, `.btn-primary`, `.banner`, `.banner-error`, `.banner-success` 클래스

- [ ] **Step 1: `CapturePage.jsx` 리디자인**

`frontend/src/pages/CapturePage.jsx`의 현재 전체 내용:

```jsx
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
```

아래 내용으로 전체 교체:

```jsx
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
```

- [ ] **Step 2: `EditPage.jsx` 리디자인**

`frontend/src/pages/EditPage.jsx`의 현재 전체 내용:

```jsx
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { createInvoice } from '../api.js'

const FIELD_DEFS = [
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

export default function EditPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const initialFields = location.state?.fields || {}
  const photoFile = location.state?.photoFile || null
  const [fields, setFields] = useState(initialFields)
  const [saving, setSaving] = useState(false)

  function handleChange(key, value) {
    setFields((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await createInvoice(fields, photoFile)
      navigate('/search')
    } catch (err) {
      alert('저장에 실패했습니다. 다시 시도해주세요.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: 16 }}>
      <h1>내용 확인 및 수정</h1>
      {FIELD_DEFS.map(([key, label]) => (
        <div key={key} style={{ marginBottom: 8 }}>
          <label>
            {label}
            <input
              type="text"
              value={fields[key] || ''}
              onChange={(e) => handleChange(key, e.target.value)}
              style={{ display: 'block', width: '100%' }}
            />
          </label>
        </div>
      ))}
      <button onClick={handleSave} disabled={saving || !fields.material_type}>
        {saving ? '저장 중...' : '저장'}
      </button>
    </div>
  )
}
```

아래 내용으로 전체 교체:

```jsx
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { createInvoice } from '../api.js'

const FIELD_DEFS = [
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

export default function EditPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const initialFields = location.state?.fields || {}
  const photoFile = location.state?.photoFile || null
  const [fields, setFields] = useState(initialFields)
  const [saving, setSaving] = useState(false)

  function handleChange(key, value) {
    setFields((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await createInvoice(fields, photoFile)
      navigate('/search')
    } catch (err) {
      alert('저장에 실패했습니다. 다시 시도해주세요.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page">
      <h1>내용 확인 및 수정</h1>
      <div className="card">
        {FIELD_DEFS.map(([key, label]) => (
          <div key={key} className="field">
            <label>{label}</label>
            <input
              className="input"
              type="text"
              value={fields[key] || ''}
              onChange={(e) => handleChange(key, e.target.value)}
            />
          </div>
        ))}
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saving || !fields.material_type}
          style={{ width: '100%' }}
        >
          {saving ? '저장 중...' : '저장'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 빌드 확인**

Run: `cd frontend && npm run build`
Expected: 에러 없이 빌드 성공

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/pages/CapturePage.jsx frontend/src/pages/EditPage.jsx
git commit -m "feat: 촬영/수정 화면을 모바일 앱 스타일로 리디자인"
```

---

### Task 4: `SearchPage.jsx` + `DetailPage.jsx` 리디자인

**Files:**
- Modify: `frontend/src/pages/SearchPage.jsx`
- Modify: `frontend/src/pages/DetailPage.jsx`

**Interfaces:**
- Consumes: Task 1의 `.page`, `.card`, `.field`, `.input`, `.btn`, `.btn-primary`, `.search-bar`, `.table-wrap`, `.table`, `.photo-preview` 클래스

이 태스크에서는 검색 결과 표를 리스트 카드가 아니라 **스크롤 가능한 표(`.table-wrap`/`.table`)**로 스타일링한다 — 현재 구현이 다중 컬럼 표 형태라 표 구조를 유지하는 것이 실제 데이터(11개 컬럼)를 보여주기에 적합하고, "구조 변경 없음" 제약과도 맞는다.

- [ ] **Step 1: `SearchPage.jsx` 리디자인**

`frontend/src/pages/SearchPage.jsx`의 현재 전체 내용:

```jsx
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
```

아래 내용으로 전체 교체:

```jsx
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
  const [materialType, setMaterialType] = useState('')
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
```

- [ ] **Step 2: `DetailPage.jsx` 리디자인**

`frontend/src/pages/DetailPage.jsx`의 현재 전체 내용:

```jsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getInvoice, updateInvoice } from '../api.js'

const FIELD_DEFS = [
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

export default function DetailPage() {
  const { id } = useParams()
  const [invoice, setInvoice] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getInvoice(id).then(setInvoice)
  }, [id])

  if (!invoice) return <p style={{ padding: 16 }}>불러오는 중...</p>

  function handleChange(key, value) {
    setInvoice((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await updateInvoice(id, invoice)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: 16 }}>
      <h1>상세/수정</h1>
      {invoice.photo_path && (
        <img src={`/storage/${invoice.photo_path}`} alt="원본 사진" style={{ maxWidth: '100%' }} />
      )}
      {FIELD_DEFS.map(([key, label]) => (
        <div key={key} style={{ marginBottom: 8 }}>
          <label>
            {label}
            <input
              type="text"
              value={invoice[key] || ''}
              onChange={(e) => handleChange(key, e.target.value)}
              style={{ display: 'block', width: '100%' }}
            />
          </label>
        </div>
      ))}
      <button onClick={handleSave} disabled={saving}>
        {saving ? '저장 중...' : '수정 저장'}
      </button>
    </div>
  )
}
```

아래 내용으로 전체 교체:

```jsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getInvoice, updateInvoice } from '../api.js'

const FIELD_DEFS = [
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

export default function DetailPage() {
  const { id } = useParams()
  const [invoice, setInvoice] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getInvoice(id).then(setInvoice)
  }, [id])

  if (!invoice)
    return (
      <div className="page">
        <p>불러오는 중...</p>
      </div>
    )

  function handleChange(key, value) {
    setInvoice((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await updateInvoice(id, invoice)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page">
      <h1>상세/수정</h1>
      <div className="card">
        {invoice.photo_path && (
          <img className="photo-preview" src={`/storage/${invoice.photo_path}`} alt="원본 사진" />
        )}
        {FIELD_DEFS.map(([key, label]) => (
          <div key={key} className="field">
            <label>{label}</label>
            <input
              className="input"
              type="text"
              value={invoice[key] || ''}
              onChange={(e) => handleChange(key, e.target.value)}
            />
          </div>
        ))}
        <button className="btn btn-primary" onClick={handleSave} disabled={saving} style={{ width: '100%' }}>
          {saving ? '저장 중...' : '수정 저장'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 빌드 확인**

Run: `cd frontend && npm run build`
Expected: 에러 없이 빌드 성공

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/pages/SearchPage.jsx frontend/src/pages/DetailPage.jsx
git commit -m "feat: 검색/상세 화면을 모바일 앱 스타일로 리디자인"
```

---

### Task 5: `ReportPage.jsx` 리디자인

**Files:**
- Modify: `frontend/src/pages/ReportPage.jsx`

**Interfaces:**
- Consumes: Task 1의 `.page`, `.card`, `.field`, `.input`, `.select`, `.btn`, `.btn-primary`, `.banner`, `.banner-error`, `.banner-warning` 클래스

- [ ] **Step 1: `ReportPage.jsx` 리디자인**

`frontend/src/pages/ReportPage.jsx`의 현재 전체 내용:

```jsx
import { useState } from 'react'
import { createMaterialInspectionReport } from '../api.js'

export default function ReportPage() {
  const [projectName, setProjectName] = useState('')
  const [workType, setWorkType] = useState('건축')
  const [materialType, setMaterialType] = useState('')
  const [sender, setSender] = useState('')
  const [receiver, setReceiver] = useState('')
  const [files, setFiles] = useState([])
  const [topPhotos, setTopPhotos] = useState([])
  const [bottomPhotos, setBottomPhotos] = useState([])
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [generating, setGenerating] = useState(false)

  function handleFilesChange(event) {
    setFiles(Array.from(event.target.files))
  }

  function handleTopPhotosChange(event) {
    setTopPhotos(Array.from(event.target.files))
  }

  function handleBottomPhotosChange(event) {
    setBottomPhotos(Array.from(event.target.files))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setWarning('')
    setGenerating(true)
    try {
      const { blob, warnings } = await createMaterialInspectionReport(
        {
          project_name: projectName,
          work_type: workType,
          material_type: materialType,
          sender,
          receiver,
        },
        files,
        topPhotos,
        bottomPhotos,
      )
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `자재검수요청서-${materialType || '자재'}.xlsx`
      link.click()
      URL.revokeObjectURL(url)
      if (warnings) {
        setWarning(warnings)
      }
    } catch (err) {
      setError(err.message || '보고서 생성에 실패했습니다')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div style={{ padding: 16 }}>
      <h1>자재검수요청서 생성</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label>
            공사명
            <input value={projectName} onChange={(e) => setProjectName(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>
            공종
            <select value={workType} onChange={(e) => setWorkType(e.target.value)}>
              <option value="건축">건축</option>
              <option value="토목">토목</option>
              <option value="기계">기계</option>
              <option value="전기">전기</option>
            </select>
          </label>
        </div>
        <div>
          <label>
            자재종류
            <input value={materialType} onChange={(e) => setMaterialType(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>
            발신자(현장대리인)
            <input value={sender} onChange={(e) => setSender(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>
            수신자(총괄관리원)
            <input value={receiver} onChange={(e) => setReceiver(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>
            송장 갑지 파일 (PDF 또는 이미지, 여러 장 가능)
            <input type="file" accept="application/pdf,image/*" multiple onChange={handleFilesChange} required />
          </label>
        </div>
        <div>
          <label>
            사진대지 상단 사진 (선택, 여러 장 가능)
            <input type="file" accept="image/*" multiple onChange={handleTopPhotosChange} />
          </label>
        </div>
        <div>
          <label>
            사진대지 하단 사진 (선택, 여러 장 가능)
            <input type="file" accept="image/*" multiple onChange={handleBottomPhotosChange} />
          </label>
        </div>
        <button type="submit" disabled={generating || files.length === 0}>
          {generating ? '생성 중...' : '보고서 생성'}
        </button>
      </form>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {warning && <p style={{ color: '#b8860b' }}>{warning}</p>}
    </div>
  )
}
```

아래 내용으로 전체 교체:

```jsx
import { useState } from 'react'
import { createMaterialInspectionReport } from '../api.js'

export default function ReportPage() {
  const [projectName, setProjectName] = useState('')
  const [workType, setWorkType] = useState('건축')
  const [materialType, setMaterialType] = useState('')
  const [sender, setSender] = useState('')
  const [receiver, setReceiver] = useState('')
  const [files, setFiles] = useState([])
  const [topPhotos, setTopPhotos] = useState([])
  const [bottomPhotos, setBottomPhotos] = useState([])
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [generating, setGenerating] = useState(false)

  function handleFilesChange(event) {
    setFiles(Array.from(event.target.files))
  }

  function handleTopPhotosChange(event) {
    setTopPhotos(Array.from(event.target.files))
  }

  function handleBottomPhotosChange(event) {
    setBottomPhotos(Array.from(event.target.files))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setWarning('')
    setGenerating(true)
    try {
      const { blob, warnings } = await createMaterialInspectionReport(
        {
          project_name: projectName,
          work_type: workType,
          material_type: materialType,
          sender,
          receiver,
        },
        files,
        topPhotos,
        bottomPhotos,
      )
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `자재검수요청서-${materialType || '자재'}.xlsx`
      link.click()
      URL.revokeObjectURL(url)
      if (warnings) {
        setWarning(warnings)
      }
    } catch (err) {
      setError(err.message || '보고서 생성에 실패했습니다')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="page">
      <h1>자재검수요청서 생성</h1>
      <form className="card" onSubmit={handleSubmit}>
        <div className="field">
          <label>공사명</label>
          <input className="input" value={projectName} onChange={(e) => setProjectName(e.target.value)} required />
        </div>
        <div className="field">
          <label>공종</label>
          <select className="select" value={workType} onChange={(e) => setWorkType(e.target.value)}>
            <option value="건축">건축</option>
            <option value="토목">토목</option>
            <option value="기계">기계</option>
            <option value="전기">전기</option>
          </select>
        </div>
        <div className="field">
          <label>자재종류</label>
          <input className="input" value={materialType} onChange={(e) => setMaterialType(e.target.value)} required />
        </div>
        <div className="field">
          <label>발신자(현장대리인)</label>
          <input className="input" value={sender} onChange={(e) => setSender(e.target.value)} required />
        </div>
        <div className="field">
          <label>수신자(총괄관리원)</label>
          <input className="input" value={receiver} onChange={(e) => setReceiver(e.target.value)} required />
        </div>
        <div className="field">
          <label>송장 갑지 파일 (PDF 또는 이미지, 여러 장 가능)</label>
          <input
            className="input"
            type="file"
            accept="application/pdf,image/*"
            multiple
            onChange={handleFilesChange}
            required
          />
        </div>
        <div className="field">
          <label>사진대지 상단 사진 (선택, 여러 장 가능)</label>
          <input className="input" type="file" accept="image/*" multiple onChange={handleTopPhotosChange} />
        </div>
        <div className="field">
          <label>사진대지 하단 사진 (선택, 여러 장 가능)</label>
          <input className="input" type="file" accept="image/*" multiple onChange={handleBottomPhotosChange} />
        </div>
        <button
          className="btn btn-primary"
          type="submit"
          disabled={generating || files.length === 0}
          style={{ width: '100%' }}
        >
          {generating ? '생성 중...' : '보고서 생성'}
        </button>
      </form>
      {error && <p className="banner banner-error">{error}</p>}
      {warning && <p className="banner banner-warning">{warning}</p>}
    </div>
  )
}
```

- [ ] **Step 2: 빌드 확인**

Run: `cd frontend && npm run build`
Expected: 에러 없이 빌드 성공

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/pages/ReportPage.jsx
git commit -m "feat: 자재검수요청서 생성 화면을 모바일 앱 스타일로 리디자인"
```

---

### Task 6: 전체 페이지 모바일 뷰포트 시각 검증

**Files:**
- 없음 (검증 전용 태스크, 코드 변경 없음)

**Interfaces:**
- Consumes: Task 1~5에서 리디자인된 모든 페이지

- [ ] **Step 1: 개발 서버 기동 및 모바일 뷰포트 설정**

Vite 개발 서버를 실행하고(`cd frontend && npm run dev`), 브라우저 프리뷰를 모바일 뷰포트(375×812)로 설정한다.

- [ ] **Step 2: 각 페이지 스크린샷으로 확인**

아래 경로들을 순서대로 접속해 스크린샷을 찍고, 다음을 확인한다:
- `/` (촬영): 카드 안에 파일 입력이 깔끔하게 들어가 있는지
- `/search` (검색): 검색창/버튼이 정렬되어 있고, 표가 카드형 컨테이너 안에서 가로 스크롤되는지
- `/report` (보고서 생성): 모든 필드가 카드 안에 세로로 정렬되고, 버튼이 전체 너비로 눈에 띄는지
- 비밀번호 게이트 화면(세션스토리지의 `appPassword`를 지우고 새로고침해서 확인): 중앙 정렬된 카드로 보이는지

각 화면에서 버튼/입력란이 터치하기에 충분히 커 보이는지, 상단 네비게이션이 스크롤해도 고정되어 있는지 확인한다.

- [ ] **Step 3: 프로덕션 빌드 최종 확인**

Run: `cd frontend && npm run build`
Expected: 에러 없이 빌드 성공

- [ ] **Step 4: 배포 (선택 — 사용자가 원할 경우)**

`master` 브랜치에 커밋된 변경 사항을 `git push origin master`로 푸시하면 Vercel이 자동으로 재배포한다. 실제 배포된 URL(`https://invoice-mgmt-rho.vercel.app/`)에서 최종적으로 다시 한번 확인한다.

---

## 자체 점검 결과

- **스펙 커버리지**: 설계 문서의 디자인 토큰(색상/간격/둥근모서리/그림자), 공통 클래스 목록, 페이지별 적용 방식(App/PasswordGate/Capture/Edit/Search/Detail/Report) 전부 각 태스크에 매핑됨. `SearchPage`는 스펙의 "`.list-item`" 표현 대신 기존 표 구조를 유지하는 `.table`/`.table-wrap`로 구현 — 표 형태의 다중 컬럼 데이터라는 실제 코드 현황에 더 적합하고, "구조 변경 없음" 원칙에 부합하므로 이 편차는 의도된 것으로 반영함.
- **플레이스홀더 스캔**: 모든 스텝에 실제 전체 파일 내용과 명령어 포함, "TODO"/"나중에" 등 표현 없음.
- **타입/클래스 일관성**: Task 1에서 정의한 클래스명(`.page`, `.card`, `.field`, `.input`, `.select`, `.btn`, `.btn-primary`, `.banner-error`, `.banner-warning`, `.table-wrap`, `.table`, `.search-bar`, `.photo-preview`)이 Task 2~5에서 정확히 동일한 이름으로 사용됨.
