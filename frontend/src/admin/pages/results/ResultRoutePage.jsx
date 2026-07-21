import { useSearchParams } from 'react-router-dom'

export default function ResultRoutePage({ AnalyticsComponent }) {
  const [searchParams, setSearchParams] = useSearchParams()

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

  const teams = (searchParams.get('team') ?? '').split(',').filter(Boolean)
  return <AnalyticsComponent filters={{ teams }} onFiltersChange={updateFilters} />
}
