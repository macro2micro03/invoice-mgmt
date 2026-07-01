# 클라우드 배포 (Vercel + Render) — 설계 문서

## 배경 및 목표

기존 MVP는 "사무실 PC에서 백엔드를 구동하고, 같은 Wi-Fi(LAN)에 연결된 폰으로 접속"하는 구조였다. 그런데 실제 사용 시나리오는 사무실 PC와 다른 네트워크(현장)에서 모바일로 접속해야 하므로, 백엔드를 인터넷에서 접근 가능한 곳에 배포해야 한다.

- **프론트엔드**: Vercel (React/Vite 정적 호스팅에 최적화된 플랫폼)
- **백엔드**: Render 무료 웹서비스 (FastAPI 서버 프로세스를 계속 띄워둘 수 있는 플랫폼)
- **비용**: 완전 무료 티어로 시작. 무료 티어는 재배포/슬립(inactivity로 인한 재시작) 시 로컬 디스크(SQLite DB, 사진, Master.xlsx, PDF)가 초기화될 수 있음 — 사용자가 별도 백업 계획을 가지고 있어 이 위험을 감수하기로 결정함.
- **접속 보호**: 인터넷에 공개되므로, 기존의 "로그인 없음" 전제를 그대로 유지할 수 없다. 다만 진짜 사용자 계정 시스템 대신, 가장 가벼운 형태인 "공유 비밀번호 하나"로 접근을 제한한다.

## 왜 Vercel + Render로 나눴는가

사용자가 처음 Vercel 단독 사용을 제안했으나, Vercel의 서버리스 함수는 요청/컨테이너마다 로컬 파일시스템이 초기화될 수 있어 지금 백엔드 구조(FastAPI 프로세스 + SQLite 파일 + 로컬 사진/엑셀/PDF 저장)와 맞지 않는다. 백엔드를 완전히 서버리스+외부 DB/스토리지 구조로 재작성하는 대안도 있었지만, 지금 구조를 거의 그대로 유지할 수 있는 "프론트는 Vercel, 백엔드는 Render"가 작업량 대비 합리적이라고 판단해 이 방향으로 결정했다.

## 아키텍처 변경

```
[모바일/PC 브라우저]
      |
      | HTTPS (인터넷, 어디서든)
      v
[Vercel] --- 정적 프론트엔드 (React 빌드, frontend/dist)
      |
      | fetch (VITE_API_BASE로 지정된 Render URL)
      v
[Render] --- FastAPI 백엔드 (기존 구조 그대로)
      |-- SQLite DB
      |-- 로컬 파일 저장 (사진 / Master.xlsx / PDF) — 무료 티어 한정, 재배포 시 초기화 가능
      |-- Upstage Document AI API 호출
```

- 백엔드는 Task 1~12에서 만든 코드를 거의 그대로 사용한다. 유일한 코드 변경은:
  1. 시작 포트를 Render가 주입하는 `$PORT` 환경변수로 읽도록 조정 (지금은 `--port 8000` 하드코딩).
  2. 공유 비밀번호 검사 의존성 추가 (`app/auth.py`).
- Task 7에서 만든 "`frontend/dist`가 있으면 정적으로 서빙" 로직(`app/main.py`)은 이 배포 모델에서는 쓰이지 않는다(Render에는 `backend/`만 배포하므로 `frontend/dist`가 존재하지 않음). 코드를 제거하지 않고 그대로 둔다 — `if FRONTEND_DIST.exists()` 조건 덕분에 자동으로 no-op 처리되어 무해하다.

## 공유 비밀번호 인증

**설계 원칙**: 진짜 HTTP Basic Auth 대신, 앱이 직접 관리하는 커스텀 헤더 검사를 쓴다. 이유: 프론트(Vercel)와 백엔드(Render)가 서로 다른 도메인이라, 브라우저 기본 인증 다이얼로그가 자연스럽게 뜨지 않아 사용자 경험이 나쁘다.

**백엔드 (`backend/app/auth.py`, 신규)**
- `APP_PASSWORD` 환경변수를 읽는다.
- FastAPI 의존성 `verify_password(request)`:
  - `APP_PASSWORD`가 비어있으면(로컬 개발 환경, 지금까지의 README 흐름) 통과시킨다 — 기존 로컬 실행 방식을 깨지 않기 위함.
  - `APP_PASSWORD`가 설정되어 있으면, 요청 헤더 `X-App-Password` 값과 비교. 일치하지 않거나 없으면 `401 Unauthorized`.
