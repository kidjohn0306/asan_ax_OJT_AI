import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '../../../api'
import { ExamSheet } from '../../../pages/Admin'
import ExamPaperPage from './ExamPaperPage'

vi.mock('../../../api', () => ({
  apiFetch: vi.fn(),
  apiUpload: vi.fn(),
  logout: vi.fn(),
}))

const papers = Array.from({ length: 12 }, (_, index) => ({
  exam_id: `EX-${index + 1}`,
  exam_set_id: `SET-${index + 1}`,
  name: index === 0 ? '안전교육 시험지' : `시험지 ${index + 1}`,
  team_code: index % 2 ? 'T2' : 'T1',
  paper_version: index + 1,
  question_count: 2,
  used_by_exam_count: index % 2,
  created_at: `2026-07-${String(index + 1).padStart(2, '0')}T09:00:00Z`,
}))

const detail = {
  exam_set: {
    exam_id: 'EX-1',
    exam_set_id: 'SET-1',
    exam_version_id: 'VERSION-2',
    name: '안전교육 시험지',
    team_code: 'T2',
    paper_version: 2,
    immutable: true,
    question_scores: { Q1: 60, Q2: 40 },
  },
  questions: [
    {
      question_id: 'Q1', category: '안전', question: '첫 번째 문제',
      options: { A: '보기 A', B: '보기 B', C: '보기 C', D: '보기 D' },
      answer: 'B', difficulty: '상', score: 60, question_version: 3,
    },
    {
      question_id: 'Q2', category: '품질', question: '두 번째 문제',
      options: { A: '두 번째 A', B: '두 번째 B', C: '두 번째 C', D: '두 번째 D' },
      answer: 'A', difficulty: '하', score: 40, question_version: 4,
    },
  ],
}

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname}{location.search}</output>
}

function renderPage(entry = '/admin/exam-papers?tab=setup', setup = null) {
  return render(
    <MemoryRouter initialEntries={[entry]} future={{ v7_startTransition:true, v7_relativeSplatPath:true }}>
      <ExamPaperPage renderSetup={setup || (() => <div>기존 시험지 설정 UI</div>)} />
      <LocationProbe />
    </MemoryRouter>,
  )
}

describe('ExamPaperPage query-owned tabs', () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset())

  it('selects setup by default and removes list-only query when switching tabs', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ papers:[] })
    renderPage('/admin/exam-papers?tab=list&selected=EX-1&q=안전&team=T1&usage=used&page=2')

    expect(screen.getByRole('tab', { name:'시험지 보기' })).toHaveAttribute('aria-selected', 'true')
    await userEvent.click(screen.getByRole('tab', { name:'시험지 설정' }))

    expect(screen.getByRole('tab', { name:'시험지 설정' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('location')).toHaveTextContent('/admin/exam-papers?tab=setup')
    expect(screen.getByText('기존 시험지 설정 UI')).toBeInTheDocument()
  })

  it('moves to the list tab and selects a newly saved exam', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ papers:[] })
    renderPage('/admin/exam-papers?tab=setup&source=EX-OLD', ({ onSaved }) => (
      <button onClick={() => onSaved('EX-NEW')}>저장 완료</button>
    ))

    await userEvent.click(screen.getByRole('button', { name:'저장 완료' }))

    expect(screen.getByTestId('location')).toHaveTextContent('/admin/exam-papers?tab=list&selected=EX-NEW')
    expect(screen.getByRole('tab', { name:'시험지 보기' })).toHaveAttribute('aria-selected', 'true')
  })

  it('keeps source query and copied form semantics when the active setup tab is clicked', async () => {
    renderPage('/admin/exam-papers?tab=setup&source=EX-OLD', ({ sourceExamId }) => (
      <div>복사 원본 {sourceExamId}</div>
    ))

    await userEvent.click(screen.getByRole('tab', { name:'시험지 설정' }))

    expect(screen.getByTestId('location')).toHaveTextContent('/admin/exam-papers?tab=setup&source=EX-OLD')
    expect(screen.getByText('복사 원본 EX-OLD')).toBeInTheDocument()
  })
})

