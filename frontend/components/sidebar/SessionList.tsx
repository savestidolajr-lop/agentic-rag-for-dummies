'use client'

import clsx from 'clsx'
import { Session } from '@/lib/types'

const DOT_COLORS = ['#10a37f', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4']

function sessionDotColor(id: string) {
  const hash = id.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0)
  return DOT_COLORS[hash % DOT_COLORS.length]
}

interface SessionListProps {
  sessions: Session[]
  activeSessionId: string | null
  onSelect: (sessionId: string) => void
  onDelete: (sessionId: string) => void
}

export default function SessionList({
  sessions,
  activeSessionId,
  onSelect,
  onDelete,
}: SessionListProps) {
  if (!sessions.length) {
    return <div className="px-3 py-2 text-xs text-[#555]">No recent chats</div>
  }

  function handleDelete(e: React.MouseEvent, sid: string) {
    e.stopPropagation()
    if (confirm('Delete this chat?')) {
      onDelete(sid)
    }
  }

  return (
    <div className="flex flex-col gap-0.5 overflow-y-auto flex-1 pb-2">
      {[...sessions].reverse().map((s) => (
        <div
          key={s.session_id}
          onClick={() => onSelect(s.session_id)}
          className={clsx(
            'group flex items-center justify-between px-3 py-2 cursor-pointer',
            'text-sm rounded-lg mx-2 transition-colors',
            s.session_id === activeSessionId
              ? 'bg-[#1e1e1e] text-[#ececec] border-l-2 border-[#10a37f]'
              : 'text-[#888] hover:bg-[#161616] hover:text-[#ccc]'
          )}
        >
          <span
            className="w-2 h-2 rounded-full flex-shrink-0 mr-2"
            style={{ background: sessionDotColor(s.session_id) }}
          />
          <span className="truncate flex-1 min-w-0 text-xs">{s.title || 'New Chat'}</span>
          <button
            onClick={(e) => handleDelete(e, s.session_id)}
            className="ml-1 text-[#444] hover:text-[#888] opacity-0 group-hover:opacity-100
                       transition-opacity flex-shrink-0 text-xs px-1"
            aria-label="Delete chat"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
