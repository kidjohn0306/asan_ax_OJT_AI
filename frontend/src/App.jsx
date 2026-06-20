import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Exam from './pages/Exam'
import Admin from './pages/Admin'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/login.html" element={<Navigate to="/login" replace />} />
        <Route path="/exam" element={<Exam />} />
        <Route path="/exam.html" element={<Navigate to="/exam" replace />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/admin.html" element={<Navigate to="/admin" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
