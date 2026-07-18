import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Admin from '../../pages/Admin'
import { adminPathToLegacyView } from '../config/navigation'

const apiFetch = vi.fn()

vi.mock('../../api', () => ({
  apiFetch: (...args) => apiFetch(...args),
  apiUpload: vi.fn(),
  logout: vi.fn(),
}))

function RouteAdmin() {
  const location = useLocation()
  const navigate = useNavigate()
  return (
    <>
      <output data-testid="location">{`${location.pathname}${location.search}`}</output>
      <button onClick={() => navigate(-1)}>뒤로</button>
      <Admin initialView={adminPathToLegacyView(location.pathname)} />
    </>
  )
}

function renderAdmin(path) {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes><Route path="/admin/*" element={<RouteAdmin />} /></Routes>
    </MemoryRouter>,
  )
}

function mockApi(method, path) {
  if (method !== 'GET') return Promise.resolve({})
  if (path === '/api/admin/question-stats') return Promise.resolve({ stats: {} })
  if (path.startsWith('/api/admin/questions')) return Promise.resolve({ questions: [{
    question_id: 'Q-1', category: '공통',
    question: path.includes('status=approved') ? '승인 문제' : path.includes('status=rejected') ? '반려 문제' : '실제 안전 문제',
    status: path.includes('status=approved') ? 'approved' : 'rejected',
    option_a: 'A', option_b: 'B', option_c: 'C', option_d: 'D', answer: 'A', difficulty_init: '중',
  }] })
  if (path === '/api/admin/results-analysis') return Promise.resolve({ summary: { count: 0 }, exams: [], insights: [] })
  if (path === '/api/admin/users') return Promise.resolve({ users: [] })
  if (path === '/api/admin/teams') return Promise.resolve({ teams: [{ team_id: 't1', team_code: 'T1', team_name: '1팀' }] })
  if (path === '/api/admin/teams/headcount') return Promise.resolve({ headcounts: { T1: 1 } })
  if (path === '/api/drive/status') return Promise.resolve({ connected: true })
  if (path === '/api/admin/system-status') return Promise.resolve({ ai_provider: 'mock' })
  if (path.startsWith('/api/admin/materials/status')) return Promise.resolve({ has_new_any: false, categories: {} })
  if (path.startsWith('/api/admin/materials/list')) return Promise.resolve({ categories: {} })
  if (path.startsWith('/api/admin/logs')) return Promise.resolve({ logs: [] })
  if (path === '/api/admin/generation-jobs') return Promise.resolve({ jobs: [], enabled: true })
  if (path === '/api/admin/audit-logs') return Promise.resolve({ logs: [], enabled: true })
  return Promise.resolve({ sets: [] })
}

