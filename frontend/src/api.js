const API = ''

export async function apiFetch(method, path, body = null) {
  const token = sessionStorage.getItem('token')
  const opts = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  }
  if (body) opts.body = JSON.stringify(body)
  const res = await fetch(API + path, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(err.detail)
  }
  return res.json()
}

export async function logout(navigate) {
  const token = sessionStorage.getItem('token')
  if (token) {
    await fetch('/api/auth/logout', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {})
  }
  sessionStorage.clear()
  navigate('/login')
}
