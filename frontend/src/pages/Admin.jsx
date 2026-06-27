import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch, logout as apiLogout } from '../api'

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

function Card({ title, action, children, noPad }) {
  return (
    <div style={{ background:'var(--card)', borderRadius:'var(--radius)', border:'1px solid var(--border)', marginBottom:16, overflow:'hidden' }}>
      {title && (
        <div style={{ padding:'13px 20px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap', gap:8 }}>
          <span style={{ fontSize:14, fontWeight:700, color:'var(--text)' }}>{title}</span>
          {action}
        </div>
      )}
      <div style={noPad ? {} : { padding:'20px' }}>{children}</div>
    </div>
  )
}

function StatCard({ iconName, iconColor, iconBg, label, value, unit }) {
  return (
    <div style={{ background:'var(--card)', borderRadius:'var(--radius)', border:'1px solid var(--border)', padding:20, display:'flex', alignItems:'flex-start', gap:14 }}>
      <div style={{ width:44, height:44, borderRadius:10, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0, background:iconBg }}>
        <Icon name={iconName} size={19} style={{ color:iconColor }} />
      </div>
      <div>
        <div style={{ fontSize:11, color:'var(--text-muted)', marginBottom:4, fontWeight:500 }}>{label}</div>
        <div style={{ fontSize:28, fontWeight:800, color:'var(--text)', lineHeight:1, fontVariantNumeric:'tabular-nums' }}>
          {value}<span style={{ fontSize:13, fontWeight:500, color:'var(--text-muted)', marginLeft:2 }}>{unit}</span>
        </div>
      </div>
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

function BtnPrimary({ onClick, children, style }) {
  return (
    <button onClick={onClick}
      style={{ background:'var(--accent)', color:'white', border:'none', borderRadius:7, padding:'10px 18px', fontFamily:'var(--font)', fontSize:14, fontWeight:700, cursor:'pointer', display:'inline-flex', alignItems:'center', gap:6, ...style }}
      onMouseOver={e => e.currentTarget.style.background='var(--accent-dark)'}
      onMouseOut={e => e.currentTarget.style.background='var(--accent)'}>
      {children}
    </button>
  )
}

function BtnOutlineSm({ onClick, children, danger }) {
  return (
    <button onClick={onClick} style={{ border:`1.5px solid ${danger ? 'var(--danger)' : 'var(--accent)'}`, background:'white', color: danger ? 'var(--danger)' : 'var(--accent)', borderRadius:6, padding:'6px 13px', fontFamily:'var(--font)', fontSize:12, cursor:'pointer', fontWeight:600, whiteSpace:'nowrap', display:'inline-flex', alignItems:'center', gap:5 }}>
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

/* ── Views ──────────────────────────────────────────────────── */

function Dashboard({ onNavigate }) {
  const [approvedCount, setApprovedCount] = useState('-')
  const [examCount, setExamCount] = useState('-')
  const [apiStatus, setApiStatus] = useState('확인 중...')
  const [driveStatus, setDriveStatus] = useState('확인 중...')

  useEffect(() => {
    apiFetch('GET', '/api/admin/user-count').then(d => setApprovedCount(d.count)).catch(() => {})
    apiFetch('GET', '/api/admin/exam-count')
      .then(d => { setExamCount(d.count); setApiStatus('정상') })
      .catch(() => setApiStatus('연결 불가'))
    apiFetch('GET', '/api/drive/status')
      .then(() => setDriveStatus('연동'))
      .catch(() => setDriveStatus('미연동'))
  }, [])

  const recent = [
    { name:'홍길동', team:'T1', score:92, pass:true,  date:'2026-06-14' },
    { name:'김철수', team:'T2', score:64, pass:false, date:'2026-06-14' },
    { name:'박영희', team:'T1', score:88, pass:true,  date:'2026-06-13' },
    { name:'이민수', team:'T3', score:65, pass:false, date:'2026-06-13' },
    { name:'최지훈', team:'T2', score:95, pass:true,  date:'2026-06-12' },
  ]

  const quickActions = [
    ['file',  '시험 생성',   'exam-create'],
    ['users', '사용자 승인', 'users'],
    ['clock', '응시 이력',   'history'],
    ['book',  '문제 관리',   'questions'],
    ['chart', '결과 분석',   'results'],
  ]

  const systemRows = [
    ['운영 모드',    'Mock 모드',  'USE_MOCK_DATA=true',       'mock'],
    ['백엔드 API',   apiStatus,    'FastAPI — localhost:8000', apiStatus === '정상' ? 'live' : 'offline'],
    ['Claude API',   '미연동',     'ANTHROPIC_API_KEY 필요',   'offline'],
    ['Google Drive', driveStatus,  '서비스 계정 인증',          driveStatus === '연동' ? 'live' : 'mock'],
  ]

  return (
    <div>
      <div style={{ background:'var(--warning-light)', border:'1px solid #FDE68A', borderRadius:8, padding:'9px 16px', marginBottom:16, fontSize:12, color:'var(--warning)', display:'flex', alignItems:'center', gap:8 }}>
        <span style={{ width:6, height:6, borderRadius:'50%', background:'#F59E0B', flexShrink:0, display:'inline-block' }} />
        Mock 모드 — Claude API · Google Drive 없이 작동 중.
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:14, marginBottom:16 }}>
        <StatCard iconName="users" iconColor="#2563EB" iconBg="#EFF6FF" label="승인된 응시자" value={approvedCount} unit="명" />
        <StatCard iconName="file"  iconColor="#D97706" iconBg="#FFFBEB" label="총 응시 완료"  value={examCount}    unit="회" />
        <StatCard iconName="check" iconColor="#059669" iconBg="#ECFDF5" label="합격률"        value="60"           unit="%" />
        <StatCard iconName="star"  iconColor="#7C3AED" iconBg="#F5F3FF" label="평균 점수"     value="80.8"         unit="점" />
      </div>

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

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
        <Card title="최근 응시 이력" noPad>
          {recent.map((r, i) => (
            <div key={i} style={{ display:'flex', alignItems:'center', gap:12, padding:'11px 20px', borderBottom: i < recent.length-1 ? '1px solid var(--border)' : 'none' }}>
              <span style={{ width:7, height:7, borderRadius:'50%', flexShrink:0, background: r.pass ? 'var(--success)' : 'var(--danger)' }} />
              <span style={{ flex:1, fontSize:13, color:'var(--text)', fontWeight:500 }}>{r.name}</span>
              <span style={{ fontSize:11, color:'var(--text-muted)' }}>{r.team}</span>
              <span style={{ fontSize:13, fontWeight:700, fontVariantNumeric:'tabular-nums', width:36, textAlign:'right' }}>{r.score}점</span>
              <Badge type={r.pass ? 'success' : 'danger'}>{r.pass ? '합격' : '재교육'}</Badge>
              <span style={{ fontSize:11, color:'var(--text-light)', width:72, textAlign:'right', fontVariantNumeric:'tabular-nums' }}>{r.date}</span>
            </div>
          ))}
        </Card>

        <Card title="시스템 상태" noPad>
          {systemRows.map(([label, val, desc, mode]) => (
            <div key={label} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'11px 20px', borderBottom:'1px solid var(--border)' }}>
              <div>
                <div style={{ fontSize:13, fontWeight:600, color:'var(--text)' }}>{label}</div>
                <div style={{ fontSize:11, color:'var(--text-muted)', marginTop:2 }}>{desc}</div>
              </div>
              <div style={{ display:'flex', alignItems:'center', gap:6, fontSize:12, fontWeight:700,
                color: mode === 'live' ? 'var(--success)' : mode === 'mock' ? 'var(--warning)' : 'var(--text-light)' }}>
                <StatusDot mode={mode} />{val}
              </div>
            </div>
          ))}
        </Card>
      </div>
    </div>
  )
}

