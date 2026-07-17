import { useLocation, useNavigate } from 'react-router-dom'
import Admin from '../pages/Admin'
import { adminPathToLegacyView, legacyViewToAdminPath } from './config/navigation'

export default function AdminRouteAdapter() {
  const location = useLocation()
  const navigate = useNavigate()
  const view = adminPathToLegacyView(location.pathname)

  function navigateToView(nextView, state) {
    const path = nextView === 'exam-assign' && state?.focusExamId
      ? `/admin/exams/${encodeURIComponent(state.focusExamId)}`
      : legacyViewToAdminPath(nextView)
    navigate(path)
  }

  return <Admin initialView={view} onRouteNavigate={navigateToView} />
}
