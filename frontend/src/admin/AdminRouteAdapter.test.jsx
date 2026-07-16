import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../pages/Admin', async importOriginal => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: function MockAdmin({ initialView, onRouteNavigate }) {
      const location = useLocation()
      const navigate = useNavigate()
      const examId = location.pathname.match(/^\/admin\/exams\/([^/]+)$/)?.[1] ?? ''

      return (
        <div>
          <span data-testid="admin-view">{initialView}</span>
          <span data-testid="admin-path">{location.pathname}{location.search}</span>
          <span data-testid="exam-id">{examId}</span>
          <button onClick={() => onRouteNavigate('exam-status')}>응시 현황</button>
          <button onClick={() => onRouteNavigate('exam-assign', { focusExamId: 'EX-2' })}>시험 선택</button>
          <button onClick={() => navigate('/admin/questions/review')}>검수 이동</button>
          <button onClick={() => navigate(-1)}>뒤로</button>
        </div>
      )
    },
  }
})

vi.mock('../pages/Login', () => ({ default: () => <div>로그인 화면</div> }))
vi.mock('../pages/Exam', () => ({ default: () => <div>시험 화면</div> }))

import AdminRouteAdapter from './AdminRouteAdapter'
import { AppRoutes } from '../App'
import { examIdFromPathname } from '../pages/Admin'

function renderAdapter(initialEntries) {
  return render(
    <MemoryRouter initialEntries={initialEntries} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/admin/*" element={<AdminRouteAdapter />} />
      </Routes>
    </MemoryRouter>,
  )
}

function authenticateAdmin() {
  sessionStorage.setItem('token', 'admin-token')
  sessionStorage.setItem('role', 'admin')
}

describe('examIdFromPathname', () => {
  it('returns the decoded exam id from an exam detail URL', () => {
    expect(examIdFromPathname('/admin/exams/EX%201')).toBe('EX 1')
  })

  it('falls back to the raw exam id when percent encoding is malformed', () => {
    expect(examIdFromPathname('/admin/exams/EX%ZZ')).toBe('EX%ZZ')
  })
})

describe('AdminRouteAdapter', () => {
  it.each([
    ['/admin/dashboard', 'dashboard'],
    ['/admin/questions/review', 'q-review'],
    ['/admin/exam-papers?tab=list', 'exam-sheet'],
  ])('maps %s to the %s legacy view', (path, expectedView) => {
    renderAdapter([path])

    expect(screen.getByTestId('admin-view')).toHaveTextContent(expectedView)
  })

  it('preserves the selected exam id on an exam detail URL', () => {
    renderAdapter(['/admin/exams/EX-1'])

    expect(screen.getByTestId('admin-view')).toHaveTextContent('exam-assign')
    expect(screen.getByTestId('exam-id')).toHaveTextContent('EX-1')
  })

  it('converts legacy view navigation to an admin URL', async () => {
    renderAdapter(['/admin/dashboard'])

    fireEvent.click(screen.getByRole('button', { name: '응시 현황' }))

    await waitFor(() => expect(screen.getByTestId('admin-path')).toHaveTextContent('/admin/exams/live'))
    expect(screen.getByTestId('admin-view')).toHaveTextContent('exam-status')
  })

  it('uses the selected exam id when navigating to exam assignment', async () => {
    renderAdapter(['/admin/dashboard'])

    fireEvent.click(screen.getByRole('button', { name: '시험 선택' }))

    await waitFor(() => expect(screen.getByTestId('admin-path')).toHaveTextContent('/admin/exams/EX-2'))
  })

  it('recomputes the legacy view after browser back navigation', async () => {
    renderAdapter(['/admin/dashboard'])
    fireEvent.click(screen.getByRole('button', { name: '검수 이동' }))
    await waitFor(() => expect(screen.getByTestId('admin-view')).toHaveTextContent('q-review'))

    fireEvent.click(screen.getByRole('button', { name: '뒤로' }))

    await waitFor(() => expect(screen.getByTestId('admin-view')).toHaveTextContent('dashboard'))
  })
})

describe('AppRoutes', () => {
  beforeEach(() => sessionStorage.clear())

  it.each([
    ['/admin', '/admin/dashboard'],
    ['/xt-hq-2b7f', '/admin/dashboard'],
  ])('redirects an authenticated administrator from %s to %s', async (from, destination) => {
    authenticateAdmin()
    render(<MemoryRouter initialEntries={[from]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><AppRoutes /></MemoryRouter>)

    await waitFor(() => expect(screen.getByTestId('admin-path')).toHaveTextContent(destination))
    expect(screen.getByTestId('admin-view')).toHaveTextContent('dashboard')
  })

  it.each([
    ['missing token', null, 'admin'],
    ['non-admin role', 'user-token', 'employee'],
  ])('redirects to login for %s', async (_label, token, role) => {
    if (token) sessionStorage.setItem('token', token)
    sessionStorage.setItem('role', role)
    render(<MemoryRouter initialEntries={['/admin/dashboard']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><AppRoutes /></MemoryRouter>)

    expect(await screen.findByText('로그인 화면')).toBeInTheDocument()
  })

  it.each([
    ['/login', '로그인 화면'],
    ['/exam', '시험 화면'],
  ])('keeps the existing %s route', (path, content) => {
    render(<MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><AppRoutes /></MemoryRouter>)

    expect(screen.getByText(content)).toBeInTheDocument()
  })
})
