import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { logout as apiLogout } from '../api'

const MOCK_QUESTIONS = [
  {id:"C-001",cat:"공통",diff:"하",q:"회사 내 작업 전 반드시 확인해야 하는 것은?",opts:["작업지시서","생산계획","설비상태","작업일지"],ans:0},
  {id:"C-002",cat:"공통",diff:"중",q:"5S 활동의 목적이 아닌 것은?",opts:["생산성 향상","안전사고 예방","개인 편의","품질 향상"],ans:2},
  {id:"C-003",cat:"공통",diff:"하",q:"품질 이상 발생 시 최초로 보고 대상은?",opts:["팀장","안전관리자","인사팀","고객사"],ans:0},
  {id:"C-004",cat:"공통",diff:"하",q:"작업 중 아차사고 발생 시 올바른 대처는?",opts:["무시하고 계속 작업","즉시 팀장에게 보고","혼자 해결","퇴근 후 보고"],ans:1},
  {id:"C-005",cat:"공통",diff:"중",q:"설비 이상 발견 시 절차로 옳은 것은?",opts:["설비 강제 가동","설비 정지 후 담당자 연락","개인 판단으로 수리","로그 작성 없이 재가동"],ans:1},
  {id:"T1-001",cat:"팀별",diff:"중",q:"생산라인 작업 시 가장 먼저 확인해야 하는 것은?",opts:["작업지시서","생산계획","설비상태","작업일지"],ans:2},
  {id:"T1-002",cat:"팀별",diff:"상",q:"주간 작업 시 안전 점검 주기는?",opts:["월 1회","주 1회","작업 전 매일","연 1회"],ans:2},
  {id:"T1-003",cat:"팀별",diff:"중",q:"설비 예방 보전 기록의 목적은?",opts:["개인 기록","설비 수명 연장 및 사고 예방","팀장 보고용","관계없음"],ans:1},
  {id:"T1-004",cat:"팀별",diff:"하",q:"작업 지시서 없이 작업을 진행해야 할 때는?",opts:["바로 진행","팀장 승인 후 진행","옆 동료에게 확인","임의 판단"],ans:1},
  {id:"T1-005",cat:"팀별",diff:"중",q:"품질 불량 발생 시 즉시 취해야 할 조치는?",opts:["라인 계속 가동","불량 격리 후 팀장 보고","불량품 폐기","다음 교대자에게 인계"],ans:1},
  {id:"T1-006",cat:"팀별",diff:"상",q:"설비 가동 중 이상 소음 발생 시 조치는?",opts:["계속 가동","설비 정지 후 점검","소음 차단 후 가동","다음 교대까지 대기"],ans:1},
  {id:"T1-007",cat:"팀별",diff:"중",q:"작업 환경 개선 제안은 누구에게 하는가?",opts:["동료","팀장","인사팀","고객사"],ans:1},
  {id:"T1-008",cat:"팀별",diff:"하",q:"작업 전 안전 교육의 목적은?",opts:["의무 이수","사고 예방","시간 채우기","규정 준수만"],ans:1},
  {id:"T1-009",cat:"팀별",diff:"상",q:"반도체 설비 클린룸 내 이물질 유입 방지 방법은?",opts:["마스크만 착용","전신 방진복 착용 후 에어샤워","장갑만 착용","빠른 속도로 입장"],ans:1},
  {id:"T1-010",cat:"팀별",diff:"중",q:"작업 후 정리정돈의 기준은?",opts:["개인 판단","5S 기준","팀장 지시 시에만","퇴근 전 5분"],ans:1},
  {id:"S-001",cat:"환경안전",diff:"하",q:"화학물질 취급 시 반드시 착용해야 하는 보호구는?",opts:["안전모만","보안경과 내화학성 장갑","일반 면장갑","없음"],ans:1},
  {id:"S-002",cat:"환경안전",diff:"중",q:"화재 발생 시 최우선 조치는?",opts:["소화기 사용","인명 대피","원인 파악","팀장 보고"],ans:1},
  {id:"S-003",cat:"환경안전",diff:"상",q:"MSDS(물질안전보건자료)를 확인해야 하는 시점은?",opts:["사고 후","화학물질 취급 전","교대 인수인계 시","월 1회"],ans:1},
  {id:"S-004",cat:"환경안전",diff:"중",q:"산업폐기물 처리 규정을 위반하면?",opts:["경고","법적 처벌 및 회사 제재","벌금만","관계없음"],ans:1},
  {id:"S-005",cat:"환경안전",diff:"중",q:"안전보호구 착용 의무를 지키지 않았을 때 책임은?",opts:["회사만","개인과 회사 공동","팀장만","없음"],ans:1},
  {id:"G-001",cat:"일반상식",diff:"중",q:"반도체 공정에서 클린룸의 주된 목적은?",opts:["냉방","미세먼지 차단 및 오염 방지","소음 차단","조명 확보"],ans:1},
  {id:"G-002",cat:"일반상식",diff:"하",q:"직장 내 괴롭힘 신고 창구는?",opts:["팀장","고충처리위원회 또는 인사팀","동료","SNS"],ans:1},
  {id:"G-003",cat:"일반상식",diff:"중",q:"근로기준법상 법정 근로시간은?",opts:["주 52시간","주 40시간","주 60시간","월 200시간"],ans:1},
  {id:"G-004",cat:"일반상식",diff:"하",q:"개인정보 보호를 위해 지켜야 할 사항은?",opts:["동료와 자유롭게 공유","업무 목적 외 사용 금지","SNS 공유 가능","관계없음"],ans:1},
  {id:"G-005",cat:"일반상식",diff:"중",q:"사내 민감 정보 외부 유출 시 결과는?",opts:["경고만","민사·형사 책임 및 해고","벌금만","문제없음"],ans:1},
]

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
function IdentityScreen({ empInfo, onStart }) {
  const today = new Date()
  const dateStr = `${today.getFullYear()}년 ${today.getMonth()+1}월 ${today.getDate()}일`

  return (
    <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'var(--bg)', padding:24 }}>
      <div style={{ background:'white', borderRadius:20, boxShadow:'0 8px 40px rgba(30,58,95,0.12)', padding:'48px 40px', width:'100%', maxWidth:480, display:'flex', flexDirection:'column', alignItems:'center' }}>
        <div style={{ display:'flex', flexDirection:'column', alignItems:'center', marginBottom:32 }}>
          <div style={{ width:56, height:56, background:'var(--primary)', borderRadius:14, display:'flex', alignItems:'center', justifyContent:'center', marginBottom:10 }}>
            <svg viewBox="0 0 32 32" width={32} height={32} fill="white"><rect x="2" y="8" width="12" height="16" rx="2"/><rect x="18" y="4" width="12" height="10" rx="2"/><rect x="18" y="18" width="12" height="10" rx="2"/></svg>
          </div>
          <div style={{ fontSize:20, fontWeight:800, color:'var(--primary)' }}>(주)엑스티</div>
          <div style={{ fontSize:13, color:'var(--text-muted)', marginTop:2 }}>인재개발부 · OJT 평가 시스템</div>
        </div>

        <div style={{ fontSize:22, fontWeight:800, color:'var(--text)', letterSpacing:'-0.5px', marginBottom:6, textAlign:'center' }}>OJT 기초고사</div>
        <div style={{ fontSize:14, color:'var(--text-muted)', marginBottom:28, textAlign:'center' }}>시험 전 응시자 정보를 확인해 주세요</div>

        <div style={{ width:'100%', background:'var(--bg)', borderRadius:12, border:'1px solid var(--border)', padding:'20px 24px', marginBottom:24 }}>
          {[
            ['응시자', empInfo.name, true],
            ['사원번호', empInfo.empno, false],
            ['소속팀', empInfo.team, false],
            ['응시일', dateStr, false],
            ['시험 시간', '60분 · 25문항', false],
          ].map(([label, value, isName]) => (
            <div key={label} style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'8px 0', borderBottom:'1px solid var(--border)' }}>
              <span style={{ fontSize:13, color:'var(--text-muted)', fontWeight:600 }}>{label}</span>
              <span style={{ fontSize: isName ? 18 : 14, color: isName ? 'var(--primary)' : 'var(--text)', fontWeight: isName ? 800 : 700 }}>{value}</span>
            </div>
          ))}
        </div>

        <p style={{ fontSize:14, color:'var(--text-muted)', textAlign:'center', marginBottom:20, lineHeight:1.6 }}>위 정보가 맞으면 시험을 시작해 주세요.</p>
        <button
          onClick={onStart}
          style={{ width:'100%', height:56, background:'var(--accent)', color:'white', border:'none', borderRadius:12, fontSize:17, fontWeight:700, cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', gap:8, fontFamily:'var(--font)' }}
        >
          시험 시작하기
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

/* ── ResultScreen ───────────────────────────────────────────── */
function ResultScreen({ empInfo, questions, answers, score, onFinish }) {
  const [accordionOpen, setAccordionOpen] = useState(false)
  const pass = score >= 70

  const catResults = { 공통:{c:0,t:5}, 팀별:{c:0,t:10}, 환경안전:{c:0,t:5}, 일반상식:{c:0,t:5} }
  questions.forEach((q, i) => { if (answers[i] === q.ans) catResults[q.cat].c++ })

  return (
    <div style={{ minHeight:'100vh', display:'flex', flexDirection:'column', background:'var(--bg)', fontFamily:'var(--font)' }}>
      <div style={{ background:'var(--primary)', padding:'20px 32px', display:'flex', alignItems:'center', justifyContent:'space-between', color:'white', flexShrink:0 }}>
        <div>
          <div style={{ fontSize:16, fontWeight:800 }}>(주)엑스티</div>
          <div style={{ fontSize:13, opacity:0.65, marginTop:2 }}>OJT 기초고사 · 시험 결과</div>
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
              const pct = Math.round((r.c / r.t) * 100)
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
              {questions.map((q, i) => {
                const unknownAnswer = q.ans === -1
                const isCorrect = !unknownAnswer && answers[i] === q.ans
                return (
                  <div key={i} style={{ display:'flex', alignItems:'center', gap:12, padding:'12px 24px', borderTop:'1px solid var(--border)' }}>
                    <span style={{ fontSize:12, fontWeight:800, color:'var(--text-muted)', width:24, flexShrink:0 }}>{i+1}</span>
                    <span style={{ flex:1, fontSize:13, color:'var(--text)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{q.q}</span>
                    <span style={{ width:28, height:28, borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', fontSize:14, fontWeight:800, flexShrink:0, background: unknownAnswer ? '#f1f5f9' : isCorrect ? 'var(--success-light)' : 'var(--danger-light)', color: unknownAnswer ? 'var(--text-muted)' : isCorrect ? 'var(--success)' : 'var(--danger)' }}>{unknownAnswer ? '−' : isCorrect ? 'O' : 'X'}</span>
                    <span style={{ fontSize:11, color:'var(--text-muted)', width:80, textAlign:'right', flexShrink:0 }}>정답: {unknownAnswer ? '(서버)' : LABEL[q.ans]}</span>
                  </div>
                )
              })}
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

  const [screen, setScreen] = useState('identity')
  const [showAdminNotice, setShowAdminNotice] = useState(sessionStorage.getItem('role') === 'admin')
  const [showExitConfirm, setShowExitConfirm] = useState(false)
  const [questions, setQuestions] = useState([...MOCK_QUESTIONS])
  const [answers, setAnswers] = useState(new Array(25).fill(null))
  const [bookmarks, setBookmarks] = useState(new Array(25).fill(false))
  const [currentQ, setCurrentQ] = useState(0)
  const [timerSeconds, setTimerSeconds] = useState(3600)
  const [examId, setExamId] = useState(null)
  const [score, setScore] = useState(null)
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

    const forceLogout = () => {
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
      if (e.key === 'PrintScreen') forceLogout()
    }

    const handleContextMenu = (e) => e.preventDefault()

    // 탭 전환, 홈키(화면 최소화) 등으로 페이지가 가려지면 즉시 로그아웃
    const handleVisibilityChange = () => {
      if (document.hidden) forceLogout()
    }

    // 뒤로가기 감지: 더미 history 항목을 쌓아 popstate로만 감지되게 하고 즉시 로그아웃
    // exam <-> confirm 전환마다 effect가 재실행되므로, 더미 항목은 세션당 한 번만 push해 history 스택 누적을 방지
    const handlePopState = () => forceLogout()
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
  }, [screen])

  async function handleStart() {
    setScreen('loading')
    // empInfo.team은 로그인 응답에서 그대로 저장된 실제 team_code(T1/T2/T3)이므로
    // 별도 변환 없이 그대로 사용한다 (과거에는 '2'/'3' 접두사로 재추정했는데,
    // 팀 코드가 'T1'/'T2'/'T3' 형태라 항상 T1로 오판정되는 버그가 있었음)
    const teamCode = empInfo.team || 'T1'
    const token = sessionStorage.getItem('token')
    try {
      const res = await fetch('/api/exam/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ team_code: teamCode }),
      })
      if (res.ok) {
        const data = await res.json()
        setExamId(data.exam_id)
        const qs = data.questions.map(q => ({
          id: q.id, cat: q.category, diff: q.difficulty || '중',
          q: q.question, opts: [q.options.A, q.options.B, q.options.C, q.options.D], ans: -1,
        }))
        setQuestions(qs)
        setAnswers(new Array(qs.length).fill(null))
        setBookmarks(new Array(qs.length).fill(false))
      }
    } catch { /* mock fallback */ }
    setScreen('exam')
    startTimer()
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

  function calculateScore(qs, ans) {
    let correct = 0
    qs.forEach((q, i) => { if (ans[i] === q.ans) correct++ })
    return Math.round((correct / qs.length) * 100)
  }

  async function handleSubmit() {
    stopTimer()
    setScreen('scoring')
    if (examId) {
      try {
        const LMAP = ['A','B','C','D']
        const answersDict = {}
        const timesDict = {}
        questions.forEach((q, i) => { answersDict[q.id] = answers[i] !== null ? LMAP[answers[i]] : 'A'; timesDict[q.id] = 30 })
        const token = sessionStorage.getItem('token')
        const res = await fetch('/api/exam/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
          body: JSON.stringify({ exam_id: examId, answers: answersDict, response_times: timesDict, employee_id: empInfo.empno, name: empInfo.name }),
        })
        if (res.ok) {
          const data = await res.json()
          setScore(data.score)
          setTimeout(() => setScreen('result'), 2000)
          return
        }
      } catch { /* fallback */ }
    }
    setScore(calculateScore(questions, answers))
    setTimeout(() => setScreen('result'), 2000)
  }

  handleSubmitRef.current = handleSubmit

  function handleFinish() {
    apiLogout(navigate)
  }

  return (
    <>
      {screen === 'identity' && <IdentityScreen empInfo={empInfo} onStart={handleStart} />}
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
        <ResultScreen empInfo={empInfo} questions={questions} answers={answers} score={score} onFinish={handleFinish} />
      )}
    </>
  )
}
