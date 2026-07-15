import { useState, useEffect, Fragment } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch, apiUpload, logout as apiLogout } from '../api'

/* ── SVG Icon ──────────────────────────────────────────────── */
function Icon({ name, size = 16, style }) {
  const paths = {
    grid:     <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    file:     <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></>,
    clock:    <><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></>,
    book:     <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></>,
    users:    <><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>,
    chart:    <><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></>,
    logout:   <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></>,
    user:     <><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></>,
    check:    <><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></>,
    star:     <><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></>,
    plus:     <><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></>,
    refresh:  <><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></>,
    ai:       <><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></>,
    swap:     <><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></>,
    trash:    <><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></>,
    edit:     <><path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></>,
    up:       <><polyline points="18 15 12 9 6 15"/></>,
    down:     <><polyline points="6 9 12 15 18 9"/></>,
    chevronLeft:  <><polyline points="15 18 9 12 15 6"/></>,
    chevronRight: <><polyline points="9 18 15 12 9 6"/></>,
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"
         strokeLinejoin="round" style={style}>
      {paths[name]}
    </svg>
  )
}

/* ── Toast ─────────────────────────────────────────────────── */
function useToast() {
  const [toasts, setToasts] = useState([])
  function toast(msg, type = 'success') {
    const id = Math.random()
    setToasts(prev => [...prev, { id, msg, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 2500)
  }
  function ToastContainer() {
    return (
      <div style={{ position:'fixed', top:16, right:16, zIndex:9999, display:'flex', flexDirection:'column', gap:8 }}>
        {toasts.map(t => (
          <div key={t.id} style={{
            padding:'10px 18px', borderRadius:8, fontSize:12, fontWeight:700,
            boxShadow:'0 4px 12px rgba(0,0,0,0.15)', animation:'fadeIn .2s ease',
            background: t.type === 'success' ? 'var(--success)' : 'var(--danger)', color:'white',
          }}>{t.msg}</div>
        ))}
      </div>
    )
  }
  return { toast, ToastContainer }
}

/* ── Shared UI ──────────────────────────────────────────────── */
function Badge({ type, children }) {
  const colors = {
    success: { background:'var(--success-light)', color:'var(--success)' },
    warning: { background:'var(--warning-light)', color:'var(--warning)' },
    danger:  { background:'var(--danger-light)',  color:'var(--danger)' },
    blue:    { background:'var(--accent-light)',  color:'var(--accent-dark)' },
    gray:    { background:'#F1F5F9',              color:'var(--text-muted)' },
  }
  return (
    <span style={{ fontSize:11, fontWeight:700, padding:'3px 8px', borderRadius:20, ...colors[type] }}>
      {children}
    </span>
  )
}

function Card({ title, action, children, noPad, style, bodyStyle }) {
  return (
    <div style={{ background:'var(--card)', borderRadius:'var(--radius)', border:'1px solid var(--border)', marginBottom:16, overflow:'hidden', ...style }}>
      {title && (
        <div style={{ padding:'13px 20px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap', gap:8, flexShrink:0 }}>
          <span style={{ fontSize:14, fontWeight:700, color:'var(--text)' }}>{title}</span>
          {action}
        </div>
      )}
      <div style={{ ...(noPad ? {} : { padding:'20px' }), ...bodyStyle }}>{children}</div>
    </div>
  )
}

function DataTable({ headers, children }) {
  return (
    <table style={{ width:'100%', borderCollapse:'collapse' }}>
      <thead>
        <tr>{headers.map(h => (
          <th key={h} style={{ fontSize:11, fontWeight:700, color:'var(--text-muted)', textAlign:'left', padding:'10px 18px', borderBottom:'1px solid var(--border)', background:'#F8FAFC', textTransform:'uppercase', letterSpacing:'0.05em', whiteSpace:'nowrap' }}>{h}</th>
        ))}</tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  )
}

function BtnPrimary({ onClick, children, style, disabled }) {
  return (
    <button onClick={onClick} disabled={disabled}
      style={{ background: disabled ? '#94A3B8' : 'var(--accent)', color:'white', border:'none', borderRadius:7, padding:'10px 18px', fontFamily:'var(--font)', fontSize:14, fontWeight:700, cursor: disabled ? 'not-allowed' : 'pointer', display:'inline-flex', alignItems:'center', gap:6, ...style }}
      onMouseOver={e => { if (!disabled) e.currentTarget.style.background='var(--accent-dark)' }}
      onMouseOut={e => { if (!disabled) e.currentTarget.style.background='var(--accent)' }}>
      {children}
    </button>
  )
}

function BtnOutlineSm({ onClick, children, danger, disabled }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{ border:`1.5px solid ${danger ? 'var(--danger)' : 'var(--accent)'}`, background:'white', color: danger ? 'var(--danger)' : 'var(--accent)', borderRadius:6, padding:'6px 13px', fontFamily:'var(--font)', fontSize:12, cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.6 : 1, fontWeight:600, whiteSpace:'nowrap', display:'inline-flex', alignItems:'center', gap:5 }}>
      {children}
    </button>
  )
}

function FilterSelect({ value, onChange, children }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)} style={{ border:'1.5px solid var(--border)', borderRadius:6, padding:'7px 10px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', background:'white', cursor:'pointer', outline:'none' }}>
      {children}
    </select>
  )
}

function FormInput({ label, ...props }) {
  return (
    <div style={{ marginBottom:14 }}>
      {label && <label style={{ display:'block', fontSize:12, fontWeight:700, color:'var(--text)', marginBottom:6, letterSpacing:'0.01em' }}>{label}</label>}
      <input style={{ width:'100%', border:'1.5px solid var(--border)', borderRadius:6, padding:'9px 12px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', background:'white', outline:'none' }} {...props} />
    </div>
  )
}

function StatusDot({ mode }) {
  const c = { live:'var(--success)', mock:'var(--warning)', offline:'var(--text-light)' }
  return <span style={{ width:7, height:7, borderRadius:'50%', background:c[mode] || c.offline, display:'inline-block', flexShrink:0 }} />
}

function Modal({ title, onClose, wide, children }) {
  return (
    <div onClick={onClose} style={{ position:'fixed', inset:0, background:'rgba(15,23,42,0.6)', backdropFilter:'blur(4px)', zIndex:200, display:'flex', alignItems:'center', justifyContent:'center', padding:20 }}>
      <div onClick={e => e.stopPropagation()} style={{ background:'white', borderRadius:16, width:'100%', maxWidth: wide ? 720 : 480, maxHeight:'85vh', display:'flex', flexDirection:'column', boxShadow:'0 20px 60px rgba(0,0,0,0.25)' }}>
        <div style={{ padding:'16px 22px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', justifyContent:'space-between', flexShrink:0 }}>
          <span style={{ fontSize:15, fontWeight:800, color:'var(--text)' }}>{title}</span>
          <button onClick={onClose} style={{ border:'none', background:'none', cursor:'pointer', color:'var(--text-muted)', fontSize:20, lineHeight:1, padding:4 }}>×</button>
        </div>
        <div style={{ padding:'18px 22px', overflowY:'auto' }}>{children}</div>
      </div>
    </div>
  )
}

function buildPageList(current, total) {
  const delta = 1
  const range = []
  for (let i = Math.max(2, current - delta); i <= Math.min(total - 1, current + delta); i++) range.push(i)
  const pages = [1]
  if (range[0] > 2) pages.push('…')
  pages.push(...range)
  if (range[range.length - 1] < total - 1) pages.push('…')
  if (total > 1) pages.push(total)
  return pages
}

function ExamPagination({ page, totalPages, onChange }) {
  const navBtnStyle = disabled => ({
    width:30, height:30, display:'flex', alignItems:'center', justifyContent:'center',
    border:'none', background:'none', borderRadius:8, padding:0,
    color: disabled ? 'var(--text-light)' : 'var(--text-muted)',
    cursor: disabled ? 'default' : 'pointer', transition:'background .15s, color .15s',
  })
  return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:2, padding:'12px 20px 20px', borderTop:'1px solid var(--border)' }}>
      <button
        onClick={() => onChange(Math.max(1, page - 1))}
        disabled={page === 1}
        aria-label="이전 페이지"
        style={navBtnStyle(page === 1)}
        onMouseOver={e => { if (page !== 1) { e.currentTarget.style.background = '#F1F5F9'; e.currentTarget.style.color = 'var(--text)' } }}
        onMouseOut={e => { e.currentTarget.style.background = 'none'; e.currentTarget.style.color = page === 1 ? 'var(--text-light)' : 'var(--text-muted)' }}
      >
        <Icon name="chevronLeft" size={15} />
      </button>

      {buildPageList(page, totalPages).map((p, i) => p === '…' ? (
        <span key={`ellipsis-${i}`} style={{ width:26, textAlign:'center', fontSize:12, color:'var(--text-light)' }}>···</span>
      ) : (
        <button key={p} onClick={() => onChange(p)}
          style={{
            minWidth:30, height:30, padding:'0 3px', border:'none', background:'none',
            fontFamily:'var(--font)', fontSize:13, fontVariantNumeric:'tabular-nums',
            fontWeight: p === page ? 800 : 500,
            color: p === page ? 'var(--text)' : 'var(--text-muted)',
            borderBottom: p === page ? '2px solid var(--accent)' : '2px solid transparent',
            cursor:'pointer', transition:'color .15s, border-color .15s',
          }}>
          {p}
        </button>
      ))}

      <button
        onClick={() => onChange(Math.min(totalPages, page + 1))}
        disabled={page === totalPages}
        aria-label="다음 페이지"
        style={navBtnStyle(page === totalPages)}
        onMouseOver={e => { if (page !== totalPages) { e.currentTarget.style.background = '#F1F5F9'; e.currentTarget.style.color = 'var(--text)' } }}
        onMouseOut={e => { e.currentTarget.style.background = 'none'; e.currentTarget.style.color = page === totalPages ? 'var(--text-light)' : 'var(--text-muted)' }}
      >
        <Icon name="chevronRight" size={15} />
      </button>
    </div>
  )
}

/* ── Views ──────────────────────────────────────────────────── */

const TEAM_LABELS = { T1:'1팀 (주간)', T2:'2팀 (4조3교대)', T3:'3팀 (3조2교대)' }

const DEFAULT_EXAM_DURATION_MIN = 60

const EXAM_STATUS_META = {
  done:      { label:'완료',   dot:'var(--success)', badge:'success' },
  ongoing:   { label:'진행중', dot:'var(--warning)',  badge:'warning' },
  scheduled: { label:'예정',   dot:'var(--text-light)', badge:'gray' },
}

function getExamStatus(examDatetime, durationMin = DEFAULT_EXAM_DURATION_MIN) {
  if (!examDatetime) return 'scheduled'
  const start = new Date(examDatetime)
  if (isNaN(start.getTime())) return 'scheduled'
  const now = new Date()
  if (now < start) return 'scheduled'
  if (now > new Date(start.getTime() + durationMin * 60 * 1000)) return 'done'
  return 'ongoing'
}

const EXAM_PAGE_SIZE = 4
const EXAM_LIST_CAP = 12
const EXAM_MANAGE_PAGE_SIZE = 8