describe('ExamPaperList and ExamPaperDetail', () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset())

  it('loads the real list once, filters it, and paginates ten rows at a time', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ papers })
    renderPage('/admin/exam-papers?tab=list')

    expect(await screen.findByText('안전교육 시험지')).toBeInTheDocument()
    expect(apiFetch).toHaveBeenCalledTimes(1)
    expect(apiFetch).toHaveBeenCalledWith('GET', '/api/admin/exam-sets/papers')
    expect(screen.getAllByTestId('exam-paper-row')).toHaveLength(10)

    await userEvent.click(screen.getByRole('button', { name:'다음 페이지' }))
    expect(screen.getAllByTestId('exam-paper-row')).toHaveLength(2)
    expect(screen.getByTestId('location')).toHaveTextContent('page=2')

    await userEvent.type(screen.getByRole('searchbox', { name:'시험지 검색' }), '안전교육')
    expect(screen.getAllByTestId('exam-paper-row')).toHaveLength(1)
    expect(screen.getByTestId('location')).toHaveTextContent('q=')

    await userEvent.selectOptions(screen.getByRole('combobox', { name:'대상 팀' }), 'T2')
    expect(screen.getByText('검색 조건에 맞는 시험지가 없습니다.')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByRole('combobox', { name:'사용 여부' }), 'unused')
    expect(screen.getByTestId('location')).toHaveTextContent('usage=unused')
  })

  it('loads one frozen detail per selection and shows ordered choices, answer, score, and versions', async () => {
    vi.mocked(apiFetch).mockImplementation((_method, path) => {
      if (path === '/api/admin/exam-sets/papers') return Promise.resolve({ papers:papers.slice(0, 2) })
      if (path === '/api/admin/exam-sets/EX-1/questions') return Promise.resolve(detail)
      return Promise.resolve({})
    })
    renderPage('/admin/exam-papers?tab=list')

    await userEvent.click(await screen.findByRole('button', { name:'안전교육 시험지 상세 보기' }))

    expect(screen.getByTestId('location')).toHaveTextContent('selected=EX-1')
    expect(await screen.findByText('첫 번째 문제')).toBeInTheDocument()
    expect(apiFetch).toHaveBeenCalledWith('GET', '/api/admin/exam-sets/EX-1/questions')
    expect(apiFetch.mock.calls.filter(([, path]) => path === '/api/admin/exam-sets/EX-1/questions')).toHaveLength(1)
    const first = screen.getByTestId('exam-paper-question-Q1')
    expect(within(first).getByText('1.')).toBeInTheDocument()
    expect(within(first).getByText('B. 보기 B')).toHaveAttribute('data-correct', 'true')
    expect(within(first).getByText('난이도 상')).toBeInTheDocument()
    expect(within(first).getByText('60점')).toBeInTheDocument()
    expect(within(first).getByText('문항 v3')).toBeInTheDocument()
    expect(screen.getByText('시험지 v2')).toBeInTheDocument()
    expect(screen.getByText('총점 100점')).toBeInTheDocument()
    expect(screen.getByText('확정 시험지')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name:'수정본 만들기' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/admin/exam-papers?tab=setup&source=EX-1')
  })

  it('keeps loading, empty, list-error, and detail-error states distinct', async () => {
    let release
    vi.mocked(apiFetch).mockReturnValue(new Promise(resolve => { release = resolve }))
    const first = renderPage('/admin/exam-papers?tab=list')
    expect(screen.getByText('시험지 목록을 불러오는 중입니다.')).toBeInTheDocument()
    release({ papers:[] })
    expect(await screen.findByText('생성된 시험지가 없습니다.')).toBeInTheDocument()
    first.unmount()

    vi.mocked(apiFetch).mockRejectedValueOnce(new Error('목록 장애'))
    const second = renderPage('/admin/exam-papers?tab=list')
    expect(await screen.findByText('목록 장애')).toBeInTheDocument()
    second.unmount()

    vi.mocked(apiFetch).mockImplementation((_method, path = '') => {
      if (!path) return Promise.resolve({})
      return path.endsWith('/papers')
        ? Promise.resolve({ papers:papers.slice(0, 1) })
        : Promise.reject(new Error('상세 장애'))
    })
    renderPage('/admin/exam-papers?tab=list&selected=EX-1')
    expect(await screen.findByText('상세 장애')).toBeInTheDocument()
    expect(screen.queryByText('생성된 시험지가 없습니다.')).not.toBeInTheDocument()
  })
})

