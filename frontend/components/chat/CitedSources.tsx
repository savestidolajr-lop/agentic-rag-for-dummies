'use client'

import { API_BASE } from '@/lib/api'

interface CitedSourcesProps {
  files: string[]
}

export default function CitedSources({ files }: CitedSourcesProps) {
  if (!files.length) return null

  return (
    <div className="rounded-lg bg-[#111] border border-[#1e1e1e] overflow-hidden flex-shrink-0">
      <div className="flex items-center gap-1.5 px-3 py-2 border-b border-[#1a1a1a]">
        <span className="text-[10px] text-[#555]">📎</span>
        <span className="text-[11px] text-[#555] font-medium">Sources ({files.length})</span>
      </div>
      <div className="px-3 py-2.5 flex flex-wrap gap-1.5">
        {files.map((f) => (
          <a
            key={f}
            href={`${API_BASE}/api/download/file/${encodeURIComponent(f)}`}
            download={f}
            className="inline-flex items-center gap-1 bg-[#1a1a1a] border border-[#2d2d2d]
                       text-[#888] hover:text-[#ddd] hover:border-[#444]
                       text-[11px] px-2.5 py-1 rounded-md transition-colors no-underline"
          >
            <span className="text-[10px]">↓</span>
            {f}
          </a>
        ))}
      </div>
    </div>
  )
}
