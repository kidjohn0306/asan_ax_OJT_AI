import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { apiFetch } from '../../../api'
import ExamScheduleCalendar, { toExamDateKey } from '../../components/ExamScheduleCalendar'

export const LIVE_POLL_INTERVAL_MS = 10_000

export function getScheduledExamStatus(exam, now = Date.now()) {
  const start = new Date(exam?.exam_datetime || '')
  if (Number.isNaN(start.getTime())) return 'unknown'
  const duration = Number(exam?.duration_min ?? 60)
  const end = start.getTime() + Math.max(1, duration) * 60 * 1000
  if (now < start.getTime()) return 'scheduled'
  if (now <= end) return 'in_progress'
  return 'done'
}

export function isErroredResult(result) {
  if (String(result?.error_code || '').trim()) return true
  const failedStatuses = ['FAILED', 'ERROR', 'PARTIAL_FAILED', 'REJECTED']
  return [result?.submission_status, result?.grading_status].some(status => (
    failedStatuses.includes(String(status || '').trim().toUpperCase())
  ))
}

export function summarizeExamLive(exam, results = []) {
  const assigned = new Set((exam.assigned_users || []).map(String).filter(Boolean))
  const submitted = new Set(results.map(result => String(result.employee_id || '')).filter(Boolean))
  const submittedAssigned = new Set([...submitted].filter(employeeId => assigned.has(employeeId)))
  const errored = new Set(
    results.filter(isErroredResult).map(result => String(result.employee_id || result.result_id || '')).filter(Boolean),
  )
  return {
    ...exam,
    statusKey: getScheduledExamStatus(exam),
    assignedCount: assigned.size,
    submittedCount: submitted.size,
    pendingCount: Math.max(assigned.size - submittedAssigned.size, 0),
    errorCount: errored.size,
  }
}

export function useLivePolling(loadSnapshot, resetKey = '') {
  const [snapshot, setSnapshot] = useState(null)
  const [initialError, setInitialError] = useState(null)
  const [pollFailed, setPollFailed] = useState(false)
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null)
  const inFlightRef = useRef(false)
  const snapshotRef = useRef(null)

  useEffect(() => {
    let active = true
    snapshotRef.current = null
    setSnapshot(null)
    setInitialError(null)
    setPollFailed(false)
    setLastUpdatedAt(null)

    async function refresh() {
      if (inFlightRef.current) return
      inFlightRef.current = true
      try {
        const next = await loadSnapshot()
        if (!active) return
        snapshotRef.current = next
        setSnapshot(next)
        setInitialError(null)
        setPollFailed(false)
        setLastUpdatedAt(new Date())
      } catch (error) {
        if (!active) return
        if (snapshotRef.current === null) setInitialError(error)
        else setPollFailed(true)
      } finally {
        if (active) inFlightRef.current = false
      }
    }

    refresh()
    const timer = window.setInterval(refresh, LIVE_POLL_INTERVAL_MS)
    return () => {
      active = false
      window.clearInterval(timer)
      inFlightRef.current = false
    }
  }, [loadSnapshot, resetKey])

  return { snapshot, initialError, pollFailed, lastUpdatedAt }
}

const STATUS_META = {
  scheduled: { label:'예정', badge:'blue' },
  in_progress: { label:'응시 중', badge:'warning' },
  done: { label:'완료', badge:'success' },
  unknown: { label:'일정 미정', badge:'gray' },
}

export function matchesLiveDateRange(exam, range, selectedDate, now = Date.now()) {
  if (range === 'all') return true
  const examDate = toExamDateKey(exam?.exam_datetime)
  if (!examDate) return false
  const today = toExamDateKey(new Date(now))
  if (range === 'today') return examDate === today
  if (range === 'date') return examDate === selectedDate
  if (range !== 'week') return true

  const todayDate = new Date(`${today}T12:00:00`)
  const weekday = todayDate.getDay()
  const mondayOffset = weekday === 0 ? -6 : 1 - weekday
  const monday = new Date(todayDate)
  monday.setDate(todayDate.getDate() + mondayOffset)
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)
  return examDate >= toExamDateKey(monday) && examDate <= toExamDateKey(sunday)
}

