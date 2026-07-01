import { Link, Route, Routes } from 'react-router-dom'
import CapturePage from './pages/CapturePage.jsx'
import DetailPage from './pages/DetailPage.jsx'
import EditPage from './pages/EditPage.jsx'
import SearchPage from './pages/SearchPage.jsx'

export default function App() {
  return (
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
  )
}
