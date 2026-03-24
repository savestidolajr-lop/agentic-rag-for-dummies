'use client'

import { useState } from 'react'

interface ActivityPanelProps {
  steps: string[]
}

export default function ActivityPanel({ steps }: ActivityPanelProps) {
  const [open, setOpen] = useState(false)

  if (!steps.length) return null

  return (
    <div className="rounded-xl bg-[#111] border border-[#1e1e1e] px-4 py-3 flex flex-col gap-2">
      {/* Header — clickable to toggle */}
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 w-full text-left"
      >
        <span className="relative flex h-3 w-3">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#10a37f] opacity-40" />
          <span className="relative inline-flex rounded-full h-3 w-3 bg-[#10a37f]" />
        </span>
        <span className="text-xs font-medium text-[#888] flex-1">Agent searching…</span>
        <svg
          className={`w-3 h-3 text-[#555] transition-transform ${open ? 'rotate-180' : ''}`}
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* Steps — only visible when open */}
      {open && (
        <div className="flex flex-col gap-1.5 pl-1 max-h-[72px] overflow-y-auto scrollbar-none">
          {steps.map((step, i) => {
            const isLast = i === steps.length - 1
            const text = step.endsWith('...') ? step.slice(0, -3) : step

            return (
              <div key={i} className="flex items-center gap-2 flex-shrink-0">
                {isLast ? (
                  <svg className="w-3 h-3 text-[#10a37f] animate-spin flex-shrink-0" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                    <path className="opacity-80" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <svg className="w-3 h-3 text-[#555] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
                <span className={`text-xs ${isLast ? 'text-[#ccc]' : 'text-[#444] line-through'}`}>
                  {text}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