describe('planned admin domain routes', () => {
  beforeEach(() => {
    apiFetch.mockReset()
    apiFetch.mockImplementation(mockApi)
  })

  it.each([
    ['/admin/questions/review', '검수 대기'],
    ['/admin/results', '응시 결과'],
    ['/admin/teams', '팀 관리'],
  ])('renders the planned title for %s', async (path, title) => {
    renderAdmin(path)
    expect(await screen.findByText(title, { selector: 'header span' })).toBeInTheDocument()
  })

  it.each([
    ['/admin/questions/generate/runs/RUN-1', '/admin/questions/generate/runs'],
    ['/admin/questions/Q-1/history', '/admin/questions/Q-1'],
    ['/admin/results/R-1', '/admin/results'],
  ])('shows an honest unavailable state for %s', async (path, backHref) => {
    renderAdmin(path)
    expect(await screen.findByText('현재 API에서 제공되지 않는 기능입니다')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '돌아가기' })).toHaveAttribute('href', backHref)
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('renders real generation job history from the API', async () => {
    apiFetch.mockImplementation((method, path) => {
      if (path === '/api/admin/generation-jobs') return Promise.resolve({
        jobs: [{ generation_job_id: 'gen-1', requested_by: 'admin001', status: 'COMPLETED', requested_count: 10, completed_count: 10, failed_count: 0, started_at: '2026-07-16T00:00:00+00:00' }],
        enabled: true,
      })
      return mockApi(method, path)
    })
    renderAdmin('/admin/questions/generate/runs')
    expect(await screen.findByText('gen-1')).toBeInTheDocument()
    expect(screen.getByText('admin001')).toBeInTheDocument()
    expect(apiFetch).toHaveBeenCalledWith('GET', '/api/admin/generation-jobs')
  })

  it('shows an honest empty state when there are no generation jobs yet', async () => {
    renderAdmin('/admin/questions/generate/runs')
    expect(await screen.findByText('아직 생성 작업이 없습니다.')).toBeInTheDocument()
  })

  it('renders real audit log entries from the API', async () => {
    apiFetch.mockImplementation((method, path) => {
      if (path === '/api/admin/audit-logs') return Promise.resolve({
        logs: [{ audit_id: 'audit-1', actor_id: 'admin001', action_type: 'APPROVE_QUESTION', target_type: 'question', target_id: 'Q-1', reason: '', created_at: '2026-07-16T00:00:00+00:00' }],
        enabled: true,
      })
      return mockApi(method, path)
    })
    renderAdmin('/admin/system/audit-logs')
    expect(await screen.findByText('admin001')).toBeInTheDocument()
    expect(screen.getByText('문제 승인')).toBeInTheDocument()
    expect(apiFetch).toHaveBeenCalledWith('GET', '/api/admin/audit-logs')
  })

  it('shows an honest empty state when there are no audit logs yet', async () => {
    renderAdmin('/admin/system/audit-logs')
    expect(await screen.findByText('아직 기록된 감사 로그가 없습니다.')).toBeInTheDocument()
  })

  it('does not treat a generation run detail as the dashboard', () => {
    expect(adminPathToLegacyView('/admin/questions/generate/runs/RUN-1')).toBe('q-generate')
  })

  it('uses real question data on a direct question detail route', async () => {
    renderAdmin('/admin/questions/Q-1')
    expect((await screen.findAllByText('실제 안전 문제')).length).toBeGreaterThan(0)
    expect(apiFetch).toHaveBeenCalledWith('GET', expect.stringContaining('/api/admin/questions?'))
  })

  it('renders the planned generation setup sections', async () => {
    renderAdmin('/admin/questions/generate/setup')
    for (const title of ['출제 대상', '문항 구성', '자료 선택', '생성 정책', '생성 전 검증']) {
      expect(await screen.findByText(title)).toBeInTheDocument()
    }
    expect(screen.getByRole('button', { name: '문제 생성 실행' })).toBeInTheDocument()
  })

  it('renders the planned review list and detail split', async () => {
    renderAdmin('/admin/questions/review')
    expect(await screen.findByText('검수 목록')).toBeInTheDocument()
    expect(screen.getByText('문제 상세')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('문제 검색')).toBeInTheDocument()
  })

  it('renders the planned dense question bank and detail panel', async () => {
    renderAdmin('/admin/questions/bank?status=approved')
    expect(await screen.findByPlaceholderText('문제 또는 코드 검색')).toBeInTheDocument()
    expect(screen.getByText('출제')).toBeInTheDocument()
    expect(screen.getByText('버전')).toBeInTheDocument()
    expect(screen.getByText('문제 상세')).toBeInTheDocument()
  })

  it('does not crash on a malformed encoded question id', async () => {
    renderAdmin('/admin/questions/Q%ZZ')
    expect(await screen.findByText('문제가 없습니다.')).toBeInTheDocument()
    expect(screen.getByText('문제 상세', { selector: 'header span' })).toBeInTheDocument()
  })
})

describe('query string filter history', () => {
  beforeEach(() => {
    apiFetch.mockReset()
    apiFetch.mockImplementation(mockApi)
  })

  it('initializes question bank filters, pushes changes, and restores them on back', async () => {
    renderAdmin('/admin/questions/bank?status=approved&category=공통')
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith('GET', '/api/admin/questions?category=%EA%B3%B5%ED%86%B5&status=approved&'))

    fireEvent.change(screen.getByLabelText('상태 필터'), { target: { value: 'rejected' } })
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('status=rejected'))
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: '뒤로' })) })
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('status=approved'))
  })

  it('represents the all status explicitly and omits only the API status filter', async () => {
    renderAdmin('/admin/questions/bank?status=all&category=공통')

    expect(await screen.findByLabelText('상태 필터')).toHaveValue('all')
    expect((await screen.findAllByText('실제 안전 문제')).length).toBeGreaterThan(0)
    expect(apiFetch).toHaveBeenCalledWith('GET', '/api/admin/questions?category=%EA%B3%B5%ED%86%B5&')
    expect(screen.getByTestId('location')).toHaveTextContent('status=all')
  })

  it('reloads the actual question list when browser back restores filters', async () => {
    renderAdmin('/admin/questions/bank?status=approved&category=공통')
    expect((await screen.findAllByText('승인 문제')).length).toBeGreaterThan(0)

    fireEvent.change(screen.getByLabelText('상태 필터'), { target: { value: 'rejected' } })
    expect((await screen.findAllByText('반려 문제')).length).toBeGreaterThan(0)
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: '뒤로' })) })

    expect((await screen.findAllByText('승인 문제')).length).toBeGreaterThan(0)
    expect(apiFetch).toHaveBeenLastCalledWith('GET', '/api/admin/questions?category=%EA%B3%B5%ED%86%B5&status=approved&')
  })

  it('initializes result filters and pushes search changes', async () => {
    renderAdmin('/admin/results?team=T2&from=2026-07-01&to=2026-07-31&q=%EA%B9%80')
    fireEvent.click(await screen.findByRole('button', { name: '조회' }))
    expect(apiFetch).toHaveBeenCalledWith('GET', '/api/admin/logs?team=T2&date_from=2026-07-01&date_to=2026-07-31&')
    expect(screen.getByPlaceholderText('이름 검색')).toHaveValue('김')

    fireEvent.change(screen.getByPlaceholderText('이름 검색'), { target: { value: '박' } })
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('q=%EB%B0%95'))
  })
})
