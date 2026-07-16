import { useLocation, useSearchParams } from 'react-router-dom'

function Unavailable() {
  return (
    <div style={{ background:'var(--card)', border:'1px solid var(--border)', borderRadius:10, padding:32, textAlign:'center' }}>
      <p style={{ margin:'0 0 16px', color:'var(--text-muted)', fontSize:14 }}>현재 API에서 제공되지 않는 기능입니다</p>
      <a href="/admin/results" style={{ color:'var(--accent)', fontWeight:700, textDecoration:'none' }}>돌아가기</a>
    </div>
  )
}

export default function ResultRoutePage({ HistoryComponent, AnalyticsComponent, toast }) {
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()

  if (/^\/admin\/results\/[^/]+$/.test(location.pathname)) return <Unavailable />

  function updateFilters(changes) {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(changes)) {
      if (Array.isArray(value)) {
        if (value.length) next.set(key, value.join(','))
        else next.delete(key)
      } else if (value) next.set(key, value)
      else next.delete(key)
    }
    setSearchParams(next)
  }

  if (location.pathname === '/admin/analytics') {
    const teams = (searchParams.get('team') ?? '').split(',').filter(Boolean)
    return <AnalyticsComponent filters={{ teams }} onFiltersChange={updateFilters} />
  }

  return (
    <HistoryComponent
      toast={toast}
      filters={{
        team: searchParams.get('team') ?? '',
        from: searchParams.get('from') ?? '',
        to: searchParams.get('to') ?? '',
        q: searchParams.get('q') ?? '',
      }}
      onFiltersChange={updateFilters}
    />
  )
}