function ExamCreate({ toast }) {
  const [team, setTeam] = useState('T1')
  const [diff, setDiff] = useState('중급')
  const [count, setCount] = useState('25문항')
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)

  async function generate() {
    setLoading(true)
    try {
      const data = await apiFetch('POST', '/api/admin/preview-exam', { team_code: team })
      setPreview(data.questions)
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
    finally { setLoading(false) }
  }

  function handlePdf() {
    if (!preview || preview.length === 0) { toast('먼저 문제를 생성해주세요.', 'error'); return }
    const teamLabel = { T1:'1팀 (주간)', T2:'2팀 (4조3교대)', T3:'3팀 (3조2교대)' }[team] || team
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
<title>OJT 시험지 — (주)엑스티</title>
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
  <h1>(주)엑스티 OJT 기초고사</h1>
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

  const teamOpts = [['T1','1팀 (주간)'],['T2','2팀 (4조3교대)'],['T3','3팀 (3조2교대)']]
  const diffOpts = ['초급','중급','고급']
  const countOpts = ['10문항','20문항','25문항']

  return (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
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
        <BtnPrimary onClick={generate} style={{ width:'100%', justifyContent:'center', marginBottom:10 }}>
          <Icon name="plus" size={14} style={{ color:'white' }} />
          {loading ? '생성 중...' : 'AI 문제 생성'}
        </BtnPrimary>
        <div style={{ fontSize:11, color:'var(--warning)', background:'var(--warning-light)', border:'1px solid #FDE68A', borderRadius:6, padding:'7px 10px' }}>
          AI 생성 문제는 반드시 검토 후 사용해주세요. (현재 Mock 모드)
        </div>
      </Card>

      <Card title="AI 생성 결과 (미리보기)" action={<span style={{ fontSize:11, fontWeight:700, color:'var(--success)', background:'var(--success-light)', padding:'3px 8px', borderRadius:20 }}>{preview ? `${preview.length}문항 생성됨` : '—'}</span>}>
        {!preview ? (
          <p style={{ color:'var(--text-muted)', fontSize:13, textAlign:'center', padding:'24px 0' }}>팀을 선택하고 'AI 문제 생성'을 눌러주세요.</p>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
            {preview.slice(0,6).map((q, i) => (
              <div key={i} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'9px 12px', border:'1px solid var(--border)', borderRadius:7 }}>
                <div>
                  <div style={{ fontSize:11, color:'var(--text-muted)' }}>문항 {i+1} · {q.category} · {q.difficulty}</div>
                  <div style={{ fontSize:12, color:'var(--text)', fontWeight:500, lineHeight:1.4, marginTop:2 }}>{q.question}</div>
                </div>
                <span style={{ fontSize:10, padding:'2px 7px', borderRadius:4, background:'var(--accent-light)', color:'var(--accent)', fontWeight:600, flexShrink:0 }}>객관식</span>
              </div>
            ))}
            {preview.length > 6 && <p style={{ textAlign:'center', fontSize:12, color:'var(--text-muted)', padding:6 }}>더보기 ({preview.length-6}문항)</p>}
          </div>
        )}
        <div style={{ height:1, background:'var(--border)', margin:'16px 0' }} />
        <div style={{ display:'flex', gap:8 }}>
          <button onClick={handlePdf} style={{ flex:1, border:'1.5px solid var(--border)', background:'white', color:'var(--text-muted)', borderRadius:7, padding:'9px 14px', fontFamily:'var(--font)', fontSize:13, cursor:'pointer' }}>PDF 생성</button>
          <button style={{ flex:1, background:'var(--accent)', color:'white', border:'none', borderRadius:7, padding:'10px 16px', fontFamily:'var(--font)', fontSize:13, fontWeight:700, cursor:'pointer' }}>시험지 저장</button>
        </div>
      </Card>
    </div>
  )
}

