import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '../../../api'
import Admin from '../../../pages/Admin'
import { adminPathToLegacyView } from '../../config/navigation'
import ExamManagementPage from './ExamManagementPage'

vi.mock('../../../api', () => ({ apiFetch:vi.fn(), apiUpload:vi.fn(), logout:vi.fn() }))

const sets = Array.from({ length:10 }, (_, index) => ({
  exam_id:`EX-${index + 1}`,
  exam_set_id:`SET-${index + 1}`,
  name:`관리 시험 ${index + 1}`,
  team_code:'T1',
  exam_datetime:index === 9 ? '2000-01-01T09:00:00' : '2099-01-01T09:00:00',
  duration_min:60,
  pass_score:70,
  evaluation_type:index === 8 ? 'practice' : 'official',
  assigned_users:[],
}))

const papers = [{ exam_set_id:'PAPER-1', exam_id:'PAPER-EX-1', name:'기초 시험지', team_code:'T1', question_count:2 }]
const users = [
  { employee_id:'E1', name:'같은팀', team:'T1' },
  { employee_id:'E2', name:'다른팀', team:'T2' },
]

function LocationProbe() {
  const location = useLocation()
  const navigate = useNavigate()
  return <><output data-testid="location">{location.pathname}</output><button onClick={() => navigate(-1)}>뒤로</button></>
}

function renderAdmin(path = '/admin/exams') {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition:true, v7_relativeSplatPath:true }}>
      <Routes><Route path="/admin/*" element={<><LocationProbe /><Admin initialView={adminPathToLegacyView(path)} /></>} /></Routes>
    </MemoryRouter>,
  )
}

function mockBase(method, path) {
  if (method === 'GET' && path === '/api/admin/exam-sets') return Promise.resolve({ sets })
  if (method === 'GET' && path === '/api/admin/users') return Promise.resolve({ users })
  if (method === 'GET' && path === '/api/admin/exam-sets/papers') return Promise.resolve({ papers })
  if (method === 'GET' && path.endsWith('/assignees')) return Promise.resolve({ assignees:[] })
  if (method === 'GET' && path.endsWith('/questions')) return Promise.resolve({ questions:[{ question_id:'Q1', question:'단일 조회 문제', category:'공통', difficulty:'중', answer:'A', options:{ A:'정답', B:'오답', C:'오답', D:'오답' } }] })
  return Promise.resolve({})
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('ExamManagementPage route ownership', () => {
  it('uses the URL as selection source and restores selection on browser back', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/exams/EX-1']} future={{ v7_startTransition:true, v7_relativeSplatPath:true }}>
        <Routes><Route path="/admin/*" element={<><LocationProbe /><ExamManagementPage renderManagement={({ selectedExamId, onSelectExam }) => <><span>선택 {selectedExamId || '없음'}</span><button onClick={() => onSelectExam('EX 2')}>변경</button></>} /></>} /></Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText('선택 EX-1')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name:'변경' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/admin/exams/EX%202')
    expect(screen.getByText('선택 EX 2')).toBeInTheDocument()
    await act(async () => { fireEvent.click(screen.getByRole('button', { name:'뒤로' })) })
    expect(await screen.findByText('선택 EX-1')).toBeInTheDocument()
  })
})

