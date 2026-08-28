import { NavLink, Route, Routes } from 'react-router-dom'
import CapturePage from './pages/CapturePage.jsx'
import DetailPage from './pages/DetailPage.jsx'
import EditPage from './pages/EditPage.jsx'
import LedgerPage from './pages/LedgerPage.jsx'
import PasswordGate from './PasswordGate.jsx'
import ReportPage from './pages/ReportPage.jsx'
import SearchPage from './pages/SearchPage.jsx'

export default function App() {
  return (
    <PasswordGate>
      <div>
        <nav className="nav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : undefined)}>
            촬영
          </NavLink>
          <NavLink to="/search" className={({ isActive }) => (isActive ? 'active' : undefined)}>
            검색
          </NavLink>
          <NavLink to="/report" className={({ isActive }) => (isActive ? 'active' : undefined)}>
            보고서 생성
          </NavLink>
          <NavLink to="/ledger" className={({ isActive }) => (isActive ? 'active' : undefined)}>
            수불부 생성
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
