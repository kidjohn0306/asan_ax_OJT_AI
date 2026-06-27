import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const styles = {
  body: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'var(--bg)',
    fontFamily: 'var(--font)',
  },
  wrap: { width: '100%', maxWidth: 420, padding: 16 },
  logoArea: { textAlign: 'center', marginBottom: 32 },
  company: { fontSize: 22, fontWeight: 700, color: 'var(--primary)' },
  system: { fontSize: 14, color: 'var(--text-muted)', marginTop: 4 },
  card: {
    background: 'white',
    borderRadius: 12,
    padding: '36px 32px',
    boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
  },
  cardTitle: { fontSize: 18, fontWeight: 700, color: 'var(--text)', marginBottom: 24 },
  label: { display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 6 },
  input: {
    width: '100%',
    padding: '10px 14px',
    border: '1px solid var(--border)',
    borderRadius: 8,
    fontSize: 14,
    color: 'var(--text)',
    outline: 'none',
    marginBottom: 16,
    fontFamily: 'var(--font)',
  },
  errorMsg: {
    fontSize: 12,
    color: 'var(--danger)',
    marginTop: -12,
    marginBottom: 12,
    padding: '8px 12px',
    background: '#fee2e2',
    borderRadius: 6,
  },
  btnLogin: {
    width: '100%',
    padding: 12,
    background: 'var(--accent)',
    color: 'white',
    border: 'none',
    borderRadius: 8,
    fontSize: 15,
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: 8,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    fontFamily: 'var(--font)',
  },
  notice: {
    marginTop: 20,
    padding: '12px 16px',
    background: '#eff6ff',
    borderRadius: 8,
    borderLeft: '3px solid var(--accent)',
    fontSize: 12,
    color: 'var(--text-muted)',
    lineHeight: 1.6,
  },
  footerNote: { textAlign: 'center', marginTop: 24, fontSize: 12, color: 'var(--text-muted)' },
  spinner: {
    width: 16,
    height: 16,
    border: '2px solid rgba(255,255,255,0.4)',
    borderTopColor: 'white',
    borderRadius: '50%',
    animation: 'spin 0.7s linear infinite',
  },
}

export default function Login() {
  const navigate = useNavigate()
  const [empId, setEmpId] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleLogin(e) {
    e.preventDefault()
    setError('')
    if (!empId || !password) {
      setError('사원번호와 비밀번호를 입력해주세요.')
      return
    }
    setLoading(true)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ employee_id: empId, password }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        setError(err.detail || '로그인에 실패했습니다.')
        return
      }
      const data = await res.json()
      sessionStorage.setItem('token', data.token)
      sessionStorage.setItem('name', data.name)
      sessionStorage.setItem('team', data.team || '')
      sessionStorage.setItem('role', data.role)
      sessionStorage.setItem('emp_id', empId)

      if (data.role === 'admin') {
        navigate('/admin')
      } else {
        navigate('/exam')
      }
    } catch {
      setError('서버에 연결할 수 없습니다. 백엔드 서버가 실행 중인지 확인하세요.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.body}>
      <div style={styles.wrap}>
        <div style={styles.logoArea}>
          <div style={styles.company}>(주)엑스티</div>
          <div style={styles.system}>OJT 평가 시스템</div>
        </div>
        <div style={styles.card}>
          <h2 style={styles.cardTitle}>로그인</h2>
          <form onSubmit={handleLogin}>
            <label style={styles.label}>사원번호</label>
            <input
              style={styles.input}
              type="text"
              value={empId}
              onChange={e => setEmpId(e.target.value)}
              placeholder="사원번호를 입력하세요"
              autoComplete="off"
            />
            <label style={styles.label}>비밀번호</label>
            <input
              style={styles.input}
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="비밀번호를 입력하세요"
            />
            {error && <p style={styles.errorMsg}>{error}</p>}
            <button
              type="submit"
              style={{ ...styles.btnLogin, opacity: loading ? 0.6 : 1, cursor: loading ? 'not-allowed' : 'pointer' }}
              disabled={loading}
            >
              {loading && <span style={styles.spinner} />}
              <span>{loading ? '로그인 중...' : '로그인'}</span>
            </button>
          </form>
          <div style={styles.notice}>
            ※ 관리자가 사전 승인한 신입사원만 응시 가능합니다.<br />
            ※ 로그인 문제는 인사팀에 문의하세요.<br />
            ※ 시험 종료 후 모든 응시 데이터는 자동 삭제됩니다.
          </div>
        </div>
        <div style={styles.footerNote}>보안 문의: 인사팀 내선 000</div>
      </div>
    </div>
  )
}
