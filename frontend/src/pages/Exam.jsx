import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch, logout as apiLogout, apiErrorMessage } from '../api'

const LABEL = ['A','B','C','D']
const CAT_ORDER = ['공통','팀별','환경안전','일반상식']
const CAT_COLORS = { 공통:'#3b82f6', 팀별:'#f59e0b', 환경안전:'#10b981', 일반상식:'#8b5cf6' }

function catBadgeStyle(cat) {
  const map = {
    공통:    { background:'#dbeafe', color:'#1d4ed8' },
    팀별:    { background:'#fef3c7', color:'#b45309' },
    환경안전:{ background:'#d1fae5', color:'#065f46' },
    일반상식:{ background:'#ede9fe', color:'#6d28d9' },
  }
  return map[cat] || {}
}

/* ── IdentityScreen ─────────────────────────────────────────── */
function IdentityScreen({ empInfo, examName, durationMin, questionCount, error, onStart }) {
  const today = new Date()
  const dateStr = `${today.getFullYear()}년 ${today.getMonth()+1}월 ${today.getDate()}일`

  return (
    <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'var(--bg)', padding:24 }}>
      <div style={{ background:'white', borderRadius:20, boxShadow:'0 8px 40px rgba(30,58,95,0.12)', padding:'48px 40px', width:'100%', maxWidth:480, display:'flex', flexDirection:'column', alignItems:'center' }}>
        <div style={{ display:'flex', flexDirection:'column', alignItems:'center', marginBottom:32 }}>
          <img src="/icons/icon-192.png" alt="(주)엑스티" style={{ width:56, height:56, borderRadius:14, marginBottom:10 }} />
          <div style={{ fontSize:20, fontWeight:800, color:'var(--primary)' }}>(주)엑스티</div>
          <div style={{ fontSize:13, color:'var(--text-muted)', marginTop:2 }}>인재개발부 · OJT 평가 시스템</div>
        </div>

        <div style={{ fontSize:22, fontWeight:800, color:'var(--text)', letterSpacing:'-0.5px', marginBottom:6, textAlign:'center' }}>{examName}</div>
        <div style={{ fontSize:14, color:'var(--text-muted)', marginBottom:28, textAlign:'center' }}>시험 전 응시자 정보를 확인해 주세요</div>

        <div style={{ width:'100%', background:'var(--bg)', borderRadius:12, border:'1px solid var(--border)', padding:'20px 24px', marginBottom:24 }}>
          {[
            ['응시자', empInfo.name, true],
            ['사원번호', empInfo.empno, false],
            ['소속팀', empInfo.team, false],
            ['응시일', dateStr, false],
            ['시험 시간', durationMin != null ? `${durationMin}분 · ${questionCount ?? 0}문항` : '확인 중…', false],
          ].map(([label, value, isName]) => (
            <div key={label} style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'8px 0', borderBottom:'1px solid var(--border)' }}>
              <span style={{ fontSize:13, color:'var(--text-muted)', fontWeight:600 }}>{label}</span>
              <span style={{ fontSize: isName ? 18 : 14, color: isName ? 'var(--primary)' : 'var(--text)', fontWeight: isName ? 800 : 700 }}>{value}</span>
            </div>
          ))}
        </div>

        <p style={{ fontSize:14, color:'var(--text-muted)', textAlign:'center', marginBottom:20, lineHeight:1.6 }}>위 정보가 맞으면 시험을 시작해 주세요.</p>
        {error && (
          <div style={{ width:'100%', background:'var(--danger-light)', color:'var(--danger)', border:'1px solid #e7b8b8', borderRadius:10, padding:'12px 14px', marginBottom:16, fontSize:13, textAlign:'center', lineHeight:1.5 }}>{error}</div>
        )}
        <button
          onClick={onStart}
          style={{ width:'100%', height:56, background:'var(--accent)', color:'white', border:'none', borderRadius:12, fontSize:17, fontWeight:700, cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', gap:8, fontFamily:'var(--font)' }}
        >
          {error ? '다시 시도' : '시험 시작하기'}
          <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </button>
        <p style={{ marginTop:16, fontSize:12, color:'var(--text-muted)', textAlign:'center' }}>정보가 다르면 인사팀에 문의하세요.</p>
      </div>
    </div>
  )
}

