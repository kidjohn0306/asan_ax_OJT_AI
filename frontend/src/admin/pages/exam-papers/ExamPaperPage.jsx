import { useSearchParams } from 'react-router-dom'

import ExamPaperDetail from './ExamPaperDetail'
import ExamPaperList from './ExamPaperList'

export default function ExamPaperPage({ renderSetup }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') === 'list' ? 'list' : 'setup'
  const selected = searchParams.get('selected') || ''
  const source = searchParams.get('source') || ''

  function switchTab(nextTab) {
    if (nextTab === tab) return
    setSearchParams({ tab:nextTab })
  }

  function selectPaper(examId) {
    const next = new URLSearchParams(searchParams)
    next.set('tab', 'list')
    next.set('selected', examId)
    next.delete('source')
    setSearchParams(next)
  }

  function createCopy(examId) {
    setSearchParams({ tab:'setup', source:examId })
  }

  function saved(examId) {
    setSearchParams({ tab:'list', selected:examId })
  }

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:16, minHeight:0 }}>
      <div role="tablist" aria-label="시험지 생성·관리" style={{ display:'flex', gap:4, padding:4, width:'fit-content', border:'1px solid var(--border)', borderRadius:9, background:'#F8FAFC' }}>
        <button type="button" role="tab" aria-selected={tab === 'setup'} onClick={() => switchTab('setup')} style={tabStyle(tab === 'setup')}>시험지 설정</button>
        <button type="button" role="tab" aria-selected={tab === 'list'} onClick={() => switchTab('list')} style={tabStyle(tab === 'list')}>시험지 보기</button>
      </div>

      {tab === 'setup' ? (
        renderSetup({ sourceExamId:source || null, onSaved:saved })
      ) : (
        <div style={{ display:'grid', gridTemplateColumns:selected ? 'minmax(460px, 1fr) minmax(420px, 1fr)' : '1fr', gap:16, alignItems:'start' }}>
          <ExamPaperList searchParams={searchParams} setSearchParams={setSearchParams} onSelect={selectPaper} />
          {selected && <ExamPaperDetail examId={selected} onCreateCopy={createCopy} />}
        </div>
      )}
    </div>
  )
}

function tabStyle(active) {
  return {
    border:0,
    borderRadius:6,
    padding:'9px 18px',
    background:active ? 'var(--accent)' : 'transparent',
    color:active ? 'white' : 'var(--text-muted)',
    fontFamily:'var(--font)',
    fontSize:13,
    fontWeight:700,
    cursor:'pointer',
  }
}