export default function ExamLivePage({ CardComponent, BadgeComponent }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const statusFilter = searchParams.get('status') || 'all'
  const teamFilter = searchParams.get('team') || 'all'
  const rangeFilter = searchParams.get('range') || 'today'
  const selectedDate = searchParams.get('date') || toExamDateKey(new Date())
  const [teams, setTeams] = useState([])

  const loadSnapshot = useCallback(async () => {
    const data = await apiFetch('GET', '/api/admin/exam-sets')
    const sets = data.sets || []
    const resultGroups = await Promise.all(sets.map(async exam => {
      const resultData = await apiFetch('GET', `/api/admin/exam-sets/${encodeURIComponent(exam.exam_id)}/results`)
      return resultData.results || []
    }))
    return sets.map((exam, index) => summarizeExamLive(exam, resultGroups[index]))
  }, [])

  const { snapshot, initialError, pollFailed, lastUpdatedAt } = useLivePolling(loadSnapshot)

  useEffect(() => {
    apiFetch('GET', '/api/admin/teams').then(data => setTeams(data.teams || [])).catch(() => {})
  }, [])

  function updateFilter(key, value) {
    const next = new URLSearchParams(searchParams)
    next.set(key, value)
    setSearchParams(next)
  }

  function updateRange(range, date = '') {
    const next = new URLSearchParams(searchParams)
    next.set('range', range)
    if (range === 'date' && date) next.set('date', date)
    else next.delete('date')
    setSearchParams(next)
  }

  if (initialError) {
    return <CardComponent><p style={{ color:'var(--danger)', textAlign:'center', padding:28 }}>응시 현황을 불러오지 못했습니다.</p></CardComponent>
  }
  if (!snapshot) {
    return <CardComponent><p style={{ color:'var(--text-muted)', textAlign:'center', padding:28 }}>불러오는 중...</p></CardComponent>
  }

  // 팀 관리에 등록된 전체 팀을 필터 옵션으로 쓴다. 아직 로딩 전이면 현재 스냅샷에
  // 실제로 등장하는 team_code로만 폴백해 최소한의 필터는 동작하게 한다.
  const teamOptions = teams.length > 0
    ? teams.map(t => t.team_code)
    : [...new Set(snapshot.map(exam => exam.team_code).filter(Boolean))]
  const teamNameByCode = Object.fromEntries(teams.map(t => [t.team_code, t.team_name]))
  const statusTeamVisible = snapshot.filter(exam => {
    const statusMatch = statusFilter === 'all'
      || (statusFilter === 'error' ? exam.errorCount > 0 : exam.statusKey === statusFilter)
    return statusMatch && (teamFilter === 'all' || exam.team_code === teamFilter)
  })
  const visible = statusTeamVisible.filter(exam => matchesLiveDateRange(exam, rangeFilter, selectedDate))
  const rangeLabel = rangeFilter === 'all'
    ? '전체 일정'
    : rangeFilter === 'week'
      ? '이번 주'
      : rangeFilter === 'today'
        ? '오늘'
        : selectedDate.replaceAll('-', '.')

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
      <CardComponent title="전체 응시 현황" action={
        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
          {pollFailed && <BadgeComponent type="danger">마지막 갱신 실패</BadgeComponent>}
          {lastUpdatedAt && <span style={{ fontSize:11, color:'var(--text-muted)' }}>최근 갱신 {lastUpdatedAt.toLocaleTimeString('ko-KR')}</span>}
        </div>
      }>
        <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
          <label style={{ fontSize:12, color:'var(--text-muted)' }}>시험 상태
            <select aria-label="시험 상태" value={statusFilter} onChange={event => updateFilter('status', event.target.value)} style={{ marginLeft:6, border:'1px solid var(--border)', borderRadius:6, padding:'7px 10px', background:'white' }}>
              <option value="all">전체</option><option value="scheduled">예정</option><option value="in_progress">응시 중</option><option value="done">완료</option><option value="error">오류</option>
            </select>
          </label>
          <label style={{ fontSize:12, color:'var(--text-muted)' }}>팀
            <select aria-label="팀" value={teamFilter} onChange={event => updateFilter('team', event.target.value)} style={{ marginLeft:6, border:'1px solid var(--border)', borderRadius:6, padding:'7px 10px', background:'white' }}>
              <option value="all">전체 팀</option>
              {teamOptions.map(team => <option key={team} value={team}>{teamNameByCode[team] || team}</option>)}
            </select>
          </label>
        </div>
      </CardComponent>

      <div className="exam-live-layout">
        <div className="exam-live-filter-panel">
          <CardComponent title="날짜 탐색">
            <div className="exam-live-range" aria-label="응시 현황 빠른 기간">
              <button type="button" className={rangeFilter === 'today' ? 'is-active' : ''} onClick={() => updateRange('today')}>오늘</button>
              <button type="button" className={rangeFilter === 'week' ? 'is-active' : ''} onClick={() => updateRange('week')}>이번 주</button>
              <button type="button" className={rangeFilter === 'all' ? 'is-active' : ''} onClick={() => updateRange('all')}>전체</button>
            </div>
            <ExamScheduleCalendar
              exams={statusTeamVisible}
              selectedDate={selectedDate}
              onSelectDate={date => updateRange('date', date)}
              statusResolver={exam => exam.errorCount ? 'error' : exam.statusKey}
              compact
              ariaLabel="응시 현황 날짜 달력"
            />
          </CardComponent>
        </div>

        <section className="exam-live-list" aria-label={`${rangeLabel} 응시 현황`}>
          <div className="exam-schedule-summary">
            <strong>{rangeLabel} 응시 현황 · {visible.length}건</strong>
            <span>상태와 팀 필터가 날짜 조회 결과에 함께 적용됩니다.</span>
          </div>
          {visible.length === 0 ? (
            <CardComponent><p style={{ color:'var(--text-muted)', textAlign:'center', padding:28 }}>선택한 기간에 표시할 시험이 없습니다.</p></CardComponent>
          ) : visible.map(exam => {
            const status = STATUS_META[exam.statusKey]
            return (
              <div key={exam.exam_id} data-exam-id={exam.exam_id}>
                <CardComponent title={exam.name} action={<BadgeComponent type={status.badge}>{status.label}</BadgeComponent>}>
                  <div style={{ display:'flex', gap:12, flexWrap:'wrap', marginBottom:12, fontSize:13 }}>
                    <span>팀 {teamNameByCode[exam.team_code] || exam.team_code || '-'}</span>
                    <strong>배정 {exam.assignedCount}명</strong>
                    <strong>제출 {exam.submittedCount}명</strong>
                    <strong>미제출 {exam.pendingCount}명</strong>
                    <span style={{ color:exam.errorCount ? 'var(--danger)' : 'var(--text-muted)', fontWeight:700 }}>오류 {exam.errorCount}명</span>
                  </div>
                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', gap:12 }}>
                    <span style={{ color:'var(--text-muted)', fontSize:12 }}>입장·이탈 정보 없음</span>
                    <Link to={`/admin/exams/${encodeURIComponent(exam.exam_id)}/live`} style={{ border:'1.5px solid var(--accent)', color:'var(--accent)', borderRadius:7, padding:'7px 12px', fontSize:12, fontWeight:700, textDecoration:'none' }}>상세 보기</Link>
                  </div>
                </CardComponent>
              </div>
            )
          })}
        </section>
      </div>
    </div>
  )
}
