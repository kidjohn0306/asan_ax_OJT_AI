import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Exam from './pages/Exam'
import AdminRouteAdapter from './admin/AdminRouteAdapter'

function RequireAdmin({ children }) {
  const token = sessionStorage.getItem('token')
  const role = sessionStorage.getItem('role')
  if (!token || role !== 'admin') return <Navigate to="/login" replace />
  return children
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/login.html" element={<Navigate to="/login" replace />} />
      <Route path="/exam" element={<Exam />} />
      <Route path="/exam.html" element={<Navigate to="/exam" replace />} />
      <Route path="/admin" element={<RequireAdmin><Navigate to="/admin/dashboard" replace /></RequireAdmin>} />
      <Route path="/admin/*" element={<RequireAdmin><AdminRouteAdapter /></RequireAdmin>} />
      <Route path="/admin.html" element={<Navigate to="/login" replace />} />
      <Route path="/xt-hq-2b7f" element={<RequireAdmin><Navigate to="/admin/dashboard" replace /></RequireAdmin>} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
