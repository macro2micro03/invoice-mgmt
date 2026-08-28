import { useCallback, useRef } from 'react'
import { NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import CapturePage from './pages/CapturePage.jsx'
import DetailPage from './pages/DetailPage.jsx'
import EditPage from './pages/EditPage.jsx'
import LedgerPage from './pages/LedgerPage.jsx'
import PasswordGate from './PasswordGate.jsx'
import ReportPage from './pages/ReportPage.jsx'
import SearchPage from './pages/SearchPage.jsx'

// 상단 탭과 동일한 순서 — 모바일에서 좌우로 스와이프하면 이 순서를
// 따라 이전/다음 탭으로 이동한다.
const TAB_ORDER = ['/', '/search', '/report', '/ledger']
const SWIPE_DISTANCE_THRESHOLD = 60

function useSwipeTabNavigation() {
  const navigate = useNavigate()
  const location = useLocation()
  const touchStart = useRef(null)

  const onTouchStart = useCallback((event) => {
    const touch = event.touches[0]
    touchStart.current = { x: touch.clientX, y: touch.clientY }
  }, [])

  const onTouchEnd = useCallback(
    (event) => {
      const start = touchStart.current
      touchStart.current = null
      if (!start) return

      // 표(수불부 목록, 검색 결과 등)는 자체적으로 가로 스크롤이 되므로,
      // 그 위에서의 좌우 스와이프는 탭 전환과 충돌하지 않게 건너뛴다.
      if (event.target.closest && event.target.closest('.table-wrap')) return

      const currentIndex = TAB_ORDER.indexOf(location.pathname)
      if (currentIndex === -1) return // 등록/검색/보고서 생성/수불부 개정 화면이 아니면 무시

      const touch = event.changedTouches[0]
      const dx = touch.clientX - start.x
      const dy = touch.clientY - start.y
      if (Math.abs(dx) < SWIPE_DISTANCE_THRESHOLD || Math.abs(dx) < Math.abs(dy) * 1.5) return

      if (dx < 0 && currentIndex < TAB_ORDER.length - 1) {
        navigate(TAB_ORDER[currentIndex + 1])
      } else if (dx > 0 && currentIndex > 0) {
        navigate(TAB_ORDER[currentIndex - 1])
      }
    },
    [location.pathname, navigate],
  )

  return { onTouchStart, onTouchEnd }
}

export default function App() {
  const swipeHandlers = useSwipeTabNavigation()

  return (
    <PasswordGate>
      <div onTouchStart={swipeHandlers.onTouchStart} onTouchEnd={swipeHandlers.onTouchEnd}>
        <nav className="nav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : undefined)}>
            등록
          </NavLink>
          <NavLink to="/search" className={({ isActive }) => (isActive ? 'active' : undefined)}>
            검색
          </NavLink>
          <NavLink to="/report" className={({ isActive }) => (isActive ? 'active' : undefined)}>
            보고서 생성
          </NavLink>
          <NavLink to="/ledger" className={({ isActive }) => (isActive ? 'active' : undefined)}>
            수불부 개정
          </NavLink>
        </nav>
        <Routes>
          <Route path="/" element={<CapturePage />} />
          <Route path="/edit" element={<EditPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/invoices/:id" element={<DetailPage />} />
          <Route path="/report" element={<ReportPage />} />
          <Route path="/ledger" element={<LedgerPage />} />
        </Routes>
      </div>
    </PasswordGate>
  )
}
