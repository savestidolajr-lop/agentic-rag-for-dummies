'use client'

import ChatPane from '@/components/chat/ChatPane'
import { useRouter } from 'next/navigation'

interface Props {
  params: { sessionId: string }
}

export default function SessionPage({ params }: Props) {
  const router = useRouter()

  function handleSessionCreated(sessionId: string) {
    router.replace(`/chat/${sessionId}`)
  }

  return (
    <div className="h-full flex flex-col">
      <ChatPane
        sessionId={params.sessionId}
        onSessionCreated={handleSessionCreated}
      />
    </div>
  )
}
