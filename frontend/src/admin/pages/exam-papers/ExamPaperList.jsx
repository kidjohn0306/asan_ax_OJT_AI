import { useEffect, useMemo, useState } from 'react'

import { apiFetch } from '../../../api'

const PAGE_SIZE = 10
const EXAM_CATEGORY_LABELS = { exam_study: '기초고사', exam_test: '업무능력평가' }

function setQuery(searchParams, setSearchParams, patch) {
  const next = new URLSearchParams(searchParams)
  Object.entries(patch).forEach(([key, value]) => {
    if (value === '' || value == null || value === 1) next.delete(key)
    else next.set(key, String(value))
  })
  setSearchParams(next)
}

export default function ExamPaperList({ searchParams, setSearchParams, onSelect }) {
  const [papers, setPapers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const query = searchParams.get('q') || ''
  const team = searchParams.get('team') || ''
  const usage = searchParams.get('usage') || ''
  const requestedPage = Math.max(1, Number(searchParams.get('page')) || 1)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    apiFetch('GET', '/api/admin/exam-sets/papers')
      .then(data => { if (active) setPapers(data.papers || []) })
      .catch(err => { if (active) setError(err.message || '시험지 목록을 불러오지 못했습니다.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const filtered = useMemo(() => papers.filter(paper => {
    const matchesQuery = !query || `${paper.name} ${paper.exam_id} ${paper.exam_set_id}`.toLowerCase().includes(query.toLowerCase())
    const matchesTeam = !team || paper.team_code === team
    const used = Number(paper.used_by_exam_count || 0) > 0
    const matchesUsage = !usage || (usage === 'used' ? used : !used)
    return matchesQuery && matchesTeam && matchesUsage
  }), [papers, query, team, usage])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const page = Math.min(requestedPage, totalPages)
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const teams = [...new Set(papers.map(paper => paper.team_code).filter(Boolean))].sort()

  function changeFilter(key, value) {
    setQuery(searchParams, setSearchParams, { [key]:value, page:null, selected:null })
  }

  if (loading) return <div style={stateStyle}>시험지 목록을 불러오는 중입니다.</div>
  if (error) return <div role="alert" style={{ ...stateStyle, color:'var(--danger)' }}>{error}</div>

  return (
    <section aria-label="시험지 목록" style={panelStyle}>
      <div style={{ padding:16, borderBottom:'1px solid var(--border)', display:'grid', gridTemplateColumns:'minmax(180px, 1fr) 150px 150px', gap:8 }}>
        <input
          type="search"
          aria-label="시험지 검색"
          placeholder="시험지명 또는 ID 검색"
          value={query}
          onChange={event => changeFilter('q', event.target.value)}
          style={controlStyle}
        />
        <select aria-label="대상 팀" value={team} onChange={event => changeFilter('team', event.target.value)} style={controlStyle}>
          <option value="">전체 팀</option>
          {teams.map(code => <option key={code} value={code}>{code}</option>)}
        </select>
        <select aria-label="사용 여부" value={usage} onChange={event => changeFilter('usage', event.target.value)} style={controlStyle}>
          <option value="">사용 여부 전체</option>
          <option value="used">사용 중</option>
          <option value="unused">미사용</option>
        </select>
      </div>

      {papers.length === 0 ? (
        <div style={stateStyle}>생성된 시험지가 없습니다.</div>
      ) : filtered.length === 0 ? (
        <div style={stateStyle}>검색 조건에 맞는 시험지가 없습니다.</div>
      ) : (
        <>
          <div style={{ overflowX:'auto' }}>
            <table style={{ width:'100%', borderCollapse:'collapse' }}>
              <thead>
                <tr>{['시험지명', '팀', '유형', '문항', '버전', '사용', '생성일'].map(label => <th key={label} style={thStyle}>{label}</th>)}</tr>
              </thead>
              <tbody>
                {visible.map(paper => (
                  <tr key={paper.exam_id} data-testid="exam-paper-row">
                    <td style={tdStyle}>
                      <button type="button" aria-label={`${paper.name} 상세 보기`} onClick={() => onSelect(paper.exam_id)} style={nameButtonStyle}>{paper.name}</button>
                      <div style={{ fontSize:11, color:'var(--text-muted)', marginTop:3 }}>{paper.exam_id}</div>
                    </td>
                    <td style={tdStyle}>{paper.team_code || '-'}</td>
                    <td style={tdStyle}>{EXAM_CATEGORY_LABELS[paper.exam_category] || '기초고사'}</td>
                    <td style={tdStyle}>{paper.question_count || 0}문항</td>
                    <td style={tdStyle}>v{paper.paper_version || 0}</td>
                    <td style={tdStyle}>{Number(paper.used_by_exam_count || 0) > 0 ? `${paper.used_by_exam_count}회` : '미사용'}</td>
                    <td style={tdStyle}>{paper.created_at ? paper.created_at.slice(0, 10) : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ padding:14, display:'flex', justifyContent:'center', alignItems:'center', gap:10, borderTop:'1px solid var(--border)' }}>
            <button type="button" aria-label="이전 페이지" disabled={page <= 1} onClick={() => setQuery(searchParams, setSearchParams, { page:page - 1 })} style={pageButtonStyle}>이전</button>
            <span style={{ fontSize:12, color:'var(--text-muted)' }}>{page} / {totalPages}</span>
            <button type="button" aria-label="다음 페이지" disabled={page >= totalPages} onClick={() => setQuery(searchParams, setSearchParams, { page:page + 1 })} style={pageButtonStyle}>다음</button>
          </div>
        </>
      )}
    </section>
  )
}

const panelStyle = { background:'var(--card)', border:'1px solid var(--border)', borderRadius:'var(--radius)', overflow:'hidden' }
const stateStyle = { ...panelStyle, padding:'42px 20px', textAlign:'center', color:'var(--text-muted)', fontSize:13 }
const controlStyle = { height:40, border:'1px solid var(--border)', borderRadius:7, padding:'0 11px', background:'white', color:'var(--text)', fontFamily:'var(--font)', fontSize:13 }
const thStyle = { padding:'10px 14px', textAlign:'left', background:'#F8FAFC', borderBottom:'1px solid var(--border)', color:'var(--text-muted)', fontSize:11 }
const tdStyle = { padding:'12px 14px', borderBottom:'1px solid var(--border)', color:'var(--text)', fontSize:12, verticalAlign:'middle' }
const nameButtonStyle = { border:0, padding:0, background:'transparent', color:'var(--accent-dark)', fontFamily:'var(--font)', fontSize:13, fontWeight:700, cursor:'pointer', textAlign:'left' }
const pageButtonStyle = { border:'1px solid var(--border)', borderRadius:6, padding:'6px 12px', background:'white', color:'var(--text)', fontFamily:'var(--font)', fontSize:12, cursor:'pointer' }
