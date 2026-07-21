import { useState, useEffect, useRef, Fragment } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { apiFetch, apiUpload, logout as apiLogout } from '../api'
import AdminLayout from '../admin/components/AdminLayout'
import { ADMIN_ROUTE_META, ADMIN_NAVIGATION } from '../admin/config/navigation'
import ExamPaperPage from '../admin/pages/exam-papers/ExamPaperPage'
import QuestionRoutePage from '../admin/pages/questions/QuestionRoutePage'
import ResultRoutePage from '../admin/pages/results/ResultRoutePage'
import SystemRoutePage from '../admin/pages/system/SystemRoutePage'
import ExamManagementPage from '../admin/pages/exams/ExamManagementPage'
import ExamLivePage from '../admin/pages/exams/ExamLivePage'
import ExamLiveDetailPage from '../admin/pages/exams/ExamLiveDetailPage'
import { PlannedGenerationRuns, PlannedQuestionBank, PlannedQuestionGeneration, PlannedQuestionReview } from '../admin/pages/questions/PlannedQuestionPages'
import PlannedAuditLog from '../admin/pages/system/PlannedAuditLog'
import { getHolidayInfo } from '../koreanHolidays'

/* ── Shared constants / helpers ─────────────────────────────── */
const DEFAULT_TEAMS = [
  { team_code:'T1', team_name:'1팀' },
  { team_code:'T2', team_name:'2팀' },
  { team_code:'T3', team_name:'3팀' },
]

// systemStatus(/api/admin/system-status)에서 대시보드·설정 화면이 공통으로 쓰는
// 파생 값(AI provider 라벨, Claude 키 설정 여부)을 한 곳에서 계산한다.
function deriveSystemInfo(systemStatus) {
  const aiProvider = systemStatus?.ai_provider ?? '확인 중'
  const aiProviderLabel = { mock:'Mock 모드', gemini:'Gemini 연동', claude:'Claude 연동' }[aiProvider] || aiProvider
  const claudeConfigured = systemStatus?.claude_key_configured ?? false
  return { aiProvider, aiProviderLabel, claudeConfigured }
}

// 시험지 문항 목록을 인쇄용 A4 HTML 문자열로 렌더링한다.
// (문제 생성·시험 생성 화면이 동일한 레이아웃을 공유 — 인쇄와 HTML 저장이 같은 출력을 쓴다)
function buildExamPdfHtml({ docTitle, heading, teamLabel, questions }) {
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
<title>${docTitle}</title>
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
  <h1>${heading}</h1>
  <p class="meta">${teamLabel} · ${questions.length}문항 · 응시일: ___년 ___월 ___일 &nbsp;&nbsp; 성명: ________________ &nbsp;&nbsp; 사원번호: ________________</p>
  <hr/>
  <div class="grid">${rows}</div>
</body>
</html>`
}

// 위 HTML을 새 창에서 인쇄한다. 팝업이 차단되면 안내 후 중단.
function openExamPdf({ docTitle, heading, teamLabel, questions, toast }) {
  const win = window.open('', '_blank')
  if (!win) { toast('팝업이 차단되어 PDF를 열 수 없습니다. 브라우저의 팝업 차단을 해제해주세요.', 'error'); return }
  win.document.write(buildExamPdfHtml({ docTitle, heading, teamLabel, questions }))
  win.document.close()
  win.focus()
  setTimeout(() => { win.print() }, 300)
}

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
    search:   <><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></>,
    calendar: <><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></>,
    alert:    <><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></>,
    x:        <><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>,
    menu:     <><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></>,
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
    <span style={{ fontSize:11, fontWeight:700, padding:'3px 8px', borderRadius:20, whiteSpace:'nowrap', ...colors[type] }}>
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
          <th key={h} style={{ fontSize:11, fontWeight:700, color:'var(--text-muted)', textAlign:'left', padding:'10px 18px', borderBottom:'1px solid var(--border)', background:'#F8FAFC', textTransform:'uppercase', letterSpacing:'0.05em', whiteSpace:'nowrap', position:'sticky', top:0, zIndex:1 }}>{h}</th>
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
const TEAM_DOT_COLORS = { T1:'#3b82f6', T2:'#8b5cf6', T3:'#0d9488' }

// 사이드바 전체 메뉴(대시보드 제외)를 즐겨찾기 후보 목록으로 사용한다.
// path가 실제로 유일한 값이라 즐겨찾기 식별자로 쓴다 — view는 "생성 작업"·"문제 생성"처럼
// 여러 메뉴가 공유할 수 있어 식별자로 부적합하다.
const NAV_ITEM_ICONS = {
  '/admin/questions/generate/setup': 'ai',
  '/admin/questions/generate/runs':  'refresh',
  '/admin/questions/review':         'check',
  '/admin/questions/bank':           'book',
  '/admin/exam-papers?tab=setup':    'file',
  '/admin/exams':                    'users',
  '/admin/exams/live':               'clock',
  '/admin/results':                  'grid',
  '/admin/analytics':                'chart',
  '/admin/employees':                'user',
  '/admin/teams':                    'users',
  '/admin/materials':                'swap',
  '/admin/system/status':            'settings',
  '/admin/system/audit-logs':        'search',
}

const ALL_NAV_ITEMS = ADMIN_NAVIGATION
  .filter(group => group.label !== '대시보드')
  .flatMap(group => group.items.map(item => ({
    ...item,
    group: group.label,
    icon: NAV_ITEM_ICONS[item.path] || 'file',
  })))

// 업무 흐름 순서대로: 문제 생성 → 검수 대기 → 시험지 생성·관리 → 시험 생성·관리 → 응시자 관리 → 응시 현황 → 결과 분석
const DEFAULT_FAVORITE_PATHS = [
  '/admin/questions/generate/setup',
  '/admin/questions/review',
  '/admin/exam-papers?tab=setup',
  '/admin/exams',
  '/admin/employees',
  '/admin/exams/live',
  '/admin/analytics',
]
const FAVORITES_STORAGE_KEY = 'ojt_admin_favorite_menu'
const LEGACY_QUICK_ACTIONS_ORDER_KEY = 'ojt_admin_quick_actions_order'

function loadFavoritePaths() {
  const validPaths = new Set(ALL_NAV_ITEMS.map(i => i.path))
  try {
    const saved = JSON.parse(localStorage.getItem(FAVORITES_STORAGE_KEY) || 'null')
    if (Array.isArray(saved) && saved.every(v => typeof v === 'string')) {
      const valid = saved.filter(p => validPaths.has(p))
      if (valid.length) return valid
    }
  } catch {}
  // 이전 "빠른 실행 순서 편집" 기능에서 저장한 값이 있으면 최선노력으로 이관한다.
  try {
    const legacy = JSON.parse(localStorage.getItem(LEGACY_QUICK_ACTIONS_ORDER_KEY) || 'null')
    if (Array.isArray(legacy) && legacy.every(v => typeof v === 'string')) {
      const mapped = legacy.map(view => ALL_NAV_ITEMS.find(i => i.view === view)?.path).filter(Boolean)
      if (mapped.length) return mapped
    }
  } catch {}
  return DEFAULT_FAVORITE_PATHS
}

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

/* ── 최근 활동 피드 ─────────────────────────────────────────── */
function formatRelativeTime(isoString) {
  if (!isoString) return ''
  const then = new Date(isoString)
  if (isNaN(then.getTime())) return ''
  const now = new Date()
  const diffMs = now - then
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '방금 전'
  if (diffMin < 60) return `${diffMin}분 전`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour}시간 전`
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startOfThen = new Date(then.getFullYear(), then.getMonth(), then.getDate())
  const diffDay = Math.round((startOfToday - startOfThen) / 86400000)
  if (diffDay === 1) return '어제'
  if (diffDay < 7) return `${diffDay}일 전`
  return `${String(then.getMonth() + 1).padStart(2, '0')}/${String(then.getDate()).padStart(2, '0')}`
}

const ACTIVITY_TYPE_META = {
  exam_submit:      { icon:'check', color:'var(--success)' },
  question_review:  { icon:'check', color:'var(--accent)' },
  question_reject:  { icon:'x',     color:'var(--danger)' },
  user_register:    { icon:'user',  color:'#8b5cf6' },
  exam_create:      { icon:'file',  color:'var(--warning)' },
}

function activityMessage(item) {
  const team = TEAM_LABELS[item.team_code] || item.team_code || ''
  switch (item.type) {
    case 'exam_submit':
      return <>{item.actor_name || '응시자'}님이 「{item.target}」 응시를 완료했습니다{item.detail ? ` · ${item.detail}` : ''}</>
    case 'question_review':
      return <>문제 「{item.target}」이 검수 승인되었습니다</>
    case 'question_reject':
      return <>문제 「{item.target}」이 반려되었습니다{item.detail ? ` · ${item.detail}` : ''}</>
    case 'user_register':
      return <>{item.target}이 {team ? `${team}에 ` : ''}등록되었습니다</>
    case 'exam_create':
      return <>「{item.target}」 시험이 생성되었습니다</>
    default:
      return item.detail || item.target || item.type
  }
}

function ActivityFeedList({ items, dense }) {
  if (!items || items.length === 0) {
    return <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'24px 0' }}>아직 활동 내역이 없습니다</p>
  }
  return (
    <div style={{ display:'flex', flexDirection:'column' }}>
      {items.map(item => {
        const meta = ACTIVITY_TYPE_META[item.type] || { icon:'check', color:'var(--text-muted)' }
        return (
          <div key={item.activity_id} style={{ display:'flex', alignItems:'flex-start', gap:10, padding: dense ? '9px 0' : '10px 0', borderBottom:'1px solid var(--border)' }}>
            <div style={{ width:22, height:22, borderRadius:'50%', flexShrink:0, display:'flex', alignItems:'center', justifyContent:'center', color:meta.color, background:`color-mix(in srgb, ${meta.color} 16%, transparent)`, marginTop:1 }}>
              <Icon name={meta.icon} size={11} />
            </div>
            <div style={{ flex:1, minWidth:0, fontSize:12.5, color:'var(--text)', lineHeight:1.5 }}>{activityMessage(item)}</div>
            <span style={{ fontSize:11, color:'var(--text-muted)', flexShrink:0, whiteSpace:'nowrap', marginTop:2 }}>{formatRelativeTime(item.created_at)}</span>
          </div>
        )
      })}
    </div>
  )
}

function ActivityFeed({ items, onViewAll }) {
  return (
    <Card
      title="최근 활동"
      style={{ height:'100%', display:'flex', flexDirection:'column', marginBottom:0 }}
      bodyStyle={{ flex:1, overflowY:'auto', minHeight:0 }}
      action={
        <button onClick={onViewAll} style={{ background:'none', border:'none', color:'var(--accent)', fontSize:12.5, fontWeight:700, cursor:'pointer', padding:0, fontFamily:'var(--font)' }}>
          전체 보기 →
        </button>
      }
    >
      {items === null ? (
        <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'24px 0' }}>불러오는 중...</p>
      ) : (
        <ActivityFeedList items={items} />
      )}
    </Card>
  )
}

function ActivityLogModal({ onClose }) {
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)

  useEffect(() => {
    setData(null)
    apiFetch('GET', `/api/admin/activity-log?page=${page}&limit=20`).then(setData).catch(() => setData({ items:[], has_more:false }))
  }, [page])

  return (
    <Modal title="전체 활동 내역" onClose={onClose} wide>
      {data === null ? (
        <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'24px 0' }}>불러오는 중...</p>
      ) : (
        <>
          <ActivityFeedList items={data.items} />
          <div style={{ display:'flex', justifyContent:'center', gap:16, marginTop:16 }}>
            <BtnOutlineSm onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>이전</BtnOutlineSm>
            <span style={{ fontSize:13, color:'var(--text-muted)', display:'flex', alignItems:'center' }}>{page}페이지</span>
            <BtnOutlineSm onClick={() => setPage(p => p + 1)} disabled={!data.has_more}>다음</BtnOutlineSm>
          </div>
        </>
      )}
    </Modal>
  )
}