describe('routed latest-main exam management', () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset()
    vi.mocked(apiFetch).mockImplementation(mockBase)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('opens a direct exam URL and loads its assignees once', async () => {
    renderAdmin('/admin/exams/EX-1')
    expect(await screen.findByText('관리 시험 1 · T1')).toBeInTheDocument()
    expect(apiFetch.mock.calls.filter(([, path]) => path === '/api/admin/exam-sets/EX-1/assignees')).toHaveLength(1)
  })

  it('keeps 60/70 defaults and navigates to the created exam URL with the existing payload', async () => {
    vi.mocked(apiFetch).mockImplementation((method, path, body) => {
      if (method === 'POST' && path === '/api/admin/exam-sets/from-paper') return Promise.resolve({ exam_id:'EX-NEW' })
      return mockBase(method, path, body)
    })
    renderAdmin()
    await screen.findByText('관리 시험 1')
    await userEvent.selectOptions(screen.getByRole('combobox', { name:'' }), 'PAPER-1')
    const spinboxes = screen.getAllByRole('spinbutton')
    expect(spinboxes[0]).toHaveValue(60)
    expect(spinboxes[1]).toHaveValue(70)
    await userEvent.click(screen.getByRole('button', { name:'생성' }))
    const post = apiFetch.mock.calls.find(([method, path]) => method === 'POST' && path === '/api/admin/exam-sets/from-paper')
    expect(post[2]).toMatchObject({ exam_set_id:'PAPER-1', duration_min:60, pass_score:70 })
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/admin/exams/EX-NEW'))
  })

  it('keeps status radios, eight-row pagination, and resets paging on filter change', async () => {
    renderAdmin()
    await screen.findByText('관리 시험 1')
    expect(screen.queryByText('관리 시험 9')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name:'다음 페이지' }))
    expect(screen.getByText('관리 시험 9')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('radio', { name:/완료/ }))
    expect(screen.getByText('관리 시험 10')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name:'이전 페이지' })).not.toBeInTheDocument()
  })

  it('blocks another-team mouse and keyboard selection', async () => {
    renderAdmin('/admin/exams/EX-1')
    const search = await screen.findByPlaceholderText('응시자 검색 (이름 또는 사번)')
    fireEvent.focus(search)
    await screen.findByText('같은팀')
    fireEvent.change(search, { target:{ value:'다른팀' } })
    const other = await screen.findByText('다른팀')
    expect(other.closest('div[style*="not-allowed"]')).toHaveTextContent('다른 팀')
    fireEvent.mouseDown(other)
    expect(screen.getByRole('button', { name:'추가' })).toBeDisabled()
    fireEvent.keyDown(search, { key:'ArrowDown' })
    fireEvent.keyDown(search, { key:'Enter' })
    expect(screen.getByRole('button', { name:'추가' })).toBeDisabled()
  })

  it('keeps same-team keyboard selection usable and shows the real assignment error detail', async () => {
    renderAdmin('/admin/exams/EX-1')
    const search = await screen.findByPlaceholderText('응시자 검색 (이름 또는 사번)')
    fireEvent.focus(search)
    await screen.findByText('같은팀')
    fireEvent.change(search, { target:{ value:'같은팀' } })
    await screen.findByText('같은팀')
    fireEvent.keyDown(search, { key:'ArrowDown' })
    fireEvent.keyDown(search, { key:'Enter' })
    expect(screen.getByRole('button', { name:'추가' })).toBeEnabled()
    vi.mocked(apiFetch).mockRejectedValueOnce(new Error('확정된 시험 버전이 있어야 응시자를 배정할 수 있습니다.'))
    fireEvent.click(screen.getByRole('button', { name:'추가' }))
    expect(await screen.findByText('확정된 시험 버전이 있어야 응시자를 배정할 수 있습니다.')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('button', { name:'추가' })).toBeEnabled())
  })

  it.each([
    ['official auto-move', 'EX-1'],
    ['practice multiple assignment', 'EX-9'],
  ])('keeps %s as a backend-driven success flow', async (_policy, examId) => {
    vi.mocked(apiFetch).mockImplementation((method, path, body) => {
      if (method === 'POST' && path.endsWith('/assign')) return Promise.resolve({ success:true, employee_id:body.employee_id })
      return mockBase(method, path, body)
    })
    renderAdmin(`/admin/exams/${examId}`)
    const search = await screen.findByPlaceholderText('응시자 검색 (이름 또는 사번)')
    fireEvent.focus(search)
    fireEvent.mouseDown(await screen.findByText('같은팀'))
    fireEvent.click(screen.getByRole('button', { name:'추가' }))

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith('POST', `/api/admin/exam-sets/${examId}/assign`, { employee_id:'E1' })
      expect(apiFetch.mock.calls.filter(([method, path]) => method === 'GET' && path === '/api/admin/exam-sets')).toHaveLength(2)
      expect(apiFetch.mock.calls.filter(([method, path]) => method === 'GET' && path === `/api/admin/exam-sets/${examId}/assignees`)).toHaveLength(2)
      expect(search).toHaveValue('')
      expect(screen.getByRole('button', { name:'추가' })).toBeDisabled()
    })
  // Isolated practice: 3.081s; focused official under heavy jsdom: 3.999s;
  // parallel full suite reached ~5.7s. Scope the contention allowance to these
  // two complete POST + dual-refresh integration flows only.
  }, 10_000)

  it('loads question detail once without changing the selected exam URL', async () => {
    renderAdmin('/admin/exams/EX-1')
    await screen.findByText('관리 시험 1 · T1')
    const row = screen.getByText('관리 시험 1').closest('tr')
    await userEvent.click(within(row).getByTitle('시험 문제 보기'))
    expect(await screen.findByText('단일 조회 문제')).toBeInTheDocument()
    expect(apiFetch.mock.calls.filter(([, path]) => path === '/api/admin/exam-sets/EX-1/questions')).toHaveLength(1)
    expect(screen.getByTestId('location')).toHaveTextContent('/admin/exams/EX-1')
  })

  it('ignores a stale assignee response after the URL selects a newer exam', async () => {
    const first = deferred()
    const second = deferred()
    vi.mocked(apiFetch).mockImplementation((method, path, body) => {
      if (method === 'GET' && path === '/api/admin/exam-sets/EX-1/assignees') return first.promise
      if (method === 'GET' && path === '/api/admin/exam-sets/EX-2/assignees') return second.promise
      return mockBase(method, path, body)
    })
    renderAdmin('/admin/exams/EX-1')
    const secondRow = (await screen.findByText('관리 시험 2')).closest('tr')

    await userEvent.click(secondRow)
    await act(async () => second.resolve({ assignees:[{ employee_id:'E2A', name:'두 번째 응시자', team:'T1' }] }))
    expect(await screen.findByText('두 번째 응시자')).toBeInTheDocument()

    await act(async () => first.resolve({ assignees:[{ employee_id:'E1A', name:'첫 번째 지연 응시자', team:'T1' }] }))
    expect(screen.getByTestId('location')).toHaveTextContent('/admin/exams/EX-2')
    expect(screen.getByText('두 번째 응시자')).toBeInTheDocument()
    expect(screen.queryByText('첫 번째 지연 응시자')).not.toBeInTheDocument()
  })

  it('returns to the base URL when the selected exam is deleted', async () => {
    renderAdmin('/admin/exams/EX-1')
    await screen.findByText('관리 시험 1 · T1')
    const row = screen.getByText('관리 시험 1').closest('tr')
    await userEvent.click(within(row).getByTitle('삭제'))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(/^\/admin\/exams$/))
  })

  it('never renders or requests a Sheets row with a blank exam_id (orphaned "ghost" exam)', async () => {
    const setsWithGhost = [
      ...sets,
      { exam_id: '', exam_set_id: '', name: '', team_code: '', exam_datetime: '', duration_min: 60, pass_score: 70, evaluation_type: 'official', assigned_users: [] },
    ]
    vi.mocked(apiFetch).mockImplementation((method, path, body) => {
      if (method === 'GET' && path === '/api/admin/exam-sets') return Promise.resolve({ sets: setsWithGhost })
      return mockBase(method, path, body)
    })
    renderAdmin()
    await screen.findByText('관리 시험 1')

    expect(apiFetch.mock.calls.some(([, path]) => path.includes('//') || path === '/api/admin/exam-sets/')).toBe(false)
  })
})
