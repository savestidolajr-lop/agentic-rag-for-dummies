'use client'

import useSWR from 'swr'
import { useCallback } from 'react'
import { Session } from '@/lib/types'
import { API_BASE } from '@/lib/api'
import { useToken } from '@/hooks/useToken'

export function useSessions() {
  const token = useToken()

  const fetcher = useCallback(
    async (url: string) => {
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) throw new Error('Failed to fetch sessions')
      return res.json()
    },
    [token]
  )

  // Only fetch once we have a real token — passing null key tells SWR to skip
  const { data, error, isLoading, mutate } = useSWR<{ sessions: Session[] }>(
    token ? `${API_BASE}/api/sessions` : null,
    fetcher,
    { revalidateOnFocus: false, revalidateOnReconnect: false }
  )

  const createSession = useCallback(async (): Promise<string | null> => {
    if (!token) return null
    try {
      const res = await fetch(`${API_BASE}/api/sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      })
      if (!res.ok) return null
      const data = await res.json()
      mutate()
      return data.session_id
    } catch {
      return null
    }
  }, [token, mutate])

  const deleteSession = useCallback(
    async (sessionId: string): Promise<boolean> => {
      if (!token) return false
      try {
        const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
          method: 'DELETE',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        })
        if (!res.ok) return false
        mutate()
        return true
      } catch {
        return false
      }
    },
    [token, mutate]
  )

  return {
    sessions: data?.sessions ?? [],
    isLoading,
    error,
    mutate,
    createSession,
    deleteSession,
  }
}
