import { Link, Route, Routes } from 'react-router-dom'
import CapturePage from './pages/CapturePage.jsx'
import EditPage from './pages/EditPage.jsx'

export default function App() {
  return (
    <div>
      <nav style={{ display: 'flex', gap: 12, padding: 12 }}>
        <Link to="/">촬영</Link>
      </nav>
      <Routes>
        <Route path="/" element={<CapturePage />} />
        <Route path="/edit" element={<EditPage />} />
      </Routes>
    </div>
  )
}
