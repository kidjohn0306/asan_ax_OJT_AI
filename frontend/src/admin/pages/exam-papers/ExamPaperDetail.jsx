import { useEffect, useState } from 'react'

import { apiFetch } from '../../../api'

const EXAM_CATEGORY_LABELS = { exam_study: '평가', exam_test: '연습문제' }

export default function ExamPaperDetail({ examId, onCreateCopy }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(Boolean(examId))
  const [error, setError] = useState('')

  useEffect(() => {
    if (!examId) {
      setDetail(null)
      setError('')
      setLoading(false)
      return undefined
    }
    let active = true
    setLoading(true)
    setError('')
    setDetail(null)
    apiFetch('GET', `/api/admin/exam-sets/${encodeURIComponent(examId)}/questions`)
      .then(data => { if (active) setDetail(data) })
      .catch(err => { if (active) setError(err.message || '시험지 상세를 불러오지 못했습니다.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [examId])

  if (!examId) return <aside style={stateStyle}>목록에서 시험지를 선택하면 상세 내용을 확인할 수 있습니다.</aside>
  if (loading) return <aside style={stateStyle}>시험지 상세를 불러오는 중입니다.</aside>
  if (error) return <aside role="alert" style={{ ...stateStyle, color:'var(--danger)' }}>{error}</aside>
  if (!detail) return null

  const exam = detail.exam_set || {}
  const questions = detail.questions || []
  const totalScore = questions.reduce((sum, question) => sum + Number(question.score || 0), 0)

  return (
    <aside aria-label="시험지 상세" style={panelStyle}>
      <div style={{ padding:18, borderBottom:'1px solid var(--border)' }}>
        <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:12 }}>
          <div>
            <h2 style={{ margin:0, fontSize:16, color:'var(--text)' }}>{exam.name || examId}</h2>
            <div style={{ display:'flex', flexWrap:'wrap', gap:6, marginTop:9 }}>
              <span style={badgeStyle}>{EXAM_CATEGORY_LABELS[exam.exam_category] || '평가'}</span>
              <span style={badgeStyle}>시험지 v{exam.paper_version || 0}</span>
              <span style={badgeStyle}>총점 {totalScore}점</span>
              <span style={badgeStyle}>{exam.immutable ? '확정 시험지' : '편집 가능'}</span>
            </div>
          </div>
          <button type="button" onClick={() => onCreateCopy(examId)} style={copyButtonStyle}>수정본 만들기</button>
        </div>
        <div style={{ marginTop:10, color:'var(--text-muted)', fontSize:11 }}>시험지 ID {exam.exam_set_id || '-'} · 버전 ID {exam.exam_version_id || '-'}</div>
      </div>

      {questions.length === 0 ? (
        <div style={{ padding:28, textAlign:'center', color:'var(--text-muted)', fontSize:13 }}>등록된 문항이 없습니다.</div>
      ) : (
        <div style={{ padding:14, display:'flex', flexDirection:'column', gap:10 }}>
          {questions.map((question, index) => (
            <article key={`${question.question_id}-${index}`} data-testid={`exam-paper-question-${question.question_id}`} style={{ border:'1px solid var(--border)', borderRadius:8, padding:14 }}>
              <div style={{ display:'flex', gap:8, alignItems:'flex-start' }}>
                <strong style={{ color:'var(--accent-dark)', fontSize:13 }}>{index + 1}.</strong>
                <div style={{ flex:1 }}>
                  <div style={{ color:'var(--text)', fontSize:14, fontWeight:700 }}>{question.question}</div>
                  <div style={{ display:'flex', gap:6, flexWrap:'wrap', margin:'8px 0' }}>
                    <span style={badgeStyle}>난이도 {question.difficulty || '-'}</span>
                    <span style={badgeStyle}>{question.score || 0}점</span>
                    <span style={badgeStyle}>문항 v{question.question_version || 0}</span>
                  </div>
                  <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:6 }}>
                    {['A', 'B', 'C', 'D'].map(key => (
                      <div key={key} data-correct={question.answer === key ? 'true' : 'false'} style={{ padding:'7px 9px', borderRadius:6, background:question.answer === key ? 'var(--success-light)' : '#F8FAFC', color:question.answer === key ? 'var(--success)' : 'var(--text-muted)', fontSize:12, fontWeight:question.answer === key ? 700 : 400 }}>
                        {key}. {question.options?.[key] || '-'}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </aside>
  )
}

const panelStyle = { background:'var(--card)', border:'1px solid var(--border)', borderRadius:'var(--radius)', overflow:'hidden' }
const stateStyle = { ...panelStyle, padding:'42px 20px', textAlign:'center', color:'var(--text-muted)', fontSize:13 }
const badgeStyle = { padding:'3px 8px', borderRadius:20, background:'#F1F5F9', color:'var(--text-muted)', fontSize:11, fontWeight:700 }
const copyButtonStyle = { border:'1.5px solid var(--accent)', borderRadius:7, padding:'8px 12px', background:'white', color:'var(--accent)', fontFamily:'var(--font)', fontSize:12, fontWeight:700, cursor:'pointer', whiteSpace:'nowrap' }
