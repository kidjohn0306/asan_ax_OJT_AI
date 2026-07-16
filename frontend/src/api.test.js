import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from './api'

describe('apiFetch error detail normalization', () => {
  beforeEach(() => {
    sessionStorage.setItem('token', 'admin-token')
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    sessionStorage.clear()
    vi.unstubAllGlobals()
  })

  it('uses the actual structured policy message instead of object stringification', async () => {
    fetch.mockResolvedValue(new Response(JSON.stringify({
      detail:{ code:'EXAM_POLICY_ERROR', message:'실제 정책 오류' },
    }), { status:409, headers:{ 'Content-Type':'application/json' } }))

    await expect(apiFetch('POST', '/api/admin/exam-sets/EX-1/assign', { employee_id:'E1' }))
      .rejects.toThrow('실제 정책 오류')
  })

  it('preserves string detail errors', async () => {
    fetch.mockResolvedValue(new Response(JSON.stringify({ detail:'문자열 오류' }), {
      status:400,
      headers:{ 'Content-Type':'application/json' },
    }))

    await expect(apiFetch('GET', '/api/admin/example')).rejects.toThrow('문자열 오류')
  })

  it('uses an HTTP fallback for a non-JSON error response', async () => {
    fetch.mockResolvedValue(new Response('gateway unavailable', { status:502 }))

    await expect(apiFetch('GET', '/api/admin/example')).rejects.toThrow('HTTP 502')
  })
})
