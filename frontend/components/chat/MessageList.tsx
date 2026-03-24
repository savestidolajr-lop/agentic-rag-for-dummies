'use client'

import { useEffect, useRef } from 'react'
import { Message as MessageType } from '@/lib/types'
import Message from './Message'

interface MessageListProps {
  messages: MessageType[]
  isStreaming: boolean
  hasActivitySteps: boolean
  activitySteps: string[]
  narrationText: string
  token: string | null
}

export default function MessageList({ messages, isStreaming, hasActivitySteps, activitySteps, narrationText, token }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming, activitySteps])

  if (!messages.length) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 px-4 text-center">
        <div className="text-4xl">⚖️</div>
        <h2 className="text-lg font-semibold text-white">Case Agent</h2>
        <p className="text-sm text-[#555] max-w-xs">
          Ask me anything about your legal documents.
        </p>
      </div>
    )
  }

  const lastAssistantIndex = messages.reduce(
    (acc, m, i) => (m.role === 'assistant' ? i : acc),
    -1
  )

  const lastMessage = messages[messages.length - 1]
  // Show agent bubble when streaming but no assistant message yet
  const showAgentBubble = isStreaming && lastMessage?.role === 'user'
  const latestStep = activitySteps[activitySteps.length - 1] ?? ''
  const stepText = latestStep.endsWith('...') ? latestStep.slice(0, -3) : latestStep
  // Prefer live narration text; fall back to latest activity step
  const bubbleText = narrationText || stepText

  return (
    <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
      {messages.map((m, i) => (
        <Message
          key={i}
          message={m}
          isLastAssistant={i === lastAssistantIndex && isStreaming}
          isThinkingPhase={i === lastAssistantIndex && isStreaming && hasActivitySteps}
          token={token}
        />
      ))}

      {showAgentBubble && (
        <div className="flex items-start gap-2.5 mb-4">
          <div className="w-7 h-7 rounded-full bg-[#10a37f] flex items-center justify-center
                          text-white text-[10px] font-bold flex-shrink-0 mt-0.5">
            CA
          </div>
          <div className="bg-[#0f0f0f] border border-[#1a1a1a] rounded-2xl rounded-tl-sm px-4 py-3 text-sm">
            {bubbleText ? (
              <span className="text-[#555] italic">{bubbleText}</span>
            ) : (
              <span className="text-[#555]">
                Thinking
                <span className="thinking-dot">.</span>
                <span className="thinking-dot">.</span>
                <span className="thinking-dot">.</span>
              </span>
            )}
          </div>
        </div>
      )}

      <div ref={bottomRef} className="h-8" />
    </div>
  )
}