function QuickActionsRow({ items, onNavigate }) {
  const scrollRef = useRef(null)

  function scrollByPage(dir) {
    scrollRef.current?.scrollBy({ left: dir * 240, behavior: 'smooth' })
  }

  const navBtnStyle = { width:28, height:28, flexShrink:0, display:'flex', alignItems:'center', justifyContent:'center', border:'1px solid var(--border)', borderRadius:8, background:'white', color:'var(--text-muted)', cursor:'pointer', padding:0 }

  if (items.length === 0) {
    return (
      <p style={{ fontSize:12.5, color:'var(--text-muted)', textAlign:'center', padding:'9px 0', margin:0 }}>
        즐겨찾기한 메뉴가 없습니다. 오른쪽 위 <Icon name="settings" size={11} style={{ verticalAlign:'-1px', margin:'0 2px' }} /> 버튼으로 추가해보세요.
      </p>
    )
  }

  return (
    <div style={{ display:'flex', alignItems:'center', gap:8 }}>
      <button onClick={() => scrollByPage(-1)} style={navBtnStyle} aria-label="이전">
        <Icon name="chevronLeft" size={14} />
      </button>
      <div ref={scrollRef} style={{ display:'flex', gap:10, overflowX:'auto', flex:1, minWidth:0, scrollbarWidth:'none' }}>
        {items.map(item => (
          <button key={item.path} onClick={() => onNavigate(item.view, { path: item.path })}
            style={{ display:'flex', alignItems:'center', gap:8, padding:'9px 16px', border:'1px solid var(--border)', borderRadius:8, background:'white', fontFamily:'var(--font)', fontSize:13, fontWeight:600, color:'var(--text)', cursor:'pointer', whiteSpace:'nowrap', flexShrink:0 }}>
            <Icon name={item.icon} size={14} style={{ opacity:0.55 }} />{item.label}
          </button>
        ))}
      </div>
      <button onClick={() => scrollByPage(1)} style={navBtnStyle} aria-label="다음">
        <Icon name="chevronRight" size={14} />
      </button>
    </div>
  )
}

