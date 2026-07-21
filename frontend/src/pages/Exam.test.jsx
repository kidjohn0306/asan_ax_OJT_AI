import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Exam from './Exam'

function setLoggedInSession() {
  sessionStorage.setItem('name', '홍길동')
  sessionStorage.setItem('emp_id', '2024001')
  sessionStorage.setItem('team', 'T1')
  sessionStorage.setItem('token', 'test-token')
  sessionStorage.setItem('role', 'examinee')
}

function renderExam() {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Exam />
    </MemoryRouter>,
  )
}

describe('Exam identity screen — assigned duration/question count', () => {
  beforeEach(() => {
    sessionStorage.clear()
    setLoggedInSession()
    global.fetch = vi.fn()
  })

  it('shows a neutral loading state before the assigned-name response resolves', async () => {
    let resolveFetch
    global.fetch.mockImplementation((url) => {
      if (url === '/api/exam/assigned-name') {
        return new Promise(resolve => { resolveFetch = resolve })
      }
      return Promise.reject(new Error(`unexpected fetch ${url}`))
    })
    renderExam()
    expect(await screen.findByText('확인 중…')).toBeInTheDocument()
    resolveFetch({ ok: true, json: async () => ({ name: 'OJT 심화평가', duration_min: 10, question_count: 5 }) })
    await waitFor(() => expect(screen.getByText('10분 · 5문항')).toBeInTheDocument())
  })

  it('renders the real assigned duration_min/question_count instead of the old 60분·25문항 hardcode', async () => {
    global.fetch.mockImplementation((url) => {
      if (url === '/api/exam/assigned-name') {
        return Promise.resolve({ ok: true, json: async () => ({ name: 'OJT 심화평가', duration_min: 10, question_count: 5 }) })
      }
      return Promise.reject(new Error(`unexpected fetch ${url}`))
    })
    renderExam()
    expect(await screen.findByText('10분 · 5문항')).toBeInTheDocument()
    expect(screen.queryByText('60분 · 25문항')).not.toBeInTheDocument()
  })

  it('falls back to a neutral loading state (not a stale 60-minute default) when assigned-name fails', async () => {
    global.fetch.mockImplementation((url) => {
      if (url === '/api/exam/assigned-name') return Promise.reject(new Error('network error'))
      return Promise.reject(new Error(`unexpected fetch ${url}`))
    })
    renderExam()
    await screen.findByText('시험 전 응시자 정보를 확인해 주세요')
    expect(screen.getByText('확인 중…')).toBeInTheDocument()
    expect(screen.queryByText('60분 · 25문항')).not.toBeInTheDocument()
  })
})

describe('Exam mid-test exit reporting (audit log)', () => {
  beforeEach(() => {
    sessionStorage.clear()
    setLoggedInSession()
    global.fetch = vi.fn()
  })

  function mockAssignedNameAndGenerate() {
    global.fetch.mockImplementation((url) => {
      if (url === '/api/exam/assigned-name') {
        return Promise.resolve({ ok: true, json: async () => ({ name: 'OJT 심화평가', duration_min: 10, question_count: 1 }) })
      }
      if (url === '/api/exam/generate') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            result_id: 'r1',
            duration_min: 10,
            questions: [{
              id: 'Q1', category: '공통', difficulty: '중', question: '테스트 문제',
              options: { A: '보기A', B: '보기B', C: '보기C', D: '보기D' },
            }],
          }),
        })
      }
      if (url === '/api/exam/exit-event') return Promise.resolve({ ok: true, json: async () => ({ success: true }) })
      return Promise.reject(new Error(`unexpected fetch ${url}`))
    })
  }

  it('reports a tab_switch exit event to the audit log when the tab is hidden mid-exam', async () => {
    mockAssignedNameAndGenerate()
    renderExam()
    await userEvent.click(await screen.findByRole('button', { name: /시험 시작하기/ }))
    await screen.findByText('테스트 문제')

    Object.defineProperty(document, 'hidden', { configurable: true, get: () => true })
    fireEvent(document, new Event('visibilitychange'))

    await waitFor(() => {
      const call = global.fetch.mock.calls.find(([url]) => url === '/api/exam/exit-event')
      expect(call).toBeTruthy()
      const body = JSON.parse(call[1].body)
      expect(body.reason).toBe('tab_switch')
      expect(body.result_id).toBe('r1')
    })
  })
})

