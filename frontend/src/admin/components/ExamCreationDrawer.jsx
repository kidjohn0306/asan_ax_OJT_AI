// 시험지 선택부터 일정 확인까지 시험 생성 단계를 안내하는 관리자 드로어
import { useEffect, useMemo, useState } from 'react'

import './ExamSchedule.css'

function teamName(code, teamLabels) {
  return teamLabels?.[code] || code || '미지정'
}

function paperVersion(paper) {
  return paper?.paper_version ? `v${paper.paper_version}` : '버전 정보 없음'
}

function PaperPicker({ papers, selectedPaperId, teamLabels, onSelect, onClose }) {
  const [teamFilter, setTeamFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [previewId, setPreviewId] = useState(selectedPaperId || papers[0]?.exam_set_id || '')
  const teams = useMemo(() => [...new Set(papers.map(paper => paper.team_code).filter(Boolean))], [papers])
  const visiblePapers = papers.filter(paper => {
    const teamMatches = teamFilter === 'all' || paper.team_code === teamFilter
    const normalizedQuery = query.trim().toLowerCase()
    const textMatches = !normalizedQuery || `${paper.name} ${paper.exam_set_id} ${paper.exam_category || ''}`.toLowerCase().includes(normalizedQuery)
    return teamMatches && textMatches
  })
  const preview = papers.find(paper => paper.exam_set_id === previewId) || visiblePapers[0]

  useEffect(() => {
    if (visiblePapers.length && !visiblePapers.some(paper => paper.exam_set_id === previewId)) {
      setPreviewId(visiblePapers[0].exam_set_id)
    }
  }, [teamFilter, query])

  return (
    <div className="exam-paper-overlay" role="dialog" aria-modal="true" aria-labelledby="exam-paper-picker-title">
      <div className="exam-paper-modal">
        <header className="exam-paper-modal__header">
          <div>
            <p>팀과 구성 정보를 비교한 뒤 회차에 사용할 시험지를 고릅니다.</p>
            <h2 id="exam-paper-picker-title">시험지 선택</h2>
          </div>
          <button type="button" className="exam-schedule-icon-button" onClick={onClose} aria-label="시험지 선택 닫기">×</button>
        </header>
        <div className="exam-paper-toolbar">
          <div className="exam-segmented" aria-label="시험지 팀 필터">
            <button type="button" className={teamFilter === 'all' ? 'is-active' : ''} onClick={() => setTeamFilter('all')}>전체</button>
            {teams.map(team => (
              <button type="button" key={team} className={teamFilter === team ? 'is-active' : ''} onClick={() => setTeamFilter(team)}>
                {teamName(team, teamLabels)}
              </button>
            ))}
          </div>
          <input
            type="search"
            value={query}
            onChange={event => setQuery(event.target.value)}
            placeholder="시험지명 또는 ID 검색"
            aria-label="시험지 검색"
          />
        </div>
        <div className="exam-paper-modal__body">
          <div className="exam-paper-list" role="listbox" aria-label="시험지 목록">
            {visiblePapers.length === 0 ? (
              <p className="exam-empty-message">조건에 맞는 시험지가 없습니다.</p>
            ) : visiblePapers.map(paper => (
              <button
                type="button"
                role="option"
                aria-selected={preview?.exam_set_id === paper.exam_set_id}
                key={paper.exam_set_id}
                className={`exam-paper-row${preview?.exam_set_id === paper.exam_set_id ? ' is-selected' : ''}`}
                onClick={() => setPreviewId(paper.exam_set_id)}
              >
                <span><strong>{paper.name}</strong><small>{paper.exam_set_id} · {paper.exam_category || '유형 미지정'}</small></span>
                <span>{teamName(paper.team_code, teamLabels)}</span>
                <span>{paperVersion(paper)}</span>
                <span>{paper.question_count ?? 0}문항</span>
              </button>
            ))}
          </div>
          <aside className="exam-paper-preview">
            {preview ? (
              <>
                <span className="exam-paper-preview__eyebrow">{teamName(preview.team_code, teamLabels)} 전용</span>
                <h3>{preview.name}</h3>
                <p>{preview.exam_set_id} · {paperVersion(preview)}</p>
                <dl>
                  <div><dt>대상 팀</dt><dd>{teamName(preview.team_code, teamLabels)}</dd></div>
                  <div><dt>시험 유형</dt><dd>{preview.exam_category || '미지정'}</dd></div>
                  <div><dt>문항 수</dt><dd>{preview.question_count ?? 0}문항</dd></div>
                  <div><dt>사용 회차</dt><dd>{preview.used_by_exam_count ?? 0}회</dd></div>
                </dl>
                <div className="exam-team-lock">잠금 · {teamName(preview.team_code, teamLabels)} 응시자만 배정할 수 있습니다.</div>
              </>
            ) : <p className="exam-empty-message">왼쪽에서 시험지를 선택하세요.</p>}
          </aside>
        </div>
        <footer className="exam-paper-modal__footer">
          <span>시험 회차의 팀은 선택한 시험지에서 상속됩니다.</span>
          <div>
            <button type="button" className="exam-button is-secondary" onClick={onClose}>취소</button>
            <button type="button" className="exam-button is-primary" disabled={!preview} onClick={() => preview && onSelect(preview)}>이 시험지 선택</button>
          </div>
        </footer>
      </div>
    </div>
  )
}

export default function ExamCreationDrawer({
  open,
  form,
  papers,
  teamLabels,
  creating,
  onChange,
  onCreate,
  onClose,
}) {
  const [step, setStep] = useState(1)
  const [paperPickerOpen, setPaperPickerOpen] = useState(false)
  const selectedPaper = papers.find(paper => paper.exam_set_id === form.paperId)

  useEffect(() => {
    if (open) setStep(1)
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    function handleEscape(event) {
      if (event.key !== 'Escape') return
      if (paperPickerOpen) setPaperPickerOpen(false)
      else onClose()
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [open, paperPickerOpen, onClose])

  if (!open) return null

  async function createExam() {
    const created = await onCreate()
    if (created) onClose()
  }

  return (
    <>
      <div className="exam-drawer-overlay" onMouseDown={event => event.target === event.currentTarget && onClose()}>
        <aside className="exam-creation-drawer" role="dialog" aria-modal="true" aria-labelledby="exam-create-title">
          <header className="exam-creation-drawer__header">
            <div>
              <p>시험지의 팀을 유지한 채 새 시험 회차를 만듭니다.</p>
              <h2 id="exam-create-title">시험 생성</h2>
            </div>
            <button type="button" className="exam-schedule-icon-button" onClick={onClose} aria-label="시험 생성 닫기">×</button>
          </header>

          <ol className="exam-create-steps" aria-label="시험 생성 단계">
            {['시험지 선택', '일정 입력', '최종 확인'].map((label, index) => (
              <li key={label} className={step === index + 1 ? 'is-active' : step > index + 1 ? 'is-done' : ''}>
                <span>{step > index + 1 ? '✓' : index + 1}</span>{label}
              </li>
            ))}
          </ol>

          <div className="exam-creation-drawer__body">
            {step === 1 && (
              <section>
                <h3>사용할 시험지를 선택하세요.</h3>
                <p className="exam-section-help">시험지에 설정된 팀이 시험 회차와 응시자 배정 범위에 그대로 적용됩니다.</p>
                {selectedPaper ? (
                  <div className="exam-selected-paper">
                    <div>
                      <span>{teamName(selectedPaper.team_code, teamLabels)} · {paperVersion(selectedPaper)}</span>
                      <strong>{selectedPaper.name}</strong>
                      <small>{selectedPaper.exam_set_id} · {selectedPaper.question_count ?? 0}문항</small>
                    </div>
                    <button type="button" className="exam-button is-secondary" onClick={() => setPaperPickerOpen(true)}>다시 선택</button>
                  </div>
                ) : (
                  <button type="button" className="exam-paper-empty" onClick={() => setPaperPickerOpen(true)}>
                    <strong>시험지 선택 레이어 열기</strong>
                    <span>팀, 버전, 문항 수와 사용 회차를 비교할 수 있습니다.</span>
                  </button>
                )}
                {selectedPaper && <div className="exam-team-lock">잠금 · {teamName(selectedPaper.team_code, teamLabels)} 시험지에서 상속됨</div>}
              </section>
            )}

            {step === 2 && (
              <section>
                <h3>시험 일정과 기준을 입력하세요.</h3>
                <p className="exam-section-help">일시를 비우면 일정 미정 시험으로 생성할 수 있습니다.</p>
                <div className="exam-form-grid">
                  <label className="is-wide">시험명
                    <input type="text" value={form.name} onChange={event => onChange({ name:event.target.value })} placeholder={selectedPaper?.name || '시험명을 입력하세요.'} />
                    <small>비워두면 시험지 이름을 그대로 사용합니다.</small>
                  </label>
                  <label className="is-wide">시험 일시
                    <input aria-label="시험 일시" type="datetime-local" value={form.datetime} onChange={event => onChange({ datetime:event.target.value })} />
                  </label>
                  <label>시험 시간(분)
                    <input aria-label="시험 시간(분)" type="number" inputMode="numeric" min="1" max="600" value={form.durationMin} onChange={event => onChange({ durationMin:event.target.value === '' ? '' : Number(event.target.value) })} />
                  </label>
                  <label>합격 커트라인
                    <input aria-label="합격 커트라인" type="number" inputMode="numeric" min="0" max="100" value={form.passScore} onChange={event => onChange({ passScore:event.target.value === '' ? '' : Number(event.target.value) })} />
                  </label>
                </div>
              </section>
            )}

            {step === 3 && (
              <section>
                <h3>생성할 시험을 확인하세요.</h3>
                <p className="exam-section-help">생성 후 기존 편집 기능에서 일정과 기준을 다시 조정할 수 있습니다.</p>
                <dl className="exam-create-summary">
                  <div><dt>시험지</dt><dd>{selectedPaper?.name || '-'}</dd></div>
                  <div><dt>대상 팀</dt><dd>{teamName(selectedPaper?.team_code, teamLabels)} · 변경 불가</dd></div>
                  <div><dt>시험명</dt><dd>{form.name.trim() || selectedPaper?.name || '-'}</dd></div>
                  <div><dt>시험 일시</dt><dd>{form.datetime ? form.datetime.replace('T', ' ') : '일정 미정'}</dd></div>
                  <div><dt>시험 기준</dt><dd>{form.durationMin || 60}분 · {form.passScore === '' ? 70 : form.passScore}점 이상</dd></div>
                </dl>
              </section>
            )}
          </div>

          <footer className="exam-creation-drawer__footer">
            <button type="button" className="exam-button is-secondary" onClick={step === 1 ? onClose : () => setStep(current => current - 1)}>
              {step === 1 ? '취소' : '이전'}
            </button>
            {step < 3 ? (
              <button type="button" className="exam-button is-primary" disabled={step === 1 && !selectedPaper} onClick={() => setStep(current => current + 1)}>다음</button>
            ) : (
              <button type="button" className="exam-button is-primary" disabled={creating} onClick={createExam}>{creating ? '생성 중...' : '시험 생성'}</button>
            )}
          </footer>
        </aside>
      </div>
      {paperPickerOpen && (
        <PaperPicker
          papers={papers}
          selectedPaperId={form.paperId}
          teamLabels={teamLabels}
          onClose={() => setPaperPickerOpen(false)}
          onSelect={paper => {
            onChange({ paperId:paper.exam_set_id })
            setPaperPickerOpen(false)
          }}
        />
      )}
    </>
  )
}
