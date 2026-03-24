'use client'

import { useEffect, useRef, useState } from 'react'
import { useAuth } from '@clerk/nextjs'

/**
 * Eagerly fetches and caches the Clerk session token.
 * Returns the token string once available, null while loading.
 *
 * Clerk v6's getToken() can return null or throw briefly during hydration
 * even after isLoaded/isSignedIn are true. This hook retries until it gets
 * a real token, then refreshes it before it expires.
 */
export function useToken(): string | null {
  const { getToken, isLoaded, isSignedIn } = useAuth()
  const [token, setToken] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return

    let cancelled = false

    async function fetchToken() {
      let attempt = 0
      while (!cancelled) {
        try {
          const t = await getToken()
          if (t) {
            if (!cancelled) setToken(t)
            if (!cancelled) {
              // Schedule next refresh 30s before actual token expiry.
              // Decoding the JWT exp claim handles any token lifetime
              // (Clerk dev tokens expire in 60s, production tokens in 60min).
              let refreshIn = 55 * 60 * 1000 // safe fallback
              try {
                const payload = JSON.parse(atob(t.split('.')[1]))
                if (payload.exp) {
                  refreshIn = Math.max(5000, payload.exp * 1000 - Date.now() - 30000)
                }
              } catch { /* use fallback */ }
              timerRef.current = setTimeout(fetchToken, refreshIn)
            }
            return
          }
        } catch {
          // token not ready yet
        }
        attempt++
        // Exponential back-off: 100, 200, 400, 800, 1600 ms, then 2 s
        await new Promise((r) =>
          setTimeout(r, Math.min(100 * Math.pow(2, attempt), 2000))
        )
      }
    }

    fetchToken()

    return () => {
      cancelled = true
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [isLoaded, isSignedIn, getToken])

  return token
}
