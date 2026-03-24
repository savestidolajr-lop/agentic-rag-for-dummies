'use client'

import { useEffect, useRef } from 'react'
import clsx from 'clsx'

interface SidebarProps {
  open: boolean
  onToggle: () => void
  children: React.ReactNode
  bottomSlot?: React.ReactNode
}

export default function Sidebar({ open, onToggle, children, bottomSlot }: SidebarProps) {
  const sidebarRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        window.innerWidth < 768 &&
        open &&
        sidebarRef.current &&
        !sidebarRef.current.contains(e.target as Node)
      ) {
        onToggle()
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open, onToggle])

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div className="fixed inset-0 bg-black/50 z-20 md:hidden" onClick={onToggle} />
      )}

      {/* When sidebar is closed on mobile, show a floating toggle at top-left */}
      {!open && (
        <button
          onClick={onToggle}
          className="fixed top-3 left-3 z-40 md:hidden flex items-center justify-center
                     w-8 h-8 rounded-lg bg-[#111] border border-[#2d2d2d]
                     text-[#666] hover:text-[#e8e8e8] transition-colors"
          aria-label="Open sidebar"
        >
          ☰
        </button>
      )}

      <div
        ref={sidebarRef}
        className={clsx(
          'fixed md:relative z-30 md:z-auto h-full flex flex-col',
          'bg-[#0d0d0d] border-r border-[#1e1e1e]',
          'transition-all duration-200 ease-in-out',
          open ? 'w-64' : 'w-0 overflow-hidden md:w-12'
        )}
      >
        {/* Toggle button — always rendered inside sidebar on desktop; shows in strip when collapsed */}
        <button
          onClick={onToggle}
          className={clsx(
            'flex items-center justify-start pl-3 flex-shrink-0 h-10 w-full',
            'text-[#666] hover:text-[#e8e8e8] transition-colors border-b border-[#1e1e1e]',
            !open && 'md:flex hidden'   // on mobile when closed, use the floating button instead
          )}
          aria-label="Toggle sidebar"
        >
          ☰
        </button>

        {/* Sidebar content */}
        <div
          className={clsx(
            'flex-1 flex flex-col overflow-hidden min-w-0',
            open ? 'opacity-100' : 'opacity-0 pointer-events-none'
          )}
        >
          {children}
        </div>

        {/* Bottom slot — avatar always visible; text clipped when collapsed */}
        {bottomSlot && (
          <div className="flex-shrink-0 border-t border-[#1e1e1e] overflow-x-hidden">
            {bottomSlot}
          </div>
        )}
      </div>
    </>
  )
}