function ExamReview() {
  const [activeTab, setActiveTab] = useState(0)
  const [activePage, setActivePage] = useState(0)
  const tabs = ['전체 문항 (25)','검토 중 (5)','수정 요청 (2)','승인 완료 (18)']
  return (
    <Card title="검토 · 수정" action={<span style={{ fontSize:12, color:'var(--text-muted)' }}>AI 생성 문제를 검토하고 수정하세요</span>}>
      <div style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:8, padding:'12px 14px', marginBottom:14 }}>
        <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:6 }}>
          <span style={{ fontSize:11, color:'var(--text-muted)' }}>현재 상태</span>
          <Badge type="warning">검토중</Badge>
        </div>
        <div style={{ display:'flex', gap:16 }}>
          {[['시험명','OJT 기초고사 2026-06'],['문항 수','25문항'],['생성일','2026.06.01']].map(([k,v]) => (
            <div key={k}><div style={{ fontSize:10, color:'var(--text-light)', marginBottom:2 }}>{k}</div><div style={{ fontSize:12, fontWeight:600, color:'var(--text)' }}>{v}</div></div>
          ))}
        </div>
      </div>
      <div style={{ display:'flex', borderBottom:'1px solid var(--border)', marginBottom:12 }}>
        {tabs.map((t, i) => (
          <button key={i} onClick={() => setActiveTab(i)} style={{ padding:'8px 12px', fontSize:12, cursor:'pointer', color: activeTab===i ? 'var(--accent)' : 'var(--text-muted)', border:'none', borderBottom: activeTab===i ? '2px solid var(--accent)' : '2px solid transparent', background:'none', fontFamily:'var(--font)', fontWeight: activeTab===i ? 700 : 500, marginBottom:-1 }}>{t}</button>
        ))}
      </div>
      <div style={{ display:'flex', gap:4, flexWrap:'wrap', marginBottom:14 }}>
        {[1,2,3,4,5].map(p => (
          <button key={p} onClick={() => setActivePage(p-1)} style={{ width:28, height:28, border:`1.5px solid ${activePage===p-1 ? 'var(--accent)' : 'var(--border)'}`, borderRadius:6, background: activePage===p-1 ? 'var(--accent)' : 'white', fontSize:12, cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', color: activePage===p-1 ? 'white' : 'var(--text-muted)', fontFamily:'var(--font)', fontWeight: activePage===p-1 ? 700 : 400 }}>{p}</button>
        ))}
      </div>
      <div style={{ border:'1px solid var(--border)', borderRadius:8, overflow:'hidden', marginBottom:14 }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'10px 14px', background:'var(--bg)', borderBottom:'1px solid var(--border)' }}>
          <span style={{ fontSize:12, fontWeight:700 }}>문항 1 (객관식 · 팀별)</span>
          <Badge type="warning">검토 중</Badge>
        </div>
        <div style={{ padding:'12px 14px' }}>
          <div style={{ fontSize:13, fontWeight:600, color:'var(--text)', marginBottom:10, lineHeight:1.5 }}>생산라인 작업 시 가장 먼저 확인해야 하는 것은?</div>
          <div style={{ display:'flex', flexDirection:'column', gap:4, marginBottom:12 }}>
            {['작업지시서','생산계획','설비상태 ✓','작업일지'].map((opt, i) => (
              <div key={i} style={{ display:'flex', alignItems:'center', gap:8, fontSize:12, color: i===2 ? 'var(--success)' : 'var(--text)', padding:'6px 10px', borderRadius:6, border:`1px solid ${i===2 ? 'var(--success)' : 'var(--border)'}`, background: i===2 ? 'var(--success-light)' : 'white', fontWeight: i===2 ? 600 : 400 }}>
                <span style={{ width:20, height:20, borderRadius:'50%', background: i===2 ? 'var(--success)' : 'var(--border)', color: i===2 ? 'white' : 'var(--text-muted)', fontSize:10, fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>{['A','B','C','D'][i]}</span>
                {opt}
              </div>
            ))}
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginBottom:10 }}>
            {[['정답','C. 설비상태'],['AI 난이도','중']].map(([k,v]) => (
              <div key={k} style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:6, padding:'8px 10px' }}>
                <div style={{ fontSize:10, fontWeight:700, color:'var(--text-muted)', marginBottom:3 }}>{k}</div>
                <div style={{ fontSize:12, color:'var(--text)', fontWeight:600 }}>{v}</div>
              </div>
            ))}
          </div>
          <div style={{ fontSize:11, fontWeight:700, color:'var(--text-muted)', marginBottom:5 }}>수정 내용 (필요 시):</div>
          <textarea rows={2} placeholder="수정 내용이 있으면 입력하세요..." style={{ width:'100%', border:'1.5px solid var(--border)', borderRadius:6, padding:'8px 10px', fontFamily:'var(--font)', fontSize:12, color:'var(--text)', resize:'vertical', minHeight:70, lineHeight:1.5, outline:'none' }} />
        </div>
        <div style={{ display:'flex', gap:6, padding:'10px 14px', borderTop:'1px solid var(--border)', background:'var(--bg)' }}>
          <button style={{ flex:1, borderRadius:6, padding:'8px', fontFamily:'var(--font)', fontSize:12, cursor:'pointer', fontWeight:600, border:'1.5px solid var(--danger)', background:'white', color:'var(--danger)' }}>수정 요청</button>
          <button style={{ flex:1, borderRadius:6, padding:'8px', fontFamily:'var(--font)', fontSize:12, cursor:'pointer', fontWeight:600, border:'1.5px solid var(--border)', background:'white', color:'var(--text-muted)' }}>임시 저장</button>
          <button style={{ flex:1, borderRadius:6, padding:'8px', fontFamily:'var(--font)', fontSize:12, cursor:'pointer', fontWeight:600, border:'none', background:'var(--accent)', color:'white' }}>승인</button>
        </div>
      </div>
      <p style={{ textAlign:'center', padding:12, fontSize:13, color:'var(--text-muted)' }}>시험 생성 후 문항이 여기에 표시됩니다. (현재 Mock 뷰)</p>
    </Card>
  )
}

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

