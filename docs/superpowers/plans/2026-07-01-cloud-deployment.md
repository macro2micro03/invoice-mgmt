# 클라우드 배포 (Vercel + Render) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 로컬 LAN 전용 MVP를 인터넷에서 접근 가능하게 만든다 — 프론트엔드는 Vercel, 백엔드는 Render에 배포하고, 인터넷 공개에 따른 최소 보호로 공유 비밀번호 인증을 추가한다.

**Architecture:** 백엔드(FastAPI, 기존 코드 거의 그대로)는 Render 무료 웹서비스에서 계속 실행되고, 프론트엔드(React/Vite 빌드)는 Vercel 정적 호스팅에 배포된다. 인증은 진짜 로그인 시스템이 아니라 `X-App-Password` 헤더와 서버 환경변수를 비교하는 단순 게이트다.

**Tech Stack:** FastAPI (기존), React (기존), Render, Vercel. 새 라이브러리 의존성 없음.

## Global Constraints

- `APP_PASSWORD` 환경변수가 **비어있으면 인증을 건너뛴다** — 기존 로컬 개발/실행 흐름(README의 로컬 실행 절차)이 깨지지 않아야 한다.
- `/health`와 `/storage/*`(사진·PDF 정적 파일)는 인증 대상에서 **제외**한다.
- `/ocr`, `/invoices` 하위 모든 라우트는 인증 대상이다.
- 인증 실패 시 상태 코드는 `401`.
- CORS는 기존 `allow_origins=["*"]`를 그대로 유지한다 (변경하지 않음).
- 프론트엔드는 `sessionStorage`에 비밀번호를 저장한다 (브라우저 탭을 닫으면 초기화되는 것을 허용 — `localStorage`가 아님).
- 기존 표준 필드명, 저장 우선순위 원칙 등 이전 계획(`2026-07-01-invoice-management-mvp.md`)의 제약은 이번 변경으로 건드리지 않는다.

---

### Task 1: 백엔드 공유 비밀번호 인증

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/auth.py`
- Modify: `backend/app/routers/ocr.py`
- Modify: `backend/app/routers/invoices.py`
- Create: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: 없음 (신규 독립 모듈)
- Produces: `app.auth.verify_password` (FastAPI dependency, 시그니처: `def verify_password(x_app_password: str = Header(default="")) -> None`, 실패 시 `HTTPException(status_code=401, ...)` 발생) — `ocr.router`와 `invoices.router` 양쪽에 적용됨

- [ ] **Step 1: `app/config.py`에 `APP_PASSWORD` 추가**

`backend/app/config.py`의 기존 `UPSTAGE_API_KEY = os.environ.get("UPSTAGE_API_KEY", "")` 줄 바로 아래에 추가:

```python
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
```

- [ ] **Step 2: 실패하는 테스트 작성 — `tests/test_auth.py`**

```python
from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)


def test_invoices_passes_when_app_password_unset(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "")
    response = client.get("/invoices")
    assert response.status_code == 200