function FavoritesMenuModal({ favorites, onSave, onClose }) {
  const [order, setOrder] = useState(favorites)

  function move(index, dir) {
    setOrder(prev => {
      const target = index + dir
      if (target < 0 || target >= prev.length) return prev
      const next = [...prev]
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })
  }

  function remove(index) {
    setOrder(prev => prev.filter((_, i) => i !== index))
  }

  function add(item) {
    setOrder(prev => [...prev, item])
  }

  const moveBtnStyle = disabled => ({
    width:26, height:26, flexShrink:0, display:'flex', alignItems:'center', justifyContent:'center',
    border:'1px solid var(--border)', borderRadius:6, background:'white', padding:0,
    color:'var(--text-muted)', cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.35 : 1,
  })

  const favoritePaths = new Set(order.map(i => i.path))
  const availableByGroup = {}
  ALL_NAV_ITEMS.forEach(item => {
    if (favoritePaths.has(item.path)) return
    ;(availableByGroup[item.group] ||= []).push(item)
  })

  return (
    <Modal title="즐겨찾기 메뉴 관리" onClose={onClose} wide>
      <div style={{ fontSize:11, fontWeight:700, color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.05em', marginBottom:8 }}>즐겨찾기 순서</div>
      <div style={{ display:'flex', flexDirection:'column', gap:8, marginBottom:24 }}>
        {order.length === 0 ? (
          <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'16px 0' }}>즐겨찾기한 메뉴가 없습니다. 아래에서 추가해보세요.</p>
        ) : order.map((item, i) => (
          <div key={item.path} style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 12px', border:'1px solid var(--border)', borderRadius:8 }}>
            <Icon name={item.icon} size={14} style={{ opacity:0.55, flexShrink:0 }} />
            <span style={{ flex:1, fontSize:13, fontWeight:600, color:'var(--text)' }}>{item.label}</span>
            <button onClick={() => move(i, -1)} disabled={i === 0} style={moveBtnStyle(i === 0)} aria-label="위로">
              <Icon name="up" size={12} />
            </button>
            <button onClick={() => move(i, 1)} disabled={i === order.length - 1} style={moveBtnStyle(i === order.length - 1)} aria-label="아래로">
              <Icon name="down" size={12} />
            </button>
            <BtnOutlineSm danger onClick={() => remove(i)}>제외</BtnOutlineSm>
          </div>
        ))}
      </div>

      <div style={{ fontSize:11, fontWeight:700, color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.05em', marginBottom:8 }}>메뉴 추가</div>
      <div style={{ display:'flex', flexDirection:'column', gap:14, marginBottom:20, maxHeight:260, overflowY:'auto' }}>
        {Object.keys(availableByGroup).length === 0 ? (
          <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'16px 0' }}>추가할 수 있는 메뉴가 없습니다.</p>
        ) : Object.entries(availableByGroup).map(([group, groupItems]) => (
          <div key={group}>
            <div style={{ fontSize:11.5, fontWeight:700, color:'var(--text-muted)', marginBottom:6 }}>{group}</div>
            <div style={{ display:'flex', flexWrap:'wrap', gap:8 }}>
              {groupItems.map(item => (
                <button key={item.path} onClick={() => add(item)}
                  style={{ display:'flex', alignItems:'center', gap:6, padding:'7px 12px', border:'1px dashed var(--border)', borderRadius:8, background:'white', fontFamily:'var(--font)', fontSize:12.5, fontWeight:600, color:'var(--text)', cursor:'pointer' }}>
                  <Icon name="plus" size={11} style={{ opacity:0.6 }} />
                  <Icon name={item.icon} size={13} style={{ opacity:0.55 }} />
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display:'flex', gap:10 }}>
        <button onClick={onClose} style={{ flex:1, height:44, border:'2px solid var(--border)', background:'white', color:'var(--text)', borderRadius:8, fontSize:14, fontWeight:700, cursor:'pointer', fontFamily:'var(--font)' }}>취소</button>
        <BtnPrimary onClick={() => onSave(order)} style={{ flex:1, justifyContent:'center' }}>저장</BtnPrimary>
      </div>
    </Modal>
  )
}

function UpcomingExamsCalendar({ examSets }) {
  const [displayDate, setDisplayDate] = useState(new Date())
  const [selectedDate, setSelectedDate] = useState(null)

  const examsByDate = {}
  examSets.forEach(exam => {
    if (exam.exam_datetime) {
      const dateStr = exam.exam_datetime.split('T')[0]
      if (!examsByDate[dateStr]) examsByDate[dateStr] = []
      examsByDate[dateStr].push(exam)
    }
  })

  const today = new Date()
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`
  const year = displayDate.getFullYear()
  const month = displayDate.getMonth()
  const monthPrefix = `${year}-${String(month + 1).padStart(2,'0')}`

  const firstDayOfWeek = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const totalCells = Math.ceil((firstDayOfWeek + daysInMonth) / 7) * 7
  const cells = []
  for (let i = 0; i < totalCells; i++) {
    const dayNum = i - firstDayOfWeek + 1
    cells.push(dayNum >= 1 && dayNum <= daysInMonth ? dayNum : null)
  }

  const monthExams = examSets
    .filter(exam => exam.exam_datetime && exam.exam_datetime.slice(0, 7) === monthPrefix)
    .sort((a, b) => new Date(a.exam_datetime) - new Date(b.exam_datetime))

  const listExams = selectedDate ? (examsByDate[selectedDate] || []) : monthExams

  const statusColor = (exam) => {
    const status = getExamStatus(exam.exam_datetime, exam.duration_min)
    return status === 'done' ? 'var(--success)' : status === 'ongoing' ? 'var(--warning)' : 'var(--accent)'
  }

  const formatTime = (iso) => {
    const d = new Date(iso)
    return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
  }

  return (
    <Card
      title="시험 일정"
      style={{ marginBottom:0, width:'100%', height:'100%', display:'flex', flexDirection:'column' }}
      bodyStyle={{ flex:1, minHeight:0, display:'flex', flexDirection:'column' }}
      action={
        <div style={{ display:'flex', alignItems:'center', gap:10, fontSize:11, fontWeight:600, color:'var(--text-muted)' }}>
          <div style={{ display:'flex', alignItems:'center', gap:4 }}>
            <span style={{ width:8, height:8, borderRadius:2, background:'var(--accent)' }} />
            예정
          </div>
          <div style={{ display:'flex', alignItems:'center', gap:4 }}>
            <span style={{ width:8, height:8, borderRadius:2, background:'var(--warning)' }} />
            진행중
          </div>
          <div style={{ display:'flex', alignItems:'center', gap:4 }}>
            <span style={{ width:8, height:8, borderRadius:2, background:'var(--success)' }} />
            완료
          </div>
        </div>
      }
    >
      <div style={{ display:'flex', flex:1, minHeight:0, padding:'8px 16px 10px', gap:12 }}>
        <div style={{ flex:'0 0 70%', minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:6 }}>
            <button onClick={() => { setDisplayDate(new Date(year, month - 1, 1)); setSelectedDate(null) }}
              style={{ width:18, height:18, border:'none', background:'none', cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text-muted)', borderRadius:4, padding:0 }}
              onMouseOver={e => e.currentTarget.style.background='#F1F5F9'}
              onMouseOut={e => e.currentTarget.style.background='none'}>
              <Icon name="chevronLeft" size={12} />
            </button>
            <span style={{ fontSize:12, fontWeight:700, color:'var(--text)' }}>{year}년 {month + 1}월</span>
            <button onClick={() => { setDisplayDate(new Date(year, month + 1, 1)); setSelectedDate(null) }}
              style={{ width:18, height:18, border:'none', background:'none', cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text-muted)', borderRadius:4, padding:0 }}
              onMouseOver={e => e.currentTarget.style.background='#F1F5F9'}
              onMouseOut={e => e.currentTarget.style.background='none'}>
              <Icon name="chevronRight" size={12} />
            </button>
          </div>

          <div style={{ display:'grid', gridTemplateColumns:'repeat(7, 1fr)', gap:2, marginBottom:4 }}>
            {['일','월','화','수','목','금','토'].map((d, i) => (
              <div key={d} style={{
                fontSize:9, fontWeight:700, textAlign:'center',
                color: i === 0 ? 'var(--danger)' : i === 6 ? 'var(--accent)' : 'var(--text-muted)'
              }}>{d}</div>
            ))}
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(7, 1fr)', gap:2 }}>
            {cells.map((dayNum, i) => {
              if (dayNum === null) return <div key={i} />
              const dateStr = `${monthPrefix}-${String(dayNum).padStart(2,'0')}`
              const examsOnDay = examsByDate[dateStr] || []
              const isTodayDate = dateStr === todayStr
              const isSelected = selectedDate === dateStr
              const dow = new Date(year, month, dayNum).getDay()
              const holidayInfo = getHolidayInfo(dateStr)
              const dayColor = isTodayDate ? 'var(--warning)'
                : (dow === 0 || holidayInfo) ? 'var(--danger)'
                : dow === 6 ? 'var(--accent)'
                : 'var(--text)'
              return (
                <div key={i}
                  title={holidayInfo ? holidayInfo.names.join(', ') : undefined}
                  onClick={() => examsOnDay.length > 0 && setSelectedDate(isSelected ? null : dateStr)}
                  style={{
                    display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
                    padding:'3px 0', borderRadius:4, minHeight:26,
                    cursor: examsOnDay.length ? 'pointer' : 'default',
                    background: isSelected ? 'var(--accent-light)' : isTodayDate ? 'var(--warning-light)' : 'transparent'
                  }}>
                  <span style={{ fontSize:11, fontWeight:600, color: dayColor }}>{dayNum}</span>
                  <div style={{ display:'flex', gap:2, marginTop:2, height:4 }}>
                    {examsOnDay.slice(0, 3).map(exam => (
                      <span key={exam.exam_id} style={{ width:4, height:4, borderRadius:'50%', background: statusColor(exam) }} />
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div style={{ flex:'0 0 30%', minWidth:0, borderLeft:'1px solid var(--border)', paddingLeft:12, display:'flex', flexDirection:'column', minHeight:0 }}>
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:6, flexShrink:0 }}>
            <span style={{ fontSize:11, fontWeight:700, color:'var(--text)' }}>
              {selectedDate ? `${Number(selectedDate.slice(5,7))}월 ${Number(selectedDate.slice(8,10))}일` : `${month + 1}월 전체`}
            </span>
            {selectedDate && (
              <button onClick={() => setSelectedDate(null)}
                style={{ background:'none', border:'none', color:'var(--accent)', fontSize:10.5, fontWeight:700, cursor:'pointer', padding:0, fontFamily:'var(--font)' }}>
                전체보기
              </button>
            )}
          </div>
          <div style={{ flex:1, minHeight:0, overflowY:'auto', display:'flex', flexDirection:'column', gap:8 }}>
            {listExams.length === 0 ? (
              <p style={{ fontSize:11.5, color:'var(--text-muted)', textAlign:'center', padding:'16px 0' }}>일정이 없습니다</p>
            ) : listExams.map(exam => (
              <div key={exam.exam_id} style={{ display:'flex', alignItems:'flex-start', gap:6 }}>
                <span style={{ width:6, height:6, borderRadius:'50%', background: statusColor(exam), marginTop:4, flexShrink:0 }} />
                <div style={{ minWidth:0 }}>
                  <div style={{ fontSize:11, fontWeight:600, color:'var(--text)', overflowWrap:'break-word' }}>{exam.name}</div>
                  <div style={{ fontSize:9.5, color:'var(--text-muted)' }}>
                    {Number(exam.exam_datetime.slice(5,7))}/{Number(exam.exam_datetime.slice(8,10))} {formatTime(exam.exam_datetime)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Card>
  )
}

function Dashboard({ onNavigate }) {
  const [examSets, setExamSets] = useState([])
  const [examStatusFilter, setExamStatusFilter] = useState('all')
  const [examPage, setExamPage] = useState(1)
  const [modal, setModal] = useState(null)
  const [modalData, setModalData] = useState(null)
  const [modalLoading, setModalLoading] = useState(false)
  const [users, setUsers] = useState([])
  const [reviewingCount, setReviewingCount] = useState(null)
  const [resultsSummary, setResultsSummary] = useState(null)
  const [activityItems, setActivityItems] = useState(null)
  const [activityModalOpen, setActivityModalOpen] = useState(false)
  const [favoritePaths, setFavoritePaths] = useState(() => loadFavoritePaths())
  const [favoritesModalOpen, setFavoritesModalOpen] = useState(false)

  function saveFavorites(itemsInOrder) {
    const paths = itemsInOrder.map(i => i.path)
    setFavoritePaths(paths)
    localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(paths))
    setFavoritesModalOpen(false)
  }

  function loadActivityFeed() {
    apiFetch('GET', '/api/admin/activity-log?limit=3').then(d => setActivityItems(d.items || [])).catch(() => setActivityItems([]))
  }

  useEffect(() => {
    apiFetch('GET', '/api/admin/exam-sets').then(d => setExamSets(d.sets || [])).catch(() => {})
    apiFetch('GET', '/api/admin/users').then(d => setUsers(d.users || [])).catch(() => {})
    apiFetch('GET', '/api/admin/reviewing-question-count').then(d => setReviewingCount(d.count ?? 0)).catch(() => {})
    apiFetch('GET', '/api/admin/results-analysis').then(d => setResultsSummary(d.summary || null)).catch(() => {})
    loadActivityFeed()
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

  const favoriteItems = favoritePaths
    .map(path => ALL_NAV_ITEMS.find(i => i.path === path))
    .filter(Boolean)

  const scheduledCount = examSets.filter(s => getExamStatus(s.exam_datetime, s.duration_min) === 'scheduled').length

  const weekStart = (() => {
    const d = new Date()
    const day = d.getDay()
    const diff = d.getDate() - day + (day === 0 ? -6 : 1) // 이번 주 월요일
    d.setDate(diff)
    d.setHours(0, 0, 0, 0)
    return d
  })()
  const weeklyRegisteredCount = users.filter(u => u.approved_date && new Date(u.approved_date) >= weekStart).length

  const hasResults = resultsSummary && resultsSummary.count > 0
  const avgScoreLabel = hasResults ? `${Math.round(resultsSummary.avg_score * 10) / 10}점` : '-'
  const passRateLabel = hasResults ? `합격률 ${Math.round((resultsSummary.pass_count / resultsSummary.count) * 100)}%` : '응시 기록 없음'

  const kpiCards = [
    { icon:'clock', label:'예정 시험수', value: `${scheduledCount}건`, sub:'예정 상태 시험', view:'exam-assign', color:'var(--accent)' },
    { icon:'check', label:'미검수 문제 대기', value: reviewingCount === null ? '-' : `${reviewingCount}건`, sub:'검수 대기 중', view:'q-review', color:'var(--warning)' },
    { icon:'user',  label:'이번주 등록 인원', value:`${weeklyRegisteredCount}명`, sub:'이번 주 승인', view:'users', color:'var(--success)' },
    { icon:'chart', label:'평균 점수', value: avgScoreLabel, sub: passRateLabel, view:'results', color:'var(--primary)' },
  ]

  return (
    <div>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(200px, 1fr))', gap:14, marginBottom:16 }}>
        {kpiCards.map(k => (
          <button
            key={k.label}
            onClick={() => onNavigate(k.view)}
            style={{
              display:'flex', flexDirection:'column', gap:10, textAlign:'left', cursor:'pointer',
              background:'var(--card)', border:'1px solid var(--border)', borderRadius:'var(--radius)',
              padding:'18px 20px', fontFamily:'var(--font)', transition:'border-color .15s, transform .15s, box-shadow .15s',
            }}
            onMouseOver={e => { e.currentTarget.style.borderColor = k.color; e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 6px 16px rgba(0,0,0,0.06)' }}
            onMouseOut={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none' }}
          >
            <div style={{ display:'flex', alignItems:'center', gap:8 }}>
              <div style={{ width:28, height:28, borderRadius:8, flexShrink:0, display:'flex', alignItems:'center', justifyContent:'center', color:k.color, background:`color-mix(in srgb, ${k.color} 14%, transparent)` }}>
                <Icon name={k.icon} size={15} />
              </div>
              <span style={{ fontSize:12, fontWeight:700, color:'var(--text-muted)' }}>{k.label}</span>
            </div>
            <div style={{ fontSize:26, fontWeight:800, color:'var(--text)', fontVariantNumeric:'tabular-nums', letterSpacing:'-0.5px' }}>{k.value}</div>
            <div style={{ fontSize:11.5, color:'var(--text-muted)' }}>{k.sub}</div>
          </button>
        ))}
      </div>

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

      <div style={{ display:'flex', gap:16, height:360 }}>
        <div style={{ flex:'0 0 40%', minWidth:0, display:'flex', flexDirection:'column', gap:16, height:'100%' }}>
          <Card
            title="즐겨찾기"
            style={{ marginBottom:0, flexShrink:0 }}
            action={
              <button onClick={() => setFavoritesModalOpen(true)} aria-label="즐겨찾기 메뉴 관리"
                style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-muted)', padding:4, display:'flex', alignItems:'center' }}>
                <Icon name="settings" size={16} />
              </button>
            }
          >
            <QuickActionsRow items={favoriteItems} onNavigate={onNavigate} />
          </Card>
          <div style={{ flex:1, minHeight:0 }}>
            <ActivityFeed items={activityItems} onViewAll={() => setActivityModalOpen(true)} />
          </div>
        </div>
        <div style={{ flex:'0 0 60%', minWidth:0, height:'100%' }}>
          <UpcomingExamsCalendar examSets={examSets} />
        </div>
      </div>

      {activityModalOpen && <ActivityLogModal onClose={() => setActivityModalOpen(false)} />}

      {favoritesModalOpen && (
        <FavoritesMenuModal
          favorites={favoriteItems}
          onSave={saveFavorites}
          onClose={() => setFavoritesModalOpen(false)}
        />
      )}

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

/* ── 시험지 생성 (자동 배분 + 피드백 편집) ───────────────────── */
function normalizeQuestionScores(questionIds, preferredScores = {}) {
  if (questionIds.length === 0 || questionIds.length > 100 || new Set(questionIds).size !== questionIds.length) return null

  const preferred = questionIds.map(questionId => Number(preferredScores[questionId]))
  if (preferred.every(score => Number.isInteger(score) && score > 0)
      && preferred.reduce((sum, score) => sum + score, 0) === 100) {
    return Object.fromEntries(questionIds.map((questionId, index) => [questionId, preferred[index]]))
  }

  const weights = preferred.map(score => Number.isFinite(score) && score > 0 ? score : 0)
  if (weights.every(weight => weight === 0)) weights.fill(1)
  const weightTotal = weights.reduce((sum, weight) => sum + weight, 0)
  const distributable = 100 - questionIds.length
  const rawShares = weights.map(weight => weight / weightTotal * distributable)
  const scores = rawShares.map(share => 1 + Math.floor(share))
  let remainder = 100 - scores.reduce((sum, score) => sum + score, 0)
  const remainderOrder = rawShares
    .map((share, index) => ({ index, fraction:share - Math.floor(share) }))
    .sort((left, right) => right.fraction - left.fraction || left.index - right.index)
  for (let index = 0; index < remainder; index += 1) scores[remainderOrder[index].index] += 1
  return Object.fromEntries(questionIds.map((questionId, index) => [questionId, scores[index]]))
}

export function ExamSheet({ toast, onNavigate, sourceExamId = null, onSaved }) {
  const [examName, setExamName] = useState('')
  const [team, setTeam] = useState('T1')
  const [teamDropdownOpen, setTeamDropdownOpen] = useState(false)
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
  const [sourceQuestionScores, setSourceQuestionScores] = useState({})

  useEffect(() => {
    const upper = Math.round(totalCount * 0.28)
    const mid = Math.round(totalCount * 0.40)
    setManualUpper(upper)
    setManualMid(mid)
    setManualLow(Math.max(0, totalCount - upper - mid))
  }, [totalCount])

  useEffect(() => {
    apiFetch('GET', '/api/admin/teams').then(d => setTeams(d.teams || [])).catch(() => {})
  }, [])

  useEffect(() => {
    if (!sourceExamId) {
      setSourceQuestionScores({})
      return undefined
    }
    let active = true
    apiFetch('GET', `/api/admin/exam-sets/${encodeURIComponent(sourceExamId)}/questions`)
      .then(data => {
        if (!active) return
        const source = data.exam_set || {}
        const copiedQuestions = (data.questions || []).map((question, index) => ({
          ...question,
          id: question.question_id || question.id,
          _order:index + 1,
        }))
        setExamName(`${source.name || '시험지'} 수정본`)
        setTeam(source.team_code || 'T1')
        setQuestions(copiedQuestions)
        setTotalCount(copiedQuestions.length || 1)
        setSelectedIdx(0)
        setSwapTargetIdx(null)
        setSourceQuestionScores(source.question_scores || Object.fromEntries(
          copiedQuestions.map(question => [question.question_id || question.id, Number(question.score || 0)]),
        ))
      })
      .catch(error => { if (active) toast(`원본 시험지 조회 실패: ${error.message}`, 'error') })
    return () => { active = false }
  }, [sourceExamId])

  const teamOpts = (teams.length > 0 ? teams : DEFAULT_TEAMS)
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
    if (sourceExamId) {
      const previousId = questions[idx]?.id || questions[idx]?.question_id
      const replacementId = normalized.id
      setSourceQuestionScores(previous => ({
        ...previous,
        [replacementId]:Number(previous[previousId] || 0),
      }))
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
      const body = { name: examName.trim(), team_code: team, question_ids }
      if (sourceExamId) {
        const normalizedScores = normalizeQuestionScores(question_ids, sourceQuestionScores)
        if (!normalizedScores) {
          toast('복사 시험지는 문항별 배점을 양의 정수로 구성해야 하며 최대 100문항까지 저장할 수 있습니다.', 'error')
          return
        }
        body.question_scores = normalizedScores
      }
      const res = await apiFetch('POST', '/api/admin/exam-sets', body)
      if (res.invalid_question_ids?.length > 0) {
        toast(`시험지가 저장됐지만, 존재하지 않는 문제 ${res.invalid_question_ids.length}개는 제외됐습니다.`, 'error')
      } else {
        toast('시험지가 저장됐습니다.')
      }
      onSaved?.(res.exam_id)
    } catch (e) { toast(`저장 실패: ${e.message}`, 'error') }
  }

  // 시험지 팀 라벨은 교대 근무 형태까지 표기한다 (문제 생성 화면의 팀명과 다르게 유지).
  const examTeamLabel = { T1:'1팀 (주간)', T2:'2팀 (4조3교대)', T3:'3팀 (3조2교대)' }[team] || team
  const examDocTitle = () => examName.trim() || '(주)엑스티 OJT 기초고사'

  function buildExamHtml() {
    const title = examDocTitle()
    return buildExamPdfHtml({ docTitle: title, heading: title, teamLabel: examTeamLabel, questions })
  }

  function handlePdf() {
    if (!questions || questions.length === 0) { toast('먼저 문제를 배분해주세요.', 'error'); return }
    const title = examDocTitle()
    openExamPdf({ docTitle: title, heading: title, teamLabel: examTeamLabel, questions, toast })
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
      <Card title="시험지 설정" style={{ flexShrink:0, overflow:'visible' }}>
        <div style={{ display:'flex', flexWrap:'wrap', gap:12, alignItems:'flex-start' }}>
          <div style={{ flex:'2 1 200px' }}>
            <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>시험지 이름</label>
            <input
              type="text"
              value={examName}
              onChange={e => setExamName(e.target.value)}
              placeholder="예) 2024년 하반기 OJT 기초고사"
              style={{ width:'100%', height:44, border:'1px solid var(--border)', borderRadius:8, padding:'0 12px', fontFamily:'var(--font)', fontSize:14, color:'var(--text)', outline:'none', boxSizing:'border-box' }}
            />
          </div>

          <div style={{ flex:'0 0 100px' }}>
            <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>대상 팀</label>
            <div style={{ position:'relative' }}>
              <button
                type="button"
                onClick={() => setTeamDropdownOpen(o => !o)}
                onBlur={() => setTimeout(() => setTeamDropdownOpen(false), 150)}
                style={{ width:'100%', height:44, display:'flex', alignItems:'center', justifyContent:'space-between', border:`1px solid ${teamDropdownOpen ? 'var(--accent)' : 'var(--border)'}`, borderRadius:8, padding:'0 10px', background:'white', fontFamily:'var(--font)', fontSize:14, color:'var(--text)', cursor:'pointer', boxSizing:'border-box' }}
              >
                <span>{teamOpts.find(([val]) => val === team)?.[1] || team}</span>
                <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color:'var(--text-muted)', transform: teamDropdownOpen ? 'rotate(180deg)' : 'none', transition:'transform .15s', flexShrink:0 }}><polyline points="6 9 12 15 18 9"/></svg>
              </button>
              {teamDropdownOpen && (
                <div style={{ position:'absolute', top:'100%', left:0, right:0, marginTop:4, background:'white', border:'1px solid var(--border)', borderRadius:8, boxShadow:'0 4px 16px rgba(0,0,0,0.1)', zIndex:50, overflow:'hidden' }}>
                  {teamOpts.map(([val, label]) => (
                    <div key={val}
                      onMouseDown={() => { setTeam(val); setTeamDropdownOpen(false) }}
                      style={{ padding:'10px 14px', cursor:'pointer', fontSize:13, fontWeight: team === val ? 700 : 400, color: team === val ? 'var(--accent-dark)' : 'var(--text)', background: team === val ? 'var(--accent-light)' : 'white' }}
                    >{label}</div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div style={{ flex:'0 0 80px' }}>
            <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)', display:'block', marginBottom:6 }}>총 문항 수</label>
            <input type="number" min={1} max={200} value={totalCount}
              onChange={e => setTotalCount(Math.max(1, Number(e.target.value) || 0))}
              style={{ width:'100%', height:44, border:'1px solid var(--border)', borderRadius:8, padding:'0 10px', fontFamily:'var(--font)', fontSize:14, color:'var(--text)', outline:'none', boxSizing:'border-box' }}
            />
          </div>

          <div style={{ flex:'0 0 190px' }}>
            <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:6 }}>
              <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)' }}>출제 횟수 제한</label>
              <button
                onClick={() => setExcludeFrequent(v => !v)}
                style={{ border:`1.5px solid ${excludeFrequent ? 'var(--accent)' : 'var(--border)'}`, background: excludeFrequent ? 'var(--accent-light)' : 'white', color: excludeFrequent ? 'var(--accent-dark)' : 'var(--text-muted)', borderRadius:20, padding:'2px 9px', fontFamily:'var(--font)', fontSize:11, fontWeight: excludeFrequent ? 700 : 400, cursor:'pointer', flexShrink:0 }}
              >{excludeFrequent ? 'ON' : 'OFF'}</button>
            </div>
            <input type="number" min={1} max={999} value={maxExamCount}
              readOnly={!excludeFrequent}
              onChange={e => setMaxExamCount(Math.max(1, Number(e.target.value) || 0))}
              style={{ width:'100%', height:44, border:'1px solid var(--border)', borderRadius:8, padding:'0 10px', fontFamily:'var(--font)', fontSize:14, color: excludeFrequent ? 'var(--text)' : 'var(--text-light)', outline:'none', boxSizing:'border-box', background: excludeFrequent ? 'white' : 'var(--bg)', cursor: excludeFrequent ? 'text' : 'default' }}
            />
            <p style={{ fontSize:10, color:'var(--text-muted)', margin:'4px 0 0' }}>회 이상 출제된 문제는 제외</p>
          </div>

          <div style={{ flex:'1 1 240px' }}>
            <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:6 }}>
              <label style={{ fontSize:13, fontWeight:600, color:'var(--text-muted)' }}>수동 배분</label>
              <button
                onClick={() => setManualMode(m => !m)}
                style={{ border:`1.5px solid ${manualMode ? 'var(--accent)' : 'var(--border)'}`, background: manualMode ? 'var(--accent-light)' : 'white', color: manualMode ? 'var(--accent-dark)' : 'var(--text-muted)', borderRadius:20, padding:'2px 9px', fontFamily:'var(--font)', fontSize:11, fontWeight: manualMode ? 700 : 400, cursor:'pointer', flexShrink:0 }}
              >{manualMode ? 'ON' : 'OFF'}</button>
            </div>

            <div style={{ display:'flex', alignItems:'center', gap:12, flexWrap:'wrap' }}>
              {[
                ['상', manualUpper, setManualUpper, '#b91c1c', '#fee2e2'],
                ['중', manualMid,   setManualMid,   '#b45309', '#fef3c7'],
                ['하', manualLow,   setManualLow,   '#065f46', '#d1fae5'],
              ].map(([label, val, setter, color, bg]) => (
                <div key={label} style={{ display:'flex', alignItems:'center', gap:8 }}>
                  <span style={{ fontSize:11, fontWeight:700, padding:'2px 8px', borderRadius:20, background:bg, color, minWidth:24, textAlign:'center' }}>{label}</span>
                  <input type="number" min={0} max={totalCount} value={val}
                    readOnly={!manualMode}
                    onChange={e => setter(Math.max(0, Math.min(totalCount, Number(e.target.value))))}
                    style={{ width:56, height:36, border:'1.5px solid var(--border)', borderRadius:6, padding:'0 8px', fontFamily:'var(--font)', fontSize:13, textAlign:'center', outline:'none', background: manualMode ? 'white' : 'var(--bg)', color: manualMode ? 'var(--text)' : 'var(--text-light)', cursor: manualMode ? 'text' : 'default' }}
                  />
                  <span style={{ fontSize:11, color:'var(--text-muted)' }}>문항</span>
                </div>
              ))}
              <span style={{ fontSize:11, color: (manualUpper+manualMid+manualLow) === totalCount ? 'var(--success)' : 'var(--danger)', fontWeight:600 }}>
                합계: {manualUpper+manualMid+manualLow} / {totalCount}문항
                {manualMode && (manualUpper+manualMid+manualLow) !== totalCount && ' ← 총 문항수와 맞춰주세요'}
              </span>
            </div>
            {!manualMode && (
              <p style={{ fontSize:10, color:'var(--text-muted)', margin:'4px 0 0' }}>
                OFF 상태에서는 위 비율대로 자동 배분됩니다. 총 문항 수를 바꾸면 비율에 맞춰 자동으로 갱신됩니다.
              </p>
            )}
          </div>

          <div style={{ flex:'0 0 auto' }}>
            <label style={{ fontSize:13, fontWeight:600, display:'block', marginBottom:6, visibility:'hidden' }}>배분</label>
            <BtnPrimary onClick={assign} style={{ height:44 }} disabled={loading}>
              <Icon name="refresh" size={14} style={{ color:'white' }} />
              {loading ? '배분 중...' : (manualMode ? '수동 배분' : '자동 배분')}
            </BtnPrimary>
          </div>
        </div>

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

          <div style={{ display:'flex', flexDirection:'column', gap:16, height:'100%', minHeight:0 }}>
            <Card title="시험지 저장" style={{ flexShrink:0, marginBottom:0 }}>
              <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
                <button onClick={handleSave} style={{ background:'var(--accent)', color:'white', border:'none', borderRadius:7, padding:'9px 14px', fontFamily:'var(--font)', fontSize:12, fontWeight:700, cursor:'pointer' }}>
                  시험지 저장
                </button>
                <button onClick={handlePdf} style={{ border:'1.5px solid var(--border)', background:'white', color:'var(--text-muted)', borderRadius:7, padding:'8px 14px', fontFamily:'var(--font)', fontSize:12, cursor:'pointer' }}>
                  PDF 저장
                </button>
                <button onClick={handleHtmlSave} style={{ border:'1.5px solid var(--border)', background:'white', color:'var(--text-muted)', borderRadius:7, padding:'8px 14px', fontFamily:'var(--font)', fontSize:12, cursor:'pointer' }}>
                  HTML 저장
                </button>
                <button onClick={() => onNavigate('q-bank')} style={{ border:'1.5px solid var(--accent)', background:'white', color:'var(--accent)', borderRadius:7, padding:'8px 14px', fontFamily:'var(--font)', fontSize:12, fontWeight:600, cursor:'pointer' }}>
                  문제은행으로 이동
                </button>
              </div>
            </Card>

            <Card
              title="문제 미리보기"
              style={{ flex:1, minHeight:0, display:'flex', flexDirection:'column', marginBottom:0 }}
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
        </div>
      )}
    </div>
  )
}

/* ── 응시 이력 ───────────────────────────────────────────────── */
function History({ toast, filters, onFiltersChange }) {
  const [rows, setRows] = useState(null)
  const [filterTeam, setFilterTeam] = useState(() => filters?.team ?? '')
  const [filterFrom, setFilterFrom] = useState(() => filters?.from ?? '')
  const [filterTo, setFilterTo] = useState(() => filters?.to ?? '')
  const [search, setSearch] = useState(() => filters?.q ?? '')

  useEffect(() => { setFilterTeam(filters?.team ?? '') }, [filters?.team])
  useEffect(() => { setFilterFrom(filters?.from ?? '') }, [filters?.from])
  useEffect(() => { setFilterTo(filters?.to ?? '') }, [filters?.to])
  useEffect(() => { setSearch(filters?.q ?? '') }, [filters?.q])

  function changeFilter(key, value, setter) {
    setter(value)
    onFiltersChange?.({ [key]: value })
  }

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
        <FilterSelect value={filterTeam} onChange={value => changeFilter('team', value, setFilterTeam)}><option value="">전체 팀</option><option value="T1">1팀</option><option value="T2">2팀</option><option value="T3">3팀</option></FilterSelect>
        <input type="date" value={filterFrom} onChange={e => changeFilter('from', e.target.value, setFilterFrom)} style={{ border:'1.5px solid var(--border)', borderRadius:6, padding:'7px 10px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', background:'white', outline:'none' }} />
        <span style={{ color:'var(--text-muted)', fontSize:13 }}>~</span>
        <input type="date" value={filterTo} onChange={e => changeFilter('to', e.target.value, setFilterTo)} style={{ border:'1.5px solid var(--border)', borderRadius:6, padding:'7px 10px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', background:'white', outline:'none' }} />
        <BtnOutlineSm onClick={load}>조회</BtnOutlineSm>
      </div>
    }>
      <div style={{ padding:'10px 20px', borderBottom:'1px solid var(--border)' }}>
        <input value={search} onChange={e => changeFilter('q', e.target.value, setSearch)} placeholder="이름 검색" style={{ border:'1.5px solid var(--border)', borderRadius:6, padding:'7px 10px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', background:'white', maxWidth:240, width:'100%', outline:'none' }} />
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

/* ── 사용자 승인 ─────────────────────────────────────────────── */
function Users({ toast }) {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState({ empno:'', name:'', team:'T1', date:'' })
  const [result, setResult] = useState({ msg:'', ok:null })
  const [teams, setTeams] = useState([])
  const [csvResult, setCsvResult] = useState(null)
  const [csvLoading, setCsvLoading] = useState(false)
  const [csvPreviewRows, setCsvPreviewRows] = useState(null)
  const [csvApproving, setCsvApproving] = useState(false)
  const [showCsvCancelConfirm, setShowCsvCancelConfirm] = useState(false)
  const [filterTeam, setFilterTeam] = useState('all')
  const [filterDateFrom, setFilterDateFrom] = useState('')
  const [filterDateTo, setFilterDateTo] = useState('')
  const [filterSearch, setFilterSearch] = useState('')

  const filteredUsers = users.filter(u => {
    if (filterTeam !== 'all' && u.team !== filterTeam) return false
    const approvedDate = (u.approved_date || '').slice(0,10)
    if (filterDateFrom && (!approvedDate || approvedDate < filterDateFrom)) return false
    if (filterDateTo && (!approvedDate || approvedDate > filterDateTo)) return false
    if (filterSearch) {
      const q = filterSearch.trim().toLowerCase()
      const matches = u.employee_id?.toLowerCase().includes(q) || u.name?.toLowerCase().includes(q)
      if (!matches) return false
    }
    return true
  })

  async function loadUsers() {
    try { const d = await apiFetch('GET', '/api/admin/users'); setUsers(d.users) } catch {}
  }
  function refreshUsers() {
    setFilterTeam('all')
    setFilterDateFrom('')
    setFilterDateTo('')
    setFilterSearch('')
    loadUsers()
  }
  useEffect(() => {
    loadUsers()
    apiFetch('GET', '/api/admin/teams').then(d => setTeams(d.teams)).catch(() => {})
  }, [])

  async function approve() {
    if (!form.empno || !form.name) { setResult({ msg:'모든 항목을 입력해주세요.', ok:false }); return }
    try {
      await apiFetch('POST', '/api/admin/approve-user', { employee_id:form.empno, name:form.name, team:form.team })
      setResult({ msg:`${form.name} (${form.empno}) 승인 완료`, ok:true })
      setForm({ empno:'', name:'', team: teams[0]?.team_code || 'T1' })
      loadUsers()
    } catch (e) { setResult({ msg:`오류: ${e.message}`, ok:false }) }
  }

  async function del(id, name) {
    if (!confirm(`${name} (${id})을 삭제하시겠습니까?`)) return
    try { await apiFetch('DELETE', `/api/admin/users/${id}`); loadUsers() } catch (e) { toast(`삭제 실패: ${e.message}`, 'error') }
  }

  function parseCsvRows(text) {
    const cleaned = text.charCodeAt(0) === 0xFEFF ? text.slice(1) : text
    const lines = cleaned.split(/\r\n|\n/).filter(l => l.trim() !== '')
    if (lines.length === 0) return []
    const headers = lines[0].split(',').map(h => h.trim())
    return lines.slice(1).map(line => {
      const cells = line.split(',').map(c => c.trim())
      const row = {}
      headers.forEach((h, i) => { row[h] = cells[i] ?? '' })
      return {
        employee_id: row.employee_id || '',
        name: row.name || '',
        team: row.team_code || row.team || '',
      }
    })
  }

  function handleCsvUpload(e) {
    const file = e.target.files[0]
    if (!file) return
    setCsvLoading(true); setCsvResult(null)
    const reader = new FileReader()
    reader.onload = () => {
      setCsvLoading(false)
      const parsed = parseCsvRows(String(reader.result))
      if (parsed.length === 0) {
        toast('CSV에서 읽을 수 있는 데이터가 없습니다.', 'error')
        return
      }
      setCsvPreviewRows(parsed.map(r => ({ ...r, excluded:false })))
    }
    reader.onerror = () => { setCsvLoading(false); toast('CSV 파일을 읽을 수 없습니다.', 'error') }
    reader.readAsText(file, 'utf-8')
    e.target.value = ''
  }

  function toggleExcludeCsvRow(idx) {
    setCsvPreviewRows(prev => prev.map((r, i) => i === idx ? { ...r, excluded:!r.excluded } : r))
  }

  function cancelCsvUpload() {
    setShowCsvCancelConfirm(false)
    setCsvPreviewRows(null)
  }

  async function approveCsvUpload() {
    const included = csvPreviewRows.filter(r => !r.excluded)
    if (included.length === 0) { toast('승인할 인원이 없습니다.', 'error'); return }
    setCsvApproving(true)
    try {
      const csvBody = ['employee_id,name,team_code', ...included.map(r => `${r.employee_id},${r.name},${r.team}`)].join('\n')
      const fd = new FormData()
      fd.append('file', new Blob([csvBody], { type:'text/csv' }), 'users.csv')
      const r = await apiUpload('/api/admin/upload-users', fd)
      setCsvResult(r)
      toast(`CSV 업로드 완료: 성공 ${r.success}건`, 'success')
      setCsvPreviewRows(null)
      loadUsers()
    } catch (err) {
      toast(`CSV 업로드 실패: ${err.message}`, 'error')
    } finally {
      setCsvApproving(false)
    }
  }

  const teamOpts = teams.length > 0 ? teams : DEFAULT_TEAMS

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
          <BtnPrimary onClick={approve} style={{ width:'100%', justifyContent:'center' }}>
            <Icon name="check" size={14} style={{ color:'white' }} /> 승인 등록
          </BtnPrimary>
          {result.msg && (
            <p style={{ marginTop:10, fontSize:12, padding:'8px 10px', borderRadius:6, background: result.ok ? 'var(--success-light)' : 'var(--danger-light)', color: result.ok ? 'var(--success)' : 'var(--danger)' }}>{result.msg}</p>
          )}
        </Card>

        <Card title="CSV 대량 업로드">
          <p style={{ fontSize:12.5, color:'var(--text)', lineHeight:1.6, marginBottom:12 }}>
            여러 명의 신입사원을 한 번에 승인 등록할 때 사용합니다. 엑셀 등에서 아래와 같은 표를 만들고 <strong>CSV(쉼표로 구분) 형식</strong>으로 저장한 뒤 업로드하면 됩니다.
          </p>
          <div style={{ border:'1px solid var(--border)', borderRadius:8, overflow:'hidden', marginBottom:10 }}>
            <table style={{ width:'100%', borderCollapse:'collapse', fontSize:11.5 }}>
              <thead>
                <tr style={{ background:'#F8FAFC' }}>
                  <th style={{ textAlign:'left', padding:'7px 10px', fontWeight:700, color:'var(--text-muted)', borderBottom:'1px solid var(--border)' }}>employee_id</th>
                  <th style={{ textAlign:'left', padding:'7px 10px', fontWeight:700, color:'var(--text-muted)', borderBottom:'1px solid var(--border)' }}>name</th>
                  <th style={{ textAlign:'left', padding:'7px 10px', fontWeight:700, color:'var(--text-muted)', borderBottom:'1px solid var(--border)' }}>team_code</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ padding:'7px 10px', color:'var(--text)', fontVariantNumeric:'tabular-nums' }}>2024001</td>
                  <td style={{ padding:'7px 10px', color:'var(--text)' }}>홍길동</td>
                  <td style={{ padding:'7px 10px', color:'var(--text)' }}>T1</td>
                </tr>
                <tr>
                  <td style={{ padding:'7px 10px', color:'var(--text)', fontVariantNumeric:'tabular-nums', borderTop:'1px solid var(--border)' }}>2024002</td>
                  <td style={{ padding:'7px 10px', color:'var(--text)', borderTop:'1px solid var(--border)' }}>김철수</td>
                  <td style={{ padding:'7px 10px', color:'var(--text)', borderTop:'1px solid var(--border)' }}>T2</td>
                </tr>
              </tbody>
            </table>
          </div>
          <ul style={{ margin:'0 0 10px', paddingLeft:18, fontSize:11.5, color:'var(--text-muted)', lineHeight:1.85 }}>
            <li><code>employee_id</code> — 사원번호. 로그인 시 아이디로 쓰이며 다른 사원과 중복될 수 없습니다.</li>
            <li><code>name</code> — 이름입니다.</li>
            <li><code>team_code</code> — 소속 팀 코드입니다(예: T1, T2, T3). 정확한 코드는 좌측 <strong>팀 관리</strong> 메뉴에서 확인할 수 있습니다.</li>
          </ul>
          <p style={{ fontSize:11, color:'var(--text-light)', marginBottom:14, lineHeight:1.6 }}>
            ※ 파일의 첫 번째 줄에는 반드시 위 표처럼 <code>employee_id</code>, <code>name</code>, <code>team_code</code>라는 컬럼 이름이 그대로 들어가야 하며, 그 다음 줄부터 실제 사원 정보를 한 줄씩 입력합니다.
          </p>
          <label style={{ display:'inline-flex', alignItems:'center', gap:8, padding:'9px 16px', border:'1.5px dashed var(--border)', borderRadius:8, cursor:'pointer', fontSize:13, color:'var(--text)', background:'#FAFAFA', width:'100%', justifyContent:'center', boxSizing:'border-box' }}>
            <Icon name="up" size={14} />
            {csvLoading ? '읽는 중...' : 'CSV 파일 선택'}
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
      <Card title="승인된 응시자 목록" noPad action={<BtnOutlineSm onClick={refreshUsers}><Icon name="refresh" size={11} /> 새로고침</BtnOutlineSm>}>
        <div style={{ display:'flex', gap:20, flexWrap:'wrap', alignItems:'flex-end', padding:'16px 20px', borderBottom:'1px solid var(--border)', background:'var(--bg)' }}>
          <div>
            <div style={{ fontSize:10.5, fontWeight:700, color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:6 }}>팀</div>
            <FilterSelect value={filterTeam} onChange={setFilterTeam}>
              <option value="all">전체 팀</option>
              {teamOpts.map(t => <option key={t.team_code} value={t.team_code}>{t.team_name}</option>)}
            </FilterSelect>
          </div>
          <div>
            <div style={{ fontSize:10.5, fontWeight:700, color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:6 }}>승인일 범위</div>
            <div style={{ display:'flex', alignItems:'center', gap:6, border:'1.5px solid var(--border)', borderRadius:8, padding:'0 10px', background:'white', height:33, boxSizing:'border-box' }}>
              <Icon name="calendar" size={13} style={{ color:'var(--text-muted)', flexShrink:0 }} />
              <input
                type="date"
                value={filterDateFrom}
                onChange={e => setFilterDateFrom(e.target.value)}
                style={{ border:'none', outline:'none', padding:'0 2px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', background:'transparent', width:126 }}
              />
              <span style={{ fontSize:12, color:'var(--text-light)' }}>–</span>
              <input
                type="date"
                value={filterDateTo}
                onChange={e => setFilterDateTo(e.target.value)}
                style={{ border:'none', outline:'none', padding:'0 2px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', background:'transparent', width:126 }}
              />
            </div>
          </div>
          <div>
            <div style={{ fontSize:10.5, fontWeight:700, color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:6 }}>검색</div>
            <div style={{ position:'relative' }}>
              <Icon name="search" size={13} style={{ position:'absolute', left:10, top:'50%', transform:'translateY(-50%)', color:'var(--text-muted)', pointerEvents:'none' }} />
              <input
                type="text"
                value={filterSearch}
                onChange={e => setFilterSearch(e.target.value)}
                placeholder="사원번호 또는 이름"
                style={{ width:170, border:'1.5px solid var(--border)', borderRadius:8, padding:'8px 12px 8px 30px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', background:'white', outline:'none', boxSizing:'border-box', height:33 }}
              />
            </div>
          </div>
          {(filterTeam !== 'all' || filterDateFrom || filterDateTo || filterSearch) && (
            <span style={{ fontSize:12, color:'var(--accent-dark)', fontWeight:600, background:'var(--accent-light)', padding:'6px 12px', borderRadius:20, marginBottom:1 }}>
              {filteredUsers.length}명 검색됨
            </span>
          )}
        </div>
        <div style={{ height:700, overflowY:'auto' }}>
        <DataTable headers={['사원번호','이름','팀','상태','승인일','관리']}>
          {filteredUsers.length === 0 ? (
            <tr><td colSpan={6} style={{ textAlign:'center', color:'var(--text-muted)', padding:'48px 0' }}>
              <Icon name="users" size={26} style={{ color:'var(--text-light)', marginBottom:10 }} />
              <div style={{ fontSize:13 }}>{users.length === 0 ? '승인된 응시자가 없습니다.' : '조건에 맞는 응시자가 없습니다.'}</div>
            </td></tr>
          ) : filteredUsers.map((u, i) => (
            <tr key={u.employee_id} style={{ background: i % 2 === 1 ? '#FAFBFC' : 'transparent', transition:'background .12s' }}
              onMouseOver={e => e.currentTarget.style.background='#F1F5F9'}
              onMouseOut={e => e.currentTarget.style.background = i % 2 === 1 ? '#FAFBFC' : 'transparent'}>
              <td style={{ fontSize:13, padding:'12px 18px', borderBottom:'1px solid var(--border)', fontVariantNumeric:'tabular-nums', color:'var(--text-muted)' }}>{u.employee_id}</td>
              <td style={{ fontSize:13, padding:'12px 18px', borderBottom:'1px solid var(--border)', fontWeight:600, color:'var(--text)' }}>{u.name}</td>
              <td style={{ fontSize:13, padding:'12px 18px', borderBottom:'1px solid var(--border)' }}>
                <span style={{ display:'inline-flex', alignItems:'center', gap:6 }}>
                  <span style={{ width:7, height:7, borderRadius:'50%', background: TEAM_DOT_COLORS[u.team] || 'var(--text-light)', flexShrink:0 }} />
                  {TEAM_LABELS[u.team] || u.team || '-'}
                </span>
              </td>
              <td style={{ fontSize:13, padding:'12px 18px', borderBottom:'1px solid var(--border)' }}><Badge type="success">승인</Badge></td>
              <td style={{ fontSize:12, padding:'12px 18px', borderBottom:'1px solid var(--border)', color:'var(--text-muted)', fontVariantNumeric:'tabular-nums' }}>{u.approved_date ? u.approved_date.slice(0,10) : '-'}</td>
              <td style={{ fontSize:13, padding:'12px 18px', borderBottom:'1px solid var(--border)' }}><BtnOutlineSm danger onClick={() => del(u.employee_id, u.name)}><Icon name="trash" size={11} /> 삭제</BtnOutlineSm></td>
            </tr>
          ))}
        </DataTable>
        </div>
      </Card>

      {csvPreviewRows && (() => {
        const indexedRows = csvPreviewRows.map((r, idx) => ({ ...r, idx }))
        const includedRows = indexedRows.filter(r => !r.excluded)
        const excludedRows = indexedRows.filter(r => r.excluded)

        const PersonRow = ({ r, excluded }) => {
          const teamHex = TEAM_DOT_COLORS[r.team]
          return (
          <div style={{ display:'flex', alignItems:'center', gap:12, padding:'10px 14px', borderBottom:'1px solid var(--border)', opacity: excluded ? 0.6 : 1 }}>
            <div style={{
              width:30, height:30, borderRadius:'50%', flexShrink:0, display:'flex', alignItems:'center', justifyContent:'center',
              background: excluded ? '#E2E8F0' : teamHex ? teamHex + '1f' : 'var(--accent-light)',
              color: excluded ? 'var(--text-muted)' : teamHex || 'var(--accent-dark)',
              fontSize:12, fontWeight:700,
            }}>
              {(r.name || '?').charAt(0)}
            </div>
            <div style={{ minWidth:0 }}>
              <div style={{ fontSize:13, fontWeight:600, color:'var(--text)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>
                {r.name || <span style={{ color:'var(--danger)' }}>이름 없음</span>}
              </div>
              <div style={{ fontSize:11.5, color:'var(--text-muted)', fontVariantNumeric:'tabular-nums', marginTop:1 }}>
                {r.employee_id || <span style={{ color:'var(--danger)' }}>사원번호 없음</span>} · {TEAM_LABELS[r.team] || r.team || '팀 미지정'}
              </div>
            </div>
            <span style={{ marginLeft:'auto', flexShrink:0 }}>
              {excluded ? (
                <BtnOutlineSm onClick={() => toggleExcludeCsvRow(r.idx)}><Icon name="plus" size={11} /> 포함</BtnOutlineSm>
              ) : (
                <BtnOutlineSm danger onClick={() => toggleExcludeCsvRow(r.idx)}><Icon name="x" size={11} /> 제외</BtnOutlineSm>
              )}
            </span>
          </div>
          )
        }

        return (
          <Modal title="CSV 업로드 확인" wide onClose={() => setShowCsvCancelConfirm(true)}>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', gap:12, marginBottom:18, flexWrap:'wrap', background:'var(--bg)', border:'1px solid var(--border)', borderRadius:10, padding:'12px 16px' }}>
              <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
                <span style={{ fontSize:12, fontWeight:700, color:'var(--text)', background:'white', border:'1px solid var(--border)', borderRadius:20, padding:'4px 12px' }}>총 {csvPreviewRows.length}명</span>
                <span style={{ fontSize:12, fontWeight:700, color:'var(--success)', background:'var(--success-light)', borderRadius:20, padding:'4px 12px' }}>승인 예정 {includedRows.length}명</span>
                <span style={{ fontSize:12, fontWeight:700, color:'var(--text-muted)', background:'#F1F5F9', borderRadius:20, padding:'4px 12px' }}>제외 {excludedRows.length}명</span>
              </div>
              <div style={{ display:'flex', gap:8 }}>
                <BtnPrimary onClick={approveCsvUpload} disabled={csvApproving}>
                  <Icon name="check" size={14} style={{ color:'white' }} /> {csvApproving ? '승인 중...' : '승인'}
                </BtnPrimary>
                <BtnOutlineSm danger onClick={() => setShowCsvCancelConfirm(true)}>취소</BtnOutlineSm>
              </div>
            </div>

            <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:8 }}>
              <span style={{ fontSize:12, fontWeight:700, color:'var(--text)' }}>업로드된 사원 목록</span>
            </div>
            <div style={{ display:'flex', flexDirection:'column', maxHeight:280, overflowY:'auto', border:'1px solid var(--border)', borderRadius:10, marginBottom:22 }}>
              {includedRows.length === 0 ? (
                <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'20px 0' }}>승인 예정 인원이 없습니다.</p>
              ) : includedRows.map(r => <PersonRow key={r.idx} r={r} excluded={false} />)}
            </div>

            <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:8 }}>
              <span style={{ fontSize:12, fontWeight:700, color:'var(--text-muted)' }}>제외된 사원 목록</span>
              <span style={{ fontSize:11, fontWeight:700, color:'var(--text-muted)', background:'#F1F5F9', borderRadius:20, padding:'1px 8px' }}>{excludedRows.length}</span>
            </div>
            <div style={{ display:'flex', flexDirection:'column', maxHeight:200, overflowY:'auto', border:'1px dashed var(--border)', borderRadius:10, background:'#FAFBFC' }}>
              {excludedRows.length === 0 ? (
                <p style={{ fontSize:13, color:'var(--text-muted)', textAlign:'center', padding:'20px 0' }}>제외된 인원이 없습니다.</p>
              ) : excludedRows.map(r => <PersonRow key={r.idx} r={r} excluded={true} />)}
            </div>
          </Modal>
        )
      })()}

      {showCsvCancelConfirm && (
        <div style={{ position:'fixed', inset:0, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(15,23,42,0.6)', backdropFilter:'blur(4px)', zIndex:300 }}>
          <div style={{ background:'white', borderRadius:20, padding:'36px 32px', width:'90%', maxWidth:400, boxShadow:'0 20px 60px rgba(0,0,0,0.25)', textAlign:'center' }}>
            <div style={{ width:52, height:52, borderRadius:'50%', background:'var(--danger-light)', display:'flex', alignItems:'center', justifyContent:'center', margin:'0 auto 18px' }}>
              <Icon name="alert" size={24} style={{ color:'var(--danger)' }} />
            </div>
            <h2 style={{ fontSize:17, fontWeight:800, color:'var(--text)', marginBottom:10, letterSpacing:'-0.4px' }}>승인 작업 취소</h2>
            <p style={{ fontSize:14, color:'var(--text-muted)', marginBottom:26, lineHeight:1.6 }}>지금 진행중인 승인 작업을 정말 취소하시겠습니까?</p>
            <div style={{ display:'flex', gap:12 }}>
              <button onClick={() => setShowCsvCancelConfirm(false)} style={{ flex:1, height:48, fontSize:15, fontWeight:700, cursor:'pointer', border:'2px solid var(--border)', background:'white', color:'var(--text)', borderRadius:10, fontFamily:'var(--font)' }}>아니오</button>
              <button onClick={cancelCsvUpload} style={{ flex:1, height:48, fontSize:15, fontWeight:700, cursor:'pointer', border:'none', background:'var(--danger)', color:'white', borderRadius:10, fontFamily:'var(--font)' }}>예</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ── 결과 분석 ───────────────────────────────────────────────── */
function computeBoxStats(scores) {
  const sorted = [...scores].sort((a, b) => a - b)
  const n = sorted.length
  const quantile = q => {
    if (n === 1) return sorted[0]
    const pos = (n - 1) * q
    const base = Math.floor(pos)
    const rest = pos - base
    return sorted[base + 1] !== undefined ? sorted[base] + rest * (sorted[base + 1] - sorted[base]) : sorted[base]
  }
  return {
    min: sorted[0],
    max: sorted[n - 1],
    q1: Math.round(quantile(0.25) * 10) / 10,
    median: Math.round(quantile(0.5) * 10) / 10,
    q3: Math.round(quantile(0.75) * 10) / 10,
    avg: Math.round((sorted.reduce((a, b) => a + b, 0) / n) * 10) / 10,
  }
}

function rankTakers(takers) {
  const sorted = [...takers].sort((a, b) => b.score - a.score)
  let rank = 0
  let prevScore = null
  return sorted.map((t, i) => {
    if (t.score !== prevScore) rank = i + 1
    prevScore = t.score
    return { ...t, rank }
  })
}

function categoryBreakdown(results) {
  const map = new Map()
  for (const q of (results || [])) {
    const cat = q.category || '기타'
    if (!map.has(cat)) map.set(cat, { correct: 0, total: 0 })
    const c = map.get(cat)
    c.total += 1
    if (q.correct) c.correct += 1
  }
  return [...map.entries()].map(([cat, v]) => ({ cat, ...v }))
}

function niceUpperBound(v) {
  if (v <= 0) return 10
  const step = v <= 50 ? 10 : v <= 100 ? 20 : 50
  return Math.ceil(v / step) * step
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function toCsvValue(v) {
  const s = String(v ?? '')
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function xmlEscape(v) {
  return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function takerExportRows(rankedTakers) {
  return rankedTakers.map(t => [t.rank, t.name, t.employee_id || '-', t.score, t.pass ? '합격' : '재교육', t.date])
}

const EXPORT_HEADERS = ['등수', '이름', '사번', '점수', '결과', '응시일']

function exportTakersCsv(examName, rankedTakers) {
  const rows = takerExportRows(rankedTakers)
  const csv = [EXPORT_HEADERS, ...rows].map(r => r.map(toCsvValue).join(',')).join('\r\n')
  downloadBlob(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' }), `${examName}_응시결과.csv`)
}

function exportTakersExcel(examName, rankedTakers) {
  const rows = takerExportRows(rankedTakers)
  const headerRow = `<Row>${EXPORT_HEADERS.map(h => `<Cell ss:StyleID="Header"><Data ss:Type="String">${xmlEscape(h)}</Data></Cell>`).join('')}</Row>`
  const dataRows = rows.map(r => `<Row>${r.map(v => `<Cell><Data ss:Type="${typeof v === 'number' ? 'Number' : 'String'}">${xmlEscape(v)}</Data></Cell>`).join('')}</Row>`).join('')
  const xml = `<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Styles>
  <Style ss:ID="Header"><Font ss:Bold="1"/><Interior ss:Color="#EEF2FF" ss:Pattern="Solid"/></Style>
 </Styles>
 <Worksheet ss:Name="응시결과">
  <Table>
   ${headerRow}
   ${dataRows}
  </Table>
 </Worksheet>
</Workbook>`
  downloadBlob(new Blob([xml], { type: 'application/vnd.ms-excel' }), `${examName}_응시결과.xls`)
}

function exportTakersPdf(exam, rankedTakers, toast) {
  const rowsHtml = takerExportRows(rankedTakers).map(r => `
    <tr>${r.map(v => `<td>${xmlEscape(v)}</td>`).join('')}</tr>`).join('')
  const html = `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<title>${xmlEscape(exam.name)} 응시 결과</title>
<style>
  @page { size: A4; margin: 18mm; }
  body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; color:#1a1a1a; }
  h1 { font-size:18pt; margin:0 0 4px; }
  .meta { font-size:10.5pt; color:#555; margin-bottom:20px; }
  table { width:100%; border-collapse:collapse; font-size:10pt; }
  th, td { padding:8px 10px; border-bottom:1px solid #e2e8f0; text-align:left; }
  th { background:#f8fafc; font-weight:700; }
</style>
</head>
<body>
  <h1>${xmlEscape(exam.name)} 응시 결과</h1>
  <p class="meta">${xmlEscape(exam.team_name)} · 응시 ${exam.taker_count}명 · 평균 ${exam.avg_score}점 · 합격 ${exam.pass_count}명</p>
  <table>
    <thead><tr>${EXPORT_HEADERS.map(h => `<th>${h}</th>`).join('')}</tr></thead>
    <tbody>${rowsHtml}</tbody>
  </table>
</body>
</html>`
  const win = window.open('', '_blank')
  if (!win) { toast?.('팝업이 차단되어 PDF를 열 수 없습니다. 브라우저의 팝업 차단을 해제해주세요.', 'error'); return }
  win.document.write(html)
  win.document.close()
  win.focus()
  setTimeout(() => { win.print() }, 300)
}

function StatTile({ label, value, accent }) {
  return (
    <div style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:8, padding:'14px 16px' }}>
      <div style={{ fontSize:11, color:'var(--text-muted)', fontWeight:600, marginBottom:6 }}>{label}</div>
      <div style={{ fontSize:22, fontWeight:800, color: accent || 'var(--text)' }}>{value}</div>
    </div>
  )
}

/* ── 점수 분포 박스플롯 (5수 요약 + 개별 응시자 점) ─────────────── */
function ScoreBoxPlot({ takers, stats, passScore }) {
  const W = 800, H = 150
  const padL = 34, padR = 34
  const plotW = W - padL - padR
  const domainMax = niceUpperBound(Math.max(stats.max, passScore || 0))
  const x = v => padL + (v / domainMax) * plotW
  const boxTop = 46, boxBottom = 86, boxMid = (boxTop + boxBottom) / 2
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(f => Math.round(domainMax * f))
  const jitterFor = i => [0, -12, 12, -6, 6, -18, 18][i % 7]

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width:'100%', height:'auto', display:'block' }}>
      {/* 축 */}
      <line x1={padL} y1={H - 24} x2={padL + plotW} y2={H - 24} stroke="var(--border)" strokeWidth={1} />
      {ticks.map((t, i) => (
        <text key={i} x={x(t)} y={H - 8} fontSize={10} fill="var(--text-muted)" textAnchor="middle">{t}</text>
      ))}

      {/* 합격 커트라인 */}
      {passScore > 0 && (
        <>
          <line x1={x(passScore)} y1={16} x2={x(passScore)} y2={H - 24} stroke="var(--danger)" strokeWidth={1.5} strokeDasharray="4 3" opacity={0.6} />
          <text x={x(passScore)} y={12} fontSize={10} fill="var(--danger)" textAnchor="middle">커트라인 {passScore}</text>
        </>
      )}

      {/* 위스커 */}
      <line x1={x(stats.min)} y1={boxMid} x2={x(stats.q1)} y2={boxMid} stroke="var(--text-muted)" strokeWidth={2} />
      <line x1={x(stats.q3)} y1={boxMid} x2={x(stats.max)} y2={boxMid} stroke="var(--text-muted)" strokeWidth={2} />
      <line x1={x(stats.min)} y1={boxTop + 8} x2={x(stats.min)} y2={boxBottom - 8} stroke="var(--text-muted)" strokeWidth={2} />
      <line x1={x(stats.max)} y1={boxTop + 8} x2={x(stats.max)} y2={boxBottom - 8} stroke="var(--text-muted)" strokeWidth={2} />
      <text x={x(stats.min)} y={boxBottom + 20} fontSize={10} fill="var(--text-muted)" textAnchor="middle">
        {stats.min === stats.max ? `최저·최고 ${stats.min}` : `최저 ${stats.min}`}
      </text>
      {stats.min !== stats.max && (
        <text x={x(stats.max)} y={boxBottom + 20} fontSize={10} fill="var(--text-muted)" textAnchor="middle">최고 {stats.max}</text>
      )}

      {/* 박스 (Q1~Q3) + 중앙값 */}
      <rect x={x(stats.q1)} y={boxTop} width={Math.max(1, x(stats.q3) - x(stats.q1))} height={boxBottom - boxTop}
        fill="var(--accent)" fillOpacity={0.15} stroke="var(--accent)" strokeWidth={2} rx={3} />
      <line x1={x(stats.median)} y1={boxTop} x2={x(stats.median)} y2={boxBottom} stroke="var(--accent-dark)" strokeWidth={2.5} />
      <text x={x(stats.median)} y={boxTop - 8} fontSize={11} fontWeight={700} fill="var(--accent-dark)" textAnchor="middle">중앙값 {stats.median}</text>

      {/* 개별 응시자 점 (지터) */}
      {takers.map((t, i) => (
        <circle key={i} cx={x(t.score)} cy={boxMid + jitterFor(i)} r={5} fill="var(--accent)" stroke="var(--card)" strokeWidth={2}>
          <title>{t.name}: {t.score}점</title>
        </circle>
      ))}
    </svg>
  )
}

function Results({ filters, onFiltersChange }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [teamFilter, setTeamFilter] = useState(() => filters?.teams ?? [])
  const [selectedExamId, setSelectedExamId] = useState(null)
  const [expandedTaker, setExpandedTaker] = useState(null)
  const [answerSheetOpen, setAnswerSheetOpen] = useState(false)
  const { toast, ToastContainer } = useToast()

  useEffect(() => {
    apiFetch('GET', '/api/admin/results-analysis')
      .then(setData)
      .catch(e => setError(e.message))
  }, [])

  useEffect(() => { setTeamFilter(filters?.teams ?? []) }, [filters?.teams?.join(',')])

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

  const rankedTakers = selectedExam ? rankTakers(selectedExam.takers) : []
  const scoreStats = selectedExam ? computeBoxStats(selectedExam.takers.map(t => t.score)) : null

  function toggleTeamFilter(teamCode) {
    setTeamFilter(prev => {
      const next = prev.includes(teamCode) ? prev.filter(t => t !== teamCode) : [...prev, teamCode]
      onFiltersChange?.({ team: next })
      return next
    })
  }

  function openExam(examSetId) {
    setSelectedExamId(examSetId)
    setExpandedTaker(null)
    setAnswerSheetOpen(false)
  }

  function toggleTaker(i) {
    setExpandedTaker(prev => prev === i ? null : i)
    setAnswerSheetOpen(false)
  }

  return (
    <div>
      <ToastContainer />
      {selectedExam ? (
        <>
          <Card title={selectedExam.name} noPad action={<BtnOutlineSm onClick={() => setSelectedExamId(null)}>← 시험 목록으로</BtnOutlineSm>}>
            <div style={{ padding:'12px 20px', display:'flex', gap:22, fontSize:12, color:'var(--text-muted)', flexWrap:'wrap' }}>
              <span>팀 <b style={{ color:'var(--text)' }}>{selectedExam.team_name}</b></span>
              <span>응시 인원 <b style={{ color:'var(--text)' }}>{selectedExam.taker_count}명</b></span>
              <span>평균 점수 <b style={{ color:'var(--text)' }}>{selectedExam.avg_score}점</b></span>
              <span>중앙값 <b style={{ color:'var(--text)' }}>{scoreStats.median}점</b></span>
              <span>정답률 <b style={{ color:'var(--text)' }}>{selectedExam.accuracy_pct}%</b></span>
              <span>합격자 <b style={{ color:'var(--text)' }}>{selectedExam.pass_count}명</b></span>
            </div>
          </Card>

          <Card title="점수 분포">
            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(110px, 1fr))', gap:12, marginBottom:22 }}>
              <StatTile label="평균" value={`${scoreStats.avg}점`} />
              <StatTile label="중앙값" value={`${scoreStats.median}점`} />
              <StatTile label="최고점" value={`${scoreStats.max}점`} accent="var(--success)" />
              <StatTile label="최저점" value={`${scoreStats.min}점`} accent="var(--danger)" />
              <StatTile label="합격률" value={`${selectedExam.taker_count ? Math.round(selectedExam.pass_count / selectedExam.taker_count * 100) : 0}%`} />
            </div>
            <ScoreBoxPlot takers={selectedExam.takers} stats={scoreStats} passScore={selectedExam.pass_score} />
          </Card>

          <Card
            title={`응시자 목록 (${rankedTakers.length}명)`}
            noPad
            action={
              <div style={{ display:'flex', gap:8 }}>
                <BtnOutlineSm onClick={() => exportTakersCsv(selectedExam.name, rankedTakers)}>CSV 저장</BtnOutlineSm>
                <BtnOutlineSm onClick={() => exportTakersExcel(selectedExam.name, rankedTakers)}>Excel 저장</BtnOutlineSm>
                <BtnOutlineSm onClick={() => exportTakersPdf(selectedExam, rankedTakers, toast)}>PDF 저장</BtnOutlineSm>
              </div>
            }
          >
            <DataTable headers={['등수','이름','점수','결과','응시일','']}>
              {rankedTakers.map((t, i) => (
                <Fragment key={i}>
                  <tr style={{ cursor:'pointer' }} onClick={() => toggleTaker(i)}>
                    <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontWeight:700, color:'var(--text-muted)', fontVariantNumeric:'tabular-nums' }}>{t.rank}</td>
                    <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontWeight:500 }}>{t.name}</td>
                    <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontWeight:700, fontVariantNumeric:'tabular-nums' }}>{t.score}점</td>
                    <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)' }}><Badge type={t.pass ? 'success' : 'danger'}>{t.pass ? '합격' : '재교육'}</Badge></td>
                    <td style={{ fontSize:12, padding:'11px 18px', borderBottom:'1px solid var(--border)', color:'var(--text-muted)', fontVariantNumeric:'tabular-nums' }}>{t.date}</td>
                    <td style={{ fontSize:12, padding:'11px 18px', borderBottom:'1px solid var(--border)', color:'var(--accent)', whiteSpace:'nowrap' }}>{expandedTaker === i ? '접기 ▲' : '상세 ▼'}</td>
                  </tr>
                  {expandedTaker === i && (
                    <tr>
                      <td colSpan={6} style={{ padding:'12px 18px 18px', borderBottom:'1px solid var(--border)', background:'#FAFAFA' }}>
                        <div style={{ fontSize:11, fontWeight:700, color:'var(--text-muted)', marginBottom:8 }}>문제 영역별 정답 수</div>
                        <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:14 }}>
                          {categoryBreakdown(t.results).length === 0 ? (
                            <span style={{ fontSize:12, color:'var(--text-muted)' }}>영역별 데이터가 없습니다.</span>
                          ) : categoryBreakdown(t.results).map(c => (
                            <span key={c.cat} style={{ fontSize:12, padding:'5px 10px', borderRadius:20, background:'white', border:'1px solid var(--border)', color:'var(--text)' }}>
                              {c.cat} <b style={{ color: c.correct === c.total ? 'var(--success)' : 'var(--text)' }}>{c.correct}</b>/{c.total}
                            </span>
                          ))}
                        </div>

                        <BtnOutlineSm onClick={() => setAnswerSheetOpen(o => !o)}>
                          {answerSheetOpen ? '정오표 닫기 ▲' : '정오표 보기 ▼'}
                        </BtnOutlineSm>

                        {answerSheetOpen && (
                          t.results.length === 0 ? (
                            <p style={{ fontSize:12, color:'var(--text-muted)', marginTop:10 }}>문항별 상세 데이터가 없습니다.</p>
                          ) : (
                            <table style={{ width:'100%', borderCollapse:'collapse', marginTop:10 }}>
                              <thead>
                                <tr>{['문항','난이도','정답','응답','정오'].map(h => (
                                  <th key={h} style={{ textAlign:'left', fontSize:11, fontWeight:700, color:'var(--text-muted)', padding:'6px 8px', borderBottom:'1px solid var(--border)' }}>{h}</th>
                                ))}</tr>
                              </thead>
                              <tbody>
                                {t.results.map((q, qi) => (
                                  <tr key={qi}>
                                    <td style={{ fontSize:12, padding:'6px 8px', maxWidth:340 }} title={q.question || ''}>
                                      <div style={{ overflow:'hidden', whiteSpace:'nowrap', textOverflow:'ellipsis', maxWidth:340 }}>{q.question || q.q_id}</div>
                                    </td>
                                    <td style={{ fontSize:12, padding:'6px 8px' }}>{q.difficulty || '-'}</td>
                                    <td style={{ fontSize:12, padding:'6px 8px', fontWeight:700 }}>{q.answer || '-'}</td>
                                    <td style={{ fontSize:12, padding:'6px 8px', fontWeight:700 }}>{q.user_answer || '-'}</td>
                                    <td style={{ fontSize:13, padding:'6px 8px', fontWeight:800, color: q.correct ? 'var(--success)' : 'var(--danger)' }}>{q.correct ? 'O' : 'X'}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </DataTable>
          </Card>
        </>
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

      {!selectedExam && data.insights.length > 0 && (
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

function MaterialsPanel({ toast }) {
  const [teams, setTeams] = useState([])
  const [team, setTeam] = useState('')
  const [materials, setMaterials] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    apiFetch('GET', '/api/admin/teams').then(data => setTeams(data.teams || [])).catch(() => {})
  }, [])

  async function load() {
    setLoading(true)
    try {
      const query = team ? `?team_code=${encodeURIComponent(team)}` : ''
      const data = await apiFetch('GET', `/api/admin/materials/list${query}`)
      setMaterials(data)
    } catch (error) {
      toast?.(`자료 상태 조회 실패: ${error.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [team])

  async function scan() {
    if (!team) return
    setLoading(true)
    try {
      await apiFetch('POST', '/api/admin/materials/scan', { team_code: team })
      toast?.('교육자료 스캔이 완료됐습니다.')
      await load()
    } catch (error) {
      toast?.(`스캔 실패: ${error.message}`, 'error')
      setLoading(false)
    }
  }

  const teamOptions = teams.length ? teams : [
    { team_code:'T1', team_name:'1팀' },
    { team_code:'T2', team_name:'2팀' },
    { team_code:'T3', team_name:'3팀' },
  ]
  const categories = materials ? Object.values(materials.categories || {}) : []
  const connectedFiles = categories.flatMap(category =>
    (category.files || []).map(file => ({ ...file, categoryLabel: category.label, scannedAt: category.scanned_at })))
  const hasNewAny = categories.some(category => category.has_new)
  const newFiles = connectedFiles.filter(file => file.status === 'new')

  const statusBadge = status => {
    if (status === 'new') return <Badge type="warning">신규 반영 대기</Badge>
    if (status === 'failed') return <Badge type="danger">추출 실패</Badge>
    return <Badge type="success">연동됨</Badge>
  }

  return (
    <Card title="자료 · 연동" noPad action={
      <div style={{ display:'flex', gap:8 }}>
        <FilterSelect value={team} onChange={setTeam}>
          <option value="">전체</option>
          {teamOptions.map(item => <option key={item.team_code} value={item.team_code}>{item.team_name}</option>)}
        </FilterSelect>
        <BtnOutlineSm onClick={load} disabled={loading}>새로고침</BtnOutlineSm>
      </div>
    }>
      <div style={{ padding:20 }}>
        {team && (
          <div style={{ padding:16, border:'1px solid var(--border)', borderRadius:8, background:'var(--bg)', marginBottom:14 }}>
            <div style={{ fontSize:13, fontWeight:700, color:'var(--text)', marginBottom:6 }}>교육자료 상태</div>
            <div style={{ fontSize:12, color:'var(--text-muted)' }}>
              {loading && !materials ? '확인 중...' : hasNewAny ? `새 자료 ${newFiles.length}개가 있습니다.` : '새로 반영할 교육자료가 없습니다.'}
            </div>
            {newFiles.length > 0 && <div style={{ marginTop:8, fontSize:12, color:'var(--text)' }}>{newFiles.map(file => file.name).join(', ')}</div>}
            <div style={{ marginTop:12 }}>
              <BtnPrimary onClick={scan} disabled={loading}>{loading ? '처리 중...' : '새 자료 스캔'}</BtnPrimary>
            </div>
          </div>
        )}
        <div style={{ fontSize:13, fontWeight:700, color:'var(--text)', marginBottom:10 }}>
          연결된 교육자료 ({connectedFiles.length}개{newFiles.length > 0 ? ` · 신규 ${newFiles.length}개` : ''})
        </div>
      </div>
      <DataTable headers={['자료명', '구분', '형식', '스캔 일시', '상태']}>
        {connectedFiles.length === 0 ? (
          <tr><td colSpan={5} style={{ textAlign:'center', color:'var(--text-muted)', padding:20, fontSize:13 }}>연결된 교육자료가 없습니다.</td></tr>
        ) : connectedFiles.map(file => (
          <tr key={`${file.categoryLabel}-${file.id || file.name}`}>
            <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)' }}>{file.name}</td>
            <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)' }}>{file.categoryLabel}</td>
            <td style={{ fontSize:12, padding:'11px 18px', borderBottom:'1px solid var(--border)', color:'var(--text-muted)' }}>{file.mimeType.includes('pdf') ? 'PDF' : file.mimeType.includes('presentation') ? 'PPTX' : '-'}</td>
            <td style={{ fontSize:12, padding:'11px 18px', borderBottom:'1px solid var(--border)', color:'var(--text-muted)', fontVariantNumeric:'tabular-nums' }}>{file.status === 'new' ? '미반영' : (file.scannedAt ? new Date(file.scannedAt).toLocaleString('ko-KR') : '-')}</td>
            <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)' }}>{statusBadge(file.status)}</td>
          </tr>
        ))}
      </DataTable>
    </Card>
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

  const { aiProvider, aiProviderLabel, claudeConfigured } = deriveSystemInfo(systemStatus)

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

  const todos = []

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
      <Card title="남은 구현 항목 (TODO)" noPad>
        {todos.length === 0 && (
          <div style={{ padding:'20px', fontSize:13, color:'var(--text-muted)', textAlign:'center' }}>현재 파악된 미구현 항목이 없습니다.</div>
        )}
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
function ExamAssign({ toast, selectedExamId, onSelectExam }) {
  const [sets, setSets] = useState([])
  const [users, setUsers] = useState([])
  const [papers, setPapers] = useState([])
  const viewedSetId = selectedExamId || ''
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
  const assigneeRequestSequence = useRef(0)

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
      onSelectExam(created.exam_id)
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
    finally { setCreating(false) }
  }

  async function loadAssignees(setId) {
    const requestSequence = ++assigneeRequestSequence.current
    if (!setId) {
      if (requestSequence === assigneeRequestSequence.current) setAssignees([])
      return
    }
    try {
      const d = await apiFetch('GET', `/api/admin/exam-sets/${setId}/assignees`)
      if (requestSequence === assigneeRequestSequence.current) setAssignees(d.assignees || [])
    } catch {
      if (requestSequence === assigneeRequestSequence.current) setAssignees([])
    }
  }

  useEffect(() => { setListPage(1) }, [listStatusFilter])

  function openSet(setId) {
    onSelectExam(setId)
  }

  useEffect(() => {
    setAssignError('')
    setUserQuery('')
    setSelectedUser('')
    if (viewedSetId) loadAssignees(viewedSetId)
    else setAssignees([])
    return () => { assigneeRequestSequence.current += 1 }
  }, [viewedSetId])

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
      if (viewedSetId === setId) onSelectExam(null)
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
  'exam-sheet':   { bc:['홈','시험 관리','시험지 생성·관리'],      title:'시험지 생성·관리' },
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

function initialAdminView(initialView) {
  if (ADMIN_VIEWS.includes(initialView)) return initialView
  const saved = sessionStorage.getItem(ADMIN_VIEW_KEY)
  return ADMIN_VIEWS.includes(saved) ? saved : 'dashboard'
}

function adminMetaForPath(pathname, fallback) {
  const exact = ADMIN_ROUTE_META[pathname]
  if (exact) return { title: exact.title, bc: exact.breadcrumbs }
  if (/^\/admin\/questions\/generate\/runs\/[^/]+$/.test(pathname)) return { title:'생성 결과', bc:['홈','문제 관리','생성 작업','생성 결과'] }
  if (/^\/admin\/questions\/[^/]+\/history$/.test(pathname)) return { title:'변경 이력', bc:['홈','문제 관리','문제은행','변경 이력'] }
  if (/^\/admin\/questions\/[^/]+$/.test(pathname)) return { title:'문제 상세', bc:['홈','문제 관리','문제은행','문제 상세'] }
  if (/^\/admin\/results\/[^/]+$/.test(pathname)) return { title:'결과 상세', bc:['홈','결과 관리','응시 결과','결과 상세'] }
  if (/^\/admin\/exams\/[^/]+\/live$/.test(pathname)) return { title:'시험별 응시 현황', bc:['홈','시험 관리','응시 현황','시험별 상세'] }
  return fallback
}

function liveExamIdFromPathname(pathname) {
  const match = pathname.match(/^\/admin\/exams\/([^/]+)\/live$/)
  if (!match) return null
  try { return decodeURIComponent(match[1]) } catch { return match[1] }
}

export function examIdFromPathname(pathname) {
  const match = pathname.match(/^\/admin\/exams\/([^/]+)$/)
  if (!match) return null
  try {
    return decodeURIComponent(match[1])
  } catch {
    return match[1]
  }
}

export default function Admin({ initialView, onRouteNavigate }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [view, setView] = useState(() => initialAdminView(initialView))
  const [examAssignFocusId, setExamAssignFocusId] = useState(() => examIdFromPathname(location.pathname))
  const { toast, ToastContainer } = useToast()

  useEffect(() => {
    if (!ADMIN_VIEWS.includes(initialView)) return
    setView(initialView)
    setExamAssignFocusId(examIdFromPathname(location.pathname))
  }, [initialView, location.pathname])

  const meta = adminMetaForPath(location.pathname, NAV_META[view] || NAV_META.dashboard)

  function goView(v, opts) {
    if (onRouteNavigate) {
      onRouteNavigate(v, opts)
      return
    }
    setView(v)
    sessionStorage.setItem(ADMIN_VIEW_KEY, v)
    if (opts?.focusExamId) setExamAssignFocusId(opts.focusExamId)
  }

  return (
    <>
      <ToastContainer />
      <AdminLayout title={meta.title} breadcrumbs={meta.bc} onLogout={() => apiLogout(navigate)}>
        {view === 'dashboard'   && <Dashboard onNavigate={goView} />}
        {Q_VIEWS.includes(view) && <QuestionRoutePage
          GenerateComponent={PlannedQuestionGeneration}
          ReviewComponent={PlannedQuestionReview}
          BankComponent={PlannedQuestionBank}
          RunsComponent={PlannedGenerationRuns}
          toast={toast}
          onNavigate={goView}
        />}
        {view === 'exam-sheet'  && (
          <ExamPaperPage renderSetup={({ sourceExamId, onSaved }) => (
            <ExamSheet toast={toast} onNavigate={goView} sourceExamId={sourceExamId} onSaved={onSaved} />
          )} />
        )}
        {view === 'exam-assign' && (
          <ExamManagementPage renderManagement={({ selectedExamId, onSelectExam }) => (
            <ExamAssign toast={toast} selectedExamId={selectedExamId} onSelectExam={onSelectExam} />
          )} />
        )}
        {view === 'exam-status' && (liveExamIdFromPathname(location.pathname) ? (
          <ExamLiveDetailPage
            examId={liveExamIdFromPathname(location.pathname)}
            CardComponent={Card}
            BadgeComponent={Badge}
            TableComponent={DataTable}
          />
        ) : (
          <ExamLivePage CardComponent={Card} BadgeComponent={Badge} />
        ))}
        {(view === 'history' || view === 'results') && <ResultRoutePage
          HistoryComponent={History}
          AnalyticsComponent={Results}
          toast={toast}
        />}
        {(view === 'users' || view === 'settings' || view === 'teams') && <SystemRoutePage
          UsersComponent={Users}
          TeamsComponent={TeamsManager}
          MaterialsComponent={MaterialsPanel}
          StatusComponent={Settings}
          AuditLogComponent={PlannedAuditLog}
          toast={toast}
        />}
      </AdminLayout>
    </>
  )
}
