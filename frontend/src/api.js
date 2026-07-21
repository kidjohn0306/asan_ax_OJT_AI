const API = ''

export function apiErrorMessage(payload, status) {
  const detail = payload?.detail
  if (typeof detail === 'string' && detail) return detail
  if (detail && typeof detail === 'object' && typeof detail.message === 'string' && detail.message) {
    return detail.message
  }
  return `HTTP ${status}`
}

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
  if (res.status === 401) {
    sessionStorage.clear()
    sessionStorage.setItem('popup_msg', '세션이 만료되었습니다.\n다시 로그인해주세요.')
    window.location.replace('/login')
    return
  }
  if (res.status === 403) {
    sessionStorage.clear()
    sessionStorage.setItem('popup_msg', '관리자 권한이 없습니다.\n접근이 차단되었습니다.')
    window.location.replace('/login')
    return
  }
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(apiErrorMessage(err, res.status))
  }
  return res.json()
}

export async function apiUpload(path, formData) {
  const token = sessionStorage.getItem('token')
  const res = await fetch(API + path, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  })
  if (res.status === 401) {
    sessionStorage.clear()
    sessionStorage.setItem('popup_msg', '세션이 만료되었습니다.\n다시 로그인해주세요.')
    window.location.replace('/login')
    return
  }
  if (res.status === 403) {
    sessionStorage.clear()
    sessionStorage.setItem('popup_msg', '관리자 권한이 없습니다.\n접근이 차단되었습니다.')
    window.location.replace('/login')
    return
  }
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(apiErrorMessage(err, res.status))
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
