'use client'

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Message as MessageType } from '@/lib/types'
import { autoHighlight } from '@/lib/markdown'
import { API_BASE } from '@/lib/api'

interface MessageProps {
  message: MessageType
  isLastAssistant?: boolean
  isThinkingPhase?: boolean
  token: string | null
}

export default function Message({ message, isLastAssistant, isThinkingPhase, token }: MessageProps) {
  const [copied, setCopied] = useState(false)

  async function handleDownload(filename: string) {
    const res = await fetch(`${API_BASE}/api/download/file/${encodeURIComponent(filename)}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) return
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }
  const isUser = message.role === 'user'
  const isThinking = !isUser && (
    message.content === '' || message.content.startsWith('Thinking')
  ) && isLastAssistant

  function handleCopy() {
    const text = message.content
    const done = () => { setCopied(true); setTimeout(() => setCopied(false), 1500) }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done).catch(copyViaTextarea)
    } else {
      copyViaTextarea()
    }
    function copyViaTextarea() {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0'
      document.body.appendChild(ta)
      ta.focus()
      ta.select()
      try { document.execCommand('copy'); done() } catch {}
      document.body.removeChild(ta)
    }
  }

  if (isUser) {
    return (
      <div className="group flex flex-col items-end mb-4">
        <div className="relative max-w-[85%] md:max-w-[75%]">
          <div className="bg-[#1d4ed8] rounded-2xl rounded-tr-sm
                          px-4 py-3 text-sm text-white whitespace-pre-wrap break-words">
            {message.content}
          </div>
          <button
            onClick={handleCopy}
            className="absolute -bottom-5 right-1 opacity-0 group-hover:opacity-100
                       transition-opacity text-xs text-[#555] hover:text-[#888] px-1 py-0.5"
            aria-label="Copy message"
          >
            {copied ? '✓ Copied' : '⧉ Copy'}
          </button>
        </div>
        {message.timestamp && (
          <span className="text-[10px] text-[#444] mt-6 mr-1">{message.timestamp}</span>
        )}
      </div>
    )
  }

  if (isThinking) {
    return (
      <div className="flex items-start gap-2.5 mb-4">
        <div className="w-7 h-7 rounded-full bg-[#10a37f] flex items-center justify-center
                        text-white text-[10px] font-bold flex-shrink-0 mt-0.5">
          CA
        </div>
        <div className="bg-[#161616] rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-[#555]">
          Thinking
          <span className="thinking-dot">.</span>
          <span className="thinking-dot">.</span>
          <span className="thinking-dot">.</span>
        </div>
      </div>
    )
  }

  const processedContent = autoHighlight(message.content)
  const sources = message.citedDocuments ?? []

  return (
    <div className="group flex items-start gap-2.5 mb-4">
      {/* CA avatar */}
      <div className="w-7 h-7 rounded-full bg-[#10a37f] flex items-center justify-center
                      text-white text-[10px] font-bold flex-shrink-0 mt-0.5">
        CA
      </div>

      <div className="flex flex-col flex-1 min-w-0">
        {/* Message bubble */}
        <div className="relative max-w-[95%] md:max-w-[90%]">
          {isThinkingPhase && (
            <div className="flex items-center gap-1.5 mb-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#10a37f] animate-pulse" />
              <span className="text-[10px] text-[#555]">Agent thinking…</span>
            </div>
          )}
          <div className={`rounded-2xl rounded-tl-sm px-4 py-3 text-sm ${
            isThinkingPhase
              ? 'bg-[#0f0f0f] border border-[#1a1a1a] text-[#555] italic'
              : 'bg-[#161616]'
          }`}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              className="prose prose-sm prose-invert"
            >
              {processedContent}
            </ReactMarkdown>
            {isLastAssistant && !isThinkingPhase && (
              <span className="inline-block w-0.5 h-3.5 bg-[#10a37f] ml-0.5 align-middle animate-pulse" />
            )}
          </div>
          {/* Copy button */}
          <button
            onClick={handleCopy}
            className="absolute -bottom-5 left-1 opacity-0 group-hover:opacity-100
                       transition-opacity text-xs text-[#555] hover:text-[#888] px-1 py-0.5"
            aria-label="Copy message"
          >
            {copied ? '✓ Copied' : '⧉ Copy'}
          </button>
        </div>

        {/* Timestamp */}
        {message.timestamp && (
          <span className="text-[10px] text-[#444] mt-6 ml-1">{message.timestamp}</span>
        )}

        {/* Source chips */}
        {sources.length > 0 && (
          <div className="mt-2">
            <span className="text-[10px] text-[#555] mb-1.5 block">Sources retrieved</span>
            <div className="flex flex-wrap gap-1.5">
              {sources.map((f, i) => {
                const short = f.length > 30 ? f.slice(0, 28) + '…' : f
                return (
                  <button
                    key={f}
                    onClick={() => handleDownload(f)}
                    className="flex items-center gap-1.5 bg-[#1a1a1a] border border-[#2a2a2a]
                               rounded-lg px-2.5 py-1 text-[11px] text-[#888]
                               hover:border-[#444] hover:text-[#ccc] transition-colors cursor-pointer"
                  >
                    <span className="w-4 h-4 rounded bg-[#252525] flex items-center justify-center
                                     text-[9px] font-bold text-[#666] flex-shrink-0">
                      {i + 1}
                    </span>
                    <span className="truncate max-w-[160px]">{short}</span>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
