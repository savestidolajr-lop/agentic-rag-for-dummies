'use client'

import ChatPane from '@/components/chat/ChatPane'

export default function ChatPage() {
  function handleSessionCreated(sessionId: string) {
    // Update URL without remounting — keeps streaming state intact
    window.history.replaceState(null, '', `/chat/${sessionId}`)
  }

  return (
    <div className="h-full flex flex-col">
      <ChatPane onSessionCreated={handleSessionCreated} />
    </div>
  )
}
