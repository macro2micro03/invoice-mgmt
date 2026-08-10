import { Link, Route, Routes } from 'react-router-dom'
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
          <Link to="/">촬영</Link>
          <Link to="/search">검색</Link>
          <Link to="/report">보고서 생성</Link>
          <Link to="/ledger">수불부 생성</Link>
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
