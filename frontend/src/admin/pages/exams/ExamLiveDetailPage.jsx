import { useCallback } from 'react'
import { Link } from 'react-router-dom'

import { apiFetch } from '../../../api'
import { isErroredResult, useLivePolling } from './ExamLivePage'

const BACK_LINK_STYLE = { border:'1.5px solid var(--border)', color:'var(--text)', borderRadius:7, padding:'7px 12px', fontSize:12, fontWeight:700, textDecoration:'none', whiteSpace:'nowrap' }
function BackToListLink() {
  return <Link to="/admin/exams/live" style={BACK_LINK_STYLE}>← 응시 현황 목록으로</Link>
}

function latestResultsByEmployee(results) {
  const latest = new Map()
  for (const result of results) {
    const employeeId = String(result.employee_id || '').trim()
    if (!employeeId) continue
    const previous = latest.get(employeeId)
    const resultTime = Date.parse(result.submitted_at || '')
    const previousTime = Date.parse(previous?.submitted_at || '')
    if (!previous || (!Number.isNaN(resultTime) && (Number.isNaN(previousTime) || resultTime >= previousTime))) {
      latest.set(employeeId, result)
    }
  }
  return latest
}

function mergeParticipants(assignees, results) {
  const latest = latestResultsByEmployee(results)
  const rows = new Map()
  for (const assignee of assignees) {
    const employeeId = String(assignee.employee_id || '').trim()
    if (!employeeId) continue
    rows.set(employeeId, { employeeId, assignee, result:latest.get(employeeId) || null })
  }
  for (const [employeeId, result] of latest) {
    if (!rows.has(employeeId)) rows.set(employeeId, { employeeId, assignee:null, result })
  }
  return [...rows.values()].sort((left, right) => left.employeeId.localeCompare(right.employeeId))
}

export default function ExamLiveDetailPage({ examId, CardComponent, BadgeComponent, TableComponent }) {
  const encodedExamId = encodeURIComponent(examId)
  const loadSnapshot = useCallback(async () => {
    const setData = await apiFetch('GET', '/api/admin/exam-sets')
    const exam = (setData.sets || []).find(item => String(item.exam_id) === String(examId)) || null
    if (!exam) return { exam:null, participants:[] }
    const [assigneeData, resultData] = await Promise.all([
      apiFetch('GET', `/api/admin/exam-sets/${encodedExamId}/assignees`),
      apiFetch('GET', `/api/admin/exam-sets/${encodedExamId}/results`),
    ])
    return {
      exam,
      participants: mergeParticipants(assigneeData.assignees || [], resultData.results || []),
    }
  }, [encodedExamId, examId])

  const { snapshot, initialError, pollFailed, lastUpdatedAt } = useLivePolling(loadSnapshot, examId)

  if (initialError) {
    return <CardComponent title="시험별 응시 현황" action={<BackToListLink />}><p style={{ color:'var(--danger)', textAlign:'center', padding:28 }}>응시 현황을 불러오지 못했습니다.</p></CardComponent>
  }
  if (!snapshot) {
    return <CardComponent title="시험별 응시 현황" action={<BackToListLink />}><p style={{ color:'var(--text-muted)', textAlign:'center', padding:28 }}>불러오는 중...</p></CardComponent>
  }
  if (!snapshot.exam) {
    return <CardComponent title="시험별 응시 현황" action={<BackToListLink />}><p style={{ color:'var(--text-muted)', textAlign:'center', padding:28 }}>시험을 찾을 수 없습니다.</p></CardComponent>
  }

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
      <CardComponent title={snapshot.exam.name} action={
        <div style={{ display:'flex', gap:8, alignItems:'center', flexWrap:'wrap' }}>
          {pollFailed && <BadgeComponent type="danger">마지막 갱신 실패</BadgeComponent>}
          {lastUpdatedAt && <span style={{ fontSize:11, color:'var(--text-muted)' }}>최근 갱신 {lastUpdatedAt.toLocaleTimeString('ko-KR')}</span>}
          <BackToListLink />
        </div>
      }>
        <div style={{ display:'flex', gap:18, flexWrap:'wrap', fontSize:12, color:'var(--text-muted)' }}>
          <span>팀 <strong style={{ color:'var(--text)' }}>{snapshot.exam.team_code || '-'}</strong></span>
          <span>입장·이탈 <strong style={{ color:'var(--text)' }}>정보 없음</strong></span>
          <span>잔여시간 <strong style={{ color:'var(--text)' }}>집계 준비 중</strong></span>
        </div>
      </CardComponent>

      <CardComponent title={`응시자 현황 (${snapshot.participants.length}명)`} noPad>
        <TableComponent headers={['이름','사번','팀','배정 여부','제출 여부','점수','제출 시각']}>
          {snapshot.participants.length === 0 ? (
            <tr><td colSpan={7} style={{ textAlign:'center', color:'var(--text-muted)', padding:28 }}>배정 또는 제출 정보가 없습니다.</td></tr>
          ) : snapshot.participants.map(({ employeeId, assignee, result }) => {
            const errored = result && isErroredResult(result)
            return (
              <tr key={employeeId}>
                <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)' }}>{assignee?.name || result?.name || '-'}</td>
                <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)', fontFamily:'monospace' }}>{employeeId}</td>
                <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)' }}>{assignee?.team || result?.team_code || '-'}</td>
                <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)' }}><BadgeComponent type={assignee ? 'success' : 'gray'}>{assignee ? '배정' : '미배정'}</BadgeComponent></td>
                <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)' }}><BadgeComponent type={errored ? 'danger' : result ? 'success' : 'gray'}>{errored ? '오류' : result ? '제출 완료' : '미제출'}</BadgeComponent></td>
                <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)', fontWeight:700 }}>{result && result.score != null && String(result.score).trim() !== '' ? `${result.score}점` : '정보 없음'}</td>
                <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)', color:'var(--text-muted)' }}>{result?.submitted_at ? result.submitted_at.slice(0, 19).replace('T', ' ') : '-'}</td>
              </tr>
            )
          })}
        </TableComponent>
      </CardComponent>
    </div>
  )
}
