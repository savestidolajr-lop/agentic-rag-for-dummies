'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useUser } from '@clerk/nextjs'
import { useStreamingChat } from '@/hooks/useStreamingChat'
import { useApiClient } from '@/lib/api'
import { useToken } from '@/hooks/useToken'
import MessageList from './MessageList'
import ActivityPanel from './ActivityPanel'
import ChatInput from './ChatInput'
import ChatHeader from './ChatHeader'
import WelcomePanel from './WelcomePanel'

const LS_FILTER_KEY = (sid: string | null | undefined) =>
  `chat_state_filter_${sid ?? 'default'}`

interface ChatPaneProps {
  sessionId?: string
  onSessionCreated?: (sessionId: string) => void
  onTitleUpdate?: (title: string) => void
}

export default function ChatPane({ sessionId, onSessionCreated, onTitleUpdate }: ChatPaneProps) {
  const router = useRouter()
  const { user } = useUser()
  const email = user?.primaryEmailAddress?.emailAddress ?? ''
  const userName = email
    ? email.split('@')[0].replace(/[._]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : ''

  const apiFetch = useApiClient()
  const authToken = useToken()

  // Lifted state — initialize with static default to avoid SSR/hydration mismatch,
  // then read localStorage after mount
  const [stateFilter, setStateFilter] = useState('NSW')
  useEffect(() => {
    const saved = localStorage.getItem(LS_FILTER_KEY(null))
    if (saved) setStateFilter(saved)
  }, [])
  const [model, setModel] = useState('Claude Haiku 4.5')
  const [namespaces, setNamespaces] = useState<string[]>([])
  useEffect(() => {
    if (!authToken) return
    apiFetch('/api/admin/namespaces')
      .then(r => r.json())
      .then(d => setNamespaces(['All States', ...d.all]))
      .catch(() => {})
  }, [authToken]) // eslint-disable-line react-hooks/exhaustive-deps

  const {
    messages,
    activitySteps,
    narrationText,
    isStreaming,
    isReady,
    sessionId: activeSessionId,
    citedDocuments,
    suggestionOptions,
    sessionTitle,
    sendMessage,
    stopStream,
    loadSession,
    clearMessages,
    token,
  } = useStreamingChat()

  // Restore state filter when a session is loaded
  useEffect(() => {
    if (typeof window === 'undefined') return
    const sid = sessionId ?? activeSessionId
    if (!sid) return
    const saved = localStorage.getItem(LS_FILTER_KEY(sid))
    if (saved) setStateFilter(saved)
  }, [sessionId, activeSessionId])

  // Load session once token is ready
  useEffect(() => {
    if (!isReady) return
    if (sessionId) {
      loadSession(sessionId)
    } else {
      clearMessages()
    }
  }, [isReady, sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Notify parent when a new session is created
  useEffect(() => {
    if (activeSessionId && !sessionId && onSessionCreated) {
      onSessionCreated(activeSessionId)
    }
  }, [activeSessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Notify parent of title updates
  useEffect(() => {
    if (sessionTitle && onTitleUpdate) {
      onTitleUpdate(sessionTitle)
    }
  }, [sessionTitle]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleFilterChange = useCallback((value: string) => {
    setStateFilter(value)
    const sid = sessionId ?? activeSessionId
    localStorage.setItem(LS_FILTER_KEY(sid), value)
    localStorage.setItem(LS_FILTER_KEY(null), value)
  }, [sessionId, activeSessionId])

  function handleSend(message: string) {
    sendMessage(message, stateFilter, model)
  }

  function handleSuggestion(text: string) {
    sendMessage(text, stateFilter, 'Claude Haiku 4.5')
  }

  function handleNewChat() {
    router.push('/chat')
  }

  return (
    <div className="flex flex-col h-full pt-10 md:pt-0">
      {/* Top header bar */}
      <ChatHeader
        stateFilter={stateFilter}
        model={model}
        sourceCount={citedDocuments.length}
        namespaces={namespaces}
        onStateChange={handleFilterChange}
        onModelChange={setModel}
        onNewChat={handleNewChat}
      />

      {/* Messages or welcome */}
      {messages.length === 0 && !isStreaming ? (
        <WelcomePanel
          userName={userName}
          stateFilter={stateFilter}
          onPrompt={handleSend}
        />
      ) : (
        <MessageList
          messages={messages}
          isStreaming={isStreaming}
          hasActivitySteps={activitySteps.length > 0}
          activitySteps={activitySteps}
          narrationText={narrationText}
          token={token}
        />
      )}

      {/* Activity + suggestions (above input) */}
      <div className="flex flex-col gap-2 mb-2 flex-shrink-0 px-3">
        <ActivityPanel steps={activitySteps} />

        {!isStreaming && suggestionOptions.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {suggestionOptions.map((opt) => (
              <button
                key={opt}
                onClick={() => handleSuggestion(opt)}
                className="text-xs px-3 py-1.5 bg-[#1a1a1a] hover:bg-[#232323]
                           border border-[#2d2d2d] rounded-full text-[#888]
                           hover:text-[#ccc] transition-colors"
              >
                {opt}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="px-1.5 md:px-2">
        <ChatInput
          onSend={handleSend}
          onStop={stopStream}
          isStreaming={isStreaming}
          stateFilter={stateFilter}
          model={model}
        />
      </div>
    </div>
  )
}