describe('Exam start failure — no more silent mock fallback', () => {
  beforeEach(() => {
    sessionStorage.clear()
    setLoggedInSession()
    global.fetch = vi.fn()
  })

  it('shows a retryable error instead of silently starting a fake mock exam when /generate fails', async () => {
    global.fetch.mockImplementation((url) => {
      if (url === '/api/exam/assigned-name') {
        return Promise.resolve({ ok: true, json: async () => ({ name: 'OJT 심화평가', duration_min: 10, question_count: 1 }) })
      }
      if (url === '/api/exam/generate') {
        return Promise.resolve({ ok: false, status: 503, json: async () => ({ detail: '일시적인 서버 오류입니다.' }) })
      }
      return Promise.reject(new Error(`unexpected fetch ${url}`))
    })
    renderExam()
    await userEvent.click(await screen.findByRole('button', { name: /시험 시작하기/ }))

    expect(await screen.findByText('일시적인 서버 오류입니다.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /다시 시도/ })).toBeInTheDocument()
    // 실패했으니 절대 시험 화면(가짜 모의문제 포함)으로 진행되면 안 된다
    expect(screen.queryByText(/작업 전 반드시 확인해야 하는 것은/)).not.toBeInTheDocument()
  })

  it('shows a retryable error on a network failure without starting a fake mock exam', async () => {
    global.fetch.mockImplementation((url) => {
      if (url === '/api/exam/assigned-name') {
        return Promise.resolve({ ok: true, json: async () => ({ name: 'OJT 심화평가', duration_min: 10, question_count: 1 }) })
      }
      if (url === '/api/exam/generate') return Promise.reject(new Error('network down'))
      return Promise.reject(new Error(`unexpected fetch ${url}`))
    })
    renderExam()
    await userEvent.click(await screen.findByRole('button', { name: /시험 시작하기/ }))

    expect(await screen.findByText(/네트워크 오류로 시험을 시작하지 못했습니다/)).toBeInTheDocument()
  })
})

describe('Exam submit failure — no more silent 0-score + false "저장되었습니다"', () => {
  beforeEach(() => {
    sessionStorage.clear()
    setLoggedInSession()
    global.fetch = vi.fn()
  })

  function mockAssignedNameAndGenerate() {
    global.fetch.mockImplementation((url) => {
      if (url === '/api/exam/assigned-name') {
        return Promise.resolve({ ok: true, json: async () => ({ name: 'OJT 심화평가', duration_min: 10, question_count: 1 }) })
      }
      if (url === '/api/exam/generate') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            result_id: 'r1',
            duration_min: 10,
            questions: [{
              id: 'Q1', category: '공통', difficulty: '중', question: '테스트 문제',
              options: { A: '보기A', B: '보기B', C: '보기C', D: '보기D' },
            }],
          }),
        })
      }
      return Promise.reject(new Error(`unexpected fetch ${url}`))
    })
  }

  it('shows a retryable submit-failed screen (not a fake result) when /submit returns a non-ok response', async () => {
    global.fetch.mockImplementation((url) => {
      if (url === '/api/exam/assigned-name') return Promise.resolve({ ok: true, json: async () => ({ name: 'OJT 심화평가', duration_min: 10, question_count: 1 }) })
      if (url === '/api/exam/generate') return Promise.resolve({ ok: true, json: async () => ({ result_id: 'r1', duration_min: 10, questions: [{ id: 'Q1', category: '공통', difficulty: '중', question: '테스트 문제', options: { A: '보기A', B: '보기B', C: '보기C', D: '보기D' } }] }) })
      if (url === '/api/exam/submit') return Promise.resolve({ ok: false, status: 503, json: async () => ({ detail: '결과 저장에 실패했습니다.' }) })
      return Promise.reject(new Error(`unexpected fetch ${url}`))
    })
    renderExam()
    await userEvent.click(await screen.findByRole('button', { name: /시험 시작하기/ }))
    await screen.findByText('테스트 문제')
    await userEvent.click(screen.getByRole('button', { name: /제출/ }))
    const confirmDialog = (await screen.findByText('시험을 제출하시겠습니까?')).closest('div')
    await userEvent.click(within(confirmDialog).getByRole('button', { name: '제출하기' }))

    expect(await screen.findByText(/결과 저장에 실패했습니다/)).toBeInTheDocument()
    // 실패했으니 "결과가 저장되었습니다"라는 문구는 어디에도 뜨면 안 된다
    expect(screen.queryByText(/결과가 인사팀에 자동 전송 및 저장되었습니다/)).not.toBeInTheDocument()
    expect(screen.queryByText('0점')).not.toBeInTheDocument()
  })

  it('retries the same submit request when "다시 제출하기" is clicked, and succeeds', async () => {
    let submitAttempts = 0
    global.fetch.mockImplementation((url) => {
      if (url === '/api/exam/assigned-name') return Promise.resolve({ ok: true, json: async () => ({ name: 'OJT 심화평가', duration_min: 10, question_count: 1 }) })
      if (url === '/api/exam/generate') return Promise.resolve({ ok: true, json: async () => ({ result_id: 'r1', duration_min: 10, questions: [{ id: 'Q1', category: '공통', difficulty: '중', question: '테스트 문제', options: { A: '보기A', B: '보기B', C: '보기C', D: '보기D' } }] }) })
      if (url === '/api/exam/submit') {
        submitAttempts += 1
        if (submitAttempts === 1) return Promise.resolve({ ok: false, status: 503, json: async () => ({ detail: '일시적 오류' }) })
        return Promise.resolve({ ok: true, json: async () => ({ score: 100, pass: true, results: [{ q_id: 'Q1', question: '테스트 문제', correct: true, category: '공통', user_answer: 'A', answer: 'A' }] }) })
      }
      return Promise.reject(new Error(`unexpected fetch ${url}`))
    })
    renderExam()
    await userEvent.click(await screen.findByRole('button', { name: /시험 시작하기/ }))
    await screen.findByText('테스트 문제')
    await userEvent.click(screen.getByRole('button', { name: /제출/ }))
    const confirmDialog = (await screen.findByText('시험을 제출하시겠습니까?')).closest('div')
    await userEvent.click(within(confirmDialog).getByRole('button', { name: '제출하기' }))
    await screen.findByText(/일시적 오류/)

    await userEvent.click(screen.getByRole('button', { name: '다시 제출하기' }))

    await waitFor(() => expect(screen.getByText('100점')).toBeInTheDocument(), { timeout: 3000 })
    expect(submitAttempts).toBe(2)
  })
})
