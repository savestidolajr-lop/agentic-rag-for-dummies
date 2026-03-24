'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useUser, useClerk } from '@clerk/nextjs'
import Sidebar from '@/components/sidebar/Sidebar'
import SessionList from '@/components/sidebar/SessionList'
import { useSessions } from '@/hooks/useSessions'

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { user, isLoaded } = useUser()
  const { signOut } = useClerk()
  const { sessions, isLoading, createSession, deleteSession } = useSessions()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)

  // Redirect to sign-in if not authenticated
  useEffect(() => {
    if (isLoaded && !user) router.push('/sign-in')
  }, [isLoaded, user, router])

  // Close sidebar by default on mobile
  useEffect(() => {
    if (window.innerWidth < 768) setSidebarOpen(false)
  }, [])

  const handleNewChat = useCallback(async () => {
    const sid = await createSession()
    if (sid) {
      setActiveSessionId(sid)
      router.push(`/chat/${sid}`)
    }
  }, [createSession, router])

  const handleSelectSession = useCallback(
    (sid: string) => {
      setActiveSessionId(sid)
      router.push(`/chat/${sid}`)
      if (window.innerWidth < 768) setSidebarOpen(false)
    },
    [router]
  )

  const handleDeleteSession = useCallback(
    async (sid: string) => {
      await deleteSession(sid)
      if (sid === activeSessionId) {
        setActiveSessionId(null)
        router.push('/chat')
      }
    },
    [deleteSession, activeSessionId, router]
  )

  const email = user?.primaryEmailAddress?.emailAddress ?? ''
  const username = email.split('@')[0].replace(/\./g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  const initial = username[0]?.toUpperCase() ?? '?'

  const userBottomSlot = user ? (
    <div className="flex items-center gap-2 px-3 py-3">
      <div className="w-7 h-7 rounded-full bg-[#10a37f] flex items-center justify-center
                      text-white text-xs font-semibold flex-shrink-0">
        {initial}
      </div>
      <div className="flex-1 min-w-0 overflow-hidden">
        <div className="text-xs text-[#ccc] truncate">{username}</div>
        <div className="text-[10px] text-[#555] truncate">{email}</div>
      </div>
      <button
        onClick={() => signOut({ redirectUrl: '/sign-in' })}
        className="text-[10px] text-[#555] hover:text-red-400 transition-colors flex-shrink-0 whitespace-nowrap"
      >
        Sign out
      </button>
    </div>
  ) : null

  return (
    <div className="flex h-screen overflow-hidden bg-[#0d0d0d]">
      <Sidebar open={sidebarOpen} onToggle={() => setSidebarOpen((v) => !v)} bottomSlot={userBottomSlot}>
        {/* Header */}
        <div className="px-4 pt-4 pb-3 border-b border-[#1e1e1e] flex-shrink-0">
          <span className="text-base font-bold text-[#ececec] tracking-tight">Case Agent</span>
        </div>

        {/* New chat */}
        <div className="px-3 pt-3 pb-2 flex-shrink-0">
          <button
            onClick={handleNewChat}
            className="w-full text-left text-sm px-3 py-2 rounded-lg
                       bg-[#111] hover:bg-[#1a1a1a] border border-[#2d2d2d]
                       text-[#888] hover:text-[#ccc] transition-colors"
          >
            ＋ &nbsp;New chat
          </button>
        </div>

        {/* Label */}
        <div className="px-4 py-1 text-[10px] text-[#444] uppercase tracking-widest flex-shrink-0">
          Recent chats
        </div>

        {/* Session list */}
        {isLoading ? (
          <div className="px-4 py-2 text-xs text-[#444]">Loading…</div>
        ) : (
          <SessionList
            sessions={sessions}
            activeSessionId={activeSessionId}
            onSelect={handleSelectSession}
            onDelete={handleDeleteSession}
          />
        )}

        <div className="flex-1" />

        {/* Admin link */}
        <div className="px-3 pb-2 flex-shrink-0">
          <a
            href="/admin"
            className="block w-full text-sm px-3 py-2 rounded-lg
                       text-[#555] hover:text-[#888] hover:bg-[#111] transition-colors"
          >
            ⚙ &nbsp;Admin Panel
          </a>
        </div>
      </Sidebar>

      {/* Main content */}
      <main className="flex-1 min-w-0 h-full overflow-hidden">
        {children}
      </main>
    </div>
  )
}
