'use client'

import { useCallback, useEffect, useRef } from 'react'
import { useToken } from '@/hooks/useToken'

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || ''

export function useApiClient() {
  const token = useToken()

  // Keep a ref so apiFetch always reads the latest token without needing to
  // recreate the function on every token change. This prevents stale-closure
  // 401s that occur when a caller holds a reference to an old apiFetch.
  const tokenRef = useRef<string | null>(token)
  useEffect(() => {
    tokenRef.current = token
  }, [token])

  const apiFetch = useCallback(
    async (path: string, options: RequestInit = {}): Promise<Response> => {
      const t = tokenRef.current
      // Hard-guard: never fire a request without a token
      if (!t) throw new Error('Not authenticated — token not yet available')
      const isFormData = options.body instanceof FormData
      return fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
          ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
          Authorization: `Bearer ${t}`,
          ...(options.headers || {}),
        },
      })
    },
    [] // stable reference — reads token from ref at call time
  )

  return apiFetch
}

/** One-shot fetch with an explicit token (for streaming / non-hook contexts) */
export async function apiFetchWithToken(
  path: string,
  token: string | null,
  options: RequestInit = {}
): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  })
}
