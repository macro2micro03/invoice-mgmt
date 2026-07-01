# 입고자재 송장관리 시스템

## 최초 설정

### 백엔드

    cd backend
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt

### 프론트엔드

    cd frontend
    npm install
    npm run build

## 실행 (매번)

1. Upstage API 키와 저장 경로를 환경변수로 설정 (PowerShell):

    $env:UPSTAGE_API_KEY = "발급받은 API 키"
    $env:STORAGE_DIR = "C:\경로\원하는\저장폴더"

2. 백엔드 실행:

    cd backend
    venv\Scripts\activate
    uvicorn app.main:app --host 0.0.0.0 --port 8000

3. 방화벽에서 8000번 포트를 한 번만 허용 (관리자 권한 PowerShell):

    New-NetFirewallRule -DisplayName "InvoiceApp" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow

4. PC의 로컬 IP 확인:

    ipconfig

   "IPv4 주소" 값을 확인 (예: 192.168.0.15)

5. 같은 Wi-Fi에 연결된 폰에서 브라우저로 접속:

    http://192.168.0.15:8000

## 프론트엔드 코드 수정 후 재배포

    cd frontend
    npm run build

빌드 결과가 `frontend/dist`에 생성되면 백엔드를 재시작할 때 자동으로 반영됩니다.

## 데이터 위치

`STORAGE_DIR` 환경변수로 지정한 폴더 안에:
- `invoices.db` — SQLite DB
- `Master.xlsx` — 자재종류별 시트로 누적되는 엑셀
- `photos/` — 원본 사진
- `pdf/` — 주요자재 입고서류 PDF

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
