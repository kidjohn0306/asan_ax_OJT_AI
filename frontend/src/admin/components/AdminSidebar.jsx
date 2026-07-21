import { SIDEBAR_W } from './AdminHeader'
import { adminPathToLegacyView } from '../config/navigation'

const ICON_BY_VIEW = {
  dashboard: 'grid',
  'q-generate': 'ai',
  'q-review': 'check',
  'q-bank': 'book',
  'exam-sheet': 'file',
  'exam-assign': 'users',
  'exam-status': 'chart',
  history: 'clock',
  results: 'chart',
  users: 'users',
  teams: 'users',
  settings: 'settings',
}

function SidebarIcon({ name, size = 16, style }) {
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></>,
    clock: <><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></>,
    book: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></>,
    users: <><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/></>,
    chart: <><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33A1.65 1.65 0 0 0 14 20.83V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15 1.65 1.65 0 0 0 3.17 14H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68 1.65 1.65 0 0 0 10 3.17V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.12.6.65 1 1.26 1H21a2 2 0 0 1 0 4h-.09A1.65 1.65 0 0 0 19.4 15z"/></>,
    ai: <><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></>,
    check: <><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></>,
    logout: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></>,
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" style={style} aria-hidden="true">
      {paths[name]}
    </svg>
  )
}

function itemPathname(path) {
  return path.split('?')[0]
}

function currentNavigationItem(navigation, pathname) {
  const items = navigation.flatMap(group => group.items)
  const exactItem = items.find(item => itemPathname(item.path) === pathname)
  if (exactItem) return exactItem

  const currentView = adminPathToLegacyView(pathname)
  return items.find(item => item.view === currentView)
}

export default function AdminSidebar({ navigation, pathname, onNavigate, onLogout }) {
  const adminName = sessionStorage.getItem('name') || '관리자'

  function handleNavigation(event, path) {
    if (!onNavigate || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    onNavigate(path)
  }

  const currentItem = currentNavigationItem(navigation, pathname)

  return (
    <nav aria-label="관리자 메뉴" style={{ width:SIDEBAR_W, background:'var(--primary)', flexShrink:0, display:'flex', flexDirection:'column', overflowY:'auto', overflowX:'hidden' }}>
      <div style={{ padding:'10px 0', flex:1 }}>
        <div style={{ padding:'10px 18px 4px', fontSize:9, fontWeight:700, letterSpacing:'.10em', color:'rgba(255,255,255,.22)', textTransform:'uppercase' }}>메뉴</div>
        {navigation.map(group => (
          <div key={group.label}>
            {group.label !== '대시보드' && (
              <div style={{ display:'flex', alignItems:'center', gap:9, padding:'9px 18px 5px', color:'rgba(255,255,255,.60)', fontSize:13, fontWeight:600 }}>
                <SidebarIcon name={ICON_BY_VIEW[group.items[0]?.view] || 'settings'} size={15} style={{ opacity:.65 }} />
                <span>{group.label}</span>
              </div>
            )}
            <div style={group.label === '대시보드' ? undefined : { background:'rgba(0,0,0,.15)' }}>
              {group.items.map(item => {
                const active = item === currentItem
                const nested = group.label !== '대시보드'
                return (
                  <a
                    key={`${item.path}-${item.label}`}
                    href={item.path}
                    aria-current={active ? 'page' : undefined}
                    onClick={event => handleNavigation(event, item.path)}
                    style={{ display:'flex', alignItems:'center', gap:8, padding: nested ? '8px 18px 8px 40px' : '9px 18px', color:active ? 'white' : 'rgba(255,255,255,.55)', cursor:'pointer', fontSize:nested ? 12.5 : 13, borderLeft:`2px solid ${active ? 'var(--accent)' : 'transparent'}`, background:active ? 'rgba(255,255,255,.08)' : 'transparent', fontWeight:active ? 600 : 400, textDecoration:'none' }}
                  >
                    <SidebarIcon name={ICON_BY_VIEW[item.view] || 'settings'} size={nested ? 13 : 15} style={{ opacity:active ? 1 : .55 }} />
                    {item.label}
                  </a>
                )
              })}
            </div>
          </div>
        ))}
      </div>
      <div style={{ borderTop:'1px solid rgba(255,255,255,.07)', padding:'14px 16px' }}>
        <div style={{ display:'flex', alignItems:'center', gap:12, padding:'8px 4px 14px' }}>
          <div style={{ width:40, height:40, background:'var(--accent)', borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', color:'white', fontSize:16, fontWeight:700, flexShrink:0 }}>{adminName[0]}</div>
          <div style={{ overflow:'hidden' }}>
            <div style={{ fontSize:15, fontWeight:700, color:'rgba(255,255,255,.88)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{adminName}</div>
            <div style={{ fontSize:11, color:'rgba(255,255,255,.35)', marginTop:2 }}>관리자</div>
          </div>
        </div>
        <button onClick={onLogout} style={{ width:'100%', background:'rgba(255,255,255,.07)', border:'1px solid rgba(255,255,255,.10)', borderRadius:7, padding:'9px 10px', fontFamily:'var(--font)', fontSize:13, color:'rgba(255,255,255,.55)', cursor:'pointer', display:'flex', alignItems:'center', gap:7 }}>
          <SidebarIcon name="logout" size={14} style={{ color:'rgba(255,255,255,.5)' }} /> 로그아웃
        </button>
      </div>
    </nav>
  )
}
