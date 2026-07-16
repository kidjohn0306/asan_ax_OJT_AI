import { useLocation, useSearchParams } from 'react-router-dom'

function Unavailable({ backHref }) {
  return (
    <div style={{ background:'var(--card)', border:'1px solid var(--border)', borderRadius:10, padding:32, textAlign:'center' }}>
      <p style={{ margin:'0 0 16px', color:'var(--text-muted)', fontSize:14 }}>현재 API에서 제공되지 않는 기능입니다</p>
      <a href={backHref} style={{ color:'var(--accent)', fontWeight:700, textDecoration:'none' }}>돌아가기</a>
    </div>
  )
}

function safeDecode(value) {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

export default function QuestionRoutePage({
  GenerateComponent,
  ReviewComponent,
  BankComponent,
  RunsComponent,
  toast,
  onNavigate,
}) {
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const path = location.pathname

  if (path === '/admin/questions/generate/runs') {
    return RunsComponent ? <RunsComponent toast={toast} /> : <Unavailable backHref="/admin/questions/generate/setup" />
  }
  if (/^\/admin\/questions\/generate\/runs\/[^/]+$/.test(path)) {
    return <Unavailable backHref="/admin/questions/generate/runs" />
  }
  const historyMatch = path.match(/^\/admin\/questions\/([^/]+)\/history$/)
  if (historyMatch) {
    return <Unavailable backHref={`/admin/questions/${encodeURIComponent(safeDecode(historyMatch[1]))}`} />
  }
  if (path === '/admin/questions/generate/setup') {
    return <GenerateComponent toast={toast} onNavigate={onNavigate} />
  }
  if (path === '/admin/questions/review') {
    return <ReviewComponent toast={toast} />
  }

  const detailMatch = path === '/admin/questions/bank'
    ? null
    : path.match(/^\/admin\/questions\/([^/]+)$/)
  const questionId = detailMatch ? safeDecode(detailMatch[1]) : null
  const filters = {
    status: questionId ? 'all' : (searchParams.get('status') ?? 'approved'),
    category: searchParams.get('category') ?? '',
  }

  function updateFilters(changes) {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setSearchParams(next)
  }

  return (
    <BankComponent
      toast={toast}
      onNavigate={onNavigate}
      filters={filters}
      onFiltersChange={updateFilters}
      questionId={questionId}
    />
  )
}
