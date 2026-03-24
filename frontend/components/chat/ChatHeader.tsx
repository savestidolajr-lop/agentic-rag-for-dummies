'use client'

const DEFAULT_STATES = ['All States', 'NSW', 'VIC', 'QLD', 'SA', 'NT', 'WA', 'TAS', 'ACT']
const MODELS = ['Claude Haiku 4.5', 'Claude Sonnet 4.6', 'GPT-5 Mini', 'GPT-5 Nano', 'GPT-5.4', 'Claude Opus 4.6']

const STATE_COLORS: Record<string, string> = {
  NSW: '#3b82f6',
  VIC: '#8b5cf6',
  QLD: '#b91c1c',
  SA:  '#ef4444',
  WA:  '#d97706',
  NT:  '#f97316',
  TAS: '#10a37f',
  ACT: '#0891b2',
  'All States': '#6b7280',
}

interface ChatHeaderProps {
  stateFilter: string
  model: string
  sourceCount: number
  namespaces?: string[]
  onStateChange: (v: string) => void
  onModelChange: (v: string) => void
  onNewChat: () => void
}

export default function ChatHeader({
  stateFilter,
  model,
  sourceCount,
  namespaces,
  onStateChange,
  onModelChange,
  onNewChat,
}: ChatHeaderProps) {
  const states = namespaces && namespaces.length > 0 ? namespaces : DEFAULT_STATES
  const dotColor = STATE_COLORS[stateFilter] ?? '#6b7280'

  return (
    <div className="flex-shrink-0 flex items-center gap-2 px-3 py-2 border-b border-[#1e1e1e]">
      {/* State filter pill */}
      <div className="relative flex items-center">
        <span
          className="absolute left-2.5 w-2 h-2 rounded-full pointer-events-none"
          style={{ background: dotColor }}
        />
        <select
          value={stateFilter}
          onChange={(e) => onStateChange(e.target.value)}
          className="pl-6 pr-5 py-1 text-xs font-medium text-[#ccc] bg-[#1a1a1a]
                     border border-[#2d2d2d] rounded-full outline-none cursor-pointer
                     hover:border-[#444] transition-colors appearance-none"
        >
          {states.map((s) => (
            <option key={s} value={s} className="bg-[#1a1a1a]">{s}</option>
          ))}
        </select>
        {/* dropdown chevron */}
        <svg className="absolute right-2 w-2.5 h-2.5 text-[#555] pointer-events-none"
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {/* Model selector */}
      <div className="relative flex items-center">
        <svg className="absolute left-2.5 w-3 h-3 text-[#555] pointer-events-none"
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        <select
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
          className="pl-7 pr-5 py-1 text-xs text-[#888] bg-transparent
                     border-none outline-none cursor-pointer hover:text-[#ccc]
                     transition-colors appearance-none"
        >
          {MODELS.map((m) => (
            <option key={m} value={m} className="bg-[#1a1a1a] text-[#e8e8e8]">{m}</option>
          ))}
        </select>
        <svg className="absolute right-0 w-2.5 h-2.5 text-[#555] pointer-events-none"
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      <div className="flex-1" />

      {/* Sources badge */}
      {sourceCount > 0 && (
        <div className="flex items-center gap-1.5 px-3 py-1 bg-[#1a1a1a] border border-[#2d2d2d]
                        rounded-full text-xs text-[#888]">
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          Sources ({sourceCount})
        </div>
      )}

      {/* New chat / reset */}
      <button
        onClick={onNewChat}
        title="New chat"
        className="w-7 h-7 flex items-center justify-center rounded-lg text-[#555]
                   hover:text-[#aaa] hover:bg-[#1a1a1a] transition-colors"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          className="w-4 h-4">
          <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
          <path d="M3 3v5h5" />
        </svg>
      </button>
    </div>
  )
}