- 이 의존성을 `ocr.router`, `invoices.router`에 적용한다 (`APIRouter(dependencies=[Depends(verify_password)])`).
- `/health`와 `/storage`(사진/PDF 정적 서빙)는 이 검사에서 **제외**한다.
  - `/storage` 제외 이유: 사진 URL은 `photos.save_photo`가 생성하는 무작위 UUID 파일명이라 추측이 거의 불가능하고, `<img src="...">` 태그는 커스텀 헤더를 실어보낼 수 없어 검사를 걸면 사진이 화면에 안 보이게 된다. "URL을 모르면 접근 불가" 수준의 보호로 충분하다고 판단(사용자 승인됨).

**프론트엔드**
- `frontend/src/PasswordGate.jsx` (신규): 앱 최상단에서 렌더링되는 게이트 컴포넌트.
  - `sessionStorage.getItem('appPassword')`가 있으면 바로 자식 컴포넌트(라우트들)를 렌더링.
  - 없으면 비밀번호 입력 폼을 보여준다. 입력 후 "확인"을 누르면 `GET /invoices`를 입력된 비밀번호로 호출해보고, 200이면 세션에 저장 후 통과, 401이면 "비밀번호가 올바르지 않습니다" 에러 표시.
- `frontend/src/api.js` 수정: 모든 fetch 함수가 `sessionStorage.getItem('appPassword')` 값을 `X-App-Password` 헤더로 첨부. 응답이 401이면 `sessionStorage.removeItem('appPassword')` 후 페이지를 새로고침 — `PasswordGate`가 다시 나타나 재입력을 받는다.
- `frontend/src/App.jsx`: 기존 라우트 전체를 `<PasswordGate>`로 감싼다.

## 배포 설정

**Render (백엔드)**
- 루트 디렉터리: `backend/`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- 환경변수: `UPSTAGE_API_KEY`, `APP_PASSWORD`, `STORAGE_DIR`(예: `/opt/render/project/src/backend/storage`)

**Vercel (프론트엔드)**
- 루트 디렉터리: `frontend/`
- Vercel이 Vite 프로젝트를 자동 인식 (Build Command `npm run build`, Output `dist`)
- 환경변수: `VITE_API_BASE` = Render 백엔드의 공개 URL (예: `https://xxx.onrender.com`)

**CORS**: 기존 `allow_origins=["*"]`를 그대로 유지한다. 실제 보호는 공유 비밀번호가 담당하므로, Origin 제한은 추가 이득이 크지 않다.

## 에러 처리

- 비밀번호가 틀리면 401 → 프론트가 세션 저장값을 지우고 재입력을 요구. 사용자에게 명확한 한국어 에러 메시지를 보여준다.
- `APP_PASSWORD` 미설정 시 인증을 건너뛰는 것은 **로컬 개발 전용 동작**이다. Render에 배포할 때는 반드시 `APP_PASSWORD`를 설정해야 하며, 이 사실을 README에 굵게 명시한다(설정을 잊으면 인터넷에 완전히 공개된다).

## 테스트 전략

- 백엔드: `backend/tests/test_auth.py` (신규) — `APP_PASSWORD` 미설정 시 통과, 설정 시 헤더 없음/틀림 → 401, 맞음 → 200 을 각각 검증.
- 기존 `test_ocr_endpoint.py`, `test_invoices_api.py` 등은 `APP_PASSWORD`가 테스트 환경에서 비어있으므로(로컬 개발 동작과 동일) 그대로 통과해야 한다 — 회귀 확인 대상.
- 프론트엔드: 로그인 게이트 수동 확인 (틀린 비밀번호 → 에러 표시, 맞는 비밀번호 → 세션 유지되어 재입력 없이 탐색 가능).
- 실제 배포 후 수동 스모크 테스트: Vercel URL로 접속 → 비밀번호 입력 → 촬영~저장~검색 플로우가 Render 백엔드를 통해 실제로 동작하는지 확인.

## 범위 밖 (이번 변경에 포함하지 않음)

- 유료 플랜으로 전환한 persistent disk 적용 (이번엔 무료 티어 + 수동 백업으로 감수)
- 사진/PDF까지 완전히 인증으로 보호 (URL 난독화 수준으로 타협)
- 진짜 사용자 계정/로그인 시스템
