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
