'use client'

import { useState, useRef, useEffect } from 'react'

interface ChatInputProps {
  onSend: (message: string) => void
  onStop: () => void
  isStreaming: boolean
  disabled?: boolean
  stateFilter: string
  model: string
}

export default function ChatInput({ onSend, onStop, isStreaming, disabled, stateFilter, model }: ChatInputProps) {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const placeholder = stateFilter && stateFilter !== 'All States'
    ? `Ask anything about ${stateFilter} construction law…`
    : 'Ask anything…'

  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`
  }, [input])

  function handleSend() {
    if (!input.trim() || isStreaming) return
    const msg = input.trim()
    setInput('')
    onSend(msg)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex-shrink-0 pb-2">
      <div className="flex items-end gap-2 bg-[#161616] border border-[#232323] rounded-2xl px-3 py-2">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none bg-transparent text-[#e8e8e8] placeholder-[#444]
                     text-sm outline-none min-h-[36px] max-h-[200px] py-2"
        />
        {isStreaming ? (
          <button
            onClick={onStop}
            className="flex-shrink-0 w-9 h-9 flex items-center justify-center
                       bg-[#333] hover:bg-[#444] rounded-lg text-[#e8e8e8]
                       transition-colors text-sm"
            aria-label="Stop"
          >
            ⏹
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!input.trim() || disabled}
            className="flex-shrink-0 w-9 h-9 flex items-center justify-center
                       bg-[#10a37f] hover:bg-[#0d8c6d] disabled:opacity-40
                       disabled:cursor-not-allowed rounded-lg text-white
                       transition-colors text-sm"
            aria-label="Send"
          >
            ⬆
          </button>
        )}
      </div>

      <div className="flex items-center gap-1.5 mt-1 px-1">
        <span className="text-xs text-[#333]">{stateFilter}</span>
        <span className="text-[#333] text-xs">·</span>
        <span className="text-xs text-[#333]">{model}</span>
        <span className="flex-1" />
        <span className="text-xs text-[#333]">AI can make mistakes. Always verify against primary legislation.</span>
      </div>
    </div>
  )
}