def test_invoices_rejects_missing_header_when_password_set(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    response = client.get("/invoices")
    assert response.status_code == 401


def test_invoices_rejects_wrong_password(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    response = client.get("/invoices", headers={"X-App-Password": "wrong"})
    assert response.status_code == 401


def test_invoices_accepts_correct_password(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    response = client.get("/invoices", headers={"X-App-Password": "secret123"})
    assert response.status_code == 200


def test_ocr_endpoint_is_protected(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    response = client.post("/ocr", files={"file": ("test.jpg", b"fake", "image/jpeg")})
    assert response.status_code == 401


def test_health_route_is_not_protected(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    response = client.get("/health")
    assert response.status_code == 200


def test_storage_mount_is_not_protected(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "secret123")
    response = client.get("/storage/nonexistent-file.jpg")
    # 파일이 없어 404가 나더라도, 인증 실패(401)가 아니라는 점이 중요하다.
    assert response.status_code == 404
```

- [ ] **Step 3: 테스트 실행해서 실패 확인**

Run: `pytest tests/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.auth'` (또는 아직 라우터에 의존성이 안 걸려있어 모든 요청이 200으로 통과, 인증 관련 테스트들이 실패)

- [ ] **Step 4: `app/auth.py` 구현**

```python
from fastapi import Header, HTTPException

from . import config


def verify_password(x_app_password: str = Header(default="")) -> None:
    if not config.APP_PASSWORD:
        return
    if x_app_password != config.APP_PASSWORD:
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다")
```

- [ ] **Step 5: `app/routers/ocr.py`에 의존성 연결**

`backend/app/routers/ocr.py`의 기존 줄:

```python
router = APIRouter()
```

을 다음으로 교체:

```python
router = APIRouter(dependencies=[Depends(verify_password)])
```

파일 상단 import 줄도 수정 (기존 `from fastapi import APIRouter, File, UploadFile`을 아래로 교체):

```python
from fastapi import APIRouter, Depends, File, UploadFile

from .. import ocr
from ..auth import verify_password
```

- [ ] **Step 6: `app/routers/invoices.py`에 의존성 연결**

`backend/app/routers/invoices.py`의 기존 줄:

```python
router = APIRouter()
```

을 다음으로 교체:

```python
router = APIRouter(dependencies=[Depends(verify_password)])
```

파일 상단 import 줄에 `verify_password`를 추가 (기존 `from .. import crud, excel, pdf, photos, schemas` 아래에 추가):

```python
from ..auth import verify_password
```

- [ ] **Step 7: 테스트 실행해서 통과 확인**

Run: `pytest tests/ -v`
Expected: 전체 테스트 통과 (기존 테스트 포함 — `APP_PASSWORD`가 기본값 `""`이므로 기존 테스트들은 인증 없이도 그대로 통과해야 함), 새로 추가한 7개 테스트도 PASSED

- [ ] **Step 8: 커밋**

```bash
git add backend/app/config.py backend/app/auth.py backend/app/routers/ocr.py backend/app/routers/invoices.py backend/tests/test_auth.py
git commit -m "feat: 공유 비밀번호(X-App-Password) 인증 추가"
```

---

### Task 2: 프론트엔드 비밀번호 게이트

**Files:**
- Create: `frontend/src/PasswordGate.jsx`
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: 없음 (Task 1의 백엔드 인증과는 헤더 규약 `X-App-Password`로만 연결됨)
- Produces: `PasswordGate` 컴포넌트 (children을 감싸는 래퍼, `sessionStorage`의 `appPassword` 키로 상태 관리) — `App.jsx`가 소비

- [ ] **Step 1: `frontend/src/PasswordGate.jsx` 작성**

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

- [ ] **Step 2: `frontend/src/api.js` 전체 교체**

기존 내용을 다음으로 교체:

```js
const API_BASE = import.meta.env.VITE_API_BASE || ''

function authHeaders() {
  return { 'X-App-Password': sessionStorage.getItem('appPassword') || '' }
}

function handleUnauthorized(response) {
  if (response.status === 401) {
    sessionStorage.removeItem('appPassword')
    window.location.reload()
    throw new Error('인증이 만료되었습니다')
  }
}

export async function runOcr(imageFile) {
  const formData = new FormData()
  formData.append('file', imageFile)
  const response = await fetch(`${API_BASE}/ocr`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('OCR 요청 실패')
  return response.json()
}

export async function createInvoice(fields, photoFile) {
  const formData = new FormData()
  Object.entries(fields).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      formData.append(key, value)
    }
  })
  if (photoFile) formData.append('photo', photoFile)
  const response = await fetch(`${API_BASE}/invoices`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('저장 실패')
  return response.json()
}

export async function searchInvoices(params) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value)).toString()
  const response = await fetch(`${API_BASE}/invoices?${query}`, {
    headers: authHeaders(),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('검색 실패')
  return response.json()
}

export async function getInvoice(id) {
  const response = await fetch(`${API_BASE}/invoices/${id}`, {
    headers: authHeaders(),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('조회 실패')
  return response.json()
}

export async function updateInvoice(id, fields) {
  const response = await fetch(`${API_BASE}/invoices/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(fields),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('수정 실패')
  return response.json()
}
```

- [ ] **Step 3: `frontend/src/App.jsx` 수정 — `PasswordGate`로 감싸기**

```jsx
import { Link, Route, Routes } from 'react-router-dom'
import CapturePage from './pages/CapturePage.jsx'
import DetailPage from './pages/DetailPage.jsx'
import EditPage from './pages/EditPage.jsx'
import PasswordGate from './PasswordGate.jsx'
import SearchPage from './pages/SearchPage.jsx'

export default function App() {
  return (
    <PasswordGate>
      <div>
        <nav style={{ display: 'flex', gap: 12, padding: 12 }}>
          <Link to="/">촬영</Link>
          <Link to="/search">검색</Link>
        </nav>
        <Routes>
          <Route path="/" element={<CapturePage />} />
          <Route path="/edit" element={<EditPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/invoices/:id" element={<DetailPage />} />
        </Routes>
      </div>
    </PasswordGate>
  )
}
```

- [ ] **Step 4: 빌드로 문법 확인**

Run: `cd frontend && npm run build`
Expected: 에러 없이 빌드 성공 (`dist/` 생성)

- [ ] **Step 5: 수동 확인 (백엔드 실행 중인 상태에서)**

터미널 1: `cd backend && venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000` (환경변수 `APP_PASSWORD`를 설정하지 않은 상태 — 로컬 개발 동작 그대로 유지되는지 먼저 확인)
터미널 2: `cd frontend && npm run dev`
`http://localhost:5173` 접속 시 `APP_PASSWORD`가 비어있으므로 백엔드가 인증을 건너뛴다. 하지만 프론트의 `PasswordGate`는 여전히 첫 화면에서 비밀번호를 요구한다 — 아무 값이나 입력해도 백엔드가 `GET /invoices`를 200으로 응답하므로 통과되는지 확인.
그다음, 터미널 1의 백엔드를 `$env:APP_PASSWORD = "test1234"`로 설정 후 재시작 → 프론트에서 틀린 비밀번호 입력 시 에러 메시지가 뜨고, 맞는 비밀번호(`test1234`) 입력 시 통과하고 이후 촬영~저장 흐름이 정상 동작하는지 확인.
확인 후 두 서버 모두 종료.

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/PasswordGate.jsx frontend/src/api.js frontend/src/App.jsx
git commit -m "feat: 공유 비밀번호 입력 게이트 추가"
```

---

### Task 3: 배포 설정 문서화 (Render + Vercel)

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 1의 `APP_PASSWORD` 환경변수, Task 2의 `VITE_API_BASE` 환경변수(기존 Task 8에서 이미 정의됨)
- Produces: 없음 (운영 문서)

- [ ] **Step 1: `README.md`에 "클라우드 배포" 섹션 추가**

기존 `README.md`의 "데이터 위치" 섹션 뒤에 다음 섹션을 추가:

```markdown
## 클라우드 배포 (Vercel + Render)

현장(사무실과 다른 네트워크)에서 접속하려면 백엔드를 인터넷에 배포해야 합니다.

### 백엔드 — Render

1. https://render.com 에서 새 "Web Service" 생성, 이 저장소의 `backend/` 디렉터리를 루트로 지정
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. 환경변수 설정 (Render 대시보드 → Environment):
   - `UPSTAGE_API_KEY` = 발급받은 Upstage API 키
   - `APP_PASSWORD` = 현장 직원들과 공유할 비밀번호 (**필수** — 설정하지 않으면 인증 없이 누구나 접속 가능합니다)
   - `STORAGE_DIR` = `/opt/render/project/src/backend/storage` (또는 원하는 경로)
5. 배포 완료 후 발급되는 URL(예: `https://xxx.onrender.com`)을 기록해둡니다.

**주의:** 무료 티어는 재배포하거나 일정 시간 사용하지 않아 서버가 슬립 상태로 들어갔다가 다시 깨어날 때 로컬 디스크(DB/사진/엑셀/PDF)가 초기화될 수 있습니다. 중요한 데이터는 주기적으로 Master.xlsx를 직접 내려받아 백업하세요.

### 프론트엔드 — Vercel

1. https://vercel.com 에서 새 프로젝트 생성, 이 저장소의 `frontend/` 디렉터리를 루트로 지정 (Vercel이 Vite 프로젝트를 자동 인식합니다)
2. 환경변수 설정 (Vercel 대시보드 → Settings → Environment Variables):
   - `VITE_API_BASE` = 위에서 기록한 Render 백엔드 URL (예: `https://xxx.onrender.com`)
3. 배포 완료 후 발급되는 Vercel URL로 현장에서 접속합니다.

### 사용 방법

앱 접속 시 비밀번호 입력 화면이 나타납니다. Render에서 설정한 `APP_PASSWORD` 값을 입력하면 이후 브라우저 탭을 닫기 전까지는 다시 입력할 필요가 없습니다.
```

- [ ] **Step 2: 커밋**

```bash
git add README.md
git commit -m "docs: Vercel+Render 클라우드 배포 절차 문서화"
```

## Self-Review 요약

- **스펙 커버리지**: 백엔드 공유 비밀번호(Task 1), 프론트엔드 게이트+세션 저장+401 처리(Task 2), Render/Vercel 배포 설정 문서화(Task 3) — 설계 문서의 모든 항목이 태스크로 매핑됨. `/health`, `/storage` 제외는 Task 1에서 라우터 단위로 의존성을 걸어 자연스럽게 보장됨(별도 코드 불필요, 테스트로 확인).
- **플레이스홀더 스캔**: 없음. 모든 스텝에 실제 코드/명령어 포함.
- **타입/시그니처 일관성**: `verify_password` 함수명과 헤더 이름(`X-App-Password`)이 백엔드(Task 1)와 프론트엔드(Task 2) 양쪽에서 동일하게 사용됨을 확인. `APP_PASSWORD`/`VITE_API_BASE` 환경변수명도 Task 1~3에서 일관됨.
