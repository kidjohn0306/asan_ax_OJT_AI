const DASHBOARD_PATH = '/admin/dashboard'

export const ADMIN_NAVIGATION = [
  {
    label: '대시보드',
    items: [
      { label: '대시보드', path: DASHBOARD_PATH, view: 'dashboard' },
    ],
  },
  {
    label: '문제 관리',
    items: [
      { label: '문제 생성', path: '/admin/questions/generate/setup', view: 'q-generate' },
      { label: '생성 작업', path: '/admin/questions/generate/runs', view: 'q-generate' },
      { label: '검수 대기', path: '/admin/questions/review', view: 'q-review' },
      { label: '문제은행', path: '/admin/questions/bank', view: 'q-bank' },
    ],
  },
  {
    label: '시험 관리',
    items: [
      { label: '시험지 생성관리', path: '/admin/exam-papers?tab=setup', view: 'exam-sheet' },
      { label: '시험 생성관리', path: '/admin/exams', view: 'exam-assign' },
      { label: '응시 현황', path: '/admin/exams/live', view: 'exam-status' },
    ],
  },
  {
    label: '결과 관리',
    items: [
      { label: '응시 결과', path: '/admin/results', view: 'history' },
      { label: '결과 분석', path: '/admin/analytics', view: 'results' },
    ],
  },
  {
    label: '시스템 관리',
    items: [
      { label: '응시자 관리', path: '/admin/employees', view: 'users' },
      { label: '팀 관리', path: '/admin/teams', view: 'teams' },
      { label: '자료·연동', path: '/admin/materials', view: 'settings' },
      { label: '시스템 상태', path: '/admin/system/status', view: 'settings' },
      { label: '감사 로그', path: '/admin/system/audit-logs', view: 'settings' },
    ],
  },
]

export const ADMIN_ROUTE_META = Object.fromEntries(
  ADMIN_NAVIGATION.flatMap(group => group.items.map(item => {
    const pathname = item.path.split('?')[0]
    const breadcrumbs = group.label === '대시보드'
      ? ['홈', item.label]
      : ['홈', group.label, item.label]

    return [pathname, {
      view: item.view,
      title: item.label,
      breadcrumbs,
    }]
  })),
)

const LEGACY_VIEW_PATHS = {
  dashboard: DASHBOARD_PATH,
  'q-generate': '/admin/questions/generate/setup',
  'q-review': '/admin/questions/review',
  'q-bank': '/admin/questions/bank',
  'exam-sheet': '/admin/exam-papers?tab=setup',
  'exam-assign': '/admin/exams',
  'exam-status': '/admin/exams/live',
  history: '/admin/results',
  results: '/admin/analytics',
  users: '/admin/employees',
  teams: '/admin/teams',
  settings: '/admin/system/status',
}

export function legacyViewToAdminPath(view) {
  return LEGACY_VIEW_PATHS[view] ?? DASHBOARD_PATH
}

function normalizePathname(pathname) {
  const withoutQueryOrHash = String(pathname ?? '').split(/[?#]/, 1)[0]
  if (withoutQueryOrHash.length > 1 && withoutQueryOrHash.endsWith('/')) {
    return withoutQueryOrHash.slice(0, -1)
  }
  return withoutQueryOrHash
}

export function adminPathToLegacyView(pathname) {
  const normalizedPathname = normalizePathname(pathname)
  const staticRoute = ADMIN_ROUTE_META[normalizedPathname]

  if (staticRoute) return staticRoute.view

  if (/^\/admin\/exams\/[^/]+\/live$/.test(normalizedPathname)) return 'exam-status'
  if (/^\/admin\/questions\/generate\/runs\/[^/]+$/.test(normalizedPathname)) return 'q-generate'
  if (/^\/admin\/questions\/[^/]+(?:\/history)?$/.test(normalizedPathname)) return 'q-bank'
  if (/^\/admin\/exams\/[^/]+(?:\/(?:edit|assign))?$/.test(normalizedPathname)) return 'exam-assign'
  if (/^\/admin\/results\/[^/]+$/.test(normalizedPathname)) return 'history'

  return 'dashboard'
}
