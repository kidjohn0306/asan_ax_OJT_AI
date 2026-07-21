import { describe, expect, it } from 'vitest'
import {
  ADMIN_NAVIGATION,
  ADMIN_ROUTE_META,
  adminPathToLegacyView,
  legacyViewToAdminPath,
} from './navigation'

describe('ADMIN_NAVIGATION', () => {
  it('defines every required administrator menu in the required order', () => {
    expect(ADMIN_NAVIGATION.map(group => group.label)).toEqual([
      '대시보드',
      '문제 관리',
      '시험 관리',
      '결과 관리',
      '시스템 관리',
    ])

    expect(ADMIN_NAVIGATION.find(g => g.label === '시험 관리').items.map(i => i.label))
      .toEqual(['시험지 생성·관리', '시험 생성·관리', '응시 현황'])

    expect(ADMIN_NAVIGATION.flatMap(group => group.items).map(item => item.path)).toEqual([
      '/admin/dashboard',
      '/admin/questions/generate/setup',
      '/admin/questions/review',
      '/admin/questions/bank',
      '/admin/exam-papers?tab=setup',
      '/admin/exams',
      '/admin/exams/live',
      '/admin/analytics',
      '/admin/employees',
      '/admin/teams',
      '/admin/materials',
      '/admin/system/status',
      '/admin/system/audit-logs',
    ])
  })
})

describe('ADMIN_ROUTE_META', () => {
  it('provides legacy view, title, and breadcrumbs for every static menu pathname', () => {
    for (const item of ADMIN_NAVIGATION.flatMap(group => group.items)) {
      const pathname = item.path.split('?')[0]
      expect(ADMIN_ROUTE_META[pathname]).toEqual(expect.objectContaining({
        view: expect.any(String),
        title: expect.any(String),
        breadcrumbs: expect.any(Array),
      }))
    }
  })
})

describe('legacyViewToAdminPath', () => {
  it('maps legacy administrator views to canonical paths', () => {
    expect(legacyViewToAdminPath('dashboard')).toBe('/admin/dashboard')
    expect(legacyViewToAdminPath('exam-sheet')).toBe('/admin/exam-papers?tab=setup')
    expect(legacyViewToAdminPath('exam-assign')).toBe('/admin/exams')
    expect(legacyViewToAdminPath('exam-status')).toBe('/admin/exams/live')
  })

  it('falls back to the dashboard for an unknown legacy view', () => {
    expect(legacyViewToAdminPath('unknown')).toBe('/admin/dashboard')
  })
})

describe('adminPathToLegacyView', () => {
  it('maps static administrator paths back to legacy views', () => {
    expect(adminPathToLegacyView('/admin/questions/review')).toBe('q-review')
    expect(adminPathToLegacyView('/admin/exam-papers')).toBe('exam-sheet')
  })

  it.each([
    ['/admin/questions/question-1', 'q-bank'],
    ['/admin/exams/exam-1', 'exam-assign'],
    ['/admin/exams/exam-1/live', 'exam-status'],
  ])('maps dynamic detail path %s by prefix', (pathname, view) => {
    expect(adminPathToLegacyView(pathname)).toBe(view)
  })

  it('ignores query strings and hashes while reverse mapping', () => {
    expect(adminPathToLegacyView('/admin/exam-papers?tab=setup')).toBe('exam-sheet')
    expect(adminPathToLegacyView('/admin/questions/review?status=pending#top')).toBe('q-review')
    expect(adminPathToLegacyView('/admin/exams/exam-1/live?refresh=10')).toBe('exam-status')
  })

  it('falls back to the dashboard for an unknown administrator path', () => {
    expect(adminPathToLegacyView('/admin/unknown')).toBe('dashboard')
  })
})
