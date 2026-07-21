const SIDEBAR_W = 220
const HEADER_H = 56

export { HEADER_H, SIDEBAR_W }

export default function AdminHeader({ title }) {
  const adminName = sessionStorage.getItem('name') || '관리자'
  return (
    <header style={{ position:'fixed', top:0, left:0, right:0, zIndex:100, height:HEADER_H, background:'var(--card)', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', padding:'0 24px 0 0' }}>
      <div style={{ width:SIDEBAR_W, padding:'0 18px', display:'flex', alignItems:'center', gap:10, borderRight:'1px solid var(--border)', height:'100%', flexShrink:0 }}>
        <img src="/favicon-32x32.png" alt="(주)엑스티" style={{ width:30, height:30, borderRadius:7, flexShrink:0 }} />
        <div>
          <div style={{ fontSize:12, fontWeight:700, color:'var(--text)', lineHeight:1.2 }}>(주)엑스티</div>
          <div style={{ fontSize:10, color:'var(--text-muted)', lineHeight:1.2 }}>OJT 평가 시스템</div>
        </div>
      </div>
      <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'space-between', padding:'0 24px' }}>
        <span style={{ fontSize:16, fontWeight:700, color:'var(--text)' }}>{title}</span>
        <div style={{ display:'flex', alignItems:'center', gap:12 }}>
          <div style={{ width:32, height:32, background:'var(--accent)', borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', color:'white', fontSize:13, fontWeight:700 }}>{adminName[0]}</div>
          <div>
            <div style={{ fontSize:13, fontWeight:700, color:'var(--text)', lineHeight:1.2 }}>{adminName}</div>
            <div style={{ fontSize:11, color:'var(--text-muted)', lineHeight:1.2 }}>관리자</div>
          </div>
        </div>
      </div>
    </header>
  )
}
