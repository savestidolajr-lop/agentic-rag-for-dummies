export type MessageRole = 'user' | 'assistant'

export interface Message {
  role: MessageRole
  content: string
  citedDocuments?: string[]
  timestamp?: string
}

export interface Session {
  session_id: string
  title: string
  created_at: string
}

export type StreamEvent =
  | { type: 'activity'; steps: string[] }
  | { type: 'narration'; text: string }
  | { type: 'token'; text: string; session_id: string }
  | { type: 'done'; session_id: string; cited_documents: string[]; options: string[]; title: string }
  | { type: 'error'; message: string }

export interface DocumentFile {
  filename: string
  state: string
  size_mb?: number
}

export interface AdminStats {
  namespaces: Record<string, number>
  vector_counts: Record<string, number>
  indexing_status: IndexingStatus[]
  health: Record<string, unknown>
}

export interface IndexingStatus {
  namespace?: string
  filename?: string
  done?: number
  total?: number
  progress?: number
  operation?: string
}
