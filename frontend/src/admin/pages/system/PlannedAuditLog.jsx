import { useEffect, useState } from 'react'
import { apiFetch } from '../../../api'
import '../questions/PlannedQuestionPages.css'

const actionLabel = action => ({ APPROVE_QUESTION:'문제 승인', REJECT_QUESTION:'문제 반려', EDIT_QUESTION:'문제 수정', SET_QUESTION_STATUS:'상태 변경', EXAM_EXIT:'응시 중 이탈' }[action] || action || '-')

function Header({ title, description }) { return <div className="qplan-head"><div><h1>{title}</h1><p>{description}</p></div></div> }
function Card({ children }) { return <section className="qplan-card"><div className="qplan-card-body">{children}</div></section> }

export default function PlannedAuditLog({ toast }) {
  const [data, setData] = useState({ logs: [], enabled: true })
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let active = true
    setLoading(true)
    apiFetch('GET', '/api/admin/audit-logs')
      .then(result => { if (active) setData(result || { logs: [], enabled: true }) })
      .catch(error => toast(`감사 로그 조회 실패: ${error.message}`, 'error'))
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [])
  const logs = data.logs || []
  return (
    <section className="qplan">
      <Header title="감사 로그" description="관리자 행동(문제 승인·반려 등)과 응시자 이탈(탭 전환·뒤로가기 등)의 실제 기록을 확인합니다." />
      <Card>
        {loading ? (
          <div className="qplan-empty">불러오는 중…</div>
        ) : !data.enabled ? (
          <div className="qplan-empty">감사 로그 저장소가 비활성화되어 있습니다.</div>
        ) : logs.length === 0 ? (
          <div className="qplan-empty">아직 기록된 감사 로그가 없습니다.</div>
        ) : (
          <div className="qplan-table-wrap">
            <table>
              <thead>
                <tr><th>시각</th><th>수행자</th><th>행동</th><th>대상</th><th>사유</th></tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.audit_id}>
                    <td>{log.created_at || '-'}</td>
                    <td>{log.actor_id || '-'}</td>
                    <td>{actionLabel(log.action_type)}</td>
                    <td>{log.target_type ? `${log.target_type}:${log.target_id}` : log.target_id || '-'}</td>
                    <td>{log.reason || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </section>
  )
}