describe('ExamSheet copy-on-write integration', () => {
  const toast = vi.fn()

  beforeEach(() => {
    toast.mockReset()
    vi.mocked(apiFetch).mockReset()
  })

  function renderSheet(sourceExamId = 'EX-1', onSaved = vi.fn()) {
    render(
      <MemoryRouter future={{ v7_startTransition:true, v7_relativeSplatPath:true }}>
        <ExamSheet toast={toast} onNavigate={vi.fn()} sourceExamId={sourceExamId} onSaved={onSaved} />
      </MemoryRouter>,
    )
    return onSaved
  }

  it('prefills name, team, question order, and frozen scores then posts no source identity', async () => {
    const onSaved = vi.fn()
    vi.mocked(apiFetch).mockImplementation((method, path, body) => {
      if (method === 'GET' && path === '/api/admin/teams') return Promise.resolve({ teams:[{ team_code:'T2', team_name:'2팀' }] })
      if (method === 'GET' && path === '/api/admin/exam-sets/EX-1/questions') return Promise.resolve(detail)
      if (method === 'POST' && path === '/api/admin/exam-sets') return Promise.resolve({ exam_id:'EX-COPY', question_ids:body.question_ids })
      throw new Error(`unexpected ${method} ${path}`)
    })
    renderSheet('EX-1', onSaved)

    expect(await screen.findByDisplayValue('안전교육 시험지 수정본')).toBeInTheDocument()
    expect(screen.getByRole('button', { name:'2팀' })).toBeInTheDocument()
    const rows = screen.getAllByText(/번째 문제/)
    expect(rows[0]).toHaveTextContent('첫 번째 문제')
    expect(rows[1]).toHaveTextContent('두 번째 문제')

    await userEvent.click(screen.getByRole('button', { name:'시험지 저장' }))
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith('EX-COPY'))
    const post = apiFetch.mock.calls.find(([method, path]) => method === 'POST' && path === '/api/admin/exam-sets')
    expect(post[2]).toEqual({
      name:'안전교육 시험지 수정본',
      team_code:'T2',
      question_ids:['Q1', 'Q2'],
      question_scores:{ Q1:60, Q2:40 },
    })
    expect(post[2]).not.toHaveProperty('exam_id')
    expect(post[2]).not.toHaveProperty('exam_set_id')
    expect(post[2]).not.toHaveProperty('exam_version_id')
    expect(post[2]).not.toHaveProperty('paper_version')
  })

  it.each([
    '이미 동일한 이름의 시험지가 있습니다.',
    '이미 동일한 문제 구성의 시험지가 있습니다.',
  ])('shows a 409 conflict detail, retains input, and never reports success: %s', async conflict => {
    vi.mocked(apiFetch).mockImplementation((method, path) => {
      if (method === 'GET' && path === '/api/admin/teams') return Promise.resolve({ teams:[] })
      if (method === 'GET') return Promise.resolve(detail)
      return Promise.reject(new Error(conflict))
    })
    renderSheet()
    const name = await screen.findByDisplayValue('안전교육 시험지 수정본')
    fireEvent.change(name, { target:{ value:'수정 중인 이름' } })

    await userEvent.click(screen.getByRole('button', { name:'시험지 저장' }))

    await waitFor(() => expect(toast).toHaveBeenCalledWith(`저장 실패: ${conflict}`, 'error'))
    expect(name).toHaveValue('수정 중인 이름')
    expect(toast).not.toHaveBeenCalledWith('시험지가 저장됐습니다.')
  })

  it('keeps the replaced position score when editing a frozen copy', async () => {
    vi.mocked(apiFetch).mockImplementation((method, path) => {
      if (method === 'GET' && path === '/api/admin/teams') return Promise.resolve({ teams:[] })
      if (method === 'GET' && path === '/api/admin/exam-sets/EX-1/questions') return Promise.resolve(detail)
      if (method === 'GET' && path.startsWith('/api/admin/questions?')) return Promise.resolve({
        questions:[{
          question_id:'Q3', category:'안전', question:'교체 문제',
          option_a:'새 A', option_b:'새 B', option_c:'새 C', option_d:'새 D',
          answer:'A', difficulty_ai:'상',
        }],
      })
      if (method === 'POST' && path === '/api/admin/exam-sets') return Promise.resolve({ exam_id:'EX-COPY' })
      throw new Error(`unexpected ${method} ${path}`)
    })
    renderSheet()
    await screen.findByDisplayValue('안전교육 시험지 수정본')

    await userEvent.click(screen.getAllByTitle('문제 교체')[0])
    await userEvent.click(await screen.findByRole('button', { name:/Q3.*교체 문제/ }))
    await userEvent.click(screen.getByRole('button', { name:'시험지 저장' }))

    const post = apiFetch.mock.calls.find(([method, path]) => method === 'POST' && path === '/api/admin/exam-sets')
    expect(post[2].question_ids).toEqual(['Q3', 'Q2'])
    expect(post[2].question_scores).toEqual({ Q3:60, Q2:40 })
  })

  it.each([
    ['automatic', false],
    ['manual', true],
  ])('rebuilds a positive exact 100-point score map after %s redistribution', async (_label, manual) => {
    const redistributed = [
      { ...detail.questions[0], question_id:'Q3', question:'재배분 1' },
      { ...detail.questions[0], question_id:'Q4', question:'재배분 2' },
      { ...detail.questions[0], question_id:'Q5', question:'재배분 3' },
    ]
    vi.mocked(apiFetch).mockImplementation((method, path) => {
      if (method === 'GET' && path === '/api/admin/teams') return Promise.resolve({ teams:[] })
      if (method === 'GET' && path === '/api/admin/exam-sets/EX-1/questions') return Promise.resolve(detail)
      if (method === 'POST' && path === '/api/admin/preview-exam') return Promise.resolve({ questions:redistributed })
      if (method === 'POST' && path === '/api/admin/exam-sets') return Promise.resolve({ exam_id:'EX-REDISTRIBUTED' })
      throw new Error(`unexpected ${method} ${path}`)
    })
    renderSheet()
    await screen.findByDisplayValue('안전교육 시험지 수정본')
    if (manual) await userEvent.click(screen.getAllByRole('button', { name:'OFF' })[1])

    await userEvent.click(screen.getByRole('button', { name:manual ? '수동 배분' : '자동 배분' }))
    expect(await screen.findAllByText('재배분 1')).not.toHaveLength(0)
    await userEvent.click(screen.getByRole('button', { name:'시험지 저장' }))

    const post = apiFetch.mock.calls.findLast(([method, path]) => method === 'POST' && path === '/api/admin/exam-sets')
    expect(Object.keys(post[2].question_scores)).toEqual(['Q3', 'Q4', 'Q5'])
    expect(Object.values(post[2].question_scores).every(score => Number.isInteger(score) && score > 0)).toBe(true)
    expect(Object.values(post[2].question_scores).reduce((sum, score) => sum + score, 0)).toBe(100)
  })

  it('removes stale IDs and rebalances remaining copied questions to 100 points', async () => {
    vi.mocked(apiFetch).mockImplementation((method, path) => {
      if (method === 'GET' && path === '/api/admin/teams') return Promise.resolve({ teams:[] })
      if (method === 'GET') return Promise.resolve(detail)
      if (method === 'POST' && path === '/api/admin/exam-sets') return Promise.resolve({ exam_id:'EX-COPY' })
      throw new Error(`unexpected ${method} ${path}`)
    })
    renderSheet()
    await screen.findByDisplayValue('안전교육 시험지 수정본')

    await userEvent.click(screen.getAllByTitle('제거')[0])
    await userEvent.click(screen.getByRole('button', { name:'시험지 저장' }))

    const post = apiFetch.mock.calls.find(([method, path]) => method === 'POST' && path === '/api/admin/exam-sets')
    expect(post[2].question_ids).toEqual(['Q2'])
    expect(post[2].question_scores).toEqual({ Q2:100 })
  })

  it('preserves the ordinary creation payload and manual total validation', async () => {
    vi.mocked(apiFetch).mockImplementation((method, path, body) => {
      if (method === 'GET') return Promise.resolve({ teams:[] })
      if (path === '/api/admin/preview-exam') return Promise.resolve({ questions:detail.questions })
      if (path === '/api/admin/exam-sets') return Promise.resolve({ exam_id:'EX-NEW', body })
      throw new Error(`unexpected ${path}`)
    })
    renderSheet(null)
    fireEvent.change(screen.getByPlaceholderText('예) 2024년 하반기 OJT 기초고사'), { target:{ value:'일반 시험지' } })
    await userEvent.click(screen.getByRole('button', { name:'자동 배분' }))
    expect(await screen.findAllByText('첫 번째 문제')).not.toHaveLength(0)
    await userEvent.click(screen.getByRole('button', { name:'시험지 저장' }))

    const post = apiFetch.mock.calls.find(([method, path]) => method === 'POST' && path === '/api/admin/exam-sets')
    expect(post[2]).toEqual({ name:'일반 시험지', team_code:'T1', question_ids:['Q1', 'Q2'] })

    await userEvent.click(screen.getAllByRole('button', { name:'OFF' })[1])
    const spinboxes = screen.getAllByRole('spinbutton')
    fireEvent.change(spinboxes.at(-1), { target:{ value:'0' } })
    await userEvent.click(screen.getByRole('button', { name:'수동 배분' }))
    expect(toast).toHaveBeenCalledWith('합계가 총 문항수와 맞지 않습니다.', 'error')
  })
})
