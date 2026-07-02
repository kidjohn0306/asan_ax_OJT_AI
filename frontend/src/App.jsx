import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Exam from './pages/Exam'
import Admin from './pages/Admin'

function RequireAdmin() {
  const token = sessionStorage.getItem('token')
  const role = sessionStorage.getItem('role')
  if (!token || role !== 'admin') return <Navigate to="/login" replace />
  return <Admin />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/login.html" element={<Navigate to="/login" replace />} />
        <Route path="/exam" element={<Exam />} />
        <Route path="/exam.html" element={<Navigate to="/exam" replace />} />
        <Route path="/admin" element={<RequireAdmin />} />
        <Route path="/admin.html" element={<Navigate to="/admin" replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
