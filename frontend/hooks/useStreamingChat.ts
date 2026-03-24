'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import { useUser, useAuth } from '@clerk/nextjs'
import { Message, StreamEvent } from '@/lib/types'
import { API_BASE } from '@/lib/api'
import { useToken } from '@/hooks/useToken'

function now() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function useStreamingChat() {
  const token = useToken()
  const { getToken } = useAuth()
  const { user } = useUser()
  const email = user?.primaryEmailAddress?.emailAddress ?? ''
  const userName = email
    ? email.split('@')[0].replace(/[._]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : ''
  const userNameRef = useRef(userName)
  useEffect(() => { userNameRef.current = userName }, [userName])
  // Always keep a ref to the latest token so sendMessage uses it at call-time,
  // not the stale value captured when the callback was last created.
  const tokenRef = useRef<string | null>(token)
  useEffect(() => { tokenRef.current = token }, [token])
  const [messages, setMessages] = useState<Message[]>([])
  const [activitySteps, setActivitySteps] = useState<string[]>([])
  const [narrationText, setNarrationText] = useState<string>('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [citedDocuments, setCitedDocuments] = useState<string[]>([])
  const [suggestionOptions, setSuggestionOptions] = useState<string[]>([])
  const [sessionTitle, setSessionTitle] = useState<string>('')
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    async (message: string, stateFilter: string | null, model: string) => {
      if (!message.trim() || isStreaming || !tokenRef.current) return

      abortRef.current = new AbortController()

      setIsStreaming(true)
      setCitedDocuments([])
      setSuggestionOptions([])
      setActivitySteps([])
      setNarrationText('')

      setMessages((prev) => [...prev, { role: 'user', content: message.trim(), timestamp: now() }])

      const MAX_ATTEMPTS = 2
      let attempt = 0
      let assistantAdded = false

      while (attempt < MAX_ATTEMPTS) {
        attempt++
        try {
          const res = await fetch(`${API_BASE}/api/chat/stream`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(tokenRef.current ? { Authorization: `Bearer ${tokenRef.current}` } : {}),
            },
            body: JSON.stringify({
              message: message.trim(),
              session_id: sessionId,
              state_filter: stateFilter && stateFilter !== 'All States' ? stateFilter : null,
              model,
              user_name: userNameRef.current || undefined,
            }),
            signal: abortRef.current.signal,
          })

          if (!res.ok || !res.body) {
            throw new Error(`HTTP ${res.status}`)
          }

          const reader = res.body.getReader()
          const decoder = new TextDecoder()
          let buffer = ''

          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            buffer += decoder.decode(value, { stream: true })
            const blocks = buffer.split('\n\n')
            buffer = blocks.pop() ?? ''

            for (const block of blocks) {
              const lines = block.split('\n')
              const eventLine = lines.find((l) => l.startsWith('event:'))
              const dataLine = lines.find((l) => l.startsWith('data:'))
              if (!eventLine || !dataLine) continue

              const eventType = eventLine.slice(6).trim()
              let data: StreamEvent

              try {
                data = { type: eventType, ...JSON.parse(dataLine.slice(5)) } as StreamEvent
              } catch {
                continue
              }

              if (data.type === 'activity') {
                setActivitySteps(data.steps)
              } else if (data.type === 'narration') {
                setNarrationText(data.text)
              } else if (data.type === 'token') {
                if (data.session_id && !sessionId) setSessionId(data.session_id)
                setNarrationText('')
                const text = data.text
                if (!assistantAdded) {
                  setMessages((prev) => [...prev, { role: 'assistant', content: text }])
                  assistantAdded = true
                } else {
                  setMessages((prev) => {
                    const next = [...prev]
                    next[next.length - 1] = { role: 'assistant', content: text }
                    return next
                  })
                }
              } else if (data.type === 'done') {
                if (data.session_id) setSessionId(data.session_id)
                if (data.title) setSessionTitle(data.title)
                const cited = data.cited_documents || []
                setCitedDocuments(cited)
                setSuggestionOptions(data.options || [])
                setActivitySteps([])
                setNarrationText('')
                setIsStreaming(false)
                if (cited.length > 0) {
                  setMessages((prev) => {
                    const next = [...prev]
                    const lastIdx = next.length - 1
                    if (next[lastIdx]?.role === 'assistant') {
                      next[lastIdx] = { ...next[lastIdx], citedDocuments: cited, timestamp: now() }
                    }
                    return next
                  })
                } else {
                  setMessages((prev) => {
                    const next = [...prev]
                    const lastIdx = next.length - 1
                    if (next[lastIdx]?.role === 'assistant') {
                      next[lastIdx] = { ...next[lastIdx], timestamp: now() }
                    }
                    return next
                  })
                }
              } else if (data.type === 'error') {
                setNarrationText('')
                setMessages((prev) => [
                  ...prev,
                  { role: 'assistant', content: `❌ ${data.message}`, timestamp: now() },
                ])
                setIsStreaming(false)
              }
            }
          }
          break // stream completed successfully — exit retry loop

        } catch (err: unknown) {
          if (err instanceof Error && err.name === 'AbortError') break

          // On 401, force-refresh the Clerk token before retrying.
          // This handles the case where the JWT expired after a long idle period.
          if (err instanceof Error && err.message === 'HTTP 401') {
            const fresh = await getToken({ skipCache: true }).catch(() => null)
            if (fresh) tokenRef.current = fresh
          }

          // Only retry if no content was received yet (clean reconnect)
          if (!assistantAdded && attempt < MAX_ATTEMPTS) {
            setNarrationText('Reconnecting…')
            await new Promise((r) => setTimeout(r, 1000))
            setNarrationText('')
            setActivitySteps([])
            continue
          }

          // Final failure — show appropriate error
          setNarrationText('')
          setActivitySteps([])
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: assistantAdded
                ? '❌ Connection lost mid-response. Please continue in a new message.'
                : '❌ Connection error. Please try again.',
              timestamp: now(),
            },
          ])
          break
        }
      }

      setIsStreaming(false)
      setActivitySteps([])
      setNarrationText('')
    },
    [isStreaming, sessionId, getToken]
  )

  const stopStream = useCallback(() => {
    abortRef.current?.abort()
    setIsStreaming(false)
    setActivitySteps([])
    setNarrationText('')
    if (sessionId && token) {
      fetch(`${API_BASE}/api/chat/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ session_id: sessionId }),
      }).catch(() => {})
    }
  }, [token, sessionId])

  const loadSession = useCallback(
    async (sid: string) => {
      if (!token) return
      try {
        const res = await fetch(`${API_BASE}/api/sessions/${sid}/messages`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) return
        const data = await res.json()
        setMessages(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (data.messages as any[])
            .filter((m) => m.content !== '__PENDING__')
            .map((m) => ({
              role: m.role,
              content: m.content,
              citedDocuments: m.cited_documents?.length ? m.cited_documents : undefined,
            } as Message))
        )
        setSessionId(sid)
        setCitedDocuments([])
        setSuggestionOptions([])
        setActivitySteps([])
        setSessionTitle('')
      } catch {}
    },
    [token]
  )

  const clearMessages = useCallback(() => {
    setMessages([])
    setSessionId(null)
    setCitedDocuments([])
    setSuggestionOptions([])
    setActivitySteps([])
    setSessionTitle('')
  }, [])

  return {
    messages,
    activitySteps,
    narrationText,
    isStreaming,
    isReady: !!token,
    token,
    sessionId,
    citedDocuments,
    suggestionOptions,
    sessionTitle,
    sendMessage,
    stopStream,
    loadSession,
    clearMessages,
    setSessionId,
  }
}
