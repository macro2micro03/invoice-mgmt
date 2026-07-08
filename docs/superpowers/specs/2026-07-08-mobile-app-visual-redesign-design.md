# 모바일 앱 스타일 시각 리디자인 — 설계 문서

## 배경

현재 프론트엔드(`frontend/`)는 전역 스타일시트가 없고, 각 페이지(`CapturePage`, `EditPage`, `SearchPage`, `DetailPage`, `ReportPage`, `PasswordGate`, `App`의 상단 네비게이션)마다 산발적인 inline style만 있는 순수 HTML 폼 형태다. Vercel 배포 후 실제 휴대폰에서 PWA로 쓰기 시작하면서, "깔끔하고 미니멀한 모바일 앱 느낌"으로 전체 시각 스타일을 통일하고 싶다는 요청이 있었다.

이 작업은 **순수 시각(CSS) 리디자인**이다 — 페이지 구조, 라우팅, 상태 관리, API 호출 로직, 상단 네비게이션의 구조(하단 탭 미도입, 상단 네비게이션 유지)는 전혀 건드리지 않는다.

## 범위

**대상 파일 (전부 시각 스타일만 교체, 로직 무변경):**
- `frontend/src/App.jsx` — 상단 네비게이션
- `frontend/src/PasswordGate.jsx`
- `frontend/src/pages/CapturePage.jsx`
- `frontend/src/pages/EditPage.jsx`
- `frontend/src/pages/SearchPage.jsx`
- `frontend/src/pages/DetailPage.jsx`
- `frontend/src/pages/ReportPage.jsx`

**신규 파일:**
- `frontend/src/styles.css` — 전역 스타일시트 (디자인 토큰 + 공통 컴포넌트 클래스)

**범위 밖 (이번에 하지 않음):**
- 하단 탭 네비게이션으로 구조 변경
- 다크모드
- 아이콘 세트 도입
- 페이지 구조/라우팅 변경
- Tailwind 등 새 npm 패키지 추가
- 접근성 감사(색 대비 WCAG 검증 등) — 상식적인 수준의 대비만 확보하고 별도 감사는 하지 않는다

## 디자인 토큰 (`styles.css` 최상단 `:root`)

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
```

색상 브랜드 톤은 기존 `frontend/vite.config.js`의 PWA manifest `theme_color: '#1f6feb'`와 동일하게 맞춘다(이미 승인된 값, 변경하지 않음).

## 공통 컴포넌트 클래스 (`styles.css`)

- `.page` — 페이지 전체 컨테이너 (배경색 `--color-bg`, 최소 높이 100vh, 패딩)
- `.nav` — 상단 네비게이션 바 (`position: sticky; top: 0;`, 배경 `--color-surface`, 그림자 `--shadow-sm`, 링크는 터치 영역 확보를 위해 패딩 포함)
- `.card` — 폼/콘텐츠를 감싸는 카드 (배경 `--color-surface`, `border-radius: var(--radius-md)`, `box-shadow: var(--shadow-sm)`, 패딩 `--space-md`)
- `.field` — label + input 한 묶음의 세로 배치 wrapper (margin-bottom 포함)
- `.input`, `.select`, `.textarea` — 공통 입력 스타일 (높이 최소 44px, 패딩, `border-radius: var(--radius-sm)`, 포커스 시 `--color-primary` 테두리)
- `.btn` — 기본 버튼 (높이 최소 44px, `border-radius: var(--radius-sm)`, 폰트 굵게)
- `.btn-primary` — 배경 `--color-primary`, 글자 흰색
- `.btn-secondary` — 배경 `--color-surface`, 테두리 `--color-border`, 글자 `--color-text`
- `.btn:disabled` — 반투명 처리, `cursor: not-allowed`
- `.banner` — 공통 배너 베이스 (패딩, `border-radius: var(--radius-sm)`, margin)
- `.banner-error` — `--color-error-bg`/`--color-error-text`
- `.banner-warning` — `--color-warning-bg`/`--color-warning-text`
- `.banner-success` — `--color-success-bg`/`--color-success-text`
- `.list-item` — 검색 결과 등 목록 항목 (카드형, 터치 시 살짝 배경 변화)

이 클래스들은 페이지 컴포넌트의 JSX에서 `className`으로만 사용되고, 각 페이지 파일 자체에는 별도 CSS를 두지 않는다(전부 `styles.css` 하나로 통일 — 파일 수 최소화, 토큰 일관성 보장).

## 페이지별 적용 방식

- **`App.jsx`**: 현재 inline `style={{ display: 'flex', gap: 12, padding: 12 }}` nav를 `.nav` 클래스로 교체. 링크는 현재와 동일하게 촬영/검색/보고서 생성 3개 유지, 구조 변경 없음.
- **`PasswordGate.jsx`**: 비밀번호 입력 폼을 `.card` 안에 중앙 정렬로 배치, 입력란/버튼에 `.input`/`.btn-primary` 적용.
- **`CapturePage.jsx`, `EditPage.jsx`, `ReportPage.jsx`**: 폼 전체를 `.card`로 감싸고, 각 필드를 `.field` + `.input`/`.select`로, 제출 버튼을 `.btn-primary`로, 에러/경고 메시지를 `.banner-error`/`.banner-warning`으로 교체.
- **`SearchPage.jsx`**: 검색창을 `.input`으로, 결과 목록 각 항목을 `.list-item`으로.
- **`DetailPage.jsx`**: 상세 정보를 `.card` 레이아웃으로.

각 페이지의 정확한 JSX 변경은 실행 계획(plan) 작성 시 현재 파일 내용을 직접 읽어 확정한다 — 이 스펙에서는 클래스 적용 방침만 규정한다.

## 전역 적용

`frontend/src/main.jsx`(또는 `App.jsx` 최상단)에서 `import './styles.css'`를 추가해 전역 로드한다. `body`에는 `font-family: var(--font-family)`와 `background: var(--color-bg)`를 기본 적용한다.

## 테스트 전략

이 작업은 순수 CSS/마크업 변경이라 별도 단위 테스트를 추가하지 않는다. 대신:
- `npm run build`가 에러 없이 통과하는지 확인 (기존 프론트엔드 빌드 검증 방식과 동일)
- 로컬 개발 서버를 모바일 뷰포트(375×812, iPhone 기준)로 띄워 각 페이지(촬영/수정/검색/상세/보고서/비밀번호 게이트)를 스크린샷으로 확인
- 버튼/입력란 터치 영역이 시각적으로 충분히 커 보이는지, 에러/경고 배너가 색상 구분되어 보이는지 확인

## 자체 점검

- 색상/토큰이 기존 PWA manifest의 `#1f6feb`와 일치 — 확인됨
- 페이지 구조/라우팅/로직 변경 없음을 범위 밖에 명시 — 확인됨
- 모든 대상 페이지(App, PasswordGate, Capture, Edit, Search, Detail, Report)가 적용 방식 섹션에 나열됨 — 확인됨
- 새 npm 의존성 없음(Tailwind 미도입) — 확인됨
