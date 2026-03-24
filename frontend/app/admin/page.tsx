'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useApiClient, API_BASE } from '@/lib/api'
import { useToken } from '@/hooks/useToken'
import { AdminStats, DocumentFile } from '@/lib/types'

type Tab = 'summary' | 'upload' | 'files' | 'ai' | 'namespaces'

const TABS: { id: Tab; label: string }[] = [
  { id: 'summary',    label: 'Summary' },
  { id: 'upload',     label: 'Upload Files' },
  { id: 'files',      label: 'Files Indexed' },
  { id: 'ai',         label: 'AI Settings' },
  { id: 'namespaces', label: 'Namespaces' },
]

export default function AdminPage() {
  const apiFetch = useApiClient()
  const token = useToken()
  const { getToken } = useAuth()

  const [activeTab, setActiveTab] = useState<Tab>('summary')

  // ── Data ──────────────────────────────────────────────────────────────────
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [files, setFiles] = useState<DocumentFile[]>([])
  const [totalFiles, setTotalFiles] = useState(0)
  const [page, setPage] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [stateFilter, setStateFilter] = useState('')
  const [search, setSearch] = useState('')

  // ── Upload ────────────────────────────────────────────────────────────────
  const [uploadState, setUploadState] = useState('NSW')
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── Model ─────────────────────────────────────────────────────────────────
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [currentModel, setCurrentModel] = useState('')

  // ── AI settings ───────────────────────────────────────────────────────────
  const [temperature, setTemperature] = useState(0)
  const [maxToolCalls, setMaxToolCalls] = useState(8)
  const [orchPrompt, setOrchPrompt] = useState('')
  const [aggPrompt, setAggPrompt] = useState('')
  const [fallbackPrompt, setFallbackPrompt] = useState('')
  const [savingAI, setSavingAI] = useState(false)
  const [aiMsg, setAiMsg] = useState('')

  // ── Namespaces ────────────────────────────────────────────────────────────
  const [defaultNs, setDefaultNs] = useState<string[]>([])
  const [customNs, setCustomNs] = useState<string[]>([])
  const [newNsName, setNewNsName] = useState('')
  const [nsMsg, setNsMsg] = useState('')
  const [nsLoading, setNsLoading] = useState(false)

  // ── Danger zone ───────────────────────────────────────────────────────────
  const [dangerOpen, setDangerOpen] = useState(false)
  const [dangerNamespace, setDangerNamespace] = useState('')
  const [reindexing, setReindexing] = useState(false)
  const [reindexMsg, setReindexMsg] = useState('')
  const [confirmReindex, setConfirmReindex] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<
    | { type: 'file'; state: string; filename: string }
    | { type: 'namespace'; state: string }
    | { type: 'all' }
    | null
  >(null)
  const [deleting, setDeleting] = useState(false)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // ETA tracking: namespace -> start snapshot {done, ts} recorded on first observation
  const etaRef = useRef<Map<string, { done: number; ts: number }>>(new Map())

  function computeEta(namespace: string, done: number, total: number): string {
    const now = Date.now()
    if (!etaRef.current.has(namespace)) {
      etaRef.current.set(namespace, { done, ts: now })
      return ''
    }
    const start = etaRef.current.get(namespace)!
    const elapsed = (now - start.ts) / 1000           // seconds since first seen
    const processed = done - start.done               // files done since first seen
    if (processed <= 0 || elapsed < 5) return ''      // wait at least 5s before estimating
    const rate = processed / elapsed                   // files/sec
    const remaining = (total - done) / rate            // seconds left
    if (!isFinite(remaining) || remaining <= 0) return ''
    if (remaining < 60) return `~${Math.round(remaining)}s left`
    if (remaining < 3600) return `~${Math.round(remaining / 60)}m left`
    return `~${(remaining / 3600).toFixed(1)}h left`
  }

  // ── Loaders ───────────────────────────────────────────────────────────────
  const loadStats = useCallback(async () => {
    const res = await apiFetch('/api/admin/stats')
    if (res.ok) {
      const data: AdminStats = await res.json()
      // Clear start snapshots for namespaces that finished
      const activeNs = new Set((data.indexing_status ?? []).map((s: { namespace?: string }) => s.namespace ?? ''))
      Array.from(etaRef.current.keys()).forEach(ns => {
        if (!activeNs.has(ns)) etaRef.current.delete(ns)
      })
      setStats(data)
      if (!data.indexing_status?.length && pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [apiFetch])

  async function loadFiles() {
    const params = new URLSearchParams({ page: String(page), page_size: '15' })
    if (stateFilter) params.set('state', stateFilter)
    if (search) params.set('search', search)
    const res = await apiFetch(`/api/documents?${params}`)
    if (res.ok) {
      const data = await res.json()
      setFiles(data.files)
      setTotalFiles(data.total)
      setTotalPages(data.total_pages)

    }
  }

  async function loadConfig() {
    const res = await apiFetch('/api/admin/config')
    if (res.ok) {
      const data = await res.json()
      setAvailableModels(data.available_models)
      setCurrentModel(data.current_model)
    }
  }

  async function loadAISettings() {
    const res = await apiFetch('/api/admin/ai-settings')
    if (res.ok) {
      const data = await res.json()
      setTemperature(data.temperature)
      setMaxToolCalls(data.max_tool_calls)
      setOrchPrompt(data.orchestrator_prompt)
      setAggPrompt(data.aggregation_prompt)
      setFallbackPrompt(data.fallback_response_prompt)
    }
  }

  async function loadNamespaces() {
    const res = await apiFetch('/api/admin/namespaces')
    if (res.ok) {
      const data = await res.json()
      setDefaultNs(data.default)
      setCustomNs(data.custom)
    }
  }

  async function handleAddNamespace(e: React.FormEvent) {
    e.preventDefault()
    const name = newNsName.trim()
    if (!name) return
    setNsLoading(true); setNsMsg('')
    try {
      const res = await apiFetch('/api/admin/namespaces', {
        method: 'POST',
        body: JSON.stringify({ name }),
      })
      const data = await res.json()
      if (res.ok) {
        setNewNsName('')
        setNsMsg(`"${name}" added.`)
        await loadNamespaces()
      } else {
        setNsMsg(data.detail || 'Failed to add namespace')
      }
    } catch { setNsMsg('Error adding namespace') }
    setNsLoading(false)
  }

  async function handleDeleteNamespaceDirect(name: string) {
    setNsLoading(true); setNsMsg('')
    try {
      const res = await apiFetch(`/api/admin/namespaces/${encodeURIComponent(name)}`, { method: 'DELETE' })
      if (res.ok) {
        setNsMsg(`"${name}" deleted.`)
        await loadNamespaces()
      } else {
        const data = await res.json()
        setNsMsg(data.detail || 'Failed to delete')
      }
    } catch { setNsMsg('Error deleting namespace') }
    setNsLoading(false)
  }

  function startPolling() {
    if (pollRef.current) return
    pollRef.current = setInterval(loadStats, 2500)
  }

  useEffect(() => {
    if (!token) return
    loadStats(); loadConfig(); loadAISettings(); loadNamespaces()
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [token]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (stats?.indexing_status?.length) startPolling()
  }, [stats?.indexing_status?.length]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!token) return
    loadFiles()
  }, [token, page, stateFilter, search]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Handlers ──────────────────────────────────────────────────────────────
  async function handleDownload(state: string, filename: string) {
    try {
      const res = await apiFetch(`/api/download/${encodeURIComponent(state)}/${encodeURIComponent(filename)}`)
      if (!res.ok) return
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch {}
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault()
    const fileInput = fileInputRef.current
    if (!fileInput?.files?.length) return
    if (uploadState === '__custom__') { setUploadMsg('Please enter a namespace name.'); return }
    setUploading(true); setUploadMsg('')

    const files = Array.from(fileInput.files)
    const isZip = files.length === 1 && files[0].name.toLowerCase().endsWith('.zip')

    try {
      let res: Response
      if (isZip) {
        // Force a fresh token — ZIP transfers take 60+ seconds and FastAPI buffers
        // the entire body before running auth, so a cached token can expire mid-transfer.
        const freshToken = await getToken({ skipCache: true })
        if (!freshToken) { setUploadMsg('Auth error — please refresh the page'); setUploading(false); return }
        const form = new FormData()
        form.append('file', files[0])
        form.append('state', uploadState)
        res = await fetch(`${API_BASE}/api/admin/upload-zip`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${freshToken}` },
          body: form,
        })
      } else {
        const form = new FormData()
        files.forEach((f) => form.append('files', f))
        form.append('state', uploadState)
        res = await apiFetch('/api/admin/upload', { method: 'POST', body: form })
      }

      if (res.ok) {
        const data = await res.json()
        setUploadMsg(`Queued ${data.queued} file(s) — indexing in background.`)
        fileInput.value = ''
        startPolling()
        setActiveTab('summary')
      } else { setUploadMsg('Upload failed') }
    } catch { setUploadMsg('Upload error') }
    setUploading(false)
  }

  async function handleModelSwitch(model: string) {
    const res = await apiFetch('/api/admin/config', { method: 'PATCH', body: JSON.stringify({ model }) })
    if (res.ok) setCurrentModel(model)
  }

  async function handleSaveAI() {
    setSavingAI(true); setAiMsg('')
    try {
      const res = await apiFetch('/api/admin/ai-settings', {
        method: 'POST',
        body: JSON.stringify({ temperature, max_tool_calls: maxToolCalls, orchestrator_prompt: orchPrompt, aggregation_prompt: aggPrompt, fallback_response_prompt: fallbackPrompt }),
      })
      setAiMsg(res.ok ? 'Settings saved.' : 'Save failed.')
    } catch { setAiMsg('Save error.') }
    setSavingAI(false)
  }

  async function handleResetAI() {
    setSavingAI(true); setAiMsg('')
    try {
      const res = await apiFetch('/api/admin/ai-settings/reset', { method: 'POST' })
      if (res.ok) {
        // Reload full settings so textareas show the built-in defaults again
        await loadAISettings()
        setAiMsg('Reset to defaults.')
      }
    } catch { setAiMsg('Reset error.') }
    setSavingAI(false)
  }

  async function handleReindex() {
    setReindexing(true); setReindexMsg(''); startPolling()
    try {
      const res = await apiFetch('/api/admin/reindex', { method: 'POST' })
      if (res.ok) { const d = await res.json(); setReindexMsg(`Re-indexed ${d.indexed} document(s)`); loadStats(); loadFiles() }
      else setReindexMsg('Reindex failed')
    } catch { setReindexMsg('Reindex error') }
    setReindexing(false)
  }

  async function handleDeleteFile(state: string, filename: string) {
    setDeleting(true)
    try {
      const res = await apiFetch(`/api/documents/${encodeURIComponent(state)}/${encodeURIComponent(filename)}`, { method: 'DELETE' })
      if (res.ok) { setConfirmDelete(null); loadFiles(); loadStats() }
    } finally { setDeleting(false) }
  }

  async function handleDeleteNamespace(state: string) {
    setDeleting(true)
    try {
      const res = await apiFetch(`/api/admin/namespace/${encodeURIComponent(state)}`, { method: 'DELETE' })
      if (res.ok) { setConfirmDelete(null); if (stateFilter === state) setStateFilter(''); setDangerNamespace(''); loadFiles(); loadStats() }
    } finally { setDeleting(false) }
  }

  async function handleDeleteAll() {
    setDeleting(true)
    try {
      const res = await apiFetch('/api/admin/all', { method: 'DELETE' })
      if (res.ok) { setConfirmDelete(null); setStateFilter(''); loadFiles(); loadStats() }
    } finally { setDeleting(false) }
  }

  const namespaces = stats ? Object.keys(stats.namespaces) : []

  // Wait for auth before rendering anything — prevents 401 flash
  if (!token) {
    return (
      <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-[#10a37f] border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-[#444]">Authenticating…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0d0d0d] text-[#e8e8e8]">

      {/* ── Confirm reindex modal ─────────────────────────────────────── */}
      {confirmReindex && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-[#111] border border-[#2d2d2d] rounded-xl p-5 max-w-sm w-full mx-4">
            <p className="text-sm font-semibold text-[#ccc] mb-1">Confirm re-index</p>
            <p className="text-xs text-[#888] mb-4">
              Clears all vectors and parent chunks then rebuilds from scratch.
              Original PDFs are preserved. This may take a while.
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setConfirmReindex(false)} className="px-3 py-1.5 text-xs rounded-lg bg-[#1e1e1e] text-[#888] hover:bg-[#2d2d2d]">Cancel</button>
              <button disabled={reindexing} onClick={() => { setConfirmReindex(false); handleReindex() }}
                className="px-3 py-1.5 text-xs rounded-lg bg-[#10a37f]/20 text-[#10a37f] hover:bg-[#10a37f]/30 disabled:opacity-50">
                Re-index All
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Confirm delete modal ──────────────────────────────────────── */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-[#111] border border-[#2d2d2d] rounded-xl p-5 max-w-sm w-full mx-4">
            <p className="text-sm font-semibold text-[#ccc] mb-1">Confirm delete</p>
            {confirmDelete.type === 'file' ? (
              <p className="text-xs text-[#888] mb-4">
                Delete <span className="text-[#e8e8e8] font-mono">{confirmDelete.filename}</span> from <span className="text-[#10a37f]">{confirmDelete.state}</span>?
                <br />Removes all vectors and chunks for this file.
              </p>
            ) : confirmDelete.type === 'namespace' ? (
              <p className="text-xs text-[#888] mb-4">
                Delete <strong>all documents</strong> in <span className="text-[#10a37f]">{confirmDelete.state}</span>?
                <br />This cannot be undone.
              </p>
            ) : (
              <p className="text-xs text-[#888] mb-4">
                Delete <span className="text-red-300 font-semibold">every document across all namespaces</span>?
                <br />All vectors, chunks, and files will be permanently removed.
              </p>
            )}
            <div className="flex gap-2 justify-end">
              <button onClick={() => setConfirmDelete(null)} className="px-3 py-1.5 text-xs rounded-lg bg-[#1e1e1e] text-[#888] hover:bg-[#2d2d2d]">Cancel</button>
              <button disabled={deleting}
                onClick={() => confirmDelete.type === 'file' ? handleDeleteFile(confirmDelete.state, confirmDelete.filename) : confirmDelete.type === 'namespace' ? handleDeleteNamespace(confirmDelete.state) : handleDeleteAll()}
                className="px-3 py-1.5 text-xs rounded-lg bg-red-900/60 text-red-300 hover:bg-red-900 disabled:opacity-50">
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-4xl mx-auto px-4 py-6">

        {/* ── Header ────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between mb-5 pb-3 border-b border-[#1e1e1e]">
          <div className="flex items-center gap-2">
            <span className="text-base font-bold text-[#ececec]">Case Agent</span>
            <span className="text-[#333]">/</span>
            <span className="text-sm text-[#666]">Admin Panel</span>
          </div>
          <a href="/chat" className="text-xs text-[#7DC4F5] hover:underline">← Back to chat</a>
        </div>

        {/* ── Tabs ──────────────────────────────────────────────────────── */}
        <div className="flex border-b border-[#1e1e1e] mb-6">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
                activeTab === t.id
                  ? 'border-[#10a37f] text-[#10a37f]'
                  : 'border-transparent text-[#555] hover:text-[#888]'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ══════════════════════════════════════════════════════════════════
            TAB: Summary
        ══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'summary' && (
          <div className="flex flex-col gap-4">

            {/* Namespace stat cards */}
            {stats && Object.keys(stats.namespaces).length > 0 && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(stats.namespaces).map(([ns, count]) => {
                  const vectors = stats.vector_counts?.[ns]
                  return (
                    <div key={ns} className="bg-[#111] border border-[#1e1e1e] rounded-xl p-4">
                      <div className="text-[11px] text-[#555] mb-1 truncate uppercase tracking-wider">{ns}</div>
                      <div className="text-2xl font-semibold text-white">{(count as number).toLocaleString()}</div>
                      <div className="text-[10px] text-[#444] mt-0.5">documents</div>
                      {vectors !== undefined && (
                        <div className="text-[10px] text-[#10a37f] mt-1">{vectors.toLocaleString()} vectors</div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {/* Indexing progress */}
            {stats?.indexing_status?.map((s, i) => {
              const eta = computeEta(s.namespace ?? '', s.done ?? 0, s.total ?? 0)
              return (
                <div key={i} className="bg-[#111] border border-[#1e1e1e] rounded-xl p-3">
                  <div className="flex items-center justify-between text-xs text-[#888] mb-2">
                    <span>{s.operation || 'Indexing'} · <strong className="text-[#aaa]">[{s.namespace}]</strong> {s.filename}</span>
                    <span className="text-[#666]">
                      {s.done}/{s.total} · {Math.round((s.progress || 0) * 100)}%
                      {eta && <span className="ml-2 text-[#10a37f]">{eta}</span>}
                    </span>
                  </div>
                  <div className="h-1.5 bg-[#1a1a1a] rounded-full overflow-hidden">
                    <div className="h-full bg-[#10a37f] transition-all" style={{ width: `${Math.round((s.progress || 0) * 100)}%` }} />
                  </div>
                </div>
              )
            })}

            {/* No data yet */}
            {stats && Object.keys(stats.namespaces).length === 0 && !stats.indexing_status?.length && (
              <div className="bg-[#111] border border-[#1e1e1e] rounded-xl p-8 text-center">
                <p className="text-sm text-[#555]">No documents indexed yet.</p>
                <button onClick={() => setActiveTab('upload')} className="mt-3 text-xs text-[#10a37f] hover:underline">
                  Upload your first documents →
                </button>
              </div>
            )}

            {/* Health */}
            {stats?.health && (
              <div className="bg-[#111] border border-[#1e1e1e] rounded-xl p-4">
                <p className="text-[11px] font-medium text-[#555] uppercase tracking-wider mb-3">System Health</p>
                <div className="flex gap-6">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${stats.health.qdrant ? 'bg-[#10a37f]' : 'bg-red-500'}`} />
                    <span className="text-xs text-[#888]">Qdrant {stats.health.qdrant ? '✓' : '✗'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${stats.health.llm ? 'bg-[#10a37f]' : 'bg-red-500'}`} />
                    <span className="text-xs text-[#888]">LLM {stats.health.llm ? '✓' : '✗'}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════
            TAB: Upload Files
        ══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'upload' && (
          <div className="grid md:grid-cols-2 gap-6">

            {/* Upload form */}
            <div className="bg-[#111] border border-[#1e1e1e] rounded-xl p-5">
              <h2 className="text-sm font-semibold text-[#ccc] mb-1">Upload Documents</h2>
              <p className="text-[11px] text-[#555] mb-4">PDF / Markdown files · or a single ZIP of PDFs for large batches</p>
              <form onSubmit={handleUpload} className="flex flex-col gap-3">
                <div>
                  <label className="text-[11px] font-medium text-[#666] uppercase tracking-wider block mb-1.5">State / Namespace</label>
                  <select
                    value={uploadState.startsWith('__custom__') ? '__custom__' : uploadState}
                    onChange={(e) => {
                      if (e.target.value === '__custom__') setUploadState('__custom__')
                      else setUploadState(e.target.value)
                    }}
                    className="w-full bg-[#1a1a1a] border border-[#2d2d2d] rounded-lg px-3 py-2 text-sm text-[#ccc] outline-none"
                  >
                    <option value="">No State</option>
                    {[...defaultNs, ...customNs].map((s) => <option key={s} value={s}>{s}</option>)}
                    <option value="__custom__">＋ Custom namespace…</option>
                  </select>
                  {uploadState === '__custom__' && (
                    <input
                      type="text"
                      placeholder="Enter namespace name"
                      autoFocus
                      onChange={(e) => setUploadState(e.target.value || '__custom__')}
                      className="mt-2 w-full bg-[#1a1a1a] border border-[#2d2d2d] rounded-lg px-3 py-2
                                 text-sm text-[#ccc] outline-none placeholder-[#444] focus:border-[#444]"
                    />
                  )}
                </div>
                <div>
                  <label className="text-[11px] font-medium text-[#666] uppercase tracking-wider block mb-1.5">Files</label>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.md,.zip"
                    className="w-full text-xs text-[#888] file:mr-3 file:py-1.5 file:px-3
                               file:rounded-lg file:border-0 file:bg-[#1e1e1e]
                               file:text-[#888] file:text-xs cursor-pointer"
                  />
                </div>
                <button
                  type="submit"
                  disabled={uploading}
                  className="w-full py-2 rounded-lg bg-[#10a37f] hover:bg-[#0d8c6d]
                             disabled:opacity-50 text-white text-sm font-medium transition-colors mt-1"
                >
                  {uploading ? 'Uploading…' : 'Upload'}
                </button>
                {uploadMsg && (
                  <p className={`text-xs ${uploadMsg.startsWith('Added') ? 'text-[#10a37f]' : 'text-red-400'}`}>{uploadMsg}</p>
                )}
              </form>
            </div>

            {/* Model picker */}
            <div className="bg-[#111] border border-[#1e1e1e] rounded-xl p-5">
              <h2 className="text-sm font-semibold text-[#ccc] mb-1">AI Model</h2>
              <p className="text-[11px] text-[#555] mb-4">Select the model used for chat responses</p>
              <div className="flex flex-col gap-2">
                {availableModels.map((m) => (
                  <button
                    key={m}
                    onClick={() => handleModelSwitch(m)}
                    className={`text-left text-sm px-3 py-2.5 rounded-lg border transition-colors ${
                      m === currentModel
                        ? 'border-[#10a37f] bg-[#10a37f]/10 text-[#10a37f]'
                        : 'border-[#2d2d2d] text-[#888] hover:bg-[#1a1a1a] hover:text-[#ccc]'
                    }`}
                  >
                    {m === currentModel ? '✓ ' : ''}{m}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════
            TAB: Files Indexed
        ══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'files' && (
          <div className="bg-[#111] border border-[#1e1e1e] rounded-xl overflow-hidden">
            {/* Toolbar */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-[#1e1e1e]">
              <h2 className="text-sm font-semibold text-[#ccc] flex-1">
                Documents <span className="text-[#555] font-normal">({totalFiles})</span>
              </h2>
              <input
                type="text"
                placeholder="Search…"
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(0) }}
                className="bg-[#1a1a1a] border border-[#2d2d2d] rounded-lg px-3 py-1.5
                           text-xs text-[#ccc] outline-none w-36 placeholder-[#444]"
              />
              <select
                value={stateFilter}
                onChange={(e) => { setStateFilter(e.target.value); setPage(0) }}
                className="bg-[#1a1a1a] border border-[#2d2d2d] rounded-lg px-2 py-1.5 text-xs text-[#ccc] outline-none"
              >
                <option value="">All States</option>
                {namespaces.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            {/* Table */}
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-[#161616] text-[#555]">
                  <th className="text-left px-4 py-2 font-medium w-16">State</th>
                  <th className="text-left px-4 py-2 font-medium">File</th>
                  <th className="px-4 py-2 text-right font-medium w-28">Actions</th>
                </tr>
              </thead>
              <tbody>
                {files.map((f) => (
                  <tr key={`${f.state}/${f.filename}`} className="border-t border-[#1a1a1a] hover:bg-[#161616]">
                    <td className="px-4 py-2.5">
                      <span className="bg-[#1e1e1e] border border-[#333] text-[#10a37f] rounded px-1.5 py-0.5 text-[10px]">
                        {f.state}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[#888] truncate max-w-xs">{f.filename}</td>
                    <td className="px-4 py-2.5 text-right whitespace-nowrap">
                      <button
                        onClick={() => handleDownload(f.state, f.filename)}
                        className="text-[#10a37f] hover:underline text-[10px] mr-3"
                      >
                        ↓ Download
                      </button>
                      <button
                        onClick={() => setConfirmDelete({ type: 'file', state: f.state, filename: f.filename })}
                        className="text-[#444] hover:text-red-400 text-[10px] transition-colors"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
                {files.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-4 py-8 text-center text-[#444] text-xs">No documents found</td>
                  </tr>
                )}
              </tbody>
            </table>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-3 px-4 py-3 border-t border-[#1a1a1a]">
                <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}
                  className="text-xs px-3 py-1 rounded bg-[#1e1e1e] text-[#888] disabled:opacity-40 hover:bg-[#2d2d2d] transition-colors">
                  ‹ Prev
                </button>
                <span className="text-xs text-[#555]">{page + 1} / {totalPages}</span>
                <button onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
                  className="text-xs px-3 py-1 rounded bg-[#1e1e1e] text-[#888] disabled:opacity-40 hover:bg-[#2d2d2d] transition-colors">
                  Next ›
                </button>
              </div>
            )}
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════
            TAB: AI Settings
        ══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'ai' && (
          <div className="flex flex-col gap-5">

            {/* Sliders */}
            <div className="bg-[#111] border border-[#1e1e1e] rounded-xl p-5">
              <h2 className="text-sm font-semibold text-[#ccc] mb-4">Model Behaviour</h2>
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <label className="text-[11px] font-medium text-[#666] uppercase tracking-wider block mb-2">
                    Temperature <span className="text-[#888] normal-case font-normal">({temperature})</span>
                  </label>
                  <input type="range" min={0} max={1} step={0.05} value={temperature}
                    onChange={(e) => setTemperature(parseFloat(e.target.value))}
                    className="w-full accent-[#10a37f] cursor-pointer" />
                  <div className="flex justify-between text-[10px] text-[#444] mt-1">
                    <span>0 — precise</span><span>1 — creative</span>
                  </div>
                </div>
                <div>
                  <label className="text-[11px] font-medium text-[#666] uppercase tracking-wider block mb-2">
                    Max Tool Calls <span className="text-[#888] normal-case font-normal">({maxToolCalls})</span>
                  </label>
                  <input type="range" min={1} max={15} step={1} value={maxToolCalls}
                    onChange={(e) => setMaxToolCalls(parseInt(e.target.value))}
                    className="w-full accent-[#10a37f] cursor-pointer" />
                  <div className="flex justify-between text-[10px] text-[#444] mt-1">
                    <span>1</span><span>15</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Prompts */}
            <div className="bg-[#111] border border-[#1e1e1e] rounded-xl p-5">
              <h2 className="text-sm font-semibold text-[#ccc] mb-4">Prompt Overrides</h2>
              <p className="text-[11px] text-[#555] mb-4">Leave any field empty to use the built-in default prompt.</p>
              <div className="flex flex-col gap-4">
                {[
                  { label: 'Orchestrator Prompt', value: orchPrompt, set: setOrchPrompt, rows: 8 },
                  { label: 'Aggregation Prompt',  value: aggPrompt,  set: setAggPrompt,  rows: 5 },
                  { label: 'Fallback Response Prompt', value: fallbackPrompt, set: setFallbackPrompt, rows: 5 },
                ].map(({ label, value, set, rows }) => (
                  <div key={label}>
                    <label className="text-[11px] font-medium text-[#666] uppercase tracking-wider block mb-1.5">{label}</label>
                    <textarea
                      value={value}
                      onChange={(e) => set(e.target.value)}
                      rows={rows}
                      placeholder="Leave empty to use default…"
                      className="w-full bg-[#1a1a1a] border border-[#2d2d2d] rounded-lg px-3 py-2
                                 text-xs text-[#ccc] outline-none resize-y font-mono placeholder-[#444]
                                 focus:border-[#444] transition-colors"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
              <button onClick={handleSaveAI} disabled={savingAI}
                className="px-4 py-2 rounded-lg bg-[#10a37f] hover:bg-[#0d8c6d] disabled:opacity-50 text-white text-sm font-medium transition-colors">
                {savingAI ? 'Saving…' : 'Save Settings'}
              </button>
              <button onClick={handleResetAI} disabled={savingAI}
                className="px-4 py-2 rounded-lg border border-[#2d2d2d] text-[#888] text-sm hover:bg-[#1a1a1a] hover:text-[#ccc] disabled:opacity-50 transition-colors">
                Reset to Defaults
              </button>
              {aiMsg && (
                <span className={`text-xs ${aiMsg.includes('error') || aiMsg.includes('failed') ? 'text-red-400' : 'text-[#10a37f]'}`}>
                  {aiMsg}
                </span>
              )}
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════
            TAB: Namespaces
        ══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'namespaces' && (
          <div className="flex flex-col gap-5">

            {/* Add custom namespace */}
            <div className="bg-[#111] border border-[#1e1e1e] rounded-xl p-5">
              <h2 className="text-sm font-semibold text-[#ccc] mb-1">Add Namespace</h2>
              <p className="text-[11px] text-[#555] mb-4">Create a custom namespace to organise documents by topic, region, or category.</p>
              <form onSubmit={handleAddNamespace} className="flex gap-2">
                <input
                  type="text"
                  value={newNsName}
                  onChange={(e) => { setNewNsName(e.target.value); setNsMsg('') }}
                  placeholder="e.g. Federal, Internal, 2024…"
                  className="flex-1 bg-[#1a1a1a] border border-[#2d2d2d] rounded-lg px-3 py-2
                             text-sm text-[#ccc] outline-none placeholder-[#444] focus:border-[#444]"
                />
                <button
                  type="submit"
                  disabled={nsLoading || !newNsName.trim()}
                  className="px-4 py-2 rounded-lg bg-[#10a37f] hover:bg-[#0d8c6d]
                             disabled:opacity-40 text-white text-sm font-medium transition-colors whitespace-nowrap"
                >
                  {nsLoading ? 'Saving…' : 'Add'}
                </button>
              </form>
              {nsMsg && (
                <p className={`text-xs mt-2 ${nsMsg.includes('Error') || nsMsg.includes('Failed') || nsMsg.includes('exist') ? 'text-red-400' : 'text-[#10a37f]'}`}>
                  {nsMsg}
                </p>
              )}
            </div>

            {/* Default namespaces */}
            <div className="bg-[#111] border border-[#1e1e1e] rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-[#1e1e1e]">
                <h2 className="text-sm font-semibold text-[#ccc]">Default Namespaces</h2>
                <p className="text-[11px] text-[#555] mt-0.5">Built-in — cannot be removed.</p>
              </div>
              <div className="px-4 py-3 flex flex-wrap gap-2">
                {defaultNs.map((ns) => (
                  <span key={ns}
                    className="inline-flex items-center gap-1.5 bg-[#1a1a1a] border border-[#2d2d2d]
                               text-[#888] text-xs px-3 py-1.5 rounded-lg">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#444] flex-shrink-0" />
                    {ns}
                  </span>
                ))}
              </div>
            </div>

            {/* Custom namespaces */}
            <div className="bg-[#111] border border-[#1e1e1e] rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-[#1e1e1e]">
                <h2 className="text-sm font-semibold text-[#ccc]">Custom Namespaces</h2>
                <p className="text-[11px] text-[#555] mt-0.5">User-defined — can be added and removed.</p>
              </div>
              {customNs.length === 0 ? (
                <div className="px-4 py-6 text-center text-[#444] text-xs">No custom namespaces yet.</div>
              ) : (
                <div className="divide-y divide-[#1a1a1a]">
                  {customNs.map((ns) => (
                    <div key={ns} className="flex items-center justify-between px-4 py-2.5 hover:bg-[#161616]">
                      <div className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#10a37f] flex-shrink-0" />
                        <span className="text-sm text-[#ccc] font-mono">{ns}</span>
                      </div>
                      <button
                        onClick={() => handleDeleteNamespaceDirect(ns)}
                        disabled={nsLoading}
                        className="text-[10px] text-[#444] hover:text-red-400 transition-colors disabled:opacity-40"
                      >
                        Delete
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════
            Danger Zone (always visible below tabs)
        ══════════════════════════════════════════════════════════════════ */}
        <div className="mt-8 border border-red-900/40 rounded-xl overflow-hidden">
          <button
            onClick={() => setDangerOpen((o) => !o)}
            className="w-full flex items-center justify-between px-4 py-3 bg-red-950/20 hover:bg-red-950/30 transition-colors"
          >
            <span className="text-sm font-semibold text-red-400">⚠ Danger Zone</span>
            <span className="text-[#555] text-xs">{dangerOpen ? '▲ Hide' : '▼ Show'}</span>
          </button>

          {dangerOpen && (
            <div className="px-4 py-4 flex flex-col gap-5 bg-[#0d0d0d]">

              {/* Re-index */}
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-[#ccc]">Re-index All Documents</p>
                  <p className="text-[11px] text-[#555] mt-0.5">Clears all vectors and parent chunks, then rebuilds from existing files. Original PDFs are preserved.</p>
                  {reindexMsg && (
                    <p className={`text-xs mt-1 ${reindexMsg.includes('error') || reindexMsg.includes('failed') ? 'text-red-400' : 'text-[#10a37f]'}`}>{reindexMsg}</p>
                  )}
                </div>
                <button onClick={() => setConfirmReindex(true)} disabled={reindexing}
                  className="shrink-0 px-3 py-1.5 text-xs rounded-lg border border-[#2d2d2d] text-[#888] hover:bg-[#1a1a1a] hover:text-[#ccc] disabled:opacity-50 transition-colors">
                  {reindexing ? 'Re-indexing…' : 'Re-index All'}
                </button>
              </div>

              <div className="border-t border-red-900/20" />

              {/* Delete by namespace */}
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <p className="text-sm font-medium text-[#ccc]">Delete by State / Namespace</p>
                  <p className="text-[11px] text-[#555] mt-0.5">Removes all vectors, chunks, and files for a specific state. Cannot be undone.</p>
                  <select value={dangerNamespace} onChange={(e) => setDangerNamespace(e.target.value)}
                    className="mt-2 bg-[#1a1a1a] border border-[#2d2d2d] rounded-lg px-3 py-1.5 text-xs text-[#ccc] outline-none">
                    <option value="">Select state…</option>
                    {namespaces.map((ns) => <option key={ns} value={ns}>{ns}</option>)}
                  </select>
                </div>
                <button onClick={() => dangerNamespace && setConfirmDelete({ type: 'namespace', state: dangerNamespace })}
                  disabled={!dangerNamespace}
                  className="shrink-0 mt-0.5 px-3 py-1.5 text-xs rounded-lg border border-red-900/50 text-red-400 hover:bg-red-950/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                  Delete State
                </button>
              </div>

              <div className="border-t border-red-900/20" />

              {/* Delete all */}
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-[#ccc]">Delete All Files</p>
                  <p className="text-[11px] text-[#555] mt-0.5">Permanently removes every document, vector, and chunk across all namespaces. Cannot be undone.</p>
                </div>
                <button onClick={() => setConfirmDelete({ type: 'all' })}
                  className="shrink-0 px-3 py-1.5 text-xs rounded-lg border border-red-900/50 text-red-400 hover:bg-red-950/30 transition-colors">
                  Delete All
                </button>
              </div>

            </div>
          )}
        </div>

        <div className="pb-8" />
      </div>
    </div>
  )
}
