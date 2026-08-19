# 철근 입고 관리 App. — Streamlit 버전

기존 React/Vercel 프론트엔드와 동일한 백엔드(FastAPI, Render)를 사용하는
대체 프론트엔드입니다. 사내망에서 Vercel(또는 브라우저→Render 직접 호출)이
막히거나 불안정할 때 쓰는 접속 경로입니다.

**왜 이게 도움이 될 수 있는가:** 이 앱의 모든 백엔드 API 호출은 사용자의
브라우저가 아니라 Streamlit 서버(파이썬 프로세스)가 대신 보냅니다.
사내망 프록시/방화벽이 사용자 PC → 외부 클라우드 도메인(Vercel, Render 등)
요청을 개별적으로 막고 있다면, 사용자는 이 Streamlit 서버 도메인 하나에만
접속하면 되고 실제 백엔드 통신은 서버 대 서버로 이루어져 그 차단을 우회할
수 있습니다. 다만 이건 어디까지나 증상에 기반한 추정이며, 사내망 자체가
Render 계열 도메인까지 막는 경우에는 이 방법도 똑같이 막힐 수 있습니다 —
그럴 땐 IT팀에 해당 도메인 화이트리스트 등록을 요청하는 것이 근본적인
해결책입니다.

## 로컬 실행

```bash
cd streamlit_app
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\streamlit run app.py
```

기본적으로 `https://invoice-mgmt-backend.onrender.com`을 백엔드로 사용합니다.
다른 백엔드를 쓰려면 환경변수로 지정하세요.

```bash
set API_BASE=http://localhost:8000
venv\Scripts\streamlit run app.py
```

## Render 배포

1. Render 대시보드에서 **New > Web Service** 선택, 이 저장소 연결
2. **Root Directory**: `streamlit_app`
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
5. 환경변수 `API_BASE`에 기존 백엔드 주소(`https://invoice-mgmt-backend.onrender.com`) 지정 (지정 안 하면 기본값으로 이미 연결됨)

배포되면 `https://<서비스이름>.onrender.com` 주소로 접속할 수 있습니다.
기존 앱과 비밀번호(X-App-Password)를 공유하므로 별도 계정 설정은 필요 없습니다.

## 기능

- **촬영**: 송장 사진 업로드 → 자동 인식(OCR) → 표에서 직접 수정 → 저장, 택 사진 대조
- **검색**: 조건별 검색, 표에서 선택해 일괄 삭제, 보고서/수불부 생성으로 이어가기
- **보고서 생성**: 검색 선택 항목 / 반입일자 집계 / 사진 직접 업로드 세 가지 방식, 사진대지 최대 5세트
- **수불부 생성**: 선택 항목 추가 + 다운로드, 기존 목록 표에서 직접 수정·제외

## 기존 프론트엔드와의 차이

- 카메라 실시간 촬영 UI는 없고, 파일 선택(모바일 브라우저는 보통 카메라 촬영 옵션도 함께 제공)만 지원합니다.
- PWA(홈 화면 설치) 기능은 없습니다.
- 그 외 핵심 기능(인식, 검색, 서류 생성, 수불부 관리)은 동일합니다.