function Dashboard({ onNavigate }) {
  const [examSets, setExamSets] = useState([])
  const [examStatusFilter, setExamStatusFilter] = useState('all')
  const [examPage, setExamPage] = useState(1)
  const [modal, setModal] = useState(null)
  const [modalData, setModalData] = useState(null)
  const [modalLoading, setModalLoading] = useState(false)

  useEffect(() => {
    apiFetch('GET', '/api/admin/exam-sets').then(d => setExamSets(d.sets || [])).catch(() => {})
  }, [])

  useEffect(() => { setExamPage(1) }, [examStatusFilter])

  const EXAM_STATUS_FILTERS = [
    { key:'all',       label:'전체' },
    { key:'done',      label:'완료' },
    { key:'ongoing',   label:'진행중' },
    { key:'scheduled', label:'예정' },
  ]

  const filteredAllSets = [...examSets]
    .filter(s => examStatusFilter === 'all' || getExamStatus(s.exam_datetime, s.duration_min) === examStatusFilter)
    .sort((a, b) => (b.exam_datetime || '').localeCompare(a.exam_datetime || ''))
  const hasMoreSets = filteredAllSets.length > EXAM_LIST_CAP
  const filteredSets = filteredAllSets.slice(0, EXAM_LIST_CAP)

  const examTotalPages = Math.max(1, Math.ceil(filteredSets.length / EXAM_PAGE_SIZE))
  const examPageClamped = Math.min(examPage, examTotalPages)
  const pagedSets = filteredSets.slice((examPageClamped - 1) * EXAM_PAGE_SIZE, examPageClamped * EXAM_PAGE_SIZE)
  const showMoreCard = hasMoreSets && examPageClamped === examTotalPages
  const visibleSets = showMoreCard ? pagedSets.slice(0, -1) : pagedSets
  const hiddenSetCount = filteredAllSets.length - EXAM_LIST_CAP

  function closeModal() { setModal(null); setModalData(null) }

  async function openQuestions(set) {
    setModal({ set })
    setModalLoading(true)
    setModalData(null)
    try {
      const d = await apiFetch('GET', `/api/admin/exam-sets/${set.exam_id}/questions`)
      setModalData(d)
    } catch (e) { setModalData({ error: e.message }) }
    finally { setModalLoading(false) }
  }

  const CARD_ACTIONS = {
    scheduled: [
      { label:'문제 보기', onClick: s => openQuestions(s) },
      { label:'시험 관리', onClick: s => onNavigate('exam-assign', { focusExamId: s.exam_id }) },
    ],
    ongoing: [
      { label:'응시 현황', onClick: () => onNavigate('exam-status') },
      { label:'시험 관리', onClick: s => onNavigate('exam-assign', { focusExamId: s.exam_id }) },
    ],
    done: [
      { label:'결과 보기', onClick: () => onNavigate('results') },
      { label:'문제 보기', onClick: s => openQuestions(s) },
    ],
  }

  // 업무 흐름 순서대로: 문제 생성 → 검토·검증 → 시험지 생성 → 시험 생성·관리 → 사용자 승인 → 응시 현황 → 결과 분석
  const quickActions = [
    ['ai',    '문제 생성',      'q-generate'],
    ['check', '검토·검증',      'q-review'],
    ['file',  '시험지 생성',    'exam-sheet'],
    ['users', '시험 생성·관리', 'exam-assign'],
    ['user',  '사용자 승인',    'users'],
    ['clock', '응시 현황',      'exam-status'],
    ['chart', '결과 분석',      'results'],
  ]

  return (
    <div>
      <Card
        title="시험 관리"
        noPad
        action={
          <div style={{ display:'flex', alignItems:'center', gap:12 }}>
            {EXAM_STATUS_FILTERS.map(f => (
              <label key={f.key} style={{ display:'flex', alignItems:'center', gap:5, fontSize:11, cursor:'pointer', color: examStatusFilter === f.key ? 'var(--text)' : 'var(--text-muted)', fontWeight: examStatusFilter === f.key ? 700 : 400 }}>
                <input
                  type="radio"
                  name="examStatusFilter"
                  checked={examStatusFilter === f.key}
                  onChange={() => setExamStatusFilter(f.key)}
                  style={{ accentColor:'var(--accent)', cursor:'pointer', margin:0 }}
                />
                {f.key !== 'all' && <span style={{ width:7, height:7, borderRadius:'50%', background:EXAM_STATUS_META[f.key].dot, display:'inline-block' }} />}
                {f.label}
              </label>
            ))}
          </div>
        }
      >
        {filteredSets.length === 0 ? (
          <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'24px 0' }}>생성된 시험이 없습니다.</p>
        ) : (
          <>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(320px, 1fr))', gap:16, padding:20 }}>
              {visibleSets.map(s => {
                const status = getExamStatus(s.exam_datetime, s.duration_min)
                return (
                  <div key={s.exam_id} style={{ border:'1px solid var(--border)', borderRadius:12, padding:'20px 22px', display:'flex', flexDirection:'column', gap:14, background:'white' }}>
                    <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:10 }}>
                      <span style={{ fontSize:17, fontWeight:800, color:'var(--text)', lineHeight:1.35 }}>{s.name}</span>
                      <Badge type={EXAM_STATUS_META[status].badge}>{EXAM_STATUS_META[status].label}</Badge>
                    </div>
                    <div style={{ display:'flex', flexDirection:'column', gap:7, fontSize:13, color:'var(--text-muted)' }}>
                      <div>대상 팀 · <span style={{ color:'var(--text)', fontWeight:600 }}>{TEAM_LABELS[s.team_code] || s.team_code}</span></div>
                      <div>시험 일시 · <span style={{ color:'var(--text)', fontWeight:600 }}>{s.exam_datetime ? s.exam_datetime.slice(0,16).replace('T',' ') : '미정'}</span></div>
                      <div>응시 인원 · <span style={{ color:'var(--text)', fontWeight:600 }}>{(s.assigned_users || []).length}명</span></div>
                    </div>
                    <div style={{ display:'flex', gap:8, marginTop:'auto', paddingTop:6 }}>
                      {CARD_ACTIONS[status].map(a => (
                        <BtnOutlineSm key={a.label} onClick={() => a.onClick(s)}>{a.label}</BtnOutlineSm>
                      ))}
                    </div>
                  </div>
                )
              })}
              {showMoreCard && (
                <button onClick={() => onNavigate('exam-assign')}
                  style={{
                    border:'1px solid var(--border)', borderRadius:12, padding:'20px 22px',
                    display:'flex', flexDirection:'column', justifyContent:'space-between', gap:16,
                    background:'linear-gradient(155deg, var(--accent-light) 0%, white 60%)',
                    cursor:'pointer', fontFamily:'var(--font)', textAlign:'left',
                    transition:'border-color .15s, transform .15s',
                  }}
                  onMouseOver={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.transform = 'translateY(-2px)' }}
                  onMouseOut={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.transform = 'translateY(0)' }}
                >
                  <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:10 }}>
                    <span style={{ fontSize:17, fontWeight:800, color:'var(--text)', lineHeight:1.35 }}>시험 더 보기</span>
                    <div style={{ width:30, height:30, borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', background:'var(--accent)', flexShrink:0 }}>
                      <Icon name="chevronRight" size={14} style={{ color:'white' }} />
                    </div>
                  </div>
                  <div>
                    <span style={{ fontSize:32, fontWeight:800, color:'var(--accent-dark)', fontVariantNumeric:'tabular-nums', lineHeight:1 }}>+{hiddenSetCount}</span>
                    <span style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', marginLeft:6 }}>개 더 있음</span>
                  </div>
                  <span style={{ fontSize:12, color:'var(--text-muted)' }}>시험 생성·관리에서 전체 목록 확인</span>
                </button>
              )}
            </div>
            {examTotalPages > 1 && (
              <ExamPagination page={examPageClamped} totalPages={examTotalPages} onChange={setExamPage} />
            )}
          </>
        )}
      </Card>

      <Card title="빠른 실행">
        <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
          {quickActions.map(([icon, label, view]) => (
            <button key={view} onClick={() => onNavigate(view)}
              style={{ display:'flex', alignItems:'center', gap:8, padding:'9px 16px', border:'1px solid var(--border)', borderRadius:8, background:'white', fontFamily:'var(--font)', fontSize:13, fontWeight:600, color:'var(--text)', cursor:'pointer' }}>
              <Icon name={icon} size={14} style={{ opacity:0.55 }} />{label}
            </button>
          ))}
        </div>
      </Card>

      {modal && (
        <Modal
          title={`${modal.set.name} · 문제 목록`}
          onClose={closeModal}
          wide
        >
          {modalLoading ? (
            <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'24px 0' }}>불러오는 중...</p>
          ) : modalData?.error ? (
            <p style={{ fontSize:13, color:'var(--danger)', textAlign:'center', padding:'24px 0' }}>오류: {modalData.error}</p>
          ) : (modalData?.questions || []).length === 0 ? (
            <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'24px 0' }}>문제가 없습니다.</p>
          ) : (
            <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
              {modalData.questions.map((q, i) => (
                <div key={q.question_id} style={{ border:'1px solid var(--border)', borderRadius:8, padding:'10px 14px' }}>
                  <div style={{ fontSize:11, color:'var(--text-muted)', marginBottom:4 }}>
                    {i + 1}. {q.question_id} · {q.category} · <span style={{ fontWeight:700 }}>{q.difficulty}</span>
                  </div>
                  <div style={{ fontSize:13, fontWeight:600, color:'var(--text)', marginBottom:6 }}>{q.question}</div>
                  <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:4 }}>
                    {['A','B','C','D'].map(k => (
                      <div key={k} style={{ fontSize:12, color: q.answer === k ? 'var(--success)' : 'var(--text-muted)', fontWeight: q.answer === k ? 700 : 400 }}>
                        {k}. {q.options[k]}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}
    </div>
  )
}

/* ── 문제 생성 (AI API 호출) ─────────────────────────────────── */
function QuestionGenerate({ toast, onNavigate }) {
  const [mode, setMode] = useState('preset')
  const [team, setTeam] = useState('T1')
  const [teams, setTeams] = useState([])
  const [diff, setDiff] = useState('중급')
  const [count, setCount] = useState('25문항')
  const [material, setMaterial] = useState('')
  const [bulkCount, setBulkCount] = useState(50)
  const [bulkCats, setBulkCats] = useState(['공통','팀별','환경안전','일반상식'])
  const [preview, setPreview] = useState(null)
  const [provider, setProvider] = useState(null)
  const [loading, setLoading] = useState(false)
  const [openPreviewId, setOpenPreviewId] = useState(null)
  const [examName, setExamName] = useState('')
  const [materialStatus, setMaterialStatus] = useState(null)
  const [scanning, setScanning] = useState(false)

  const DIFF_MAP = { '초급': '하', '중급': '중', '고급': '상' }
  const COUNT_MAP = { '10문항': 10, '20문항': 20, '25문항': 25 }

  useEffect(() => {
    apiFetch('GET', '/api/admin/teams').then(d => setTeams(d.teams || [])).catch(() => {})
  }, [])

  function refreshMaterialStatus() {
    if (!team) return
    apiFetch('GET', `/api/admin/materials/status?team_code=${team}`)
      .then(setMaterialStatus)
      .catch(() => setMaterialStatus(null))
  }

  useEffect(refreshMaterialStatus, [team])

  async function scanNewMaterials() {
    setScanning(true)
    try {
      const res = await apiFetch('POST', '/api/admin/materials/scan', { team_code: team })
      refreshMaterialStatus()
      const skipped = Object.values(res.categories || {}).flatMap(c => c.skipped || [])
      if (skipped.length > 0) {
        toast(`스캔 완료 (일부 파일 제외: ${skipped.map(s => s.name).join(', ')} — 파일 크기 초과)`, 'error')
      } else {
        toast('교육자료 스캔 완료! 다음 문제 생성부터 반영됩니다.')
      }
    } catch (e) { toast(`스캔 실패: ${e.message}`, 'error') }
    finally { setScanning(false) }
  }

  const newMaterialFiles = materialStatus
    ? Object.values(materialStatus.categories || {}).flatMap(c => c.new_files || [])
    : []

  async function generate() {
    setLoading(true)
    setOpenPreviewId(null)
    try {
      const data = await apiFetch('POST', '/api/admin/generate-ai-questions', {
        team_code: team,
        material_text: material,
        count: COUNT_MAP[count],
        difficulty_hint: DIFF_MAP[diff],
      })
      setPreview(data.questions)
      setProvider(data.provider)
      toast('문제 생성 완료! 검토·검증 탭에서 승인 후 문제은행에 등록됩니다.')
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
    finally { setLoading(false) }
  }

  async function handleSave() {
    if (!examName.trim()) { toast('시험지 이름을 입력해주세요.', 'error'); return }
    if (!preview || preview.length === 0) { toast('먼저 문제를 생성해주세요.', 'error'); return }
    try {
      const question_ids = preview.map(q => q.id || q.question_id).filter(Boolean)
      const res = await apiFetch('POST', '/api/admin/exam-sets', { name: examName.trim(), team_code: team, question_ids })
      if (res.invalid_question_ids?.length > 0) {
        toast(`시험지가 저장됐지만, 존재하지 않는 문제 ${res.invalid_question_ids.length}개는 제외됐습니다.`, 'error')
      } else {
        toast('시험지가 저장됐습니다.')
      }
    } catch (e) { toast(`저장 실패: ${e.message}`, 'error') }
  }

  function handlePdf() {
    if (!preview || preview.length === 0) { toast('먼저 문제를 생성해주세요.', 'error'); return }
    const teamLabel = teamOpts.find(([val]) => val === team)?.[1] || team
    const title = examName.trim() || '(주)엑스티 OJT 기초고사'
    const rows = preview.map((q, i) => {
      const opts = q.options || {}
      return `
        <div class="question">
          <p class="q-text"><span class="q-num">${i + 1}.</span> ${q.question}</p>
          <ol class="opts">
            ${['A','B','C','D'].map(k => opts[k] ? `<li><span class="opt-label">${k}.</span>${opts[k]}</li>` : '').join('')}
          </ol>
        </div>`
    }).join('')

    const html = `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<title>${title}</title>
<style>
  @page { size: A4; margin: 20mm 18mm; }
  body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; font-size: 10.5pt; color: #1a1a1a; }
  h1 { font-size: 16pt; font-weight: 800; text-align: center; margin-bottom: 4px; }
  .meta { text-align: center; font-size: 10pt; color: #555; margin-bottom: 24px; }
  hr { border: none; border-top: 1px solid #e2e8f0; margin: 0 0 20px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 24px; }
  .question { page-break-inside: avoid; margin-bottom: 14px; }
  .q-text { font-size: 10.5pt; font-weight: 600; line-height: 1.55; margin: 0 0 6px 0; }
  .q-num { font-weight: 800; color: #1e3a5f; }
  .opts { list-style: none; padding: 0; margin: 0 0 0 14px; }
  .opts li { display: flex; align-items: flex-start; gap: 6px; font-size: 10pt; padding: 2px 0; line-height: 1.45; }
  .opt-label { font-weight: 700; min-width: 16px; color: #555; }
</style>
</head>
<body>
  <h1>${title}</h1>
  <p class="meta">${teamLabel} · ${preview.length}문항 · 응시일: ___년 ___월 ___일 &nbsp;&nbsp; 성명: ________________ &nbsp;&nbsp; 사원번호: ________________</p>
  <hr/>
  <div class="grid">${rows}</div>
</body>
</html>`

    const win = window.open('', '_blank')
    win.document.write(html)
    win.document.close()
    win.focus()
    setTimeout(() => { win.print() }, 300)
  }

  function toggleCat(cat) {
    setBulkCats(prev => prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat])
  }

  const teamOpts = (teams.length > 0 ? teams : [{ team_code:'T1', team_name:'1팀' }, { team_code:'T2', team_name:'2팀' }, { team_code:'T3', team_name:'3팀' }])
    .map(t => [t.team_code, t.team_name])
  const diffOpts = ['초급','중급','고급']
  const countOpts = ['10문항','20문항','25문항']
  const catOpts = ['공통','팀별','환경안전','일반상식']

  const modeTabStyle = (m) => ({
    flex:1, border:'none', padding:'9px 4px', cursor:'pointer',
    fontFamily:'var(--font)', fontSize:13, fontWeight: mode===m ? 700 : 400,
    background: mode===m ? 'var(--accent)' : 'white',
    color: mode===m ? 'white' : 'var(--text-muted)',
  })

  return (
    <div style={{ display:'grid', gridTemplateColumns:'2fr 3fr', gap:14 }}>
      <Card title="시험 생성" action={<BtnOutlineSm>이전 시험 불러오기</BtnOutlineSm>}>
        <div style={{ fontSize:12, fontWeight:700, color:'var(--text)', marginBottom:8 }}>1. 직무 / 팀 선택</div>
        <div style={{ display:'flex', gap:6, marginBottom:14 }}>
          {teamOpts.map(([val, label]) => (
            <button key={val} onClick={() => setTeam(val)} style={{ flex:1, background: team===val ? 'var(--accent-light)' : 'white', border:`1.5px solid ${team===val ? 'var(--accent)' : 'var(--border)'}`, borderRadius:8, padding:'10px 4px', cursor:'pointer', fontFamily:'var(--font)', fontSize:12, color: team===val ? 'var(--accent-dark)' : 'var(--text-muted)', fontWeight: team===val ? 700 : 400, lineHeight:1.4, textAlign:'center' }}>
              <div style={{ marginBottom:3, display:'flex', justifyContent:'center' }}><Icon name="users" size={13} style={{ opacity:0.6 }} /></div>
              {label}
            </button>
          ))}
        </div>

        {materialStatus?.has_new_any && (
          <div style={{ background:'var(--warning-light)', border:'1px solid #FDE68A', borderRadius:8, padding:'10px 12px', marginBottom:14, fontSize:12, color:'var(--warning)' }}>
            <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:6, fontWeight:700 }}>
              <span style={{ width:6, height:6, borderRadius:'50%', background:'#F59E0B', flexShrink:0, display:'inline-block' }} />
              새로운 교육자료가 업로드되었습니다
            </div>
            <div style={{ color:'var(--text-muted)', marginBottom:8 }}>
              {newMaterialFiles.map(f => f.name).join(', ')} — 추가로 스캔하여 문제 생성에 반영하시겠습니까?
            </div>
            <BtnOutlineSm onClick={scanNewMaterials} disabled={scanning}>{scanning ? '스캔 중...' : '지금 스캔하기'}</BtnOutlineSm>
          </div>
        )}

        {mode === 'preset' && (<>
          <div style={{ fontSize:12, fontWeight:700, color:'var(--text)', marginBottom:8 }}>2. 난이도</div>
          <div style={{ display:'flex', border:'1.5px solid var(--border)', borderRadius:7, overflow:'hidden', marginBottom:14 }}>
            {diffOpts.map(d => (
              <button key={d} onClick={() => setDiff(d)} style={{ flex:1, border:'none', borderRight:'1px solid var(--border)', padding:'9px 4px', cursor:'pointer', fontFamily:'var(--font)', fontSize:13, background: diff===d ? 'var(--accent)' : 'white', color: diff===d ? 'white' : 'var(--text-muted)', fontWeight: diff===d ? 700 : 400 }}>{d}</button>
            ))}
          </div>
          <div style={{ fontSize:12, fontWeight:700, color:'var(--text)', marginBottom:8 }}>3. 문항 수</div>
          <div style={{ display:'flex', border:'1.5px solid var(--border)', borderRadius:7, overflow:'hidden', marginBottom:14 }}>
            {countOpts.map(c => (
              <button key={c} onClick={() => setCount(c)} style={{ flex:1, border:'none', borderRight:'1px solid var(--border)', padding:'9px 4px', cursor:'pointer', fontFamily:'var(--font)', fontSize:13, background: count===c ? 'var(--accent)' : 'white', color: count===c ? 'white' : 'var(--text-muted)', fontWeight: count===c ? 700 : 400 }}>{c}</button>
            ))}
          </div>
          <div style={{ fontSize:12, fontWeight:700, color:'var(--text)', marginBottom:8 }}>4. 교육자료 추가 입력 (선택)</div>
          <textarea
            value={material}
            onChange={e => setMaterial(e.target.value)}
            placeholder="Google Drive에 스캔해둔 교육자료가 자동으로 포함됩니다. 이번 출제에만 추가로 반영할 내용이 있다면 붙여넣으세요."
            style={{ width:'100%', minHeight:88, border:'1.5px solid var(--border)', borderRadius:7, padding:'9px 10px', fontFamily:'var(--font)', fontSize:12, color:'var(--text)', resize:'vertical', boxSizing:'border-box', marginBottom:14, outline:'none' }}
          />
        </>)}

        {mode === 'bulk' && (<>
          <div style={{ fontSize:12, fontWeight:700, color:'var(--text)', marginBottom:8 }}>2. 카테고리 선택 <span style={{ fontSize:11, fontWeight:400, color:'var(--text-muted)' }}>(복수 선택 가능)</span></div>
          <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginBottom:14 }}>
            {catOpts.map(cat => {
              const on = bulkCats.includes(cat)
              return (
                <button key={cat} onClick={() => toggleCat(cat)} style={{ padding:'7px 14px', borderRadius:20, border:`1.5px solid ${on ? 'var(--accent)' : 'var(--border)'}`, background: on ? 'var(--accent-light)' : 'white', color: on ? 'var(--accent-dark)' : 'var(--text-muted)', fontFamily:'var(--font)', fontSize:12, fontWeight: on ? 700 : 400, cursor:'pointer' }}>
                  {on ? '✓ ' : ''}{cat}
                </button>
              )
            })}
          </div>
          <div style={{ fontSize:12, fontWeight:700, color:'var(--text)', marginBottom:8 }}>3. 생성 문항 수</div>
          <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:6 }}>
            <input type="range" min={10} max={200} step={10} value={bulkCount}
              onChange={e => setBulkCount(Number(e.target.value))}
              style={{ flex:1, accentColor:'var(--accent)' }} />
            <span style={{ fontSize:18, fontWeight:800, color:'var(--accent)', minWidth:52, textAlign:'right', fontVariantNumeric:'tabular-nums' }}>{bulkCount}문</span>
          </div>
          <div style={{ fontSize:11, color:'var(--text-muted)', marginBottom:14 }}>
            선택 카테고리 {bulkCats.length}개 · 카테고리당 약 {bulkCats.length ? Math.round(bulkCount / bulkCats.length) : 0}문항
          </div>
        </>)}

        <BtnPrimary onClick={generate} style={{ width:'100%', justifyContent:'center', marginBottom:10 }}>
          <Icon name="ai" size={14} style={{ color:'white' }} />
          {loading ? '생성 중...' : mode === 'bulk' ? `${bulkCount}문항 일괄 생성` : 'AI 문제 생성'}
        </BtnPrimary>
        <div style={{ fontSize:11, color:'var(--warning)', background:'var(--warning-light)', border:'1px solid #FDE68A', borderRadius:6, padding:'7px 10px' }}>
          생성된 문제는 <strong>검토·검증</strong> 탭에서 승인 후 문제은행에 등록됩니다.{provider && ` (${provider.toUpperCase()} 모드)`}
        </div>
      </Card>

      <Card title="시험 문제 미리보기" action={<span style={{ fontSize:11, fontWeight:700, color:'var(--success)', background:'var(--success-light)', padding:'3px 8px', borderRadius:20 }}>{preview ? `${preview.length}문항 생성됨` : '—'}</span>}>
        {!preview ? (
          <p style={{ color:'var(--text-muted)', fontSize:13, textAlign:'center', padding:'24px 0' }}>팀을 선택하고 'AI 문제 생성'을 눌러주세요.</p>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:4, maxHeight:600, overflowY:'auto' }}>
            {preview.map((q, i) => {
              const isOpen = openPreviewId === (q.id || i)
              const opts = q.options || {}
              return (
                <div key={q.id || i} style={{ border:'1px solid var(--border)', borderRadius:7, overflow:'hidden' }}>
                  <div
                    onClick={() => setOpenPreviewId(isOpen ? null : (q.id || i))}
                    style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'9px 12px', cursor:'pointer', background: isOpen ? 'var(--accent-light)' : 'white' }}
                  >
                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{ fontSize:11, color:'var(--text-muted)' }}>문항 {i+1} · {q.category} · {q.difficulty}</div>
                      <div style={{ fontSize:12, color:'var(--text)', fontWeight:500, lineHeight:1.4, marginTop:2 }}>{q.question}</div>
                    </div>
                    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2.5" strokeLinecap="round" style={{ transition:'transform 0.2s', transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)', flexShrink:0, marginLeft:8 }}>
                      <path d="M6 9l6 6 6-6"/>
                    </svg>
                  </div>
                  {isOpen && (
                    <div style={{ padding:'10px 14px', background:'var(--bg)', borderTop:'1px solid var(--border)' }}>
                      <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
                        {['A','B','C','D'].map(k => opts[k] ? (
                          <div key={k} style={{ display:'flex', alignItems:'flex-start', gap:8 }}>
                            <span style={{ width:20, height:20, borderRadius:'50%', flexShrink:0, background:'var(--border)', color:'var(--text-muted)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:10, fontWeight:700 }}>{k}</span>
                            <span style={{ fontSize:12, color:'var(--text)', lineHeight:1.5, paddingTop:2 }}>{opts[k]}</span>
                          </div>
                        ) : null)}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
        <div style={{ height:1, background:'var(--border)', margin:'16px 0' }} />
        <input
          value={examName}
          onChange={e => setExamName(e.target.value)}
          placeholder="시험지 이름 입력"
          style={{ width:'100%', border:'1.5px solid var(--border)', borderRadius:7, padding:'9px 10px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', boxSizing:'border-box', marginBottom:8, outline:'none' }}
        />
        <div style={{ display:'flex', gap:8 }}>
          <button onClick={handlePdf} style={{ flex:1, border:'1.5px solid var(--border)', background:'white', color:'var(--text-muted)', borderRadius:7, padding:'9px 14px', fontFamily:'var(--font)', fontSize:13, cursor:'pointer' }}>PDF 생성</button>
          <button onClick={handleSave} style={{ flex:1, background:'var(--accent)', color:'white', border:'none', borderRadius:7, padding:'10px 16px', fontFamily:'var(--font)', fontSize:13, fontWeight:700, cursor:'pointer' }}>시험지 저장</button>
        </div>
      </Card>
    </div>
  )
}

/* ── 검토·검증 ───────────────────────────────────────────────── */
function ExamReview({ toast }) {
  const [items, setItems] = useState(null)
  const [selected, setSelected] = useState(null)
  const [rejectReason, setRejectReason] = useState('')
  const [rejectingId, setRejectingId] = useState(null)

  async function load() {
    try {
      const data = await apiFetch('GET', '/api/admin/questions?status=reviewing')
      setItems(data.questions)
      if (data.questions.length > 0 && !selected) setSelected(data.questions[0])
    } catch (e) { toast?.(`오류: ${e.message}`, 'error') }
  }

  useEffect(() => { load() }, [])

  async function approveQ(qid) {
    try {
      await apiFetch('POST', `/api/admin/questions/${qid}/approve`)
      toast?.(`${qid} 승인 완료`, 'success')
      setSelected(null)
      load()
    } catch (e) { toast?.(`오류: ${e.message}`, 'error') }
  }

  async function rejectQ(qid) {
    if (!rejectReason.trim()) { toast?.('반려 사유를 입력해주세요.', 'error'); return }
    try {
      await apiFetch('POST', `/api/admin/questions/${qid}/reject`, { reason: rejectReason })
      toast?.(`${qid} 반려 처리됨`)
      setRejectingId(null); setRejectReason(''); setSelected(null)
      load()
    } catch (e) { toast?.(`오류: ${e.message}`, 'error') }
  }

  const q = selected

  return (
    <div style={{ display:'grid', gridTemplateColumns:'240px 1fr', gap:14 }}>
      <Card title={`검토 대기 ${items ? `(${items.length})` : ''}`} noPad>
        {!items ? (
          <p style={{ textAlign:'center', color:'var(--text-muted)', padding:20, fontSize:13 }}>불러오는 중...</p>
        ) : items.length === 0 ? (
          <p style={{ textAlign:'center', color:'var(--text-muted)', padding:20, fontSize:13 }}>검토 대기 문제가 없습니다.</p>
        ) : items.map(item => (
          <div key={item.question_id} onClick={() => { setSelected(item); setRejectingId(null); setRejectReason('') }}
            style={{ padding:'10px 14px', borderBottom:'1px solid var(--border)', cursor:'pointer',
              background: selected?.question_id === item.question_id ? 'var(--accent-light)' : 'white' }}>
            <div style={{ fontSize:11, color:'var(--text-muted)', marginBottom:3, display:'flex', gap:4 }}>
              <span>{item.question_id}</span>
              {item.flags?.warning && <span>⚠️</span>}
              {item.flags?.security_hold && <span>🔒</span>}
            </div>
            <div style={{ fontSize:12, color:'var(--text)', fontWeight:500, lineHeight:1.4,
              overflow:'hidden', display:'-webkit-box', WebkitLineClamp:2, WebkitBoxOrient:'vertical' }}>
              {item.question}
            </div>
            <div style={{ fontSize:11, color:'var(--text-muted)', marginTop:3 }}>{item.category}</div>
          </div>
        ))}
      </Card>

      <Card title="문항 검토" action={<BtnOutlineSm onClick={load}><Icon name="refresh" size={11} /> 새로고침</BtnOutlineSm>}>
        {!q ? (
          <p style={{ textAlign:'center', color:'var(--text-muted)', padding:'32px 0', fontSize:13 }}>
            {items?.length === 0 ? '검토 대기 문제가 없습니다.' : '좌측 목록에서 문항을 선택하세요.'}
          </p>
        ) : (
          <>
            <div style={{ display:'flex', gap:8, marginBottom:12, flexWrap:'wrap' }}>
              <span style={{ fontSize:11, color:'var(--text-muted)', background:'var(--bg)', border:'1px solid var(--border)', padding:'3px 8px', borderRadius:4 }}>{q.question_id}</span>
              <span style={{ fontSize:11, color:'var(--text-muted)', background:'var(--bg)', border:'1px solid var(--border)', padding:'3px 8px', borderRadius:4 }}>{q.category}</span>
              <Badge type="blue">{q.difficulty_ai || q.difficulty_init || '?'}</Badge>
              {q.flags?.warning && <Badge type="warning">⚠️ 카테고리 불일치</Badge>}
              {q.flags?.security_hold && <Badge type="danger">🔒 보안 키워드</Badge>}
            </div>

            <div style={{ fontSize:14, fontWeight:600, color:'var(--text)', marginBottom:12, lineHeight:1.6 }}>{q.question}</div>

            <div style={{ display:'flex', flexDirection:'column', gap:6, marginBottom:14 }}>
              {['A','B','C','D'].map(opt => {
                const text = q[`option_${opt.toLowerCase()}`]
                const isAnswer = q.answer === opt
                return (
                  <div key={opt} style={{ display:'flex', alignItems:'center', gap:8, fontSize:13, padding:'8px 12px', borderRadius:6,
                    border:`1px solid ${isAnswer ? 'var(--success)' : 'var(--border)'}`,
                    background: isAnswer ? 'var(--success-light)' : 'white',
                    color: isAnswer ? 'var(--success)' : 'var(--text)', fontWeight: isAnswer ? 600 : 400 }}>
                    <span style={{ width:22, height:22, borderRadius:'50%', flexShrink:0, fontSize:11, fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center',
                      background: isAnswer ? 'var(--success)' : 'var(--border)', color: isAnswer ? 'white' : 'var(--text-muted)' }}>{opt}</span>
                    {text}
                  </div>
                )
              })}
            </div>

            {q.explanation && (
              <div style={{ fontSize:12, color:'var(--text-muted)', background:'var(--bg)', border:'1px solid var(--border)', borderRadius:6, padding:'10px 12px', marginBottom:14, lineHeight:1.6 }}>
                <span style={{ fontWeight:700, color:'var(--text)', marginRight:6 }}>해설</span>{q.explanation}
              </div>
            )}

            {rejectingId === q.question_id ? (
              <div style={{ display:'flex', gap:8, marginBottom:10 }}>
                <input value={rejectReason} onChange={e => setRejectReason(e.target.value)}
                  placeholder="반려 사유 입력 (필수)"
                  style={{ flex:1, border:'1.5px solid var(--danger)', borderRadius:6, padding:'8px 10px', fontFamily:'var(--font)', fontSize:13, outline:'none' }} />
                <BtnOutlineSm danger onClick={() => rejectQ(q.question_id)}>반려 확정</BtnOutlineSm>
                <BtnOutlineSm onClick={() => { setRejectingId(null); setRejectReason('') }}>취소</BtnOutlineSm>
              </div>
            ) : (
              <div style={{ display:'flex', gap:8 }}>
                <BtnOutlineSm danger onClick={() => setRejectingId(q.question_id)}>✕ 반려</BtnOutlineSm>
                <BtnPrimary onClick={() => approveQ(q.question_id)}>✓ 승인 → 문제은행 등록</BtnPrimary>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  )
}

/* ── 문제은행 (승인된 문제 목록) ─────────────────────────────── */
function QuestionBank({ toast, onNavigate }) {
  const [items, setItems] = useState(null)
  const [stats, setStats] = useState({})
  const [cat, setCat] = useState('')
  const [statusFilter, setStatusFilter] = useState('approved')
  const [rejectingId, setRejectingId] = useState(null)
  const [rejectReason, setRejectReason] = useState('')
  const [reasonCodes, setReasonCodes] = useState({})

  useEffect(() => {
    apiFetch('GET', '/api/admin/question-stats').then(data => setStats(data.stats || {})).catch(() => {})
  }, [])

  const STATUS_TABS = [
    { value: 'approved',  label: '승인 (문제은행)' },
    { value: 'reviewing', label: '검토대기' },
    { value: 'rejected',  label: '반려' },
    { value: '',          label: '전체' },
  ]

  async function load(sf = statusFilter) {
    try {
      let path = '/api/admin/questions?'
      if (cat) path += `category=${encodeURIComponent(cat)}&`
      if (sf)  path += `status=${sf}&`
      const data = await apiFetch('GET', path)
      setItems(data.questions)
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
  }

  async function updateDiff(qid, newDiff) {
    const reasonCode = reasonCodes[qid] || ''
    if (!reasonCode) { toast('사유 코드를 선택해주세요.', 'error'); return }
    try {
      await apiFetch('PATCH', '/api/admin/difficulty', { question_id: qid, new_difficulty: newDiff, reason_code: reasonCode })
      toast(`${qid} 난이도 → ${newDiff} 변경 완료`)
      setReasonCodes(prev => { const n = {...prev}; delete n[qid]; return n })
      load()
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
  }

  async function approveQ(qid) {
    try {
      await apiFetch('POST', `/api/admin/questions/${qid}/approve`)
      toast(`${qid} 승인 완료`, 'success')
      load()
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
  }

  async function rejectQ(qid) {
    if (!rejectReason.trim()) { toast('반려 사유를 입력해주세요.', 'error'); return }
    try {
      await apiFetch('POST', `/api/admin/questions/${qid}/reject`, { reason: rejectReason })
      toast(`${qid} 반려 처리됨`)
      setRejectingId(null); setRejectReason(''); load()
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
  }

  function switchTab(v) {
    setStatusFilter(v)
    load(v)
  }

  return (
    <Card title="문제은행" noPad action={
      <div style={{ display:'flex', gap:8 }}>
        <FilterSelect value={cat} onChange={setCat}>
          <option value="">전체 카테고리</option>
          <option value="공통">공통</option>
          <option value="팀별">팀별</option>
          <option value="환경안전">환경안전</option>
          <option value="일반상식">일반상식</option>
        </FilterSelect>
        <BtnOutlineSm onClick={() => load()}>조회</BtnOutlineSm>
        <BtnPrimary onClick={() => onNavigate('exam-sheet')} style={{ padding:'6px 14px', fontSize:13 }}>
          <Icon name="file" size={13} style={{ color:'white' }} /> 시험지 생성
        </BtnPrimary>
      </div>
    }>
      <div style={{ display:'flex', borderBottom:'1px solid var(--border)', padding:'0 20px', background:'var(--bg)' }}>
        {STATUS_TABS.map(tab => (
          <button key={tab.value} onClick={() => switchTab(tab.value)}
            style={{ padding:'9px 14px', fontSize:12, cursor:'pointer', border:'none', borderBottom: statusFilter===tab.value ? '2px solid var(--accent)' : '2px solid transparent', background:'none', fontFamily:'var(--font)', fontWeight: statusFilter===tab.value ? 700 : 500, color: statusFilter===tab.value ? 'var(--accent)' : 'var(--text-muted)', marginBottom:-1 }}>
            {tab.label}
          </button>
        ))}
      </div>
      <div style={{ padding:'9px 20px', background:'var(--bg)', borderBottom:'1px solid var(--border)', fontSize:12, color:'var(--text-muted)' }}>
        {statusFilter === 'approved'
          ? '승인된 문제만 시험지 생성에 사용됩니다. 난이도 조정은 즉시 반영됩니다.'
          : '난이도 드롭다운 변경은 즉시 반영됩니다. 승인/반려는 검토대기 문제에서 가능합니다.'}
      </div>
      <div style={{ padding:'14px 20px' }}>
        {!items ? (
          <p style={{ color:'var(--text-muted)', textAlign:'center', padding:'28px 0', fontSize:13 }}>조회 버튼을 눌러 문제를 불러오세요.</p>
        ) : items.length === 0 ? (
          <p style={{ color:'var(--text-muted)', textAlign:'center', padding:'28px 0', fontSize:13 }}>
            {statusFilter === 'approved' ? '승인된 문제가 없습니다. 검토·검증 탭에서 승인해주세요.' : '문제가 없습니다.'}
          </p>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
            {items.map(q => {
              const d = q.admin_override || q.difficulty_ai || q.difficulty_init
              const isReviewing = q.status === 'reviewing'
              const isRejecting = rejectingId === q.question_id
              return (
                <div key={q.question_id} style={{ border:'1px solid var(--border)', borderRadius:8, overflow:'hidden' }}>
                  <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'10px 12px' }}>
                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{ fontSize:11, color:'var(--text-muted)', marginBottom:3, display:'flex', alignItems:'center', gap:6 }}>
                        <span>{q.question_id} · {q.category}</span>
                        <StatusBadge status={q.status} />
                        {q.flags?.warning && <span title="카테고리·팀 불일치">⚠️</span>}
                        {q.flags?.security_hold && <span title="보안 키워드 감지">🔒</span>}
                        {stats[q.question_id]?.exam_count > 0 && (
                          <span title="누적 출제 횟수" style={{ fontSize:11, color:'var(--text-muted)' }}>
                            출제 {stats[q.question_id].exam_count}회
                          </span>
                        )}
                        {stats[q.question_id]?.flagged_frequent && <Badge type="warning">자주 출제됨</Badge>}
                      </div>
                      <div style={{ fontSize:12, color:'var(--text)', fontWeight:500, lineHeight:1.4 }}>{q.question}</div>
                    </div>
                    <div style={{ display:'flex', alignItems:'center', gap:6, flexShrink:0, marginLeft:12 }}>
                      <Badge type="blue">{d}</Badge>
                      <select value={reasonCodes[q.question_id] || ''}
                        onChange={e => setReasonCodes(prev => ({...prev, [q.question_id]: e.target.value}))}
                        style={{ border:'1.5px solid var(--border)', borderRadius:6, padding:'5px 8px', fontFamily:'var(--font)', fontSize:12, cursor:'pointer', background:'white', outline:'none', color: reasonCodes[q.question_id] ? 'var(--text)' : 'var(--text-muted)' }}>
                        <option value="">사유 선택</option>
                        <option value="AI오류">AI 오류</option>
                        <option value="실무반영">실무 반영</option>
                        <option value="학습자수준">학습자 수준</option>
                        <option value="기타">기타</option>
                      </select>
                      <select value={d} onChange={e => updateDiff(q.question_id, e.target.value)}
                        style={{ border:'1.5px solid var(--border)', borderRadius:6, padding:'5px 8px', fontFamily:'var(--font)', fontSize:12, cursor:'pointer', background:'white', outline:'none' }}>
                        <option value="하">하</option><option value="중">중</option><option value="상">상</option>
                      </select>
                      {isReviewing && (
                        <>
                          <BtnOutlineSm onClick={() => approveQ(q.question_id)}>✓ 승인</BtnOutlineSm>
                          <BtnOutlineSm danger onClick={() => { setRejectingId(isRejecting ? null : q.question_id); setRejectReason('') }}>✕ 반려</BtnOutlineSm>
                        </>
                      )}
                    </div>
                  </div>
                  {isRejecting && (
                    <div style={{ padding:'10px 12px', borderTop:'1px solid var(--border)', background:'var(--danger-light)', display:'flex', gap:8, alignItems:'center' }}>
                      <input value={rejectReason} onChange={e => setRejectReason(e.target.value)}
                        placeholder="반려 사유를 입력하세요 (필수)"
                        style={{ flex:1, border:'1.5px solid var(--danger)', borderRadius:6, padding:'7px 10px', fontFamily:'var(--font)', fontSize:12, outline:'none', background:'white' }} />
                      <BtnOutlineSm danger onClick={() => rejectQ(q.question_id)}>반려 확정</BtnOutlineSm>
                      <BtnOutlineSm onClick={() => setRejectingId(null)}>취소</BtnOutlineSm>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </Card>
  )
}

/* ── 시험지 생성 (자동 배분 + 피드백 편집) ───────────────────── */
function ExamSheet({ toast, onNavigate }) {
  const [examName, setExamName] = useState('')
  const [team, setTeam] = useState('T1')
  const [teams, setTeams] = useState([])
  const [totalCount, setTotalCount] = useState(25)
  const [excludeFrequent, setExcludeFrequent] = useState(false)
  const [maxExamCount, setMaxExamCount] = useState(5)
  const [manualMode, setManualMode] = useState(false)
  const [manualUpper, setManualUpper] = useState(7)
  const [manualMid, setManualMid] = useState(10)
  const [manualLow, setManualLow] = useState(8)
  const [questions, setQuestions] = useState(null)
  const [loading, setLoading] = useState(false)
  const [swapTargetIdx, setSwapTargetIdx] = useState(null)
  const [swapPool, setSwapPool] = useState([])
  const [selectedIdx, setSelectedIdx] = useState(0)

  useEffect(() => {
    apiFetch('GET', '/api/admin/teams').then(d => setTeams(d.teams || [])).catch(() => {})
  }, [])

  const teamOpts = (teams.length > 0 ? teams : [{ team_code:'T1', team_name:'1팀' }, { team_code:'T2', team_name:'2팀' }, { team_code:'T3', team_name:'3팀' }])
    .map(t => [t.team_code, t.team_name])

  async function assign() {
    if (manualMode && (manualUpper + manualMid + manualLow) !== totalCount) {
      toast('합계가 총 문항수와 맞지 않습니다.', 'error'); return
    }
    setLoading(true)
    setSwapTargetIdx(null)
    try {
      const body = { team_code: team, total_count: totalCount }
      if (manualMode) body.manual_dist = { 상: manualUpper, 중: manualMid, 하: manualLow }
      if (excludeFrequent) body.max_exam_count = maxExamCount
      const data = await apiFetch('POST', '/api/admin/preview-exam', body)
      const qs = data.questions
      setQuestions(qs.map((q, i) => ({ ...q, _order: i + 1 })))
      setSelectedIdx(0)
      toast(`${qs.length}문항 ${manualMode ? '수동' : '자동'} 배분 완료. 순서 변경·문제 교체가 가능합니다.`)
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
    finally { setLoading(false) }
  }

  function moveUp(i) {
    if (i === 0) return
    setQuestions(prev => {
      const arr = [...prev]
      ;[arr[i - 1], arr[i]] = [arr[i], arr[i - 1]]
      return arr
    })
  }

  function moveDown(i) {
    setQuestions(prev => {
      if (i === prev.length - 1) return prev
      const arr = [...prev]
      ;[arr[i], arr[i + 1]] = [arr[i + 1], arr[i]]
      return arr
    })
  }

  function removeQ(i) {
    setQuestions(prev => prev.filter((_, idx) => idx !== i))
    setSelectedIdx(prev => Math.max(0, i < prev ? prev - 1 : (i === prev ? 0 : prev)))
    toast('문제가 제거됐습니다.')
  }

  async function openSwap(idx) {
    if (swapTargetIdx === idx) { setSwapTargetIdx(null); return }
    setSwapTargetIdx(idx)
    try {
      const current = questions[idx]
      const currentId = current.id || current.question_id
      const diff = current.difficulty || ''
      const path = `/api/admin/questions?status=approved${diff ? `&difficulty=${diff}` : ''}`
      const data = await apiFetch('GET', path)
      const pool = (data.questions || []).filter(q => q.question_id !== currentId)
      setSwapPool(pool.slice(0, 5))
    } catch {
      setSwapPool([])
    }
  }

  function swapQuestion(idx, replacement) {
    // 교체 후보(replacement)는 /api/admin/questions(문제은행 원본 스키마: option_a..d,
    // difficulty_ai/difficulty_init/admin_override)에서 오지만, 시험지 문항은 미리보기
    // 스키마(options.A..D, difficulty)를 쓰므로 필드명을 맞춰줘야 함
    // (안 맞추면 교체된 문항만 난이도 배지·PDF 보기가 깨짐)
    const normalized = {
      id: replacement.question_id || replacement.id,
      category: replacement.category,
      question: replacement.question,
      options: replacement.options || {
        A: replacement.option_a,
        B: replacement.option_b,
        C: replacement.option_c,
        D: replacement.option_d,
      },
      difficulty: replacement.difficulty || replacement.admin_override || replacement.difficulty_ai || replacement.difficulty_init || '중',
      answer: replacement.answer,
    }
    setQuestions(prev => {
      const arr = [...prev]
      arr[idx] = { ...normalized, _order: arr[idx]._order }
      return arr
    })
    setSwapTargetIdx(null)
    toast('문제 교체 완료')
  }

  async function handleSave() {
    if (!examName.trim()) { toast('시험지 이름을 입력해주세요.', 'error'); return }
    if (!questions || questions.length === 0) { toast('먼저 문제를 배분해주세요.', 'error'); return }
    try {
      const question_ids = questions.map(q => q.id || q.question_id).filter(Boolean)
      const res = await apiFetch('POST', '/api/admin/exam-sets', { name: examName.trim(), team_code: team, question_ids })
      if (res.invalid_question_ids?.length > 0) {
        toast(`시험지가 저장됐지만, 존재하지 않는 문제 ${res.invalid_question_ids.length}개는 제외됐습니다.`, 'error')
      } else {
        toast('시험지가 저장됐습니다.')
      }
    } catch (e) { toast(`저장 실패: ${e.message}`, 'error') }
  }

  function buildExamHtml() {
    const teamLabel = { T1:'1팀 (주간)', T2:'2팀 (4조3교대)', T3:'3팀 (3조2교대)' }[team] || team
    const title = examName.trim() || '(주)엑스티 OJT 기초고사'
    const rows = questions.map((q, i) => {
      const opts = q.options || {}
      return `
        <div class="question">
          <p class="q-text"><span class="q-num">${i + 1}.</span> ${q.question}</p>
          <ol class="opts">
            ${['A','B','C','D'].map(k => opts[k] ? `<li><span class="opt-label">${k}.</span>${opts[k]}</li>` : '').join('')}
          </ol>
        </div>`
    }).join('')

    return `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<title>${title}</title>
<style>
  @page { size: A4; margin: 20mm 18mm; }
  body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; font-size: 10.5pt; color: #1a1a1a; }
  h1 { font-size: 16pt; font-weight: 800; text-align: center; margin-bottom: 4px; }
  .meta { text-align: center; font-size: 10pt; color: #555; margin-bottom: 24px; }
  hr { border: none; border-top: 1px solid #e2e8f0; margin: 0 0 20px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 24px; }
  .question { page-break-inside: avoid; margin-bottom: 14px; }
  .q-text { font-size: 10.5pt; font-weight: 600; line-height: 1.55; margin: 0 0 6px 0; }
  .q-num { font-weight: 800; color: #1e3a5f; }
  .opts { list-style: none; padding: 0; margin: 0 0 0 14px; }
  .opts li { display: flex; align-items: flex-start; gap: 6px; font-size: 10pt; padding: 2px 0; line-height: 1.45; }
  .opt-label { font-weight: 700; min-width: 16px; color: #555; }
</style>
</head>
<body>
  <h1>${title}</h1>
  <p class="meta">${teamLabel} · ${questions.length}문항 · 응시일: ___년 ___월 ___일 &nbsp;&nbsp; 성명: ________________ &nbsp;&nbsp; 사원번호: ________________</p>
  <hr/>
  <div class="grid">${rows}</div>
</body>
</html>`
  }

  function handlePdf() {
    if (!questions || questions.length === 0) { toast('먼저 문제를 배분해주세요.', 'error'); return }
    const win = window.open('', '_blank')
    win.document.write(buildExamHtml())
    win.document.close()
    win.focus()
    setTimeout(() => { win.print() }, 300)
  }

  function handleHtmlSave() {
    if (!questions || questions.length === 0) { toast('먼저 문제를 배분해주세요.', 'error'); return }
    const blob = new Blob([buildExamHtml()], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${examName.trim() || '시험지'}.html`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast('HTML 파일이 저장됐습니다.')
  }

  const diffColor = { 상:'var(--danger)', 중:'var(--warning)', 하:'var(--success)' }
  const diffCount = questions
    ? { 상: questions.filter(q => q.difficulty === '상').length,
        중: questions.filter(q => q.difficulty === '중').length,
        하: questions.filter(q => q.difficulty === '하').length }
    : null

  const selected = questions && questions.length > 0 ? questions[Math.min(selectedIdx, questions.length - 1)] : null

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:20, height:'100%', minHeight:0 }}>
      <Card title="시험지 설정" style={{ flexShrink:0 }}>
        <div style={{ display:'grid', gridTemplateColumns:'1.3fr 1.3fr 1.4fr 1.3fr auto', gap:12, alignItems:'end' }}>
          <div>
            <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>시험지 이름</label>
            <input
              type="text"
              value={examName}
              onChange={e => setExamName(e.target.value)}
              placeholder="예) 2024년 하반기 OJT 기초고사"
              style={{ width:'100%', height:44, border:'1px solid var(--border)', borderRadius:8, padding:'0 12px', fontFamily:'var(--font)', fontSize:14, color:'var(--text)', outline:'none', boxSizing:'border-box' }}
            />
          </div>

          <div>
            <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>대상 팀</label>
            <div style={{ display:'flex', height:44, border:'1px solid var(--border)', borderRadius:8, overflow:'hidden' }}>
              {teamOpts.map(([val, label], idx) => (
                <button key={val} onClick={() => setTeam(val)}
                  style={{ flex:1, border:'none', borderLeft: idx > 0 ? '1px solid var(--border)' : 'none', background: team === val ? 'var(--accent)' : 'white', color: team === val ? 'white' : 'var(--text-muted)', fontFamily:'var(--font)', fontSize:13, fontWeight: team === val ? 700 : 500, cursor:'pointer', transition:'background .15s, color .15s' }}>
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>총 문항 수</label>
            <div style={{ display:'flex', alignItems:'center', gap:10, height:44 }}>
              <input type="range" min={10} max={50} step={5} value={totalCount}
                onChange={e => setTotalCount(Number(e.target.value))}
                style={{ flex:1, accentColor:'var(--accent)' }} />
              <span style={{ fontSize:16, fontWeight:800, color:'var(--accent)', minWidth:30, textAlign:'right', fontVariantNumeric:'tabular-nums' }}>{totalCount}</span>
            </div>
          </div>

          <div>
            <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>출제 횟수 제한</label>
            <div style={{ display:'flex', alignItems:'center', gap:8, height:44 }}>
              <button
                onClick={() => setExcludeFrequent(v => !v)}
                style={{ border:`1.5px solid ${excludeFrequent ? 'var(--accent)' : 'var(--border)'}`, background: excludeFrequent ? 'var(--accent-light)' : 'white', color: excludeFrequent ? 'var(--accent-dark)' : 'var(--text-muted)', borderRadius:20, padding:'5px 12px', fontFamily:'var(--font)', fontSize:12, fontWeight: excludeFrequent ? 700 : 400, cursor:'pointer', flexShrink:0 }}
              >{excludeFrequent ? 'ON' : 'OFF'}</button>
              {excludeFrequent && (
                <>
                  <input type="range" min={1} max={20} step={1} value={maxExamCount}
                    onChange={e => setMaxExamCount(Number(e.target.value))}
                    style={{ flex:1, accentColor:'var(--accent)' }} />
                  <span style={{ fontSize:16, fontWeight:800, color:'var(--accent)', minWidth:24, textAlign:'right', fontVariantNumeric:'tabular-nums' }}>{maxExamCount}</span>
                </>
              )}
            </div>
          </div>

          <BtnPrimary onClick={assign} style={{ height:44 }} disabled={loading}>
            <Icon name="refresh" size={14} style={{ color:'white' }} />
            {loading ? '배분 중...' : (manualMode ? '수동 배분' : '자동 배분')}
          </BtnPrimary>
        </div>

        <div style={{ display:'flex', alignItems:'center', gap:8, marginTop:14 }}>
          <span style={{ fontSize:12, fontWeight:600, color:'var(--text-muted)' }}>수동 배분</span>
          <button
            onClick={() => setManualMode(m => !m)}
            style={{ border:`1.5px solid ${manualMode ? 'var(--accent)' : 'var(--border)'}`, background: manualMode ? 'var(--accent-light)' : 'white', color: manualMode ? 'var(--accent-dark)' : 'var(--text-muted)', borderRadius:20, padding:'3px 10px', fontFamily:'var(--font)', fontSize:11, fontWeight: manualMode ? 700 : 400, cursor:'pointer' }}
          >{manualMode ? 'ON' : 'OFF'}</button>
          {!manualMode && (
            <span style={{ fontSize:11, color:'var(--text-muted)' }}>
              자동 배분: 상 {Math.round(totalCount*0.28)}·중 {Math.round(totalCount*0.40)}·하 {Math.round(totalCount*0.32)}문항 (예상)
            </span>
          )}
        </div>

        {manualMode && (
          <div style={{ marginTop:12, display:'flex', alignItems:'center', gap:16, flexWrap:'wrap' }}>
            {[
              ['상', manualUpper, setManualUpper, '#b91c1c', '#fee2e2'],
              ['중', manualMid,   setManualMid,   '#b45309', '#fef3c7'],
              ['하', manualLow,   setManualLow,   '#065f46', '#d1fae5'],
            ].map(([label, val, setter, color, bg]) => (
              <div key={label} style={{ display:'flex', alignItems:'center', gap:8 }}>
                <span style={{ fontSize:11, fontWeight:700, padding:'2px 8px', borderRadius:20, background:bg, color, minWidth:24, textAlign:'center' }}>{label}</span>
                <input type="number" min={0} max={totalCount} value={val}
                  onChange={e => setter(Math.max(0, Math.min(totalCount, Number(e.target.value))))}
                  style={{ width:56, border:'1.5px solid var(--border)', borderRadius:6, padding:'5px 8px', fontFamily:'var(--font)', fontSize:13, textAlign:'center', outline:'none' }}
                />
                <span style={{ fontSize:11, color:'var(--text-muted)' }}>문항</span>
              </div>
            ))}
            <span style={{ fontSize:11, color: (manualUpper+manualMid+manualLow) === totalCount ? 'var(--success)' : 'var(--danger)', fontWeight:600 }}>
              합계: {manualUpper+manualMid+manualLow} / {totalCount}문항
              {(manualUpper+manualMid+manualLow) !== totalCount && ' ← 총 문항수와 맞춰주세요'}
            </span>
          </div>
        )}

        {questions && (
          <div style={{ marginTop:14, fontSize:11, color:'var(--text-muted)', background:'var(--bg)', border:'1px solid var(--border)', borderRadius:6, padding:'8px 10px' }}>
            현재 시험지: <strong>{questions.length}문항</strong>
            {diffCount && (
              <span style={{ marginLeft:6 }}>
                · 상 <span style={{ color:'var(--danger)', fontWeight:700 }}>{diffCount.상}</span>
                · 중 <span style={{ color:'var(--warning)', fontWeight:700 }}>{diffCount.중}</span>
                · 하 <span style={{ color:'var(--success)', fontWeight:700 }}>{diffCount.하}</span>
              </span>
            )}
          </div>
        )}
      </Card>

      {questions && (
        <Card title="시험지 저장" style={{ flexShrink:0 }}>
          <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
            <button onClick={handleSave} style={{ background:'var(--accent)', color:'white', border:'none', borderRadius:7, padding:'10px 18px', fontFamily:'var(--font)', fontSize:13, fontWeight:700, cursor:'pointer' }}>
              시험지 저장
            </button>
            <button onClick={handlePdf} style={{ border:'1.5px solid var(--border)', background:'white', color:'var(--text-muted)', borderRadius:7, padding:'9px 18px', fontFamily:'var(--font)', fontSize:13, cursor:'pointer' }}>
              PDF 저장
            </button>
            <button onClick={handleHtmlSave} style={{ border:'1.5px solid var(--border)', background:'white', color:'var(--text-muted)', borderRadius:7, padding:'9px 18px', fontFamily:'var(--font)', fontSize:13, cursor:'pointer' }}>
              HTML 저장
            </button>
            <button onClick={() => onNavigate('q-bank')} style={{ border:'1.5px solid var(--accent)', background:'white', color:'var(--accent)', borderRadius:7, padding:'9px 18px', fontFamily:'var(--font)', fontSize:13, fontWeight:600, cursor:'pointer' }}>
              문제은행으로 이동
            </button>
          </div>
        </Card>
      )}

      {!questions ? (
        <Card style={{ flex:1, minHeight:0 }}>
          <div style={{ textAlign:'center', padding:'48px 0', color:'var(--text-muted)' }}>
            <Icon name="file" size={36} style={{ opacity:0.2, display:'block', margin:'0 auto 12px' }} />
            <p style={{ fontSize:13 }}>조건을 설정하고 '자동 배분'을 눌러주세요.</p>
            <p style={{ fontSize:11, marginTop:6 }}>문제은행의 승인된 문제에서 자동으로 배분됩니다.</p>
          </div>
        </Card>
      ) : (
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, flex:1, minHeight:0 }}>
          <Card
            title={`문제 목록 (${questions.length}문항)`}
            noPad
            style={{ height:'100%', display:'flex', flexDirection:'column', marginBottom:0 }}
            bodyStyle={{ flex:1, minHeight:0, overflowY:'auto', padding:14 }}
          >
            <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
              {questions.map((q, i) => {
                const diff = q.difficulty || '중'
                const isSwapOpen = swapTargetIdx === i
                const isSelected = selectedIdx === i
                return (
                  <div key={`${q.id ?? q.question_id ?? i}-${i}`}
                    style={{ border:`1px solid ${isSwapOpen ? 'var(--accent)' : (isSelected ? 'var(--accent)' : 'var(--border)')}`, borderRadius:8, overflow:'hidden', transition:'border-color .15s', background: isSelected ? 'var(--accent-light)' : 'white' }}>
                    <div onClick={() => setSelectedIdx(i)} style={{ display:'flex', alignItems:'center', gap:8, padding:'10px 12px', cursor:'pointer' }}>
                      {/* 순서 번호 */}
                      <span style={{ width:24, height:24, borderRadius:'50%', background:'var(--accent)', color:'white', fontSize:11, fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0, fontVariantNumeric:'tabular-nums' }}>{i + 1}</span>

                      {/* 문제 내용 */}
                      <div style={{ flex:1, minWidth:0 }}>
                        <div style={{ fontSize:11, color:'var(--text-muted)', marginBottom:2 }}>
                          {q.id || q.question_id} · {q.category}
                          <span style={{ marginLeft:6, fontWeight:700, color: diffColor[diff] || 'var(--text-muted)' }}>[{diff}]</span>
                        </div>
                        <div style={{ fontSize:13, color:'var(--text)', fontWeight:500, lineHeight:1.4,
                          overflow:'hidden', whiteSpace:'nowrap', textOverflow:'ellipsis' }}>{q.question}</div>
                      </div>

                      {/* 편집 버튼들 */}
                      <div onClick={e => e.stopPropagation()} style={{ display:'flex', alignItems:'center', gap:4, flexShrink:0 }}>
                        <button onClick={() => moveUp(i)} disabled={i === 0}
                          title="위로" style={{ border:'1px solid var(--border)', background:'white', borderRadius:5, padding:'4px 6px', cursor: i === 0 ? 'not-allowed' : 'pointer', opacity: i === 0 ? 0.3 : 1, display:'flex', alignItems:'center' }}>
                          <Icon name="up" size={12} style={{ color:'var(--text-muted)' }} />
                        </button>
                        <button onClick={() => moveDown(i)} disabled={i === questions.length - 1}
                          title="아래로" style={{ border:'1px solid var(--border)', background:'white', borderRadius:5, padding:'4px 6px', cursor: i === questions.length - 1 ? 'not-allowed' : 'pointer', opacity: i === questions.length - 1 ? 0.3 : 1, display:'flex', alignItems:'center' }}>
                          <Icon name="down" size={12} style={{ color:'var(--text-muted)' }} />
                        </button>
                        <button onClick={() => openSwap(i)}
                          title="문제 교체" style={{ border:`1px solid ${isSwapOpen ? 'var(--accent)' : 'var(--border)'}`, background: isSwapOpen ? 'var(--accent-light)' : 'white', borderRadius:5, padding:'4px 7px', cursor:'pointer', display:'flex', alignItems:'center', gap:3, fontSize:11, color: isSwapOpen ? 'var(--accent-dark)' : 'var(--text-muted)', fontWeight: isSwapOpen ? 700 : 400 }}>
                          <Icon name="swap" size={11} /> 교체
                        </button>
                        <button onClick={() => removeQ(i)}
                          title="제거" style={{ border:'1px solid var(--border)', background:'white', borderRadius:5, padding:'4px 6px', cursor:'pointer', display:'flex', alignItems:'center' }}>
                          <Icon name="trash" size={12} style={{ color:'var(--danger)' }} />
                        </button>
                      </div>
                    </div>

                    {/* 교체 패널 */}
                    {isSwapOpen && (
                      <div onClick={e => e.stopPropagation()} style={{ borderTop:'1px solid var(--accent)', background:'var(--accent-light)', padding:'10px 12px' }}>
                        <div style={{ fontSize:11, fontWeight:700, color:'var(--accent-dark)', marginBottom:8 }}>
                          동일 난이도({diff}) 대체 문제 선택
                        </div>
                        {swapPool.length === 0 ? (
                          <p style={{ fontSize:12, color:'var(--text-muted)' }}>대체 가능한 문제가 없습니다.</p>
                        ) : (
                          <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
                            {swapPool.map(alt => (
                              <button key={alt.question_id} onClick={() => swapQuestion(i, alt)}
                                style={{ display:'flex', alignItems:'center', gap:8, padding:'8px 10px', border:'1px solid var(--border)', borderRadius:6, background:'white', cursor:'pointer', textAlign:'left', width:'100%', fontFamily:'var(--font)' }}>
                                <span style={{ fontSize:10, padding:'2px 6px', borderRadius:4, background:'var(--accent-light)', color:'var(--accent-dark)', fontWeight:700, flexShrink:0 }}>{alt.question_id}</span>
                                <span style={{ fontSize:12, color:'var(--text)', flex:1, overflow:'hidden', whiteSpace:'nowrap', textOverflow:'ellipsis' }}>{alt.question}</span>
                                <span style={{ fontSize:11, color:'var(--text-muted)', flexShrink:0 }}>{alt.category}</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </Card>

          <Card
            title="문제 미리보기"
            style={{ height:'100%', display:'flex', flexDirection:'column', marginBottom:0 }}
            bodyStyle={{ flex:1, minHeight:0, overflowY:'auto' }}
          >
            {!selected ? (
              <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'24px 0' }}>왼쪽에서 문제를 선택하세요.</p>
            ) : (
              <div>
                <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:14 }}>
                  <span style={{ fontSize:12, color:'var(--text-muted)' }}>{selected.id || selected.question_id} · {selected.category}</span>
                  <Badge type={selected.difficulty === '상' ? 'danger' : selected.difficulty === '하' ? 'success' : 'warning'}>{selected.difficulty || '중'}</Badge>
                </div>
                <div style={{ fontSize:16, fontWeight:700, color:'var(--text)', lineHeight:1.6, marginBottom:20 }}>{selected.question}</div>
                <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
                  {['A','B','C','D'].map(k => {
                    const optText = selected.options?.[k]
                    if (!optText) return null
                    const isAnswer = selected.answer === k
                    return (
                      <div key={k} style={{ display:'flex', alignItems:'center', gap:10, padding:'12px 14px', borderRadius:8, border:`1.5px solid ${isAnswer ? 'var(--success)' : 'var(--border)'}`, background: isAnswer ? 'var(--success-light)' : 'white' }}>
                        <span style={{ width:24, height:24, borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', fontSize:12, fontWeight:700, flexShrink:0, background: isAnswer ? 'var(--success)' : '#F1F5F9', color: isAnswer ? 'white' : 'var(--text-muted)' }}>{k}</span>
                        <span style={{ fontSize:14, color:'var(--text)', flex:1 }}>{optText}</span>
                        {isAnswer && <Icon name="check" size={16} style={{ color:'var(--success)', flexShrink:0 }} />}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}

/* ── 응시 이력 ───────────────────────────────────────────────── */
function History({ toast }) {
  const [rows, setRows] = useState(null)
  const [filterTeam, setFilterTeam] = useState('')
  const [filterFrom, setFilterFrom] = useState('')
  const [filterTo, setFilterTo] = useState('')
  const [search, setSearch] = useState('')

  async function load() {
    try {
      let path = '/api/admin/logs?'
      if (filterTeam) path += `team=${filterTeam}&`
      if (filterFrom) path += `date_from=${filterFrom}&`
      if (filterTo)   path += `date_to=${filterTo}&`
      const data = await apiFetch('GET', path)
      setRows(data.logs)
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
  }

  const filtered = rows ? rows.filter(r => !search || r.name.includes(search)) : null

  return (
    <Card title="응시 이력" noPad action={
      <div style={{ display:'flex', gap:8, alignItems:'center', flexWrap:'wrap' }}>
        <FilterSelect value={filterTeam} onChange={setFilterTeam}><option value="">전체 팀</option><option value="T1">1팀</option><option value="T2">2팀</option><option value="T3">3팀</option></FilterSelect>
        <input type="date" value={filterFrom} onChange={e => setFilterFrom(e.target.value)} style={{ border:'1.5px solid var(--border)', borderRadius:6, padding:'7px 10px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', background:'white', outline:'none' }} />
        <span style={{ color:'var(--text-muted)', fontSize:13 }}>~</span>
        <input type="date" value={filterTo} onChange={e => setFilterTo(e.target.value)} style={{ border:'1.5px solid var(--border)', borderRadius:6, padding:'7px 10px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', background:'white', outline:'none' }} />
        <BtnOutlineSm onClick={load}>조회</BtnOutlineSm>
      </div>
    }>
      <div style={{ padding:'10px 20px', borderBottom:'1px solid var(--border)' }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="이름 검색" style={{ border:'1.5px solid var(--border)', borderRadius:6, padding:'7px 10px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', background:'white', maxWidth:240, width:'100%', outline:'none' }} />
      </div>
      <DataTable headers={['이름','팀','점수','결과','응시일','난이도 분포']}>
        {!filtered ? (
          <tr><td colSpan={6} style={{ textAlign:'center', color:'var(--text-muted)', padding:28, fontSize:13 }}>조회 버튼을 눌러 이력을 불러오세요.</td></tr>
        ) : filtered.length === 0 ? (
          <tr><td colSpan={6} style={{ textAlign:'center', color:'var(--text-muted)', padding:28, fontSize:13 }}>해당 조건의 이력이 없습니다.</td></tr>
        ) : filtered.map((l, i) => (
          <tr key={i}>
            <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontWeight:500 }}>{l.name}</td>
            <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)' }}>{l.team}</td>
            <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontWeight:700, fontVariantNumeric:'tabular-nums' }}>{l.score}점</td>
            <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)' }}><Badge type={l.pass ? 'success' : 'danger'}>{l.pass ? '합격' : '재교육'}</Badge></td>
            <td style={{ fontSize:12, padding:'11px 18px', borderBottom:'1px solid var(--border)', color:'var(--text-muted)', fontVariantNumeric:'tabular-nums' }}>{l.date}</td>
            <td style={{ fontSize:12, padding:'11px 18px', borderBottom:'1px solid var(--border)', color:'var(--text-muted)' }}>상{l.difficulty_dist?.상||0}/중{l.difficulty_dist?.중||0}/하{l.difficulty_dist?.하||0}</td>
          </tr>
        ))}
      </DataTable>
    </Card>
  )
}

function StatusBadge({ status }) {
  const map = {
    draft:     { type:'gray',    label:'초안' },
    reviewing: { type:'warning', label:'검토중' },
    approved:  { type:'success', label:'승인' },
    rejected:  { type:'danger',  label:'반려' },
  }
  const m = map[status] || { type:'gray', label: status }
  return <Badge type={m.type}>{m.label}</Badge>
}

/* ── 사용자 승인 ─────────────────────────────────────────────── */
function Users({ toast }) {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState({ empno:'', name:'', team:'T1', date:'' })
  const [result, setResult] = useState({ msg:'', ok:null })
  const [teams, setTeams] = useState([])
  const [csvResult, setCsvResult] = useState(null)
  const [csvLoading, setCsvLoading] = useState(false)

  async function loadUsers() {
    try { const d = await apiFetch('GET', '/api/admin/users'); setUsers(d.users) } catch {}
  }
  useEffect(() => {
    loadUsers()
    apiFetch('GET', '/api/admin/teams').then(d => setTeams(d.teams)).catch(() => {})
  }, [])

  async function approve() {
    if (!form.empno || !form.name || !form.date) { setResult({ msg:'모든 항목을 입력해주세요.', ok:false }); return }
    try {
      await apiFetch('POST', '/api/admin/approve-user', { employee_id:form.empno, name:form.name, team:form.team, exam_date:form.date })
      setResult({ msg:`${form.name} (${form.empno}) 승인 완료`, ok:true })
      setForm({ empno:'', name:'', team: teams[0]?.team_code || 'T1', date:'' })
      loadUsers()
    } catch (e) { setResult({ msg:`오류: ${e.message}`, ok:false }) }
  }

  async function del(id, name) {
    if (!confirm(`${name} (${id})을 삭제하시겠습니까?`)) return
    try { await apiFetch('DELETE', `/api/admin/users/${id}`); loadUsers() } catch (e) { toast(`삭제 실패: ${e.message}`, 'error') }
  }

  async function handleCsvUpload(e) {
    const file = e.target.files[0]
    if (!file) return
    setCsvLoading(true); setCsvResult(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const r = await apiUpload('/api/admin/upload-users', fd)
      setCsvResult(r)
      toast(`CSV 업로드 완료: 성공 ${r.success}건`, 'success')
      loadUsers()
    } catch (err) {
      setCsvResult({ error: err.message })
      toast(`CSV 업로드 실패: ${err.message}`, 'error')
    } finally {
      setCsvLoading(false)
      e.target.value = ''
    }
  }

  const teamOpts = teams.length > 0 ? teams : [{ team_code:'T1', team_name:'1팀' }, { team_code:'T2', team_name:'2팀' }, { team_code:'T3', team_name:'3팀' }]

  return (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
      <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
        <Card title="신입사원 응시 승인">
          <FormInput label="사원번호" value={form.empno} onChange={e => setForm(p=>({...p,empno:e.target.value}))} placeholder="예: 2024003" autoComplete="off" />
          <FormInput label="이름" value={form.name} onChange={e => setForm(p=>({...p,name:e.target.value}))} placeholder="홍길동" />
          <div style={{ marginBottom:14 }}>
            <label style={{ display:'block', fontSize:12, fontWeight:700, color:'var(--text)', marginBottom:6 }}>소속 팀</label>
            <select value={form.team} onChange={e => setForm(p=>({...p,team:e.target.value}))} style={{ width:'100%', border:'1.5px solid var(--border)', borderRadius:6, padding:'9px 12px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', background:'white', outline:'none' }}>
              {teamOpts.map(t => <option key={t.team_code} value={t.team_code}>{t.team_name}</option>)}
            </select>
          </div>
          <FormInput label="응시 예정일" type="date" value={form.date} onChange={e => setForm(p=>({...p,date:e.target.value}))} />
          <BtnPrimary onClick={approve} style={{ width:'100%', justifyContent:'center' }}>
            <Icon name="check" size={14} style={{ color:'white' }} /> 승인 등록
          </BtnPrimary>
          {result.msg && (
            <p style={{ marginTop:10, fontSize:12, padding:'8px 10px', borderRadius:6, background: result.ok ? 'var(--success-light)' : 'var(--danger-light)', color: result.ok ? 'var(--success)' : 'var(--danger)' }}>{result.msg}</p>
          )}
        </Card>

        <Card title="CSV 대량 업로드">
          <p style={{ fontSize:12, color:'var(--text-muted)', marginBottom:10 }}>컬럼: <code>employee_id, name, team_code, exam_date</code> (첫 행 헤더)</p>
          <label style={{ display:'inline-flex', alignItems:'center', gap:8, padding:'9px 16px', border:'1.5px dashed var(--border)', borderRadius:8, cursor:'pointer', fontSize:13, color:'var(--text)', background:'#FAFAFA', width:'100%', justifyContent:'center', boxSizing:'border-box' }}>
            <Icon name="up" size={14} />
            {csvLoading ? '업로드 중...' : 'CSV 파일 선택'}
            <input type="file" accept=".csv" style={{ display:'none' }} onChange={handleCsvUpload} disabled={csvLoading} />
          </label>
          {csvResult && !csvResult.error && (
            <div style={{ marginTop:10, fontSize:12, padding:'8px 12px', borderRadius:6, background:'var(--success-light)', color:'var(--success)' }}>
              성공 {csvResult.success}건 · 중복 skip {csvResult.skipped}건 · 오류 {csvResult.errors}건
            </div>
          )}
          {csvResult?.error && (
            <div style={{ marginTop:10, fontSize:12, padding:'8px 12px', borderRadius:6, background:'var(--danger-light)', color:'var(--danger)' }}>{csvResult.error}</div>
          )}
        </Card>
      </div>
      <Card title="승인된 응시자 목록" noPad action={<BtnOutlineSm onClick={loadUsers}><Icon name="refresh" size={11} /> 새로고침</BtnOutlineSm>}>
        <DataTable headers={['사원번호','이름','팀','응시일','상태','관리']}>
          {users.length === 0 ? (
            <tr><td colSpan={6} style={{ textAlign:'center', color:'var(--text-muted)', padding:20, fontSize:13 }}>승인된 응시자가 없습니다.</td></tr>
          ) : users.map(u => (
            <tr key={u.employee_id}>
              <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontVariantNumeric:'tabular-nums' }}>{u.employee_id}</td>
              <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)' }}>{u.name}</td>
              <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)' }}>{u.team}</td>
              <td style={{ fontSize:12, padding:'11px 18px', borderBottom:'1px solid var(--border)', color:'var(--text-muted)', fontVariantNumeric:'tabular-nums' }}>{u.exam_date || '-'}</td>
              <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)' }}><Badge type="success">승인</Badge></td>
              <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)' }}><BtnOutlineSm danger onClick={() => del(u.employee_id, u.name)}>삭제</BtnOutlineSm></td>
            </tr>
          ))}
        </DataTable>
      </Card>
    </div>
  )
}

/* ── 결과 분석 ───────────────────────────────────────────────── */
function Results() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [teamFilter, setTeamFilter] = useState([])
  const [selectedExamId, setSelectedExamId] = useState(null)
  const [expandedTaker, setExpandedTaker] = useState(null)

  useEffect(() => {
    apiFetch('GET', '/api/admin/results-analysis')
      .then(setData)
      .catch(e => setError(e.message))
  }, [])

  if (error) {
    return <Card><p style={{ fontSize:13, color:'var(--danger)', textAlign:'center', padding:'24px 0' }}>조회 실패: {error}</p></Card>
  }
  if (!data) {
    return <Card><p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'24px 0' }}>불러오는 중...</p></Card>
  }
  if (data.summary.count === 0) {
    return <Card><p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'24px 0' }}>아직 응시 결과가 없습니다.</p></Card>
  }

  const selectedExam = selectedExamId ? data.exams.find(e => e.exam_id === selectedExamId) : null
  const teamOptions = [...new Map(data.exams.map(e => [e.team_code, e.team_name])).entries()]
  const filteredExams = data.exams.filter(e => teamFilter.length === 0 || teamFilter.includes(e.team_code))

  function toggleTeamFilter(teamCode) {
    setTeamFilter(prev => prev.includes(teamCode) ? prev.filter(t => t !== teamCode) : [...prev, teamCode])
  }

  function openExam(examSetId) {
    setSelectedExamId(examSetId)
    setExpandedTaker(null)
  }

  return (
    <div>
      {selectedExam ? (
        <Card title={selectedExam.name} noPad action={<BtnOutlineSm onClick={() => setSelectedExamId(null)}>← 시험 목록으로</BtnOutlineSm>}>
          <div style={{ padding:'12px 20px', borderBottom:'1px solid var(--border)', display:'flex', gap:22, fontSize:12, color:'var(--text-muted)', flexWrap:'wrap' }}>
            <span>팀 <b style={{ color:'var(--text)' }}>{selectedExam.team_name}</b></span>
            <span>응시 인원 <b style={{ color:'var(--text)' }}>{selectedExam.taker_count}명</b></span>
            <span>평균 점수 <b style={{ color:'var(--text)' }}>{selectedExam.avg_score}점</b></span>
            <span>정답률 <b style={{ color:'var(--text)' }}>{selectedExam.accuracy_pct}%</b></span>
            <span>합격자 <b style={{ color:'var(--text)' }}>{selectedExam.pass_count}명</b></span>
          </div>
          <DataTable headers={['이름','점수','결과','응시일','']}>
            {selectedExam.takers.map((t, i) => (
              <Fragment key={i}>
                <tr style={{ cursor:'pointer' }} onClick={() => setExpandedTaker(expandedTaker === i ? null : i)}>
                  <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontWeight:500 }}>{t.name}</td>
                  <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontWeight:700, fontVariantNumeric:'tabular-nums' }}>{t.score}점</td>
                  <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)' }}><Badge type={t.pass ? 'success' : 'danger'}>{t.pass ? '합격' : '재교육'}</Badge></td>
                  <td style={{ fontSize:12, padding:'11px 18px', borderBottom:'1px solid var(--border)', color:'var(--text-muted)', fontVariantNumeric:'tabular-nums' }}>{t.date}</td>
                  <td style={{ fontSize:12, padding:'11px 18px', borderBottom:'1px solid var(--border)', color:'var(--accent)', whiteSpace:'nowrap' }}>{expandedTaker === i ? '접기 ▲' : '상세 ▼'}</td>
                </tr>
                {expandedTaker === i && (
                  <tr>
                    <td colSpan={5} style={{ padding:'4px 18px 16px', borderBottom:'1px solid var(--border)', background:'#FAFAFA' }}>
                      {t.results.length === 0 ? (
                        <p style={{ fontSize:12, color:'var(--text-muted)', margin:0 }}>문항별 상세 데이터가 없습니다.</p>
                      ) : (
                        <table style={{ width:'100%', borderCollapse:'collapse' }}>
                          <thead>
                            <tr>{['문항','난이도','정답','응답','정오'].map(h => (
                              <th key={h} style={{ textAlign:'left', fontSize:11, fontWeight:700, color:'var(--text-muted)', padding:'6px 8px', borderBottom:'1px solid var(--border)' }}>{h}</th>
                            ))}</tr>
                          </thead>
                          <tbody>
                            {t.results.map((q, qi) => (
                              <tr key={qi}>
                                <td style={{ fontSize:12, padding:'6px 8px' }}>{q.q_id}</td>
                                <td style={{ fontSize:12, padding:'6px 8px' }}>{q.difficulty || '-'}</td>
                                <td style={{ fontSize:12, padding:'6px 8px' }}>{q.answer || '-'}</td>
                                <td style={{ fontSize:12, padding:'6px 8px' }}>{q.user_answer || '-'}</td>
                                <td style={{ fontSize:12, padding:'6px 8px' }}><Badge type={q.correct ? 'success' : 'danger'}>{q.correct ? '정답' : '오답'}</Badge></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </DataTable>
        </Card>
      ) : (
        <Card
          title="시험 목록"
          noPad
          action={
            <div style={{ display:'flex', alignItems:'center', gap:12, flexWrap:'wrap' }}>
              {teamOptions.map(([code, name]) => (
                <label key={code} style={{ display:'flex', alignItems:'center', gap:5, fontSize:12, cursor:'pointer', color: teamFilter.includes(code) ? 'var(--text)' : 'var(--text-muted)', fontWeight: teamFilter.includes(code) ? 700 : 400 }}>
                  <input type="checkbox" checked={teamFilter.includes(code)} onChange={() => toggleTeamFilter(code)} style={{ accentColor:'var(--accent)', cursor:'pointer', margin:0 }} />
                  {name}
                </label>
              ))}
            </div>
          }
        >
          <DataTable headers={['시험명','팀','응시일','인원','평균점수','정답률','합격자']}>
            {filteredExams.length === 0 ? (
              <tr><td colSpan={7} style={{ textAlign:'center', color:'var(--text-muted)', padding:20, fontSize:13 }}>표시할 시험이 없습니다.</td></tr>
            ) : filteredExams.map(e => (
              <tr key={e.exam_id} style={{ cursor:'pointer' }} onClick={() => openExam(e.exam_id)}>
                <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontWeight:500 }}>{e.name}</td>
                <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)' }}>{e.team_name}</td>
                <td style={{ fontSize:12, padding:'11px 18px', borderBottom:'1px solid var(--border)', color:'var(--text-muted)', fontVariantNumeric:'tabular-nums' }}>{e.exam_datetime ? e.exam_datetime.slice(0,10) : '-'}</td>
                <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontVariantNumeric:'tabular-nums' }}>{e.taker_count}명</td>
                <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontWeight:700, fontVariantNumeric:'tabular-nums' }}>{e.avg_score}점</td>
                <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontVariantNumeric:'tabular-nums' }}>{e.accuracy_pct}%</td>
                <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontVariantNumeric:'tabular-nums' }}>{e.pass_count}명</td>
              </tr>
            ))}
          </DataTable>
        </Card>
      )}

      {data.insights.length > 0 && (
        <div style={{ background:'#EFF6FF', border:'1px solid #BFDBFE', borderRadius:8, padding:16, marginBottom:14 }}>
          <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:10 }}>
            <div style={{ width:28, height:28, background:'var(--accent)', borderRadius:6, display:'flex', alignItems:'center', justifyContent:'center' }}>
              <Icon name="chart" size={14} style={{ color:'white' }} />
            </div>
            <span style={{ fontSize:13, fontWeight:700, color:'#1E3A8A' }}>분석 인사이트</span>
          </div>
          {data.insights.map((t,i) => (
            <div key={i} style={{ display:'flex', gap:8, fontSize:12, color:'#1E40AF', lineHeight:1.5, marginBottom: i < data.insights.length-1 ? 6 : 0 }}>
              <span style={{ width:4, height:4, borderRadius:'50%', background:'var(--accent)', flexShrink:0, marginTop:6 }} />
              {t}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── 설정 ────────────────────────────────────────────────────── */
function Settings() {
  const [driveStatus, setDriveStatus] = useState('확인 중...')
  const [systemStatus, setSystemStatus] = useState(null)

  useEffect(() => {
    apiFetch('GET', '/api/drive/status')
      .then(() => setDriveStatus('연동'))
      .catch(() => setDriveStatus('미연동'))
    apiFetch('GET', '/api/admin/system-status')
      .then(setSystemStatus)
      .catch(() => setSystemStatus(null))
  }, [])

  const aiProvider = systemStatus?.ai_provider ?? '확인 중'
  const aiProviderLabel = { mock:'Mock 모드', gemini:'Gemini 연동', claude:'Claude 연동' }[aiProvider] || aiProvider
  const claudeConfigured = systemStatus?.claude_key_configured ?? false

  const groups = [
    { label:'운영 모드', rows:[
      ['데이터 소스',  `AI_PROVIDER 환경변수`,  systemStatus ? aiProviderLabel : '확인 중...', aiProvider === 'mock' ? 'mock' : 'live'],
      ['백엔드 API',   'FastAPI — localhost:8000', '실행 중',   'live'],
      ['JWT 인증',     'python-jose (구현 완료)',   '활성',      'live'],
    ]},
    { label:'외부 연동 현황', rows:[
      ['Claude API',   'CLAUDE_API_KEY 필요',   systemStatus ? (claudeConfigured ? '연동' : '미연동') : '확인 중...', claudeConfigured ? 'live' : 'offline'],
      ['Google Drive', '서비스 계정 인증',          driveStatus, driveStatus === '연동' ? 'live' : 'mock'],
    ]},
  ]

  const todos = [
    { text: 'Google Drive Service Account 연동', done: true },
    { text: '문제 상태 머신 (draft→reviewing→approved→rejected)', done: true },
    { text: '규칙 게이트 7개 (V-01~V-07)', done: true },
    { text: '시험지 스냅샷 저장 (보기 순서맵)', done: true },
    { text: '결과 JSONL 영속화 (results.jsonl)', done: true },
    { text: 'Admin UI 문제 생성 / 문제은행 / 시험지 생성 분리', done: true },
    { text: 'Claude API 문제 생성 JSON 파싱', done: false },
    { text: 'Drive 문제은행 Excel 파싱', done: false },
    { text: '난이도 AI 자동 확정 피드백 루프', done: false },
    { text: '결과 리포트 PDF 내보내기', done: false },
    { text: 'Google Drive 결과 저장 연동', done: false },
  ]

  return (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
      <Card title="시스템 설정" noPad>
        {groups.map(({ label, rows }) => (
          <div key={label}>
            <div style={{ padding:'9px 20px 7px', fontSize:10, fontWeight:700, textTransform:'uppercase', letterSpacing:'0.08em', color:'var(--text-muted)', borderBottom:'1px solid var(--border)', background:'#F8FAFC' }}>{label}</div>
            {rows.map(([name, desc, val, mode]) => (
              <div key={name} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'12px 20px', borderBottom:'1px solid var(--border)' }}>
                <div>
                  <div style={{ fontSize:13, fontWeight:600, color:'var(--text)' }}>{name}</div>
                  <div style={{ fontSize:11, color:'var(--text-muted)', marginTop:2 }}>{desc}</div>
                </div>
                <div style={{ display:'flex', alignItems:'center', gap:6, fontSize:12, fontWeight:700,
                  color: mode === 'live' ? 'var(--success)' : mode === 'mock' ? 'var(--warning)' : 'var(--text-light)' }}>
                  <StatusDot mode={mode} />{val}
                </div>
              </div>
            ))}
          </div>
        ))}
      </Card>
      <Card title="구현 현황 (TODO)" noPad>
        {todos.map((t, i) => (
          <div key={i} style={{ display:'flex', alignItems:'center', gap:10, padding:'11px 20px', borderBottom: i < todos.length-1 ? '1px solid var(--border)' : 'none' }}>
            {t.done ? (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <rect x="1" y="1" width="12" height="12" rx="2" fill="var(--success)" stroke="var(--success)" strokeWidth="1.5"/>
                <polyline points="3,7 6,10 11,4" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <rect x="1" y="1" width="12" height="12" rx="2" stroke="#CBD5E1" strokeWidth="1.5"/>
              </svg>
            )}
            <span style={{ fontSize:13, color: t.done ? 'var(--text)' : 'var(--text-muted)', fontWeight: t.done ? 500 : 400 }}>{t.text}</span>
            {t.done && <span style={{ marginLeft:'auto', fontSize:10, fontWeight:700, color:'var(--success)', background:'var(--success-light)', padding:'2px 7px', borderRadius:10 }}>완료</span>}
          </div>
        ))}
      </Card>
    </div>
  )
}

/* ── Admin Layout ───────────────────────────────────────────── */
/* ── 시험 생성·관리 ──────────────────────────────────────────── */
function ExamAssign({ toast, focusExamId, onFocusConsumed }) {
  const [sets, setSets] = useState([])
  const [users, setUsers] = useState([])
  const [papers, setPapers] = useState([])
  const [viewedSetId, setViewedSetId] = useState('')
  const [assignees, setAssignees] = useState([])
  const [userQuery, setUserQuery] = useState('')
  const [selectedUser, setSelectedUser] = useState('')
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [focusedIdx, setFocusedIdx] = useState(-1)
  const [assigning, setAssigning] = useState(false)
  const [assignError, setAssignError] = useState('')

  const [createForm, setCreateForm] = useState({ paperId: '', name: '', datetime: '', durationMin: 60, passScore: 70 })
  const [creating, setCreating] = useState(false)

  const [editingSet, setEditingSet] = useState(null)
  const [editDatetime, setEditDatetime] = useState('')
  const [editDurationMin, setEditDurationMin] = useState(60)
  const [editPassScore, setEditPassScore] = useState(70)
  const [savingEdit, setSavingEdit] = useState(false)

  const [listStatusFilter, setListStatusFilter] = useState('all')
  const [listPage, setListPage] = useState(1)
  const [questionsModalSet, setQuestionsModalSet] = useState(null)
  const [questionsModalData, setQuestionsModalData] = useState(null)
  const [questionsModalLoading, setQuestionsModalLoading] = useState(false)

  function loadSets() {
    return apiFetch('GET', '/api/admin/exam-sets').then(d => setSets(d.sets || [])).catch(() => {})
  }

  useEffect(() => {
    loadSets()
    apiFetch('GET', '/api/admin/users').then(d => setUsers(d.users || [])).catch(() => {})
    apiFetch('GET', '/api/admin/exam-sets/papers').then(d => setPapers(d.papers || [])).catch(() => {})
  }, [])

  async function handleCreate() {
    if (!createForm.paperId) { toast('시험지를 선택하세요.', 'error'); return }
    setCreating(true)
    try {
      const created = await apiFetch('POST', '/api/admin/exam-sets/from-paper', {
        exam_set_id: createForm.paperId,
        ...(createForm.name.trim() ? { name: createForm.name.trim() } : {}),
        ...(createForm.datetime ? { exam_datetime: createForm.datetime } : {}),
        duration_min: createForm.durationMin === '' ? 60 : Number(createForm.durationMin),
        pass_score: createForm.passScore === '' ? 70 : Number(createForm.passScore),
      })
      toast('새 시험을 만들었습니다.')
      setCreateForm({ paperId: '', name: '', datetime: '', durationMin: 60, passScore: 70 })
      await loadSets()
      setViewedSetId(created.exam_id)
      loadAssignees(created.exam_id)
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
    finally { setCreating(false) }
  }

  async function loadAssignees(setId) {
    if (!setId) { setAssignees([]); return }
    try {
      const d = await apiFetch('GET', `/api/admin/exam-sets/${setId}/assignees`)
      setAssignees(d.assignees || [])
    } catch { setAssignees([]) }
  }

  useEffect(() => { setListPage(1) }, [listStatusFilter])

  function openSet(setId) {
    setViewedSetId(setId)
    setAssignError('')
    setUserQuery('')
    setSelectedUser('')
    loadAssignees(setId)
  }

  useEffect(() => {
    if (!focusExamId) return
    openSet(focusExamId)
    onFocusConsumed?.()
  }, [focusExamId])

  async function handleAssign() {
    if (!viewedSetId || !selectedUser) { toast('응시자를 선택하세요.', 'error'); return }
    setAssignError('')
    setAssigning(true)
    try {
      await apiFetch('POST', `/api/admin/exam-sets/${viewedSetId}/assign`, { employee_id: selectedUser })
      toast('배정 완료!')
      setSelectedUser('')
      setUserQuery('')
      const [setsData] = await Promise.all([
        apiFetch('GET', '/api/admin/exam-sets'),
        loadAssignees(viewedSetId),
      ])
      setSets(setsData.sets || [])
    } catch (e) { setAssignError(e.message) }
    finally { setAssigning(false) }
  }

  async function handleUnassign(employeeId) {
    try {
      await apiFetch('DELETE', `/api/admin/exam-sets/${viewedSetId}/assign/${employeeId}`)
      toast('배정이 취소됐습니다.')
      const [setsData] = await Promise.all([
        apiFetch('GET', '/api/admin/exam-sets'),
        loadAssignees(viewedSetId),
      ])
      setSets(setsData.sets || [])
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
  }

  async function handleDeleteSet(setId, setName, e) {
    e.stopPropagation()
    if (!window.confirm(`"${setName}" 시험세트를 삭제할까요? 배정 정보도 함께 사라지며 되돌릴 수 없습니다.`)) return
    try {
      await apiFetch('DELETE', `/api/admin/exam-sets/${setId}`)
      toast('시험세트가 삭제됐습니다.')
      if (viewedSetId === setId) { setViewedSetId(''); setAssignees([]) }
      const setsData = await apiFetch('GET', '/api/admin/exam-sets')
      setSets(setsData.sets || [])
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
  }

  function openEdit(s, e) {
    e.stopPropagation()
    setEditingSet(s)
    setEditDatetime(s.exam_datetime ? s.exam_datetime.slice(0, 16) : '')
    setEditDurationMin(s.duration_min ?? 60)
    setEditPassScore(s.pass_score ?? 70)
  }

  async function handleSaveEdit() {
    if (!editingSet) return
    setSavingEdit(true)
    try {
      await Promise.all([
        apiFetch('PATCH', `/api/admin/exam-sets/${editingSet.exam_id}/schedule`, { exam_datetime: editDatetime }),
        apiFetch('PATCH', `/api/admin/exam-sets/${editingSet.exam_id}/duration`, { duration_min: editDurationMin === '' ? 60 : Number(editDurationMin) }),
        apiFetch('PATCH', `/api/admin/exam-sets/${editingSet.exam_id}/pass-score`, { pass_score: editPassScore === '' ? 70 : Number(editPassScore) }),
      ])
      toast('시험 정보가 수정됐습니다.')
      setEditingSet(null)
      await loadSets()
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
    finally { setSavingEdit(false) }
  }

  async function openQuestionsModal(set, e) {
    e.stopPropagation()
    setQuestionsModalSet(set)
    setQuestionsModalLoading(true)
    setQuestionsModalData(null)
    try {
      const d = await apiFetch('GET', `/api/admin/exam-sets/${set.exam_id}/questions`)
      setQuestionsModalData(d)
    } catch (err) { setQuestionsModalData({ error: err.message }) }
    finally { setQuestionsModalLoading(false) }
  }

  function closeQuestionsModal() { setQuestionsModalSet(null); setQuestionsModalData(null) }

  const filteredUsers = userQuery.trim()
    ? users.filter(u =>
        u.name.includes(userQuery) ||
        u.employee_id.includes(userQuery)
      )
    : users

  function selectUser(u) {
    setSelectedUser(u.employee_id)
    setUserQuery(`${u.name} (${u.employee_id})`)
    setDropdownOpen(false)
    setFocusedIdx(-1)
    setAssignError('')
  }

  function canSelectUser(u) {
    return !!viewedSet && u.team === viewedSet.team_code
  }

  function handleUserKeyDown(e) {
    if (!dropdownOpen) return
    if (e.key === 'ArrowDown') { e.preventDefault(); setFocusedIdx(i => Math.min(i + 1, filteredUsers.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setFocusedIdx(i => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter') { e.preventDefault(); if (focusedIdx >= 0 && filteredUsers[focusedIdx] && canSelectUser(filteredUsers[focusedIdx])) selectUser(filteredUsers[focusedIdx]) }
    else if (e.key === 'Escape') { setDropdownOpen(false) }
  }

  const viewedSet = sets.find(s => s.exam_id === viewedSetId)
  const selectedPaper = papers.find(p => p.exam_set_id === createForm.paperId)

  const LIST_STATUS_FILTERS = [
    { key:'all',       label:'전체' },
    { key:'done',      label:'완료' },
    { key:'ongoing',   label:'진행중' },
    { key:'scheduled', label:'예정' },
  ]

  const filteredSetList = sets.filter(s => listStatusFilter === 'all' || getExamStatus(s.exam_datetime, s.duration_min) === listStatusFilter)
  const listTotalPages = Math.max(1, Math.ceil(filteredSetList.length / EXAM_MANAGE_PAGE_SIZE))
  const listPageClamped = Math.min(listPage, listTotalPages)
  const pagedSetList = filteredSetList.slice((listPageClamped - 1) * EXAM_MANAGE_PAGE_SIZE, listPageClamped * EXAM_MANAGE_PAGE_SIZE)

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:20, height:'100%', minHeight:0 }}>
      <Card title="시험 생성" style={{ flexShrink:0 }}>
        <div style={{ display:'grid', gridTemplateColumns:'1.3fr 0.5fr 1.3fr 1.1fr 0.7fr 0.7fr auto', gap:12, alignItems:'end' }}>
          <div>
            <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>시험지 선택</label>
            <select value={createForm.paperId} onChange={e => setCreateForm(p => ({ ...p, paperId: e.target.value }))}
              style={{ width:'100%', height:44, border:'1px solid var(--border)', borderRadius:8, padding:'0 12px', fontSize:14, fontFamily:'var(--font)', background:'white' }}>
              <option value="">-- 시험지 선택 --</option>
              {papers.map(p => <option key={p.exam_set_id} value={p.exam_set_id}>{p.name} ({p.team_code} · {p.question_count}문항)</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>대상</label>
            <div style={{ width:'100%', height:44, border:'1px solid var(--border)', borderRadius:8, padding:'0 10px', fontSize:13, fontFamily:'var(--font)', background:'#F1F5F9', color:'var(--text-muted)', boxSizing:'border-box', display:'flex', alignItems:'center', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>
              {selectedPaper ? (TEAM_LABELS[selectedPaper.team_code] || selectedPaper.team_code) : '-'}
            </div>
          </div>
          <div>
            <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>시험명 (비워둘 시 시험지 이름 그대로 저장)</label>
            <input
              type="text"
              value={createForm.name}
              onChange={e => setCreateForm(p => ({ ...p, name: e.target.value }))}
              placeholder="예: 2026년 2차 OJT 평가"
              style={{ width:'100%', height:44, border:'1px solid var(--border)', borderRadius:8, padding:'0 12px', fontSize:14, fontFamily:'var(--font)', background:'white', boxSizing:'border-box' }}
            />
          </div>
          <div>
            <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>시험 일시</label>
            <input
              type="datetime-local"
              value={createForm.datetime}
              onChange={e => setCreateForm(p => ({ ...p, datetime: e.target.value }))}
              style={{ width:'100%', height:44, border:'1px solid var(--border)', borderRadius:8, padding:'0 12px', fontSize:14, fontFamily:'var(--font)', background:'white', boxSizing:'border-box' }}
            />
          </div>
          <div>
            <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>시험 시간(분)</label>
            <input
              type="number"
              inputMode="numeric"
              min={1}
              max={600}
              value={createForm.durationMin}
              onChange={e => setCreateForm(p => ({ ...p, durationMin: e.target.value === '' ? '' : Number(e.target.value) }))}
              style={{ width:'100%', height:44, border:'1px solid var(--border)', borderRadius:8, padding:'0 12px', fontSize:14, fontFamily:'var(--font)', background:'white', boxSizing:'border-box' }}
            />
          </div>
          <div>
            <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>합격 커트라인</label>
            <input
              type="number"
              inputMode="numeric"
              min={0}
              max={100}
              value={createForm.passScore}
              onChange={e => setCreateForm(p => ({ ...p, passScore: e.target.value === '' ? '' : Number(e.target.value) }))}
              style={{ width:'100%', height:44, border:'1px solid var(--border)', borderRadius:8, padding:'0 12px', fontSize:14, fontFamily:'var(--font)', background:'white', boxSizing:'border-box' }}
            />
          </div>
          <button onClick={handleCreate} disabled={creating}
            style={{ height:44, padding:'0 20px', background:'var(--accent)', color:'white', border:'none', borderRadius:8, fontSize:14, fontWeight:700, cursor:'pointer', fontFamily:'var(--font)', whiteSpace:'nowrap', opacity: creating ? 0.6 : 1 }}>
            {creating ? '생성 중...' : '생성'}
          </button>
        </div>
      </Card>

      <div style={{ display:'grid', gridTemplateColumns:'7fr 3fr', gap:16, flex:1, minHeight:0 }}>
        <Card
          title={`생성된 시험 목록 (${filteredSetList.length})`}
          noPad
          style={{ height:'100%', display:'flex', flexDirection:'column', marginBottom:0 }}
          bodyStyle={{ flex:1, minHeight:0, display:'flex', flexDirection:'column' }}
          action={
            <div style={{ display:'flex', alignItems:'center', gap:12 }}>
              {LIST_STATUS_FILTERS.map(f => (
                <label key={f.key} style={{ display:'flex', alignItems:'center', gap:5, fontSize:11, cursor:'pointer', color: listStatusFilter === f.key ? 'var(--text)' : 'var(--text-muted)', fontWeight: listStatusFilter === f.key ? 700 : 400 }}>
                  <input
                    type="radio"
                    name="listStatusFilter"
                    checked={listStatusFilter === f.key}
                    onChange={() => setListStatusFilter(f.key)}
                    style={{ accentColor:'var(--accent)', cursor:'pointer', margin:0 }}
                  />
                  {f.key !== 'all' && <span style={{ width:7, height:7, borderRadius:'50%', background:EXAM_STATUS_META[f.key].dot, display:'inline-block' }} />}
                  {f.label}
                </label>
              ))}
            </div>
          }
        >
          {filteredSetList.length === 0 ? (
            <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'24px 0' }}>표시할 시험이 없습니다.</p>
          ) : (
            <div style={{ flex:1, minHeight:0, overflowY:'auto', display:'flex', flexDirection:'column' }}>
              <DataTable headers={['이름','팀','상태','시험 일시','시험 시간','합격 커트라인','']}>
                {pagedSetList.map(s => {
                  const status = getExamStatus(s.exam_datetime, s.duration_min)
                  return (
                    <tr key={s.exam_id}
                      onClick={() => openSet(s.exam_id)}
                      style={{ cursor:'pointer', background: viewedSetId === s.exam_id ? 'var(--accent-light)' : 'white' }}>
                      <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)', fontSize:13, fontWeight:600, color: viewedSetId === s.exam_id ? 'var(--accent-dark)' : 'var(--text)' }}>{s.name}</td>
                      <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)', fontSize:13 }}>{s.team_code}</td>
                      <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)' }}><Badge type={EXAM_STATUS_META[status].badge}>{EXAM_STATUS_META[status].label}</Badge></td>
                      <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)', fontSize:12, color:'var(--text-muted)' }}>{s.exam_datetime ? s.exam_datetime.slice(0,16).replace('T',' ') : '미정'}</td>
                      <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)', fontSize:13 }}>{s.duration_min ?? 60}분</td>
                      <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)', fontSize:13 }}>{s.pass_score ?? 70}점</td>
                      <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)', textAlign:'right', whiteSpace:'nowrap' }}>
                        <div style={{ display:'inline-flex', gap:6 }}>
                          <button onClick={(e) => openEdit(s, e)} title="편집"
                            style={{ width:30, height:30, borderRadius:8, border:'1px solid var(--border)', background:'white', color:'var(--text-muted)', cursor:'pointer', display:'inline-flex', alignItems:'center', justifyContent:'center', padding:0, transition:'background .15s, border-color .15s, color .15s' }}
                            onMouseOver={e => { e.currentTarget.style.borderColor='var(--accent)'; e.currentTarget.style.color='var(--accent)'; e.currentTarget.style.background='var(--accent-light)' }}
                            onMouseOut={e => { e.currentTarget.style.borderColor='var(--border)'; e.currentTarget.style.color='var(--text-muted)'; e.currentTarget.style.background='white' }}>
                            <Icon name="edit" size={14} />
                          </button>
                          <button onClick={(e) => openQuestionsModal(s, e)} title="시험 문제 보기"
                            style={{ width:30, height:30, borderRadius:8, border:'1px solid var(--border)', background:'white', color:'var(--text-muted)', cursor:'pointer', display:'inline-flex', alignItems:'center', justifyContent:'center', padding:0, transition:'background .15s, border-color .15s, color .15s' }}
                            onMouseOver={e => { e.currentTarget.style.borderColor='var(--accent)'; e.currentTarget.style.color='var(--accent)'; e.currentTarget.style.background='var(--accent-light)' }}
                            onMouseOut={e => { e.currentTarget.style.borderColor='var(--border)'; e.currentTarget.style.color='var(--text-muted)'; e.currentTarget.style.background='white' }}>
                            <Icon name="file" size={14} />
                          </button>
                          <button onClick={(e) => handleDeleteSet(s.exam_id, s.name, e)} title="삭제"
                            style={{ width:30, height:30, borderRadius:8, border:'1px solid var(--border)', background:'white', color:'var(--text-muted)', cursor:'pointer', display:'inline-flex', alignItems:'center', justifyContent:'center', padding:0, transition:'background .15s, border-color .15s, color .15s' }}
                            onMouseOver={e => { e.currentTarget.style.borderColor='var(--danger)'; e.currentTarget.style.color='var(--danger)'; e.currentTarget.style.background='var(--danger-light)' }}
                            onMouseOut={e => { e.currentTarget.style.borderColor='var(--border)'; e.currentTarget.style.color='var(--text-muted)'; e.currentTarget.style.background='white' }}>
                            <Icon name="trash" size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </DataTable>
              {listTotalPages > 1 && (
                <ExamPagination page={listPageClamped} totalPages={listTotalPages} onChange={setListPage} />
              )}
            </div>
          )}
        </Card>

        <Card
          title={viewedSetId ? `응시자 목록 (${assignees.length}명)` : '응시자 목록'}
          action={viewedSet ? <span style={{ fontSize:11, color:'var(--text-muted)' }}>{viewedSet.name} · {viewedSet.team_code}</span> : null}
          style={{ height:'100%', display:'flex', flexDirection:'column', marginBottom:0 }}
          bodyStyle={{ flex:1, minHeight:0, display:'flex', flexDirection:'column' }}
        >
          {!viewedSetId ? (
            <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'24px 0' }}>왼쪽에서 시험을 선택하세요.</p>
          ) : (
            <div style={{ display:'flex', flexDirection:'column', height:'100%', minHeight:0 }}>
              <div style={{ position:'relative', marginBottom:12, flexShrink:0 }}>
                <div style={{ display:'flex', gap:8 }}>
                  <div style={{ position:'relative', flex:1 }}>
                    <input
                      type="text"
                      value={userQuery}
                      onChange={e => { setUserQuery(e.target.value); setSelectedUser(''); setDropdownOpen(true); setFocusedIdx(-1); setAssignError('') }}
                      onFocus={() => setDropdownOpen(true)}
                      onBlur={() => setTimeout(() => setDropdownOpen(false), 150)}
                      onKeyDown={handleUserKeyDown}
                      placeholder="응시자 검색 (이름 또는 사번)"
                      style={{ width:'100%', height:44, border:`1.5px solid ${selectedUser ? 'var(--accent)' : 'var(--border)'}`, borderRadius:8, padding:'0 36px 0 12px', fontSize:14, fontFamily:'var(--font)', background:'white', boxSizing:'border-box', outline:'none' }}
                    />
                    {userQuery && (
                      <button onMouseDown={e => { e.preventDefault(); setUserQuery(''); setSelectedUser(''); setDropdownOpen(false) }}
                        style={{ position:'absolute', right:10, top:'50%', transform:'translateY(-50%)', width:20, height:20, borderRadius:'50%', background:'var(--border)', border:'none', cursor:'pointer', padding:0, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text-muted)', flexShrink:0 }}>
                        <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                      </button>
                    )}
                    {dropdownOpen && filteredUsers.length > 0 && (
                      <div style={{ position:'absolute', top:'100%', left:0, right:0, background:'white', border:'1px solid var(--border)', borderRadius:8, boxShadow:'0 4px 16px rgba(0,0,0,0.1)', zIndex:50, maxHeight:200, overflowY:'auto', marginTop:2 }}>
                        {filteredUsers.map((u, i) => {
                          const selectable = canSelectUser(u)
                          return (
                            <div key={u.employee_id}
                              onMouseDown={() => { if (selectable) selectUser(u) }}
                              style={{ padding:'10px 14px', cursor: selectable ? 'pointer' : 'not-allowed', background: selectable && i === focusedIdx ? 'var(--accent-light)' : 'white', borderBottom:'1px solid var(--border)', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                              <span style={{ fontSize:13, color: !selectable ? 'var(--text-light)' : (i === focusedIdx ? 'var(--accent-dark)' : 'var(--text)') }}>
                                <span style={{ fontWeight:600 }}>{u.name}</span>
                                <span style={{ fontWeight:400, marginLeft:4, color: !selectable ? 'var(--text-light)' : 'var(--text-muted)' }}>({u.employee_id} · {u.team})</span>
                              </span>
                              {!selectable && <span style={{ fontSize:11, color:'var(--text-light)' }}>다른 팀</span>}
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                  <button onClick={handleAssign} disabled={assigning || !selectedUser}
                    style={{ height:44, padding:'0 18px', background:'var(--accent)', color:'white', border:'none', borderRadius:8, fontSize:13, fontWeight:700, cursor: (assigning || !selectedUser) ? 'default' : 'pointer', fontFamily:'var(--font)', whiteSpace:'nowrap', opacity: (assigning || !selectedUser) ? 0.6 : 1 }}>
                    {assigning ? '추가 중...' : '추가'}
                  </button>
                </div>
                {assignError && (
                  <p style={{ fontSize:12, color:'var(--danger)', marginTop:6, marginBottom:0 }}>{assignError}</p>
                )}
              </div>

              <div style={{ flex:1, minHeight:0, overflowY:'auto' }}>
                {assignees.length === 0 ? (
                  <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'24px 0' }}>배정된 응시자가 없습니다.</p>
                ) : (
                  <div style={{ display:'flex', flexDirection:'column' }}>
                    {assignees.map(u => (
                      <div key={u.employee_id} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'11px 18px', borderBottom:'1px solid var(--border)' }}>
                        <div>
                          <span style={{ fontSize:13, fontWeight:600, color:'var(--text)' }}>{u.name}</span>
                          <span style={{ fontSize:12, color:'var(--text-muted)', marginLeft:8 }}>{u.employee_id} · {u.team}</span>
                        </div>
                        <button onClick={() => handleUnassign(u.employee_id)} title="제외"
                          style={{ width:24, height:24, borderRadius:'50%', background:'none', border:'1px solid var(--border)', cursor:'pointer', padding:0, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text-muted)', flexShrink:0 }}>
                          <svg width={11} height={11} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </Card>
      </div>

      {editingSet && (
        <Modal title={`${editingSet.name} 편집`} onClose={() => setEditingSet(null)}>
          <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
            <div>
              <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>시험 일시</label>
              <input
                type="datetime-local"
                value={editDatetime}
                onChange={e => setEditDatetime(e.target.value)}
                style={{ width:'100%', height:44, border:'1px solid var(--border)', borderRadius:8, padding:'0 12px', fontSize:14, fontFamily:'var(--font)', background:'white', boxSizing:'border-box' }}
              />
            </div>
            <div>
              <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>시험 시간(분)</label>
              <input
                type="number"
                inputMode="numeric"
                min={1}
                max={600}
                value={editDurationMin}
                onChange={e => setEditDurationMin(e.target.value === '' ? '' : Number(e.target.value))}
                style={{ width:'100%', height:44, border:'1px solid var(--border)', borderRadius:8, padding:'0 12px', fontSize:14, fontFamily:'var(--font)', background:'white', boxSizing:'border-box' }}
              />
            </div>
            <div>
              <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>합격 커트라인</label>
              <input
                type="number"
                inputMode="numeric"
                min={0}
                max={100}
                value={editPassScore}
                onChange={e => setEditPassScore(e.target.value === '' ? '' : Number(e.target.value))}
                style={{ width:'100%', height:44, border:'1px solid var(--border)', borderRadius:8, padding:'0 12px', fontSize:14, fontFamily:'var(--font)', background:'white', boxSizing:'border-box' }}
              />
            </div>
            <button onClick={handleSaveEdit} disabled={savingEdit}
              style={{ height:44, background:'var(--accent)', color:'white', border:'none', borderRadius:8, fontSize:14, fontWeight:700, cursor:'pointer', fontFamily:'var(--font)', opacity: savingEdit ? 0.6 : 1 }}>
              {savingEdit ? '저장 중...' : '저장'}
            </button>
          </div>
        </Modal>
      )}

      {questionsModalSet && (
        <Modal title={`${questionsModalSet.name} · 문제 목록`} onClose={closeQuestionsModal} wide>
          {questionsModalLoading ? (
            <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'24px 0' }}>불러오는 중...</p>
          ) : questionsModalData?.error ? (
            <p style={{ fontSize:13, color:'var(--danger)', textAlign:'center', padding:'24px 0' }}>오류: {questionsModalData.error}</p>
          ) : (questionsModalData?.questions || []).length === 0 ? (
            <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'24px 0' }}>문제가 없습니다.</p>
          ) : (
            <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
              {questionsModalData.questions.map((q, i) => (
                <div key={q.question_id} style={{ border:'1px solid var(--border)', borderRadius:8, padding:'10px 14px' }}>
                  <div style={{ fontSize:11, color:'var(--text-muted)', marginBottom:4 }}>
                    {i + 1}. {q.question_id} · {q.category} · <span style={{ fontWeight:700 }}>{q.difficulty}</span>
                  </div>
                  <div style={{ fontSize:13, fontWeight:600, color:'var(--text)', marginBottom:6 }}>{q.question}</div>
                  <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:4 }}>
                    {['A','B','C','D'].map(k => (
                      <div key={k} style={{ fontSize:12, color: q.answer === k ? 'var(--success)' : 'var(--text-muted)', fontWeight: q.answer === k ? 700 : 400 }}>
                        {k}. {q.options[k]}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}
    </div>
  )
}

/* ── 응시 현황 ──────────────────────────────────────────────── */
function ExamStatus({ toast }) {
  const [sets, setSets] = useState([])
  const [selectedSet, setSelectedSet] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    apiFetch('GET', '/api/admin/exam-sets').then(d => setSets(d.sets || [])).catch(() => {})
  }, [])

  async function loadResults(setId) {
    setSelectedSet(setId)
    if (!setId) { setResults([]); return }
    setLoading(true)
    try {
      const d = await apiFetch('GET', `/api/admin/exam-sets/${setId}/results`)
      setResults(d.results || [])
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
    finally { setLoading(false) }
  }

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:20 }}>
      <Card title="응시 현황 조회">
        <select value={selectedSet} onChange={e => loadResults(e.target.value)}
          style={{ width:'100%', height:44, border:'1px solid var(--border)', borderRadius:8, padding:'0 12px', fontSize:14, fontFamily:'var(--font)', background:'white' }}>
          <option value="">-- 시험세트 선택 --</option>
          {sets.map(s => <option key={s.exam_id} value={s.exam_id}>{s.name} ({s.team_code})</option>)}
        </select>
      </Card>

      {selectedSet && (
        <Card title={`응시 결과 (${results.length}명)`}>
          {loading ? (
            <p style={{ color:'var(--text-muted)', fontSize:14 }}>불러오는 중...</p>
          ) : results.length === 0 ? (
            <p style={{ color:'var(--text-muted)', fontSize:14 }}>아직 응시 결과가 없습니다.</p>
          ) : (
            <DataTable headers={['응시자 ID','점수','합격 여부','응시일']}>
              {results.map((r, i) => (
                <tr key={i}>
                  <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)', fontSize:13, fontFamily:'monospace' }}>{r.employee_id || '-'}</td>
                  <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)', fontSize:13, fontWeight:700 }}>{r.score}점</td>
                  <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)' }}>
                    <span style={{ fontSize:12, fontWeight:700, padding:'3px 10px', borderRadius:20, background: r.pass ? 'var(--success-light)' : 'var(--danger-light)', color: r.pass ? 'var(--success)' : 'var(--danger)' }}>
                      {r.pass ? '합격' : '불합격'}
                    </span>
                  </td>
                  <td style={{ padding:'11px 18px', borderBottom:'1px solid var(--border)', fontSize:12, color:'var(--text-muted)' }}>{r.submitted_at ? r.submitted_at.slice(0,10) : '-'}</td>
                </tr>
              ))}
            </DataTable>
          )}
        </Card>
      )}
    </div>
  )
}

/* ── 팀 관리 ─────────────────────────────────────────────────── */
function TeamsManager({ toast }) {
  const [teams, setTeams] = useState([])
  const [headcounts, setHeadcounts] = useState({})
  const [form, setForm] = useState({ team_id:'', team_name:'', team_code:'' })
  const [editId, setEditId] = useState(null)
  const [editName, setEditName] = useState('')

  async function load() {
    try { const d = await apiFetch('GET', '/api/admin/teams'); setTeams(d.teams) } catch {}
    try { const d = await apiFetch('GET', '/api/admin/teams/headcount'); setHeadcounts(d.headcounts || {}) } catch {}
  }
  useEffect(() => { load() }, [])

  async function create() {
    if (!form.team_id || !form.team_name || !form.team_code) { toast('모든 항목을 입력해주세요.', 'error'); return }
    try {
      await apiFetch('POST', '/api/admin/teams', form)
      setForm({ team_id:'', team_name:'', team_code:'' })
      toast('팀이 추가되었습니다.'); load()
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
  }

  async function save(id) {
    if (!editName.trim()) return
    try {
      await apiFetch('PATCH', `/api/admin/teams/${id}`, { team_name: editName })
      setEditId(null); toast('팀명이 수정되었습니다.'); load()
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
  }

  async function remove(id, name) {
    if (!confirm(`'${name}' 팀을 삭제하시겠습니까?`)) return
    try { await apiFetch('DELETE', `/api/admin/teams/${id}`); toast('삭제되었습니다.'); load() }
    catch (e) { toast(`삭제 실패: ${e.message}`, 'error') }
  }

  return (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
      <Card title="팀 추가">
        <FormInput label="팀 ID" value={form.team_id} onChange={e => setForm(p=>({...p,team_id:e.target.value}))} placeholder="예: team-sales" />
        <FormInput label="팀명" value={form.team_name} onChange={e => setForm(p=>({...p,team_name:e.target.value}))} placeholder="예: 영업팀" />
        <FormInput label="팀 코드" value={form.team_code} onChange={e => setForm(p=>({...p,team_code:e.target.value}))} placeholder="예: SALES" />
        <BtnPrimary onClick={create} style={{ width:'100%', justifyContent:'center' }}>
          <Icon name="plus" size={14} style={{ color:'white' }} /> 팀 추가
        </BtnPrimary>
      </Card>

      <Card title="팀 목록" noPad action={<BtnOutlineSm onClick={load}><Icon name="refresh" size={11} /> 새로고침</BtnOutlineSm>}>
        <DataTable headers={['팀 ID','팀명','코드','실제 인원','관리']}>
          {teams.length === 0 ? (
            <tr><td colSpan={5} style={{ textAlign:'center', color:'var(--text-muted)', padding:20, fontSize:13 }}>팀이 없습니다.</td></tr>
          ) : teams.map(t => (
            <tr key={t.team_id}>
              <td style={{ padding:'10px 14px', borderBottom:'1px solid var(--border)', fontSize:12, color:'var(--text-muted)', fontFamily:'monospace' }}>{t.team_id}</td>
              <td style={{ padding:'10px 14px', borderBottom:'1px solid var(--border)', fontSize:13 }}>
                {editId === t.team_id ? (
                  <input value={editName} onChange={e => setEditName(e.target.value)}
                    style={{ border:'1.5px solid var(--accent)', borderRadius:5, padding:'4px 8px', fontSize:13, fontFamily:'var(--font)', width:'100%', outline:'none' }} />
                ) : t.team_name}
              </td>
              <td style={{ padding:'10px 14px', borderBottom:'1px solid var(--border)', fontSize:12 }}>{t.team_code}</td>
              <td style={{ padding:'10px 14px', borderBottom:'1px solid var(--border)', fontSize:12, color:'var(--text-muted)' }}>{headcounts[t.team_code] || 0}명</td>
              <td style={{ padding:'10px 14px', borderBottom:'1px solid var(--border)', display:'flex', gap:6 }}>
                {editId === t.team_id ? (
                  <>
                    <BtnOutlineSm onClick={() => save(t.team_id)}>저장</BtnOutlineSm>
                    <BtnOutlineSm onClick={() => setEditId(null)}>취소</BtnOutlineSm>
                  </>
                ) : (
                  <>
                    <BtnOutlineSm onClick={() => { setEditId(t.team_id); setEditName(t.team_name) }}>수정</BtnOutlineSm>
                    <BtnOutlineSm danger onClick={() => remove(t.team_id, t.team_name)}>삭제</BtnOutlineSm>
                  </>
                )}
              </td>
            </tr>
          ))}
        </DataTable>
      </Card>
    </div>
  )
}

const NAV_META = {
  dashboard:      { bc:['홈','대시보드'],                          title:'관리자 대시보드' },
  'q-generate':   { bc:['홈','문제 관리','문제 생성'],             title:'문제 생성' },
  'q-review':     { bc:['홈','문제 관리','검토·검증'],             title:'검토 · 검증' },
  'q-bank':       { bc:['홈','문제 관리','문제은행'],              title:'문제은행' },
  'exam-sheet':   { bc:['홈','시험 관리','시험지 생성'],           title:'시험지 생성' },
  'exam-assign':  { bc:['홈','시험 관리','시험 생성·관리'],         title:'시험 생성·관리' },
  'exam-status':  { bc:['홈','시험 관리','응시 현황'],             title:'응시 현황' },
  history:        { bc:['홈','응시 이력'],                         title:'응시 이력' },
  users:          { bc:['홈','사용자 승인'],                       title:'사용자 승인' },
  results:        { bc:['홈','결과 분석'],                         title:'결과 분석' },
  settings:       { bc:['홈','설정'],                              title:'시스템 설정' },
  teams:          { bc:['홈','팀 관리'],                           title:'팀 관리' },
}

const ADMIN_VIEW_KEY = 'admin_view'
const Q_VIEWS    = ['q-generate','q-review','q-bank']
const EXAM_VIEWS = ['exam-sheet','exam-assign','exam-status']
const ADMIN_VIEWS = ['dashboard', ...Q_VIEWS, ...EXAM_VIEWS, 'history', 'users', 'results', 'settings', 'teams']

function initialAdminView() {
  const saved = sessionStorage.getItem(ADMIN_VIEW_KEY)
  return ADMIN_VIEWS.includes(saved) ? saved : 'dashboard'
}

export default function Admin() {
  const navigate = useNavigate()
  const [view, setView] = useState(initialAdminView)
  const [qSubOpen, setQSubOpen] = useState(() => Q_VIEWS.includes(initialAdminView()))
  const [examSubOpen, setExamSubOpen] = useState(() => EXAM_VIEWS.includes(initialAdminView()))
  const [examAssignFocusId, setExamAssignFocusId] = useState(null)
  const { toast, ToastContainer } = useToast()

  const meta = NAV_META[view] || NAV_META.dashboard

  function goView(v, opts) {
    setView(v)
    sessionStorage.setItem(ADMIN_VIEW_KEY, v)
    if (opts?.focusExamId) setExamAssignFocusId(opts.focusExamId)
    if (Q_VIEWS.includes(v))    setQSubOpen(true)
    if (EXAM_VIEWS.includes(v)) setExamSubOpen(true)
  }

  const navItems = [
    { id:'dashboard',   icon:'grid',  label:'대시보드' },
    { id:'q-manage',    icon:'book',  label:'문제 관리', sub:[
      { id:'q-generate', icon:'ai',    label:'문제 생성' },
      { id:'q-review',   icon:'check', label:'검토·검증' },
      { id:'q-bank',     icon:'book',  label:'문제은행' },
    ]},
    { id:'exam-manage', icon:'file',  label:'시험 관리', sub:[
      { id:'exam-sheet',  icon:'file',  label:'시험지 생성' },
      { id:'exam-assign', icon:'users', label:'시험 생성·관리' },
      { id:'exam-status', icon:'chart', label:'응시 현황' },
    ]},
    { id:'history',     icon:'clock',    label:'응시 이력' },
    { id:'users',       icon:'users',    label:'사용자 승인' },
    { id:'results',     icon:'chart',    label:'결과 분석' },
    { id:'settings',    icon:'settings', label:'설정' },
    { id:'teams',       icon:'users',    label:'팀 관리' },
  ]

  const SIDEBAR_W = 220
  const HEADER_H  = 56

  const isActive = id => {
    if (id === 'q-manage')    return Q_VIEWS.includes(view)
    if (id === 'exam-manage') return EXAM_VIEWS.includes(view)
    return view === id
  }

  return (
    <div style={{ fontFamily:'var(--font)', fontSize:14, color:'var(--text)', background:'var(--bg)', height:'100vh', overflow:'hidden', display:'flex', flexDirection:'column' }}>
      <ToastContainer />

      {/* Header */}
      <header style={{ position:'fixed', top:0, left:0, right:0, zIndex:100, height:HEADER_H, background:'var(--card)', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', padding:'0 24px 0 0' }}>
        <div style={{ width:SIDEBAR_W, padding:'0 18px', display:'flex', alignItems:'center', gap:10, borderRight:'1px solid var(--border)', height:'100%', flexShrink:0 }}>
          <div style={{ width:30, height:30, background:'var(--accent)', borderRadius:7, display:'flex', alignItems:'center', justifyContent:'center', fontSize:13, color:'white', fontWeight:800, flexShrink:0 }}>X</div>
          <div>
            <div style={{ fontSize:12, fontWeight:700, color:'var(--text)', lineHeight:1.2 }}>(주)엑스티</div>
            <div style={{ fontSize:10, color:'var(--text-muted)', lineHeight:1.2 }}>OJT 평가 시스템</div>
          </div>
        </div>
        <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'space-between', padding:'0 24px' }}>
          <span style={{ fontSize:16, fontWeight:700, color:'var(--text)' }}>{meta.title}</span>
          <div style={{ display:'flex', alignItems:'center', gap:12 }}>
            <div style={{ width:32, height:32, background:'var(--accent)', borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', color:'white', fontSize:13, fontWeight:700 }}>김</div>
            <div>
              <div style={{ fontSize:13, fontWeight:700, color:'var(--text)', lineHeight:1.2 }}>김흥길 과장</div>
              <div style={{ fontSize:11, color:'var(--text-muted)', lineHeight:1.2 }}>인사팀 · 관리자</div>
            </div>
          </div>
        </div>
      </header>

      {/* Shell */}
      <div style={{ display:'flex', marginTop:HEADER_H, height:`calc(100vh - ${HEADER_H}px)`, overflow:'hidden' }}>

        {/* Sidebar */}
        <nav style={{ width:SIDEBAR_W, background:'var(--primary)', flexShrink:0, display:'flex', flexDirection:'column', overflowY:'auto', overflowX:'hidden' }}>
          <div style={{ padding:'10px 0', flex:1 }}>
            <div style={{ padding:'10px 18px 4px', fontSize:9, fontWeight:700, letterSpacing:'.10em', color:'rgba(255,255,255,.22)', textTransform:'uppercase' }}>메뉴</div>
            {navItems.map(item => (
              <div key={item.id}>
                <div
                  onClick={() => item.id === 'q-manage' ? setQSubOpen(v => !v) : item.id === 'exam-manage' ? setExamSubOpen(v => !v) : goView(item.id)}
                  style={{ display:'flex', alignItems:'center', gap:9, padding:'9px 18px', color: isActive(item.id) ? 'white' : 'rgba(255,255,255,.60)', cursor:'pointer', fontSize:13, borderLeft:`2px solid ${isActive(item.id) ? 'var(--accent)' : 'transparent'}`, background: isActive(item.id) ? 'rgba(255,255,255,.10)' : 'transparent', fontWeight: isActive(item.id) ? 600 : 400 }}
                >
                  <Icon name={item.icon} size={15} style={{ opacity: isActive(item.id) ? 1 : 0.65 }} />
                  <span>{item.label}</span>
                  {item.sub && <span style={{ marginLeft:'auto', fontSize:11, color:'rgba(255,255,255,.30)', display:'inline-block', transform: (item.id === 'q-manage' ? qSubOpen : examSubOpen) ? 'rotate(90deg)' : 'none', transition:'transform .2s' }}>›</span>}
                </div>
                {item.sub && (item.id === 'q-manage' ? qSubOpen : examSubOpen) && (
                  <div style={{ background:'rgba(0,0,0,.15)' }}>
                    {item.sub.map(s => (
                      <div key={s.id} onClick={() => goView(s.id)}
                        style={{ display:'flex', alignItems:'center', gap:8, padding:'8px 18px 8px 40px', color: view === s.id ? 'white' : 'rgba(255,255,255,.55)', cursor:'pointer', fontSize:12.5, borderLeft:`2px solid ${view === s.id ? 'var(--accent)' : 'transparent'}`, background: view === s.id ? 'rgba(255,255,255,.08)' : 'transparent', fontWeight: view === s.id ? 600 : 400 }}>
                        <Icon name={s.icon} size={13} style={{ opacity: view === s.id ? 1 : 0.55 }} />
                        {s.label}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
          <div style={{ borderTop:'1px solid rgba(255,255,255,.07)', padding:'14px 16px' }}>
            <div style={{ display:'flex', alignItems:'center', gap:12, padding:'8px 4px 14px' }}>
              <div style={{ width:40, height:40, background:'var(--accent)', borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', color:'white', fontSize:16, fontWeight:700, flexShrink:0 }}>김</div>
              <div style={{ overflow:'hidden' }}>
                <div style={{ fontSize:15, fontWeight:700, color:'rgba(255,255,255,.88)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>김흥길 과장</div>
                <div style={{ fontSize:11, color:'rgba(255,255,255,.35)', marginTop:2 }}>관리자</div>
              </div>
            </div>
            <button onClick={() => apiLogout(navigate)} style={{ width:'100%', background:'rgba(255,255,255,.07)', border:'1px solid rgba(255,255,255,.10)', borderRadius:7, padding:'9px 10px', fontFamily:'var(--font)', fontSize:13, color:'rgba(255,255,255,.55)', cursor:'pointer', display:'flex', alignItems:'center', gap:7 }}>
              <Icon name="logout" size={14} style={{ color:'rgba(255,255,255,.5)' }} /> 로그아웃
            </button>
          </div>
        </nav>

        {/* Main */}
        <main style={{ flex:1, overflow:'hidden', display:'flex', flexDirection:'column' }}>
          <div style={{ padding:'8px 24px', display:'flex', alignItems:'center', gap:6, fontSize:12, color:'var(--text-muted)', borderBottom:'1px solid var(--border)', background:'var(--card)', flexShrink:0 }}>
            {meta.bc.map((c, i) => (
              <span key={i} style={{ display:'flex', alignItems:'center', gap:6 }}>
                {i > 0 && <span style={{ color:'var(--text-light)' }}>›</span>}
                <span style={{ color: i === meta.bc.length-1 ? 'var(--text)' : 'var(--text-muted)', fontWeight: i === meta.bc.length-1 ? 600 : 400 }}>{c}</span>
              </span>
            ))}
          </div>
          <div style={{ flex:1, overflowY:'auto', padding:24 }}>
            {view === 'dashboard'   && <Dashboard onNavigate={goView} />}
            {view === 'q-generate'  && <QuestionGenerate toast={toast} onNavigate={goView} />}
            {view === 'q-review'    && <ExamReview toast={toast} />}
            {view === 'q-bank'      && <QuestionBank toast={toast} onNavigate={goView} />}
            {view === 'exam-sheet'  && <ExamSheet toast={toast} onNavigate={goView} />}
            {view === 'exam-assign' && <ExamAssign toast={toast} focusExamId={examAssignFocusId} onFocusConsumed={() => setExamAssignFocusId(null)} />}
            {view === 'exam-status' && <ExamStatus toast={toast} />}
            {view === 'history'     && <History toast={toast} />}
            {view === 'users'       && <Users toast={toast} />}
            {view === 'results'     && <Results />}
            {view === 'settings'    && <Settings />}
            {view === 'teams'       && <TeamsManager toast={toast} />}
          </div>
        </main>
      </div>
    </div>
  )
}
