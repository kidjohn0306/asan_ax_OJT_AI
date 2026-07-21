import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Admin from '../../../pages/Admin'
import { isErroredResult, useLivePolling } from './ExamLivePage'

const apiFetch = vi.fn()

vi.mock('../../../api', () => ({
  apiFetch: (...args) => apiFetch(...args),
  apiUpload: vi.fn(),
  logout: vi.fn(),
}))

const BASE_TIME = Date.now()

const exams = [
  { exam_id:'EX-S', name:'예정 교육', team_code:'T1', exam_datetime:new Date(BASE_TIME + 60 * 60 * 1000).toISOString(), duration_min:60, assigned_users:['E1','E1','E2'] },
  { exam_id:'EX-L', name:'진행 교육', team_code:'T2', exam_datetime:new Date(BASE_TIME - 30 * 60 * 1000).toISOString(), duration_min:120, assigned_users:['E4'] },
  { exam_id:'EX-D', name:'완료 교육', team_code:'T1', exam_datetime:'2026-07-15T00:00:00Z', duration_min:60, assigned_users:['E5'] },
  { exam_id:'EX-U', name:'미정 교육', team_code:'T3', exam_datetime:'not-a-date', duration_min:60, assigned_users:[] },
]

const resultsByExam = {
  'EX-S': [
    { result_id:'R1', employee_id:'E1', name:'김신입', team_code:'T1', score:50, submitted_at:'2026-07-15T23:00:00Z' },
    { result_id:'R2', employee_id:'E1', name:'김신입', team_code:'T1', score:90, submitted_at:'2026-07-15T23:10:00Z', submission_status:'SUBMITTED', grading_status:'FAILED' },
  ],
  'EX-L': [],
  'EX-D': [{ result_id:'R3', employee_id:'E5', name:'이완료', team_code:'T1', score:80, submitted_at:'2026-07-15T00:30:00Z' }],
  'EX-U': [],
  'EX 1': [
    { result_id:'NEW', employee_id:'E1', name:'김신입', team_code:'T1', score:90, submitted_at:'2026-07-15T02:30:00Z' },
    { result_id:'OLD', employee_id:'E1', name:'김신입', team_code:'T1', score:50, submitted_at:'2026-07-15T10:00:00+09:00' },
    { result_id:'ONLY', employee_id:'E3', name:'결과만', team_code:'T2', submitted_at:'2026-07-15T09:30:00Z' },
  ],
}

describe('exam live result classification', () => {
  it('counts a failed grading status even when submission status is normal', () => {
    expect(isErroredResult({ submission_status:'SUBMITTED', grading_status:'FAILED' })).toBe(true)
  })
})

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function PollHarness({ loadSnapshot, resetKey = '' }) {
  const { snapshot } = useLivePolling(loadSnapshot, resetKey)
  return <output data-testid="poll-snapshot">{snapshot?.label || '비어 있음'}</output>
}

describe('exam live polling lifecycle', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('does not overlap a poll while the prior request is pending', async () => {
    vi.useFakeTimers()
    const first = deferred()
    const loadSnapshot = vi.fn()
      .mockImplementationOnce(() => first.promise)
      .mockResolvedValue({ label:'두 번째' })

    render(<PollHarness loadSnapshot={loadSnapshot} />)
    await act(async () => { await Promise.resolve() })
    expect(loadSnapshot).toHaveBeenCalledTimes(1)

    await act(async () => { await vi.advanceTimersByTimeAsync(10_000) })
    expect(loadSnapshot).toHaveBeenCalledTimes(1)

    await act(async () => { first.resolve({ label:'첫 번째' }); await first.promise })
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000) })
    expect(loadSnapshot).toHaveBeenCalledTimes(2)
  })

  it('does not let a stale prior response overwrite a newer reset snapshot', async () => {
    const first = deferred()
    const oldLoader = vi.fn(() => first.promise)
    const newLoader = vi.fn().mockResolvedValue({ label:'새 응답' })
    const view = render(<PollHarness loadSnapshot={oldLoader} resetKey="old" />)
    await act(async () => { await Promise.resolve() })

    view.rerender(<PollHarness loadSnapshot={newLoader} resetKey="new" />)
    expect(await screen.findByText('새 응답')).toBeInTheDocument()
    await act(async () => { first.resolve({ label:'오래된 응답' }); await first.promise })
    expect(screen.getByTestId('poll-snapshot')).toHaveTextContent('새 응답')
  })

  it('ignores a late response after unmount', async () => {
    const pending = deferred()
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const view = render(<PollHarness loadSnapshot={() => pending.promise} />)
    await act(async () => { await Promise.resolve() })

    view.unmount()
    await act(async () => { pending.resolve({ label:'늦은 응답' }); await pending.promise })
    expect(consoleError).not.toHaveBeenCalled()
    consoleError.mockRestore()
  })
})