function Questions({ toast }) {
  const [items, setItems] = useState(null)
  const [cat, setCat] = useState('')

  async function load() {
    try {
      const data = await apiFetch('GET', `/api/admin/questions${cat ? `?category=${encodeURIComponent(cat)}` : ''}`)
      setItems(data.questions)
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
  }

  async function updateDiff(qid, newDiff) {
    try {
      await apiFetch('PATCH', '/api/admin/difficulty', { question_id: qid, new_difficulty: newDiff })
      toast(`${qid} 난이도 → ${newDiff} 변경 완료`)
    } catch (e) { toast(`오류: ${e.message}`, 'error') }
  }

  return (
    <Card title="문제 관리 · 난이도 조정" noPad action={
      <div style={{ display:'flex', gap:8 }}>
        <FilterSelect value={cat} onChange={setCat}>
          <option value="">전체 카테고리</option>
          <option value="공통">공통</option><option value="팀별">팀별</option><option value="환경안전">환경안전</option><option value="일반상식">일반상식</option>
        </FilterSelect>
        <BtnOutlineSm onClick={load}>조회</BtnOutlineSm>
      </div>
    }>
      <div style={{ padding:'9px 20px', background:'var(--bg)', borderBottom:'1px solid var(--border)', fontSize:12, color:'var(--text-muted)' }}>
        난이도 드롭다운을 변경하면 즉시 서버에 반영됩니다.
      </div>
      <div style={{ padding:'14px 20px' }}>
        {!items ? (
          <p style={{ color:'var(--text-muted)', textAlign:'center', padding:'28px 0', fontSize:13 }}>조회 버튼을 눌러 문제를 불러오세요.</p>
        ) : items.length === 0 ? (
          <p style={{ color:'var(--text-muted)', textAlign:'center', padding:'28px 0', fontSize:13 }}>문제가 없습니다.</p>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
            {items.map(q => {
              const d = q.difficulty_ai || q.difficulty_init
              return (
                <div key={q.question_id} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'10px 12px', border:'1px solid var(--border)', borderRadius:7 }}>
                  <div>
                    <div style={{ fontSize:11, color:'var(--text-muted)' }}>{q.question_id} · {q.category}</div>
                    <div style={{ fontSize:12, color:'var(--text)', fontWeight:500, lineHeight:1.4, marginTop:2 }}>{q.question}</div>
                  </div>
                  <div style={{ display:'flex', alignItems:'center', gap:8, flexShrink:0 }}>
                    <Badge type="blue">{d}</Badge>
                    <select value={d} onChange={e => updateDiff(q.question_id, e.target.value)} style={{ border:'1.5px solid var(--border)', borderRadius:6, padding:'5px 8px', fontFamily:'var(--font)', fontSize:12, cursor:'pointer', background:'white', outline:'none' }}>
                      <option value="하">하</option><option value="중">중</option><option value="상">상</option>
                    </select>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </Card>
  )
}

function Users({ toast }) {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState({ empno:'', name:'', team:'T1', date:'' })
  const [result, setResult] = useState({ msg:'', ok:null })

  async function loadUsers() {
    try { const d = await apiFetch('GET', '/api/admin/users'); setUsers(d.users) } catch {}
  }
  useEffect(() => { loadUsers() }, [])

  async function approve() {
    if (!form.empno || !form.name || !form.date) { setResult({ msg:'모든 항목을 입력해주세요.', ok:false }); return }
    try {
      await apiFetch('POST', '/api/admin/approve-user', { employee_id:form.empno, name:form.name, team:form.team, exam_date:form.date })
      setResult({ msg:`${form.name} (${form.empno}) 승인 완료`, ok:true })
      setForm({ empno:'', name:'', team:'T1', date:'' })
      loadUsers()
    } catch (e) { setResult({ msg:`오류: ${e.message}`, ok:false }) }
  }

  async function del(id, name) {
    if (!confirm(`${name} (${id})을 삭제하시겠습니까?`)) return
    try { await apiFetch('DELETE', `/api/admin/users/${id}`); loadUsers() } catch (e) { toast(`삭제 실패: ${e.message}`, 'error') }
  }

  return (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
      <Card title="신입사원 응시 승인">
        <FormInput label="사원번호" value={form.empno} onChange={e => setForm(p=>({...p,empno:e.target.value}))} placeholder="예: 2024003" autoComplete="off" />
        <FormInput label="이름" value={form.name} onChange={e => setForm(p=>({...p,name:e.target.value}))} placeholder="홍길동" />
        <div style={{ marginBottom:14 }}>
          <label style={{ display:'block', fontSize:12, fontWeight:700, color:'var(--text)', marginBottom:6 }}>소속 팀</label>
          <select value={form.team} onChange={e => setForm(p=>({...p,team:e.target.value}))} style={{ width:'100%', border:'1.5px solid var(--border)', borderRadius:6, padding:'9px 12px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', background:'white', outline:'none' }}>
            <option value="T1">1팀 (주간)</option><option value="T2">2팀 (4조3교대)</option><option value="T3">3팀 (3조2교대)</option>
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

function Results() {
  const resultData = [
    { name:'홍길동', dept:'생산팀', score:92, pass:true,  date:'2026.06.14' },
    { name:'김철수', dept:'생산팀', score:64, pass:false, date:'2026.06.14' },
    { name:'박영희', dept:'품질팀', score:88, pass:true,  date:'2026.06.13' },
    { name:'이민수', dept:'설비팀', score:65, pass:false, date:'2026.06.13' },
    { name:'최지훈', dept:'품질팀', score:95, pass:true,  date:'2026.06.12' },
  ]
  const bars = [['생산팀',85,'var(--accent)'],['품질팀',91,'var(--success)'],['설비팀',76,'#F59E0B'],['인사팀',82,'var(--purple)']]

  return (
    <div>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:14, marginBottom:16 }}>
        <StatCard iconName="user"  iconColor="#2563EB" iconBg="#EFF6FF" label="응시 인원" value="18"   unit="명" />
        <StatCard iconName="star"  iconColor="#D97706" iconBg="#FFFBEB" label="평균 점수" value="84.6" unit="점" />
        <StatCard iconName="check" iconColor="#059669" iconBg="#ECFDF5" label="정답률"    value="77.8" unit="%" />
        <StatCard iconName="chart" iconColor="#7C3AED" iconBg="#F5F3FF" label="합격자"    value="14"   unit="명" />
      </div>

      <Card title="응시자 결과 목록" noPad>
        <div style={{ padding:'10px 20px', borderBottom:'1px solid var(--border)' }}>
          <input placeholder="이름 검색" style={{ border:'1.5px solid var(--border)', borderRadius:6, padding:'7px 10px', fontFamily:'var(--font)', fontSize:13, color:'var(--text)', background:'white', maxWidth:220, width:'100%', outline:'none' }} />
        </div>
        <DataTable headers={['이름','부서','점수','결과','응시일']}>
          {resultData.map((r, i) => (
            <tr key={i}>
              <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontWeight:500 }}>{r.name}</td>
              <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)' }}>{r.dept}</td>
              <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)', fontWeight:700, fontVariantNumeric:'tabular-nums' }}>{r.score}점</td>
              <td style={{ fontSize:13, padding:'11px 18px', borderBottom:'1px solid var(--border)' }}><Badge type={r.pass ? 'success' : 'danger'}>{r.pass ? '합격' : '재교육'}</Badge></td>
              <td style={{ fontSize:12, padding:'11px 18px', borderBottom:'1px solid var(--border)', color:'var(--text-muted)', fontVariantNumeric:'tabular-nums' }}>{r.date}</td>
            </tr>
          ))}
        </DataTable>
      </Card>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14, marginBottom:16 }}>
        <div style={{ border:'1px solid var(--border)', borderRadius:8, padding:20, background:'var(--card)' }}>
          <div style={{ fontSize:11, fontWeight:700, color:'var(--text-muted)', marginBottom:14, textTransform:'uppercase', letterSpacing:'0.04em' }}>부서별 평균 점수</div>
          {bars.map(([label, pct, color]) => (
            <div key={label} style={{ display:'flex', alignItems:'center', gap:10, marginBottom:10 }}>
              <span style={{ fontSize:11, color:'var(--text-muted)', width:36, textAlign:'right', flexShrink:0 }}>{label}</span>
              <div style={{ flex:1, height:6, background:'var(--border)', borderRadius:3, overflow:'hidden' }}>
                <div style={{ height:'100%', borderRadius:3, background:color, width:`${pct}%` }} />
              </div>
              <span style={{ fontSize:11, fontWeight:700, color:'var(--text)', width:26, fontVariantNumeric:'tabular-nums' }}>{pct}</span>
            </div>
          ))}
        </div>
        <div style={{ border:'1px solid var(--border)', borderRadius:8, padding:20, background:'var(--card)' }}>
          <div style={{ fontSize:11, fontWeight:700, color:'var(--text-muted)', marginBottom:14, textTransform:'uppercase', letterSpacing:'0.04em' }}>문항 유형별 정답률</div>
          <div style={{ display:'flex', alignItems:'center', gap:16 }}>
            <svg width={80} height={80} viewBox="0 0 72 72">
              <circle cx="36" cy="36" r="26" fill="none" stroke="var(--border)" strokeWidth="10"/>
              <circle cx="36" cy="36" r="26" fill="none" stroke="#3b82f6" strokeWidth="10" strokeDasharray="138.9 163.4" strokeDashoffset="0" transform="rotate(-90 36 36)"/>
              <circle cx="36" cy="36" r="26" fill="none" stroke="#f59e0b" strokeWidth="10" strokeDasharray="111.1 163.4" strokeDashoffset="-138.9" transform="rotate(-90 36 36)"/>
              <circle cx="36" cy="36" r="26" fill="none" stroke="#10b981" strokeWidth="10" strokeDasharray="147.1 163.4" strokeDashoffset="-250" transform="rotate(-90 36 36)"/>
              <text x="36" y="33" textAnchor="middle" fontSize="9" fontWeight="700" fill="var(--text-muted)">평균</text>
              <text x="36" y="44" textAnchor="middle" fontSize="11" fontWeight="800" fill="var(--text)">81%</text>
            </svg>
            <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
              {[['#3b82f6','객관식','85%'],['#f59e0b','주관식','68%'],['#10b981','OX문제','90%']].map(([c,l,v]) => (
                <div key={l} style={{ display:'flex', alignItems:'center', gap:7, fontSize:12, color:'var(--text)' }}>
                  <span style={{ width:8, height:8, borderRadius:'50%', background:c, flexShrink:0 }} />
                  <span>{l}</span>
                  <span style={{ fontWeight:700, marginLeft:4, fontVariantNumeric:'tabular-nums' }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div style={{ background:'#EFF6FF', border:'1px solid #BFDBFE', borderRadius:8, padding:16, marginBottom:14 }}>
        <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:10 }}>
          <div style={{ width:28, height:28, background:'var(--accent)', borderRadius:6, display:'flex', alignItems:'center', justifyContent:'center' }}>
            <Icon name="ai" size={14} style={{ color:'white' }} />
          </div>
          <span style={{ fontSize:13, fontWeight:700, color:'#1E3A8A' }}>AI 분석 결과</span>
        </div>
        {['설비점검 안전과정 항목의 정답률이 42%로 낮습니다.','비상상황 대응 절차 관련 문제의 정답률이 높습니다.','추가 교육 및 현장 OJT 강화가 필요합니다.'].map((t,i) => (
          <div key={i} style={{ display:'flex', gap:8, fontSize:12, color:'#1E40AF', lineHeight:1.5, marginBottom: i < 2 ? 6 : 0 }}>
            <span style={{ width:4, height:4, borderRadius:'50%', background:'var(--accent)', flexShrink:0, marginTop:6 }} />
            {t}
          </div>
        ))}
      </div>
      <button style={{ width:'100%', border:'1.5px solid var(--accent)', background:'white', color:'var(--accent)', borderRadius:8, padding:11, fontFamily:'var(--font)', fontSize:13, fontWeight:700, cursor:'pointer' }}>
        상세 분석 리포트 보기 →
      </button>
    </div>
  )
}

function Settings() {
  const [driveStatus, setDriveStatus] = useState('확인 중...')

  useEffect(() => {
    apiFetch('GET', '/api/drive/status')
      .then(() => setDriveStatus('연동'))
      .catch(() => setDriveStatus('미연동'))
  }, [])

  const groups = [
    { label:'운영 모드', rows:[
      ['데이터 소스',  'USE_MOCK_DATA 환경변수',  'Mock 모드', 'mock'],
      ['백엔드 API',   'FastAPI — localhost:8000', '실행 중',   'live'],
      ['JWT 인증',     'python-jose (구현 완료)',   '활성',      'live'],
    ]},
    { label:'외부 연동 현황', rows:[
      ['Claude API',   'ANTHROPIC_API_KEY 필요',   '미연동',    'offline'],
      ['Google Drive', '서비스 계정 인증',          driveStatus, driveStatus === '연동' ? 'live' : 'mock'],
    ]},
  ]

  const todos = [
    'Google Drive Service Account 연동',
    'Claude API 문제 생성 JSON 파싱',
    'Drive 문제은행 Excel 파싱',
    'Drive 결과로그 저장',
    '난이도 AI 자동 확정 피드백 루프',
    '결과 리포트 PDF 내보내기',
    '비밀번호 초기화 기능',
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
      <Card title="향후 구현 항목 (TODO)" noPad>
        {todos.map((t, i) => (
          <div key={i} style={{ display:'flex', alignItems:'center', gap:10, padding:'11px 20px', borderBottom: i < todos.length-1 ? '1px solid var(--border)' : 'none' }}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <rect x="1" y="1" width="12" height="12" rx="2" stroke="#CBD5E1" strokeWidth="1.5"/>
            </svg>
            <span style={{ fontSize:13, color:'var(--text-muted)' }}>{t}</span>
          </div>
        ))}
      </Card>
    </div>
  )
}

/* ── Admin Layout ───────────────────────────────────────────── */
const NAV_META = {
  dashboard:     { bc:['홈','대시보드'],              title:'관리자 대시보드' },
  'exam-create': { bc:['홈','시험 관리','시험 생성'], title:'시험 생성' },
  'exam-review': { bc:['홈','시험 관리','검토·수정'], title:'검토 · 수정' },
  history:       { bc:['홈','응시 이력'],             title:'응시 이력' },
  questions:     { bc:['홈','문제 관리'],             title:'문제 관리 · 난이도 조정' },
  users:         { bc:['홈','사용자 승인'],           title:'사용자 승인' },
  results:       { bc:['홈','결과 분석'],             title:'결과 분석' },
  settings:      { bc:['홈','설정'],                  title:'시스템 설정' },
}

export default function Admin() {
  const navigate = useNavigate()
  const [view, setView] = useState('dashboard')
  const [examSubOpen, setExamSubOpen] = useState(false)
  const { toast, ToastContainer } = useToast()

  const meta = NAV_META[view] || NAV_META.dashboard

  function goView(v) {
    setView(v)
    if (v === 'exam-create' || v === 'exam-review') setExamSubOpen(true)
  }

  const navItems = [
    { id:'dashboard', icon:'grid',     label:'대시보드' },
    { id:'exam',      icon:'file',     label:'시험 관리', sub:[{ id:'exam-create', icon:'plus',  label:'시험 생성' },{ id:'exam-review', icon:'check', label:'검토 · 수정' }] },
    { id:'history',   icon:'clock',    label:'응시 이력' },
    { id:'questions', icon:'book',     label:'문제 관리' },
    { id:'users',     icon:'users',    label:'사용자 승인' },
    { id:'results',   icon:'chart',    label:'결과 분석' },
    { id:'settings',  icon:'settings', label:'설정' },
  ]

  const SIDEBAR_W = 220
  const HEADER_H  = 56

  const isActive = id => view === id || (id === 'exam' && (view === 'exam-create' || view === 'exam-review'))

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
                  onClick={() => item.sub ? setExamSubOpen(v => !v) : goView(item.id)}
                  style={{ display:'flex', alignItems:'center', gap:9, padding:'9px 18px', color: isActive(item.id) ? 'white' : 'rgba(255,255,255,.60)', cursor:'pointer', fontSize:13, borderLeft:`2px solid ${isActive(item.id) ? 'var(--accent)' : 'transparent'}`, background: isActive(item.id) ? 'rgba(255,255,255,.10)' : 'transparent', fontWeight: isActive(item.id) ? 600 : 400 }}
                >
                  <Icon name={item.icon} size={15} style={{ opacity: isActive(item.id) ? 1 : 0.65 }} />
                  <span>{item.label}</span>
                  {item.sub && <span style={{ marginLeft:'auto', fontSize:11, color:'rgba(255,255,255,.30)', display:'inline-block', transform: examSubOpen ? 'rotate(90deg)' : 'none', transition:'transform .2s' }}>›</span>}
                </div>
                {item.sub && examSubOpen && (
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
            {view === 'dashboard'    && <Dashboard onNavigate={goView} />}
            {view === 'exam-create'  && <ExamCreate toast={toast} />}
            {view === 'exam-review'  && <ExamReview />}
            {view === 'history'      && <History toast={toast} />}
            {view === 'questions'    && <Questions toast={toast} />}
            {view === 'users'        && <Users toast={toast} />}
            {view === 'results'      && <Results />}
            {view === 'settings'     && <Settings />}
          </div>
        </main>
      </div>
    </div>
  )
}
