import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Admin from '../../pages/Admin'
import { ADMIN_NAVIGATION } from '../config/navigation'
import AdminHeader from './AdminHeader'
import AdminLayout from './AdminLayout'
import AdminSidebar from './AdminSidebar'

const apiFetch = vi.fn()

vi.mock('../../api', () => ({
  apiFetch: (...args) => apiFetch(...args),
  apiUpload: vi.fn(),
  logout: vi.fn(),
}))

function renderAt(pathname, ui) {
  return render(
    <MemoryRouter initialEntries={[pathname]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      {ui}
    </MemoryRouter>,
  )
}

describe('administrator shell', () => {
  it('keeps the latest-main header identity and renders the supplied title', () => {
    render(<AdminHeader title="시험 생성·관리" />)

    expect(screen.getByText('(주)엑스티')).toBeInTheDocument()
    expect(screen.getByText('OJT 평가 시스템')).toBeInTheDocument()
    expect(screen.getByText('시험 생성·관리')).toBeInTheDocument()
    expect(screen.getByText('김흥길 과장')).toBeInTheDocument()
    expect(screen.getByText('인사팀 · 관리자')).toBeInTheDocument()
  })

  it('uses planned hrefs, marks the current URL, and delegates navigation', () => {
    const onNavigate = vi.fn()
    renderAt('/admin/exams', (
      <AdminSidebar
        navigation={ADMIN_NAVIGATION}
        pathname="/admin/exams"
        onNavigate={onNavigate}
      />
    ))

    const activeLink = screen.getByRole('link', { name: '시험 생성·관리' })
    expect(activeLink).toHaveAttribute('href', '/admin/exams')
    expect(activeLink).toHaveAttribute('aria-current', 'page')

    const paperLink = screen.getByRole('link', { name: '시험지 생성·관리' })
    expect(paperLink).toHaveAttribute('href', '/admin/exam-papers?tab=setup')
    fireEvent.click(paperLink)
    expect(onNavigate).toHaveBeenCalledWith('/admin/exam-papers?tab=setup')
  })

  it.each([
    ['/admin/exams/live', '응시 현황'],
    ['/admin/exams/EX-1/live', '응시 현황'],
    ['/admin/exams/EX-1/edit', '시험 생성·관리'],
    ['/admin/exams/EX-1/assign', '시험 생성·관리'],
    ['/admin/questions/review', '검수 대기'],
    ['/admin/questions/Q-1', '문제은행'],
    ['/admin/questions/Q-1/history', '문제은행'],
  ])('selects only the most-specific menu for %s', (pathname, expectedLabel) => {
    renderAt(pathname, (
      <AdminSidebar navigation={ADMIN_NAVIGATION} pathname={pathname} onNavigate={vi.fn()} />
    ))

    const currentLinks = screen.getAllByRole('link').filter(link => link.getAttribute('aria-current') === 'page')
    expect(currentLinks).toHaveLength(1)
    expect(currentLinks[0]).toHaveAccessibleName(expectedLabel)
  })

  it.each([
    ['Ctrl', { ctrlKey:true, button:0 }],
    ['Meta', { metaKey:true, button:0 }],
    ['Shift', { shiftKey:true, button:0 }],
    ['Alt', { altKey:true, button:0 }],
    ['middle button', { button:1 }],
  ])('preserves native %s-click behavior', (_label, eventInit) => {
    const onNavigate = vi.fn()
    renderAt('/admin/exams', (
      <AdminSidebar navigation={ADMIN_NAVIGATION} pathname="/admin/exams" onNavigate={onNavigate} />
    ))
    const paperLink = screen.getByRole('link', { name:'시험지 생성·관리' })
    const click = new MouseEvent('click', { bubbles:true, cancelable:true, ...eventInit })
    let preventedByComponent
    document.addEventListener('click', event => {
      preventedByComponent = event.defaultPrevented
      event.preventDefault()
    }, { once:true })

    paperLink.dispatchEvent(click)

    expect(preventedByComponent).toBe(false)
    expect(onNavigate).not.toHaveBeenCalled()
  })

  it('renders breadcrumbs, content, and logout through the common layout', () => {
    const onLogout = vi.fn()
    renderAt('/admin/exams', (
      <AdminLayout
        title="시험 생성·관리"
        breadcrumbs={['홈', '시험 관리', '시험 생성·관리']}
        onLogout={onLogout}
      >
        <section>관리 화면 본문</section>
      </AdminLayout>
    ))

    expect(screen.getByText('관리 화면 본문')).toBeInTheDocument()
    expect(screen.getAllByText('시험 관리')).toHaveLength(2)
    fireEvent.click(screen.getByRole('button', { name: '로그아웃' }))
    expect(onLogout).toHaveBeenCalledOnce()
  })
})

describe('latest-main dashboard preservation contract', () => {
  beforeEach(() => {
    apiFetch.mockReset()
    apiFetch.mockResolvedValue({
      sets: Array.from({ length: 13 }, (_, index) => ({
        exam_id: `EX-${index + 1}`,
        name: `보존 시험 ${index + 1}`,
        team_code: 'T1',
        exam_datetime: '2099-01-01T09:00:00',
        duration_min: 60,
        assigned_users: [],
      })),
    })
  })

  it('keeps the single dashboard API load, four-card pagination, 12-item cap, and more card', async () => {
    renderAt('/admin/dashboard', <Admin initialView="dashboard" onRouteNavigate={vi.fn()} />)

    expect(await screen.findByText('보존 시험 1')).toBeInTheDocument()
    expect(apiFetch).toHaveBeenCalledTimes(1)
    expect(apiFetch).toHaveBeenCalledWith('GET', '/api/admin/exam-sets')

    expect(screen.getByText('보존 시험 4')).toBeInTheDocument()
    expect(screen.queryByText('보존 시험 5')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '3' }))
    expect(await screen.findByText('보존 시험 9')).toBeInTheDocument()
    expect(screen.getByText('보존 시험 11')).toBeInTheDocument()
    expect(screen.queryByText('보존 시험 12')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /시험 더 보기/ })).toHaveTextContent('+1')
    expect(screen.getByText('시험 생성·관리에서 전체 목록 확인')).toBeInTheDocument()
  })

  it('keeps scheduled card actions and forwards the selected exam to management', async () => {
    const onRouteNavigate = vi.fn()
    renderAt('/admin/dashboard', <Admin initialView="dashboard" onRouteNavigate={onRouteNavigate} />)

    await screen.findByText('보존 시험 1')
    expect(screen.getAllByRole('button', { name: '문제 보기' })).toHaveLength(4)
    const manageButtons = screen.getAllByRole('button', { name: '시험 관리' })
    expect(manageButtons).toHaveLength(4)

    fireEvent.click(manageButtons[0])
    await waitFor(() => expect(onRouteNavigate).toHaveBeenCalledWith('exam-assign', { focusExamId: 'EX-1' }))
  })

  it('keeps the scheduled, ongoing, and completed action sets', async () => {
    const onRouteNavigate = vi.fn()
    apiFetch.mockResolvedValueOnce({
      sets: [
        { exam_id:'EX-S', name:'예정 시험', team_code:'T1', exam_datetime:'2099-01-01T09:00:00', duration_min:60, assigned_users:[] },
        { exam_id:'EX-O', name:'진행 시험', team_code:'T1', exam_datetime:new Date(Date.now() - 10 * 60 * 1000).toISOString(), duration_min:60, assigned_users:[] },
        { exam_id:'EX-D', name:'완료 시험', team_code:'T1', exam_datetime:'2000-01-01T09:00:00', duration_min:60, assigned_users:[] },
      ],
    })
    renderAt('/admin/dashboard', <Admin initialView="dashboard" onRouteNavigate={onRouteNavigate} />)

    const scheduledCard = (await screen.findByText('예정 시험')).parentElement.parentElement
    const ongoingCard = screen.getByText('진행 시험').parentElement.parentElement
    const doneCard = screen.getByText('완료 시험').parentElement.parentElement

    expect(within(scheduledCard).getAllByRole('button').map(button => button.textContent)).toEqual(['문제 보기', '시험 관리'])
    expect(within(ongoingCard).getAllByRole('button').map(button => button.textContent)).toEqual(['응시 현황', '시험 관리'])
    expect(within(doneCard).getAllByRole('button').map(button => button.textContent)).toEqual(['결과 보기', '문제 보기'])

    fireEvent.click(within(ongoingCard).getByRole('button', { name:'응시 현황' }))
    fireEvent.click(within(doneCard).getByRole('button', { name:'결과 보기' }))
    expect(onRouteNavigate).toHaveBeenNthCalledWith(1, 'exam-status', undefined)
    expect(onRouteNavigate).toHaveBeenNthCalledWith(2, 'results', undefined)
  })
})