function RouteHarness() {
  const location = useLocation()
  const navigate = useNavigate()
  return (
    <>
      <output data-testid="location">{`${location.pathname}${location.search}`}</output>
      <button onClick={() => navigate(-1)}>뒤로</button>
      <Admin initialView="exam-status" />
    </>
  )
}

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes><Route path="/admin/*" element={<RouteHarness />} /></Routes>
    </MemoryRouter>,
  )
}

function successfulApi(method, path) {
  if (method !== 'GET') return Promise.resolve({})
  if (path === '/api/admin/exam-sets') return Promise.resolve({ sets: exams })
  const resultMatch = path.match(/^\/api\/admin\/exam-sets\/(.+)\/results$/)
  if (resultMatch) return Promise.resolve({ results: resultsByExam[decodeURIComponent(resultMatch[1])] || [] })
  const assigneeMatch = path.match(/^\/api\/admin\/exam-sets\/(.+)\/assignees$/)
  if (assigneeMatch) return Promise.resolve({ assignees: [
    { employee_id:'E1', name:'김신입', team:'T1' },
    { employee_id:'E2', name:'박미제출', team:'T1' },
  ] })
  return Promise.resolve({})
}

describe('routed exam live overview', () => {
  beforeEach(() => {
    apiFetch.mockReset()
    apiFetch.mockImplementation(successfulApi)
  })

  afterEach(() => {
    cleanup()
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('renders honest scheduled statuses, distinct aggregates, errors, and detail links', async () => {
    renderAt('/admin/exams/live')

    expect(await screen.findByText('예정 교육')).toBeInTheDocument()
    const scheduledRow = screen.getByText('예정 교육').closest('[data-exam-id]')
    expect(within(scheduledRow).getByText('예정')).toBeInTheDocument()
    expect(within(screen.getByText('진행 교육').closest('[data-exam-id]')).getByText('응시 중')).toBeInTheDocument()
    expect(within(screen.getByText('완료 교육').closest('[data-exam-id]')).getByText('완료')).toBeInTheDocument()
    expect(within(screen.getByText('미정 교육').closest('[data-exam-id]')).getByText('일정 미정')).toBeInTheDocument()
    expect(within(scheduledRow).getByText('배정 2명')).toBeInTheDocument()
    expect(within(scheduledRow).getByText('제출 1명')).toBeInTheDocument()
    expect(within(scheduledRow).getByText('미제출 1명')).toBeInTheDocument()
    expect(within(scheduledRow).getByText('오류 1명')).toBeInTheDocument()
    expect(within(scheduledRow).getByText('입장·이탈 정보 없음')).toBeInTheDocument()
    expect(within(scheduledRow).getByRole('link', { name:'상세 보기' })).toHaveAttribute('href', '/admin/exams/EX-S/live')
  })

  it('polls at exactly ten seconds', async () => {
    vi.useFakeTimers()
    renderAt('/admin/exams/live')
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    const initialSetCalls = apiFetch.mock.calls.filter(([, path]) => path === '/api/admin/exam-sets').length
    expect(initialSetCalls).toBe(1)

    await act(async () => { await vi.advanceTimersByTimeAsync(9_999) })
    expect(apiFetch.mock.calls.filter(([, path]) => path === '/api/admin/exam-sets')).toHaveLength(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(apiFetch.mock.calls.filter(([, path]) => path === '/api/admin/exam-sets')).toHaveLength(2)
  })

  it('shows a full error panel when the first load fails', async () => {
    apiFetch.mockRejectedValueOnce(new Error('sheets down'))
    renderAt('/admin/exams/live')
    expect(await screen.findByText('응시 현황을 불러오지 못했습니다.')).toBeInTheDocument()
    expect(screen.queryByText('예정 교육')).not.toBeInTheDocument()
  })

  it('keeps the last snapshot on a later polling failure and recovers', async () => {
    vi.useFakeTimers()
    let failResults = false
    apiFetch.mockImplementation((method, path) => {
      if (failResults && path.endsWith('/EX-S/results')) return Promise.reject(new Error('poll failed'))
      return successfulApi(method, path)
    })
    renderAt('/admin/exams/live')
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByText('예정 교육')).toBeInTheDocument()

    failResults = true
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000) })
    expect(screen.getByText('예정 교육')).toBeInTheDocument()
    expect(screen.getByText('마지막 갱신 실패')).toBeInTheDocument()

    failResults = false
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000) })
    expect(screen.queryByText('마지막 갱신 실패')).not.toBeInTheDocument()
  })

  it('uses URL filters and pushes changes to browser history', async () => {
    renderAt('/admin/exams/live?status=scheduled&team=T1')
    expect(await screen.findByText('예정 교육')).toBeInTheDocument()
    expect(screen.queryByText('진행 교육')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('시험 상태'), { target:{ value:'all' } })
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('status=all'))
    expect(await screen.findByText('완료 교육')).toBeInTheDocument()
    await act(async () => { fireEvent.click(screen.getByRole('button', { name:'뒤로' })) })
    await waitFor(() => expect(screen.queryByText('진행 교육')).not.toBeInTheDocument())
  })
})

