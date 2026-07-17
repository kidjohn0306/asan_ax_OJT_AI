import { useLocation } from 'react-router-dom'

function Unavailable() {
  return (
    <div style={{ background:'var(--card)', border:'1px solid var(--border)', borderRadius:10, padding:32, textAlign:'center' }}>
      <p style={{ margin:'0 0 16px', color:'var(--text-muted)', fontSize:14 }}>현재 API에서 제공되지 않는 기능입니다</p>
      <a href="/admin/system/status" style={{ color:'var(--accent)', fontWeight:700, textDecoration:'none' }}>돌아가기</a>
    </div>
  )
}

export default function SystemRoutePage({
  UsersComponent,
  TeamsComponent,
  MaterialsComponent,
  StatusComponent,
  AuditLogComponent,
  toast,
}) {
  const { pathname } = useLocation()

  if (pathname === '/admin/system/audit-logs') {
    return AuditLogComponent ? <AuditLogComponent toast={toast} /> : <Unavailable />
  }
  if (pathname === '/admin/employees') return <UsersComponent toast={toast} />
  if (pathname === '/admin/teams') return <TeamsComponent toast={toast} />
  if (pathname === '/admin/materials') return <MaterialsComponent toast={toast} />
  return <StatusComponent />
}