/* ── ExamScreen ─────────────────────────────────────────────── */
function ExamScreen({ questions, answers, currentQ, timerSeconds, onSelectAnswer, onPrev, onNext, onOpenConfirm, bookmarks, onToggleBookmark, empInfo }) {
  const q = questions[currentQ]
  const m = Math.floor(timerSeconds / 60)
  const s = timerSeconds % 60
  const timeStr = `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
  const timerColor = timerSeconds <= 300 ? 'var(--danger)' : timerSeconds <= 600 ? 'var(--warning)' : 'white'
  const answered = answers.filter(a => a !== null).length
  const isLast = currentQ === questions.length - 1

  if (!q) return null

  return (
    <div style={{ display:'flex', height:'100vh', overflow:'hidden', fontFamily:'var(--font)' }}>
      {/* Sidebar */}
      <aside style={{ width:280, minWidth:280, background:'var(--primary)', display:'flex', flexDirection:'column', padding:'24px 16px', gap:20, overflow:'hidden', flexShrink:0 }}>
        <div style={{ background:'rgba(255,255,255,0.07)', borderRadius:12, padding:16, textAlign:'center', border:'1px solid rgba(255,255,255,0.1)' }}>
          <div style={{ fontSize:11, color:'rgba(255,255,255,0.55)', fontWeight:600, letterSpacing:'0.8px', textTransform:'uppercase', marginBottom:6 }}>남은 시간</div>
          <div style={{ fontSize:38, fontWeight:800, color:timerColor, fontVariantNumeric:'tabular-nums', letterSpacing:2, lineHeight:1, transition:'color 0.5s' }}>{timeStr}</div>
        </div>

        <div style={{ fontSize:11, fontWeight:600, color:'rgba(255,255,255,0.45)', letterSpacing:'0.8px', textTransform:'uppercase', padding:'0 4px' }}>문항 현황</div>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(5, 1fr)', gap:5 }}>
          {questions.map((_, i) => (
            <button
              key={i}
              onClick={() => onSelectAnswer(i, null, true)}
              style={{
                position:'relative',
                aspectRatio:1, border:`1.5px solid ${i === currentQ ? 'white' : answers[i] !== null ? 'var(--accent)' : 'rgba(255,255,255,0.3)'}`,
                borderRadius:8, background: i === currentQ ? 'white' : answers[i] !== null ? 'var(--accent)' : 'transparent',
                color: i === currentQ ? 'var(--primary)' : answers[i] !== null ? 'white' : 'rgba(255,255,255,0.7)',
                fontSize:12, fontWeight: i === currentQ ? 800 : 600, cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', minHeight:44, fontFamily:'var(--font)',
              }}
            >
              {i + 1}
              {bookmarks[i] && (
                <span style={{ position:'absolute', top:0, right:0, lineHeight:1, pointerEvents:'none' }}>
                  <svg width={13} height={13} viewBox="0 0 24 24" fill="#f59e0b" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
                  </svg>
                </span>
              )}
            </button>
          ))}
        </div>

        <div style={{ marginTop:'auto', borderTop:'1px solid rgba(255,255,255,0.07)', paddingTop:14 }}>
          <div style={{ display:'flex', alignItems:'center', gap:12, padding:'8px 4px 14px' }}>
            <div style={{ width:40, height:40, background:'var(--accent)', borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', color:'white', fontSize:16, fontWeight:700, flexShrink:0 }}>
              {empInfo.name.charAt(0)}
            </div>
            <div style={{ overflow:'hidden' }}>
              <div style={{ fontSize:15, fontWeight:700, color:'rgba(255,255,255,0.88)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{empInfo.name}</div>
              <div style={{ fontSize:11, color:'rgba(255,255,255,0.35)', marginTop:2 }}>{empInfo.empno} · {empInfo.team}</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div style={{ flex:1, display:'flex', flexDirection:'column', overflow:'hidden', background:'var(--bg)' }}>
        <div style={{ flex:1, overflowY:'auto', padding:24, display:'flex', flexDirection:'column' }}>
          <div style={{ background:'white', borderRadius:12, boxShadow:'var(--shadow)', padding:'28px 32px', flex:1, display:'flex', flexDirection:'column' }}>
            <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:20, flexWrap:'wrap' }}>
              <button
                onClick={() => onToggleBookmark(currentQ)}
                title={bookmarks[currentQ] ? '책갈피 해제' : '책갈피 표시'}
                style={{ background:'none', border:'none', cursor:'pointer', padding:4, display:'flex', alignItems:'center', justifyContent:'center', borderRadius:6 }}
              >
                <svg width={22} height={22} viewBox="0 0 24 24" fill={bookmarks[currentQ] ? '#f59e0b' : 'none'} stroke={bookmarks[currentQ] ? '#f59e0b' : '#cbd5e1'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transition:'fill 0.15s, stroke 0.15s' }}>
                  <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
                </svg>
              </button>
              <span style={{ fontSize:12, fontWeight:700, padding:'4px 10px', borderRadius:20, ...catBadgeStyle(q.cat) }}>{q.cat}</span>
              <span style={{ marginLeft:'auto', fontSize:13, fontWeight:700, color:'var(--text-muted)' }}>문항 {currentQ+1} / {questions.length}</span>
            </div>
            <p style={{ fontSize:18, fontWeight:700, lineHeight:1.65, color:'var(--text)', marginBottom:24, letterSpacing:'-0.3px' }}>{q.q}</p>
            <div style={{ display:'flex', flexDirection:'column', gap:10, flex:1 }}>
              {q.opts.map((optText, oi) => (
                <button
                  key={oi}
                  onClick={() => onSelectAnswer(currentQ, oi)}
                  style={{
                    display:'flex', alignItems:'center', gap:14, padding:'0 18px', height:56, minHeight:56,
                    border:`2px solid ${answers[currentQ] === oi ? 'var(--accent)' : 'var(--border)'}`,
                    borderRadius:10, background: answers[currentQ] === oi ? 'var(--accent-light)' : 'white',
                    cursor:'pointer', fontSize:16, textAlign:'left', fontFamily:'var(--font)', color:'var(--text)',
                    transition:'border-color 0.15s, background 0.15s',
                  }}
                >
                  <span style={{
                    width:32, height:32, borderRadius:'50%',
                    background: answers[currentQ] === oi ? 'var(--accent)' : 'var(--bg)',
                    display:'flex', alignItems:'center', justifyContent:'center',
                    fontWeight:800, fontSize:13, flexShrink:0,
                    color: answers[currentQ] === oi ? 'white' : 'var(--text-muted)',
                    transition:'background 0.15s, color 0.15s',
                  }}>{LABEL[oi]}</span>
                  <span style={{ fontWeight:500, lineHeight:1.4 }}>{optText}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Footer nav */}
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'16px 24px', background:'white', borderTop:'1px solid var(--border)', gap:12 }}>
          <button
            onClick={onPrev}
            disabled={currentQ === 0}
            style={{ height:48, padding:'0 24px', borderRadius:10, fontSize:15, fontWeight:700, cursor: currentQ === 0 ? 'not-allowed' : 'pointer', border:'2px solid var(--border)', background:'white', color:'var(--text)', display:'flex', alignItems:'center', gap:6, opacity: currentQ === 0 ? 0.4 : 1, fontFamily:'var(--font)' }}
          >
            <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
            이전
          </button>

          <div style={{ display:'flex', gap:6, alignItems:'center' }}>
            {[0,1,2,3,4].map(d => (
              <div key={d} style={{ width: d === (currentQ%5) ? 20 : 8, height:8, borderRadius: d === (currentQ%5) ? 4 : '50%', background: d === (currentQ%5) ? 'var(--accent)' : 'var(--border)', transition:'all 0.3s' }} />
            ))}
          </div>

          {isLast ? (
            <button
              onClick={onOpenConfirm}
              style={{ height:48, padding:'0 24px', borderRadius:10, fontSize:15, fontWeight:700, cursor:'pointer', border:'none', background:'var(--success)', color:'white', display:'flex', alignItems:'center', gap:6, fontFamily:'var(--font)' }}
            >
              제출하기
              <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="20 6 9 17 4 12"/></svg>
            </button>
          ) : (
            <button
              onClick={onNext}
              style={{ height:48, padding:'0 24px', borderRadius:10, fontSize:15, fontWeight:700, cursor:'pointer', border:'none', background:'var(--accent)', color:'white', display:'flex', alignItems:'center', gap:6, fontFamily:'var(--font)' }}
            >
              다음
              <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

/* ── ConfirmScreen ──────────────────────────────────────────── */
function ConfirmScreen({ answers, onBack, onSubmit }) {
  const unanswered = answers.map((a,i) => a === null ? i+1 : null).filter(Boolean)
  return (
    <div style={{ position:'fixed', inset:0, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(15,23,42,0.6)', backdropFilter:'blur(4px)', zIndex:10 }}>
      <div style={{ background:'white', borderRadius:20, padding:'40px 36px', width:'90%', maxWidth:480, boxShadow:'0 20px 60px rgba(0,0,0,0.25)' }}>
        <h2 style={{ fontSize:20, fontWeight:800, color:'var(--text)', marginBottom:6, letterSpacing:'-0.4px' }}>시험을 제출하시겠습니까?</h2>
        <p style={{ fontSize:15, color:'var(--text-muted)', marginBottom:20, lineHeight:1.5 }}>
          {unanswered.length > 0 ? `총 ${answers.length}문항 중 ${unanswered.length}문항 미답변입니다.` : `총 ${answers.length}문항 모두 답변하셨습니다.`}
        </p>
        {unanswered.length > 0 && (
          <div style={{ background:'var(--warning-light)', border:'1px solid var(--warning)', borderRadius:10, padding:'12px 16px', marginBottom:16 }}>
            <p style={{ fontSize:13, fontWeight:700, color:'#b45309', marginBottom:8 }}>미답변 문항이 있습니다.</p>
            <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
              {unanswered.map(n => <span key={n} style={{ fontSize:12, fontWeight:700, padding:'3px 9px', background:'var(--warning)', color:'white', borderRadius:6 }}>{n}</span>)}
            </div>
          </div>
        )}
        <div style={{ fontSize:13, color:'var(--text-muted)', marginBottom:24, padding:'10px 14px', background:'var(--bg)', borderRadius:8, lineHeight:1.5 }}>제출 후에는 수정이 불가합니다.</div>
        <div style={{ display:'flex', gap:12 }}>
          <button onClick={onBack} style={{ flex:1, height:56, fontSize:16, fontWeight:700, cursor:'pointer', border:'2px solid var(--border)', background:'white', color:'var(--text)', borderRadius:10, fontFamily:'var(--font)' }}>계속 풀기</button>
          <button onClick={onSubmit} style={{ flex:1, height:56, fontSize:16, fontWeight:700, cursor:'pointer', border:'none', background:'var(--success)', color:'white', borderRadius:10, display:'flex', alignItems:'center', justifyContent:'center', gap:6, fontFamily:'var(--font)' }}>
            제출하기
            <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="20 6 9 17 4 12"/></svg>
          </button>
        </div>
      </div>
    </div>
  )
}

/* ── ExitConfirmModal ───────────────────────────────────────── */
function ExitConfirmModal({ onLeave, onCancel }) {
  return (
    <div style={{ position:'fixed', inset:0, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(15,23,42,0.6)', backdropFilter:'blur(4px)', zIndex:30 }}>
      <div style={{ background:'white', borderRadius:20, padding:'40px 36px', width:'90%', maxWidth:400, boxShadow:'0 20px 60px rgba(0,0,0,0.25)' }}>
        <h2 style={{ fontSize:18, fontWeight:800, color:'var(--text)', marginBottom:12, letterSpacing:'-0.4px' }}>시험 진행 중</h2>
        <p style={{ fontSize:15, color:'var(--text-muted)', marginBottom:28, lineHeight:1.6 }}>
          이대로 나가실 시 시험 응시가 초기화 될 수 있습니다.
        </p>
        <div style={{ display:'flex', gap:12 }}>
          <button onClick={onLeave} style={{ flex:1, height:52, fontSize:15, fontWeight:700, cursor:'pointer', border:'2px solid var(--border)', background:'white', color:'var(--text)', borderRadius:10, fontFamily:'var(--font)' }}>나가기</button>
          <button onClick={onCancel} style={{ flex:1, height:52, fontSize:15, fontWeight:700, cursor:'pointer', border:'none', background:'var(--accent)', color:'white', borderRadius:10, fontFamily:'var(--font)' }}>취소</button>
        </div>
      </div>
    </div>
  )
}

/* ── ScoringScreen ──────────────────────────────────────────── */
function ScoringScreen({ title, sub }) {
  return (
    <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'var(--bg)' }}>
      <div style={{ textAlign:'center', padding:40 }}>
        <div style={{ fontSize:20, fontWeight:800, color:'var(--primary)', marginBottom:40 }}>(주)엑스티</div>
        <div style={{ display:'flex', justifyContent:'center', gap:8, marginBottom:32 }}>
          {[0,1,2].map(i => <span key={i} style={{ width:10, height:10, borderRadius:'50%', background:'var(--accent)', display:'inline-block', animation:`pulse 1.2s ease-in-out ${i*0.2}s infinite` }} />)}
        </div>
        <div style={{ fontSize:22, fontWeight:700, color:'var(--text)', marginBottom:8, letterSpacing:'-0.4px' }}>{title}</div>
        <div style={{ fontSize:15, color:'var(--text-muted)' }}>{sub}</div>
      </div>
    </div>
  )
}

/* ── SubmitErrorScreen ──────────────────────────────────────── */
function SubmitErrorScreen({ message, onRetry }) {
  return (
    <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'var(--bg)', padding:24 }}>
      <div style={{ background:'white', borderRadius:20, boxShadow:'0 8px 40px rgba(30,58,95,0.12)', padding:'48px 40px', width:'100%', maxWidth:440, textAlign:'center' }}>
        <div style={{ fontSize:20, fontWeight:800, color:'var(--danger)', marginBottom:12 }}>제출에 실패했습니다</div>
        <p style={{ fontSize:14, color:'var(--text-muted)', marginBottom:28, lineHeight:1.6 }}>{message || '알 수 없는 오류가 발생했습니다.'}<br/>답안은 그대로 보존되어 있으니 다시 제출해 주세요.</p>
        <button
          onClick={onRetry}
          style={{ width:'100%', height:56, background:'var(--accent)', color:'white', border:'none', borderRadius:12, fontSize:17, fontWeight:700, cursor:'pointer', fontFamily:'var(--font)' }}
        >
          다시 제출하기
        </button>
      </div>
    </div>
  )
}

/* ── ResultScreen ───────────────────────────────────────────── */
function ResultScreen({ empInfo, examName, score, pass, submitResults, onFinish }) {
  const [accordionOpen, setAccordionOpen] = useState(false)
  const [expandedRow, setExpandedRow] = useState(null)
  // 서버가 pass를 안 준 경우에만 기본 70점 기준으로 클라이언트에서 계산한다.
  // 정상 흐름에서는 회차별 합격 커트라인이 다를 수 있어 서버 판정을 그대로 써야 한다.
  if (pass === null || pass === undefined) pass = score >= 70

  // 이 화면은 제출이 실제로 성공했을 때만 렌더링된다(handleSubmit이 실패 시 submit-error
  // 화면으로 보냄) — 서버 채점 결과(문제 텍스트·정답·내 답·해설 포함)를 기준으로 표시한다.
  const hasServerResults = Array.isArray(submitResults) && submitResults.length > 0

  const catResults = { 공통:{c:0,t:0}, 팀별:{c:0,t:0}, 환경안전:{c:0,t:0}, 일반상식:{c:0,t:0} }
  if (hasServerResults) {
    submitResults.forEach(r => {
      if (!catResults[r.category]) catResults[r.category] = { c:0, t:0 }
      catResults[r.category].t++
      if (r.correct) catResults[r.category].c++
    })
  }

  return (
    <div style={{ minHeight:'100vh', display:'flex', flexDirection:'column', background:'var(--bg)', fontFamily:'var(--font)' }}>
      <div style={{ background:'var(--primary)', padding:'20px 32px', display:'flex', alignItems:'center', justifyContent:'space-between', color:'white', flexShrink:0 }}>
        <div>
          <div style={{ fontSize:16, fontWeight:800 }}>(주)엑스티</div>
          <div style={{ fontSize:13, opacity:0.65, marginTop:2 }}>{examName} · 시험 결과</div>
        </div>
        <div style={{ fontSize:13, opacity:0.7, textAlign:'right' }}>{empInfo.name} · {empInfo.empno}</div>
      </div>

      <div style={{ flex:1, padding:'24px 32px', display:'flex', flexDirection:'column', gap:20, maxWidth:800, width:'100%', margin:'0 auto' }}>
        {/* Score card */}
        <div style={{ background:'white', borderRadius:16, padding:32, boxShadow:'var(--shadow)', display:'flex', alignItems:'center', gap:32 }}>
          <div style={{ flex:1, textAlign:'center' }}>
            <div style={{ display:'inline-flex', alignItems:'center', gap:8, padding:'8px 20px', borderRadius:30, fontSize:16, fontWeight:800, marginBottom:16, background: pass ? 'var(--success-light)' : 'var(--danger-light)', color: pass ? '#065f46' : '#991b1b' }}>
              {pass ? '✅ 합격' : '❌ 재교육 필요'}
            </div>
            <div style={{ fontSize:72, fontWeight:900, lineHeight:1, letterSpacing:'-3px', marginBottom:8, color: pass ? 'var(--success)' : 'var(--danger)' }}>{score}점</div>
            <div style={{ fontSize:14, color:'var(--text-muted)' }}>합격 기준: 70점 이상</div>
          </div>
          <div style={{ flex:1, display:'flex', flexDirection:'column', gap:14 }}>
            {CAT_ORDER.map(cat => {
              const r = catResults[cat]
              const pct = r.t ? Math.round((r.c / r.t) * 100) : 0
              return (
                <div key={cat}>
                  <div style={{ display:'grid', gridTemplateColumns:'70px 1fr 48px', gap:10, alignItems:'center' }}>
                    <span style={{ fontSize:13, fontWeight:700, color:'var(--text)' }}>{cat}</span>
                    <div style={{ height:10, background:'var(--bg)', borderRadius:5, overflow:'hidden' }}>
                      <div style={{ height:'100%', borderRadius:5, background:CAT_COLORS[cat], width:`${pct}%`, transition:'width 1s' }} />
                    </div>
                    <span style={{ fontSize:12, fontWeight:700, color:'var(--text-muted)', textAlign:'right' }}>{pct}%</span>
                  </div>
                  <div style={{ display:'flex', justifyContent:'flex-end', paddingRight:48, marginTop:2 }}>
                    <span style={{ fontSize:11, color:'var(--text-muted)' }}>{r.c}/{r.t} 정답</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Accordion */}
        <div style={{ background:'white', borderRadius:12, boxShadow:'var(--shadow)', overflow:'hidden' }}>
          <button
            onClick={() => setAccordionOpen(v => !v)}
            style={{ width:'100%', padding:'18px 24px', background:'none', border:'none', fontFamily:'var(--font)', fontSize:15, fontWeight:700, color:'var(--text)', cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'space-between' }}
          >
            <span>문항별 결과 보기</span>
            <span style={{ fontSize:18, transition:'transform 0.3s', transform: accordionOpen ? 'rotate(180deg)' : 'none', color:'var(--text-muted)' }}>▾</span>
          </button>
          {accordionOpen && (
            <div style={{ maxHeight:600, overflowY:'auto' }}>
              {hasServerResults ? submitResults.map((r, i) => {
                const isOpen = expandedRow === i
                return (
                  <div key={r.q_id || i} style={{ borderTop:'1px solid var(--border)' }}>
                    <div
                      onClick={() => setExpandedRow(isOpen ? null : i)}
                      style={{ display:'flex', alignItems:'center', gap:12, padding:'12px 24px', cursor:'pointer' }}
                    >
                      <span style={{ fontSize:12, fontWeight:800, color:'var(--text-muted)', width:24, flexShrink:0 }}>{i+1}</span>
                      <span style={{ flex:1, fontSize:13, color:'var(--text)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{r.question}</span>
                      <span style={{ width:28, height:28, borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', fontSize:14, fontWeight:800, flexShrink:0, background: r.correct ? 'var(--success-light)' : 'var(--danger-light)', color: r.correct ? 'var(--success)' : 'var(--danger)' }}>{r.correct ? 'O' : 'X'}</span>
                      <span style={{ fontSize:11, color:'var(--text-muted)', width:150, textAlign:'right', flexShrink:0, whiteSpace:'nowrap' }}>내 답: {r.user_answer || '미응답'} · 정답: {r.answer}</span>
                      <span style={{ fontSize:14, color:'var(--text-muted)', flexShrink:0 }}>{isOpen ? '▴' : '▾'}</span>
                    </div>
                    {isOpen && (
                      <div style={{ padding:'0 24px 16px 60px', display:'flex', flexDirection:'column', gap:8 }}>
                        {['A','B','C','D'].map(k => r.options?.[k] && (
                          <div key={k} style={{ fontSize:12, color: k === r.answer ? 'var(--success)' : k === r.user_answer ? 'var(--danger)' : 'var(--text-muted)', fontWeight: (k === r.answer || k === r.user_answer) ? 700 : 400 }}>
                            {k}. {r.options[k]}
                            {k === r.answer && '  (정답)'}
                            {k === r.user_answer && k !== r.answer && '  (내 답)'}
                          </div>
                        ))}
                        {r.explanation && (
                          <div style={{ fontSize:12, color:'var(--text)', background:'var(--bg)', borderRadius:8, padding:'10px 12px', marginTop:4, lineHeight:1.6 }}>
                            💡 {r.explanation}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              }) : (
                <div style={{ padding:'24px', textAlign:'center', color:'var(--text-muted)', fontSize:13 }}>문항별 채점 결과를 불러오지 못했습니다.</div>
              )}
            </div>
          )}
        </div>
      </div>

      <div style={{ background:'white', borderTop:'1px solid var(--border)', padding:'20px 32px', flexShrink:0 }}>
        <div style={{ marginBottom:16 }}>
          <p style={{ fontSize:12, color:'var(--text-muted)' }}>결과가 인사팀에 자동 전송 및 저장되었습니다.</p>
        </div>
        <button onClick={onFinish} style={{ width:'100%', height:56, background:'var(--primary)', color:'white', border:'none', borderRadius:12, fontSize:16, fontWeight:700, cursor:'pointer', fontFamily:'var(--font)' }}>확인 후 로그아웃</button>
      </div>
    </div>
  )
}

/* ── Main Exam Page ─────────────────────────────────────────── */
export default function Exam() {
  const navigate = useNavigate()
  const empInfo = {
    name:  sessionStorage.getItem('name')   || '',
    empno: sessionStorage.getItem('emp_id') || '',
    team:  sessionStorage.getItem('team')   || '',
  }

  useEffect(() => {
    if (!empInfo.name || !empInfo.empno) navigate('/', { replace: true })
  }, [])

  useEffect(() => {
    if (!empInfo.empno) return
    const token = sessionStorage.getItem('token')
    fetch('/api/exam/assigned-name', { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (!data) return
        if (data.name) setExamName(data.name)
        if (data.duration_min != null) setAssignedDurationMin(data.duration_min)
        if (data.question_count != null) setAssignedQuestionCount(data.question_count)
      })
      .catch(() => {})
  }, [])

  const [screen, setScreen] = useState('identity')
  const [showAdminNotice, setShowAdminNotice] = useState(sessionStorage.getItem('role') === 'admin')
  const [showExitConfirm, setShowExitConfirm] = useState(false)
  const [questions, setQuestions] = useState([])
  const [answers, setAnswers] = useState([])
  const [bookmarks, setBookmarks] = useState([])
  const [currentQ, setCurrentQ] = useState(0)
  const [timerSeconds, setTimerSeconds] = useState(3600)
  const [resultId, setResultId] = useState(null)
  const [examName, setExamName] = useState('OJT 기초고사')
  const [assignedDurationMin, setAssignedDurationMin] = useState(null)
  const [assignedQuestionCount, setAssignedQuestionCount] = useState(null)
  const [startError, setStartError] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [score, setScore] = useState(null)
  const [pass, setPass] = useState(null)
  const [submitResults, setSubmitResults] = useState(null)
  const timerRef = useRef(null)
  const handleSubmitRef = useRef(null)
  const historyGuardPushedRef = useRef(false)

  const stopTimer = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current)
  }, [])

  const startTimer = useCallback(() => {
    timerRef.current = setInterval(() => {
      setTimerSeconds(prev => {
        if (prev <= 1) {
          stopTimer()
          handleSubmitRef.current?.()
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }, [stopTimer])

  useEffect(() => () => stopTimer(), [])

  useEffect(() => {
    if (screen !== 'exam' && screen !== 'confirm') return

    const reportExit = (reason) => {
      if (!sessionStorage.getItem('token')) return
      apiFetch('POST', '/api/exam/exit-event', { reason, result_id: resultId || '' }).catch(() => {})
    }

    const forceLogout = (reason) => {
      reportExit(reason)
      stopTimer()
      apiLogout(navigate)
    }

    const handleBeforeUnload = (e) => { e.preventDefault(); e.returnValue = '' }

    const handleKeyDown = (e) => {
      if (e.key === 'F5' || (e.ctrlKey && e.key === 'r') || (e.metaKey && e.key === 'r')) {
        e.preventDefault()
        setShowExitConfirm(true)
        return
      }
      // 개발자 도구 진입 방해 (완전 차단은 불가능 — 우회 가능한 수준의 저지선)
      const key = e.key.toLowerCase()
      if (
        e.key === 'F12' ||
        (e.ctrlKey && e.shiftKey && ['i', 'j', 'c'].includes(key)) ||
        (e.ctrlKey && key === 'u')
      ) {
        e.preventDefault()
      }
    }

    // PrintScreen은 OS가 브라우저보다 먼저 가로채는 경우가 많아 keydown이 아닌
    // keyup에서만 감지되는 환경이 있음(그마저도 100% 보장되지 않음)
    const handleKeyUp = (e) => {
      if (e.key === 'PrintScreen') forceLogout('print_screen')
    }

    const handleContextMenu = (e) => e.preventDefault()

    // 탭 전환, 홈키(화면 최소화) 등으로 페이지가 가려지면 즉시 로그아웃
    const handleVisibilityChange = () => {
      if (document.hidden) forceLogout('tab_switch')
    }

    // 뒤로가기 감지: 더미 history 항목을 쌓아 popstate로만 감지되게 하고 즉시 로그아웃
    // exam <-> confirm 전환마다 effect가 재실행되므로, 더미 항목은 세션당 한 번만 push해 history 스택 누적을 방지
    const handlePopState = () => forceLogout('back_navigation')
    if (!historyGuardPushedRef.current) {
      window.history.pushState(null, '', window.location.href)
      historyGuardPushedRef.current = true
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    window.addEventListener('contextmenu', handleContextMenu)
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('popstate', handlePopState)
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
      window.removeEventListener('contextmenu', handleContextMenu)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('popstate', handlePopState)
    }
  }, [screen, resultId])

  async function handleStart() {
    setScreen('loading')
    setStartError('')
    // empInfo.team은 로그인 응답에서 그대로 저장된 실제 team_code(T1/T2/T3)이므로
    // 별도 변환 없이 그대로 사용한다 (과거에는 '2'/'3' 접두사로 재추정했는데,
    // 팀 코드가 'T1'/'T2'/'T3' 형태라 항상 T1로 오판정되는 버그가 있었음)
    const teamCode = empInfo.team || 'T1'
    const token = sessionStorage.getItem('token')
    try {
      const res = await fetch('/api/exam/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ team_code: teamCode, employee_id: empInfo.empno }),
      })
      if (!res.ok) {
        // 과거에는 이 실패를 무음으로 삼키고 하드코딩된 25문항 모의시험으로 조용히 진행시켰다 —
        // 응시자가 실제로는 시험을 못 받았는데도 정상 진행되는 것처럼 보이는 문제가 있었다.
        const err = await res.json().catch(() => null)
        setStartError(apiErrorMessage(err, res.status))
        setScreen('identity')
        return
      }
      const data = await res.json()
      setResultId(data.result_id)
      if (data.name) setExamName(data.name)
      if (data.duration_min) setTimerSeconds(data.duration_min * 60)
      const qs = data.questions.map(q => ({
        id: q.id, cat: q.category, diff: q.difficulty || '중',
        q: q.question, opts: [q.options.A, q.options.B, q.options.C, q.options.D], ans: -1,
      }))
      setQuestions(qs)
      setAnswers(new Array(qs.length).fill(null))
      setBookmarks(new Array(qs.length).fill(false))
      setScreen('exam')
      startTimer()
    } catch {
      setStartError('네트워크 오류로 시험을 시작하지 못했습니다. 인터넷 연결을 확인한 후 다시 시도해주세요.')
      setScreen('identity')
    }
  }

  function handleSelectAnswer(qIdx, optIdx, navOnly = false) {
    if (!navOnly && optIdx !== null) {
      setAnswers(prev => { const next = [...prev]; next[qIdx] = optIdx; return next })
    }
    setCurrentQ(qIdx)
  }

  function handleToggleBookmark(qIdx) {
    setBookmarks(prev => { const next = [...prev]; next[qIdx] = !next[qIdx]; return next })
  }

  async function handleSubmit() {
    stopTimer()
    setScreen('scoring')
    setSubmitError('')
    const LMAP = ['A','B','C','D']
    const answersDict = {}
    const timesDict = {}
    questions.forEach((q, i) => { answersDict[q.id] = answers[i] !== null ? LMAP[answers[i]] : ''; timesDict[q.id] = 30 })
    const token = sessionStorage.getItem('token')
    try {
      const res = await fetch('/api/exam/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        // result_id를 그대로 재사용하는 재시도는 백엔드에서 같은 결과를 반환하므로(멱등),
        // 이 함수를 재호출(재제출)해도 중복 채점·중복 저장이 발생하지 않는다.
        body: JSON.stringify({ result_id: resultId, answers: answersDict, response_times: timesDict, employee_id: empInfo.empno, name: empInfo.name }),
      })
      if (!res.ok) {
        // 과거에는 이 실패를 무음으로 삼키고 서버가 정답을 숨긴 문항으로 로컬 채점(항상 0점)한 뒤
        // 화면 하단에 "결과가 저장되었습니다"라고 거짓 안내하는 심각한 버그가 있었다.
        const err = await res.json().catch(() => null)
        setSubmitError(apiErrorMessage(err, res.status))
        setScreen('submit-error')
        return
      }
      const data = await res.json()
      setScore(data.score)
      setPass(typeof data.pass === 'boolean' ? data.pass : null)
      setSubmitResults(data.results || null)
      setTimeout(() => setScreen('result'), 2000)
    } catch {
      setSubmitError('네트워크 오류로 제출하지 못했습니다. 인터넷 연결을 확인한 후 다시 시도해주세요.')
      setScreen('submit-error')
    }
  }

  handleSubmitRef.current = handleSubmit

  function handleFinish() {
    apiLogout(navigate)
  }

  return (
    <>
      {screen === 'identity' && <IdentityScreen empInfo={empInfo} examName={examName} durationMin={assignedDurationMin} questionCount={assignedQuestionCount} error={startError} onStart={handleStart} />}
      {(screen === 'exam' || screen === 'confirm') && (
        <ExamScreen
          questions={questions}
          answers={answers}
          currentQ={currentQ}
          timerSeconds={timerSeconds}
          onSelectAnswer={handleSelectAnswer}
          onPrev={() => setCurrentQ(q => Math.max(0, q - 1))}
          onNext={() => setCurrentQ(q => Math.min(questions.length - 1, q + 1))}
          onOpenConfirm={() => setScreen('confirm')}
          bookmarks={bookmarks}
          onToggleBookmark={handleToggleBookmark}
          empInfo={empInfo}
        />
      )}
      {screen === 'confirm' && (
        <ConfirmScreen answers={answers} onBack={() => setScreen('exam')} onSubmit={handleSubmit} />
      )}
      {screen === 'loading' && <ScoringScreen title="로그인 중입니다..." sub="잠시만 기다려주세요" />}
      {screen === 'scoring' && <ScoringScreen title="채점 중입니다..." sub="잠시만 기다려주세요" />}
      {screen === 'submit-error' && <SubmitErrorScreen message={submitError} onRetry={handleSubmit} />}
      {showAdminNotice && (
        <div style={{ position:'fixed', inset:0, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(15,23,42,0.6)', backdropFilter:'blur(4px)', zIndex:100 }}>
          <div style={{ background:'white', borderRadius:20, padding:'40px 36px', width:'90%', maxWidth:380, boxShadow:'0 20px 60px rgba(0,0,0,0.25)', textAlign:'center' }}>
            <div style={{ width:52, height:52, borderRadius:'50%', background:'#fef3c7', display:'flex', alignItems:'center', justifyContent:'center', margin:'0 auto 20px' }}>
              <svg width={26} height={26} viewBox="0 0 24 24" fill="none" stroke="#b45309" strokeWidth="2.5" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            </div>
            <h2 style={{ fontSize:18, fontWeight:800, color:'#1e293b', marginBottom:12 }}>관리자 계정 응시 안내</h2>
            <p style={{ fontSize:14, color:'#64748b', marginBottom:28, lineHeight:1.7 }}>관리자 계정으로 응시 시<br/>결과가 저장되지 않습니다.</p>
            <button onClick={() => setShowAdminNotice(false)} style={{ width:'100%', height:48, background:'#1e3a5f', color:'white', border:'none', borderRadius:10, fontSize:15, fontWeight:700, cursor:'pointer' }}>확인</button>
          </div>
        </div>
      )}
      {showExitConfirm && (
        <ExitConfirmModal
          onLeave={() => { setShowExitConfirm(false); window.location.reload() }}
          onCancel={() => setShowExitConfirm(false)}
        />
      )}
      {screen === 'result' && score !== null && (
        <ResultScreen empInfo={empInfo} examName={examName} score={score} pass={pass} submitResults={submitResults} onFinish={handleFinish} />
      )}
    </>
  )
}