describe('routed exam live detail', () => {
  beforeEach(() => {
    apiFetch.mockReset()
    apiFetch.mockImplementation((method, path) => {
      if (path === '/api/admin/exam-sets') return Promise.resolve({ sets:[{ ...exams[0], exam_id:'EX 1', name:'상세 시험' }] })
      return successfulApi(method, path)
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('merges assignees with latest and result-only submissions without invented live data', async () => {
    renderAt('/admin/exams/EX%201/live')
    expect(await screen.findByText('상세 시험')).toBeInTheDocument()
    expect(screen.getByText('E1')).toBeInTheDocument()
    expect(screen.getByText('E2')).toBeInTheDocument()
    expect(screen.getByText('E3')).toBeInTheDocument()
    expect(screen.getByText('90점')).toBeInTheDocument()
    expect(screen.queryByText('50점')).not.toBeInTheDocument()
    expect(screen.getByText('결과만')).toBeInTheDocument()
    const resultOnlyRow = screen.getByText('E3').closest('tr')
    expect(within(resultOnlyRow).getByText('정보 없음')).toBeInTheDocument()
    expect(screen.getAllByText('정보 없음').length).toBeGreaterThan(0)
    expect(screen.getAllByText('집계 준비 중').length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name:/강제 종료|시간 연장/ })).not.toBeInTheDocument()
    expect(apiFetch).toHaveBeenCalledWith('GET', '/api/admin/exam-sets/EX%201/assignees')
    expect(apiFetch).toHaveBeenCalledWith('GET', '/api/admin/exam-sets/EX%201/results')
  })

  it.each(['/admin/exams/MISSING/live', '/admin/exams/EX%ZZ/live'])(
    'shows not found for %s even when child detail endpoints reject with 404',
    async path => {
      apiFetch.mockImplementation((method, apiPath) => {
        if (method === 'GET' && apiPath === '/api/admin/exam-sets') {
          return Promise.resolve({ sets:[{ ...exams[0], exam_id:'EX 1', name:'상세 시험' }] })
        }
        return Promise.reject(Object.assign(new Error('not found'), { status:404 }))
      })

      renderAt(path)
      expect(await screen.findByText('시험을 찾을 수 없습니다.')).toBeInTheDocument()
      expect(screen.queryByText('응시 현황을 불러오지 못했습니다.')).not.toBeInTheDocument()
    },
  )

  it('handles malformed exam ids without crashing', async () => {
    renderAt('/admin/exams/EX%ZZ/live')
    expect(await screen.findByText('시험을 찾을 수 없습니다.')).toBeInTheDocument()
  })

  it('provides a back link to the exam status list instead of trapping the admin in the detail view', async () => {
    renderAt('/admin/exams/EX%201/live')
    expect(await screen.findByText('상세 시험')).toBeInTheDocument()
    const backLink = screen.getByRole('link', { name:/응시 현황 목록으로/ })
    expect(backLink).toHaveAttribute('href', '/admin/exams/live')
    fireEvent.click(backLink)
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/admin/exams/live'))
  })

  it('shows the back link even when the exam cannot be found', async () => {
    renderAt('/admin/exams/MISSING/live')
    expect(await screen.findByText('시험을 찾을 수 없습니다.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name:/응시 현황 목록으로/ })).toHaveAttribute('href', '/admin/exams/live')
  })
})
