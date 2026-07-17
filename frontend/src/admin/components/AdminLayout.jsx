import { useLocation, useNavigate } from 'react-router-dom'

import { ADMIN_NAVIGATION } from '../config/navigation'
import AdminHeader, { HEADER_H } from './AdminHeader'
import AdminSidebar from './AdminSidebar'

export default function AdminLayout({ title, breadcrumbs, children, onLogout }) {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <div style={{ fontFamily:'var(--font)', fontSize:14, color:'var(--text)', background:'var(--bg)', height:'100vh', overflow:'hidden', display:'flex', flexDirection:'column' }}>
      <AdminHeader title={title} />
      <div style={{ display:'flex', marginTop:HEADER_H, height:`calc(100vh - ${HEADER_H}px)`, overflow:'hidden' }}>
        <AdminSidebar
          navigation={ADMIN_NAVIGATION}
          pathname={location.pathname}
          onNavigate={path => navigate(path)}
          onLogout={onLogout}
        />
        <main style={{ flex:1, overflow:'hidden', display:'flex', flexDirection:'column' }}>
          <div style={{ padding:'8px 24px', display:'flex', alignItems:'center', gap:6, fontSize:12, color:'var(--text-muted)', borderBottom:'1px solid var(--border)', background:'var(--card)', flexShrink:0 }}>
            {breadcrumbs.map((crumb, index) => (
              <span key={`${crumb}-${index}`} style={{ display:'flex', alignItems:'center', gap:6 }}>
                {index > 0 && <span style={{ color:'var(--text-light)' }}>›</span>}
                <span style={{ color:index === breadcrumbs.length - 1 ? 'var(--text)' : 'var(--text-muted)', fontWeight:index === breadcrumbs.length - 1 ? 600 : 400 }}>{crumb}</span>
              </span>
            ))}
          </div>
          <div style={{ flex:1, overflowY:'auto', padding:24 }}>
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
