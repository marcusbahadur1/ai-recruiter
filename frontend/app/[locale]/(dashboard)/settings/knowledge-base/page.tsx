'use client'
import { useEffect, useRef, useState } from 'react'
import { useRouter } from '@/i18n/navigation'
import { ragApi, settingsApi } from '@/lib/api'
import type { RagDocument, Tenant } from '@/lib/api'

// Plans that include the Chat Widget + RAG feature
const WIDGET_PLANS = new Set(['agency_small', 'agency_medium', 'enterprise'])

function fmt(date: string) {
  return new Date(date).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })
}

function fmtTime(date: string) {
  return new Date(date).toLocaleString('en-AU', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

// Group all chunks by their source key (filename or source_url)
function groupDocs(docs: RagDocument[]) {
  const groups: Record<string, RagDocument[]> = {}
  for (const doc of docs) {
    const key = doc.filename ?? doc.source_url ?? doc.id
    ;(groups[key] = groups[key] ?? []).push(doc)
  }
  return groups
}

// Derive a scrape history timeline from chunks grouped by day
function scrapeHistory(docs: RagDocument[]): { date: string; count: number }[] {
  const byDay: Record<string, number> = {}
  for (const doc of docs) {
    const day = doc.created_at.slice(0, 10)
    byDay[day] = (byDay[day] ?? 0) + 1
  }
  return Object.entries(byDay)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, count]) => ({ date, count }))
}

// ── Source card ───────────────────────────────────────────────────────────────

interface SourceCardProps {
  label: string
  docs: RagDocument[]
  isWebsite: boolean
  onDelete: (ids: string[]) => Promise<void>
  onRescrape?: (url: string, ids: string[]) => Promise<void>
  deleting: boolean
  rescraping: boolean
}

function SourceCard({ label, docs, isWebsite, onDelete, onRescrape, deleting, rescraping }: SourceCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [expandedChunks, setExpandedChunks] = useState<Record<string, boolean>>({})
  const ids       = docs.map(d => d.id)
  const oldest    = docs.reduce((a, b) => a.created_at < b.created_at ? a : b)
  const newest    = docs.reduce((a, b) => a.created_at > b.created_at ? a : b)
  const history   = isWebsite ? scrapeHistory(docs) : null
  const sourceUrl = docs[0].source_url

  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 10,
      overflow: 'hidden', marginBottom: 10,
    }}>
      {/* Card header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '12px 16px', background: 'var(--card)',
      }}>
        <span style={{ fontSize: 20, flexShrink: 0 }}>{isWebsite ? '🌐' : '📄'}</span>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--white)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {label}
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
            {docs.length} chunk{docs.length !== 1 ? 's' : ''}
            {' · '}
            {isWebsite
              ? history && history.length > 1
                ? `${history.length} scrapes · last ${fmt(newest.created_at)}`
                : `scraped ${fmt(oldest.created_at)}`
              : `uploaded ${fmt(oldest.created_at)}`}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
          {isWebsite && onRescrape && sourceUrl && (
            <button
              className="btn btn-primary btn-sm"
              disabled={rescraping || deleting}
              onClick={() => onRescrape(sourceUrl, ids)}
            >
              {rescraping ? 'Scraping…' : 'Re-scrape'}
            </button>
          )}
          <button
            className="btn btn-ghost btn-sm"
            style={{ color: 'var(--red)' }}
            disabled={deleting || rescraping}
            onClick={() => onDelete(ids)}
          >
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setExpanded(e => !e)}
            style={{ color: 'var(--muted)', minWidth: 28 }}
          >
            {expanded ? '▲' : '▼'}
          </button>
        </div>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div style={{ borderTop: '1px solid var(--border)', background: 'var(--navy-mid)' }}>

          {/* Scrape history timeline (website only) */}
          {isWebsite && history && history.length > 0 && (
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
                Scrape History
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {history.map(({ date, count }) => (
                  <div key={date} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12 }}>
                    <div style={{
                      width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                      background: 'var(--cyan)',
                    }} />
                    <span style={{ color: 'var(--muted)' }}>{fmt(date)}</span>
                    <span style={{ color: 'var(--white)' }}>{count} chunk{count !== 1 ? 's' : ''} stored</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Chunk list */}
          <div style={{ padding: '12px 16px' }}>
            <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
              Chunks ({docs.length})
            </div>
            {docs.map((doc, i) => {
              const isOpen = expandedChunks[doc.id]
              const preview = doc.content_text.slice(0, 220)
              const hasMore = doc.content_text.length > 220
              return (
                <div key={doc.id} style={{
                  background: 'var(--card)', border: '1px solid var(--border)',
                  borderRadius: 6, padding: '10px 12px', marginBottom: 6,
                }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                    <div style={{ fontSize: 11, color: 'var(--muted)', flexShrink: 0, marginTop: 1 }}>
                      #{i + 1}
                    </div>
                    <div style={{ flex: 1, fontSize: 12, color: 'var(--fg)', lineHeight: 1.6, fontFamily: 'DM Mono, monospace' }}>
                      {isOpen ? doc.content_text : preview}
                      {!isOpen && hasMore && '…'}
                    </div>
                    {hasMore && (
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ fontSize: 11, flexShrink: 0, padding: '2px 8px' }}
                        onClick={() => setExpandedChunks(p => ({ ...p, [doc.id]: !p[doc.id] }))}
                      >
                        {isOpen ? 'Less' : 'More'}
                      </button>
                    )}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 6 }}>
                    {fmtTime(doc.created_at)}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function KnowledgeBasePage() {
  const router    = useRouter()
  const fileRef   = useRef<HTMLInputElement>(null)
  const [tenant, setTenant]         = useState<Tenant | null>(null)
  const [docs, setDocs]             = useState<RagDocument[]>([])
  const [loading, setLoading]       = useState(true)
  const [uploading, setUploading]   = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadOk, setUploadOk]     = useState(false)
  const [dragging, setDragging]     = useState(false)
  const [scrapeUrl, setScrapeUrl]   = useState('')
  const [scraping, setScraping]     = useState(false)
  const [scrapeMsg, setScrapeMsg]   = useState<{ ok: boolean; text: string } | null>(null)
  // per-source loading state
  const [deletingKey, setDeletingKey]     = useState<string | null>(null)
  const [rescrapingKey, setRescrapingKey] = useState<string | null>(null)
  const [rescrapeAllBusy, setRescrapeAllBusy] = useState(false)

  async function load() {
    try {
      const t = await settingsApi.getTenant()
      setTenant(t)
    } catch {
      // auth failure — layout will redirect to login
    }

    try {
      const d = await ragApi.getDocuments({ limit: 500 })
      setDocs(d.items)
    } catch {
      // 403 if plan doesn't include RAG — planOk check handles the UI
    }

    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const groups      = groupDocs(docs)
  const websiteKeys = Object.keys(groups).filter(k => groups[k][0].source_type === 'website_scrape')
  const uploadKeys  = Object.keys(groups).filter(k => groups[k][0].source_type === 'manual_upload')
  const totalChunks = docs.length
  const lastUpdated = docs.length > 0
    ? docs.reduce((a, b) => a.created_at > b.created_at ? a : b).created_at
    : null

  const planOk = tenant ? WIDGET_PLANS.has(tenant.plan) : false

  // ── Actions ──────────────────────────────────────────────────────────────────

  async function handleUpload(file: File) {
    setUploadError(null)
    setUploadOk(false)
    setUploading(true)
    try {
      await ragApi.uploadDocument(file)
      setUploadOk(true)
      setTimeout(() => setUploadOk(false), 3000)
      await load()
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  async function handleDelete(ids: string[], key: string) {
    setDeletingKey(key)
    try {
      await Promise.all(ids.map(id => ragApi.deleteDocument(id)))
      await load()
    } finally {
      setDeletingKey(null)
    }
  }

  async function handleRescrape(url: string, existingIds: string[], key: string) {
    setRescrapingKey(key)
    setScrapeMsg(null)
    try {
      // Delete existing chunks for this URL first to avoid duplicates
      await Promise.all(existingIds.map(id => ragApi.deleteDocument(id)))
      const result = await ragApi.scrapeWebsite(url)
      setScrapeMsg({ ok: true, text: `Re-scraped — ${result.chunks_stored} chunks stored` })
      await load()
    } catch (err: unknown) {
      setScrapeMsg({ ok: false, text: err instanceof Error ? err.message : 'Re-scrape failed' })
    } finally {
      setRescrapingKey(null)
    }
  }

  async function handleScrapeNew() {
    if (!scrapeUrl.trim()) return
    setScraping(true)
    setScrapeMsg(null)
    try {
      const result = await ragApi.scrapeWebsite(scrapeUrl.trim())
      setScrapeMsg({ ok: true, text: `Scraped — ${result.chunks_stored} chunks stored from ${scrapeUrl}` })
      setScrapeUrl('')
      await load()
    } catch (err: unknown) {
      setScrapeMsg({ ok: false, text: err instanceof Error ? err.message : 'Scrape failed' })
    } finally {
      setScraping(false)
    }
  }

  async function handleRescrapeAll() {
    setRescrapeAllBusy(true)
    setScrapeMsg(null)
    let total = 0
    try {
      for (const key of websiteKeys) {
        const urlDocs = groups[key]
        const url     = urlDocs[0].source_url!
        const ids     = urlDocs.map(d => d.id)
        await Promise.all(ids.map(id => ragApi.deleteDocument(id)))
        const result  = await ragApi.scrapeWebsite(url)
        total += result.chunks_stored
      }
      setScrapeMsg({ ok: true, text: `Re-scraped ${websiteKeys.length} site${websiteKeys.length !== 1 ? 's' : ''} — ${total} chunks stored` })
      await load()
    } catch (err: unknown) {
      setScrapeMsg({ ok: false, text: err instanceof Error ? err.message : 'Re-scrape failed' })
    } finally {
      setRescrapeAllBusy(false)
    }
  }

  // ── Drag and drop ─────────────────────────────────────────────────────────

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleUpload(file)
  }

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return <div style={{ padding: 32, color: 'var(--muted)', fontSize: 14 }}>Loading knowledge base…</div>
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 24, maxWidth: 860 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <button
              className="btn btn-ghost btn-sm"
              style={{ color: 'var(--muted)', padding: '2px 0' }}
              onClick={() => router.push('/settings')}
            >
              ← Settings
            </button>
          </div>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Knowledge Base</h1>
          <p style={{ fontSize: 13, color: 'var(--muted)', margin: '4px 0 0' }}>
            Documents and website content your AI Chat Widget uses to answer candidate questions
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {websiteKeys.length > 1 && planOk && (
            <button
              className="btn btn-primary"
              disabled={rescrapeAllBusy}
              onClick={handleRescrapeAll}
            >
              {rescrapeAllBusy ? 'Re-scraping…' : `Re-scrape All (${websiteKeys.length})`}
            </button>
          )}
          {planOk && (
            <button className="btn btn-primary" onClick={() => fileRef.current?.click()} disabled={uploading}>
              {uploading ? 'Uploading…' : '+ Upload Document'}
            </button>
          )}
        </div>
      </div>

      {/* Plan guard */}
      {!planOk && (
        <div style={{
          background: 'rgba(27,108,168,0.1)', border: '1px solid var(--blue)',
          borderRadius: 10, padding: '20px 24px', marginBottom: 24, textAlign: 'center',
        }}>
          <div style={{ fontSize: 22, marginBottom: 8 }}>🔒</div>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>Agency Small plan or above required</div>
          <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 14 }}>
            The Knowledge Base and Chat Widget are available from the Agency Small plan.
          </div>
          <button className="btn btn-cyan" onClick={() => router.push('/billing')}>
            Upgrade Plan →
          </button>
        </div>
      )}

      {planOk && (
        <>
          {/* Stats row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
            <div className="stat-card">
              <div className="stat-label">Sources</div>
              <div className="stat-value">{Object.keys(groups).length}</div>
            </div>
            <div className="stat-card green">
              <div className="stat-label">Total Chunks</div>
              <div className="stat-value">{totalChunks}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Last Updated</div>
              <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4 }}>
                {lastUpdated ? fmt(lastUpdated) : '—'}
              </div>
            </div>
          </div>

          {/* Global feedback */}
          {scrapeMsg && (
            <div style={{
              padding: '10px 14px', borderRadius: 8, marginBottom: 16, fontSize: 13,
              background: scrapeMsg.ok ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
              border: `1px solid ${scrapeMsg.ok ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
              color: scrapeMsg.ok ? 'var(--green)' : 'var(--red)',
            }}>
              {scrapeMsg.ok ? '✓ ' : '✕ '}{scrapeMsg.text}
            </div>
          )}

          {/* ── Website Sources ───────────────────────────────────────────── */}
          {websiteKeys.length > 0 && (
            <div style={{ marginBottom: 28 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>
                Website Sources ({websiteKeys.length})
              </div>
              {websiteKeys.map(key => (
                <SourceCard
                  key={key}
                  label={groups[key][0].source_url?.replace(/^https?:\/\//, '').replace(/\/$/, '') ?? key}
                  docs={groups[key]}
                  isWebsite
                  onDelete={(ids) => handleDelete(ids, key)}
                  onRescrape={(url, ids) => handleRescrape(url, ids, key)}
                  deleting={deletingKey === key}
                  rescraping={rescrapingKey === key}
                />
              ))}
            </div>
          )}

          {/* ── Uploaded Documents ────────────────────────────────────────── */}
          {uploadKeys.length > 0 && (
            <div style={{ marginBottom: 28 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>
                Uploaded Documents ({uploadKeys.length})
              </div>
              {uploadKeys.map(key => (
                <SourceCard
                  key={key}
                  label={groups[key][0].filename ?? key}
                  docs={groups[key]}
                  isWebsite={false}
                  onDelete={(ids) => handleDelete(ids, key)}
                  deleting={deletingKey === key}
                  rescraping={false}
                />
              ))}
            </div>
          )}

          {/* Empty state */}
          {Object.keys(groups).length === 0 && (
            <div style={{
              textAlign: 'center', padding: '40px 24px',
              border: '1px dashed var(--border)', borderRadius: 10, marginBottom: 28,
            }}>
              <div style={{ fontSize: 32, marginBottom: 10 }}>📚</div>
              <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>No knowledge base yet</div>
              <div style={{ fontSize: 13, color: 'var(--muted)' }}>
                Upload documents or scrape your website below to get started.
              </div>
            </div>
          )}

          {/* ── Scrape a URL ─────────────────────────────────────────────── */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-title" style={{ marginBottom: 4 }}>Scrape a Website</div>
            <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 12 }}>
              Enter any URL — we'll crawl the page and store the content as searchable chunks.
              Your website URL from General settings is the default starting point.
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                type="url"
                className="input"
                placeholder={tenant?.website_url ?? 'https://your-firm.com'}
                value={scrapeUrl}
                onChange={e => setScrapeUrl(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleScrapeNew()}
                style={{ flex: 1 }}
              />
              <button
                className="btn btn-primary"
                disabled={scraping || !scrapeUrl.trim()}
                onClick={handleScrapeNew}
              >
                {scraping ? 'Scraping…' : 'Scrape'}
              </button>
            </div>
            {tenant?.website_url && scrapeUrl === '' && (
              <button
                className="btn btn-ghost btn-sm"
                style={{ marginTop: 8, color: 'var(--cyan)' }}
                onClick={() => { setScrapeUrl(tenant.website_url!); handleScrapeNew() }}
              >
                Scrape {tenant.website_url} →
              </button>
            )}
          </div>

          {/* ── Upload zone ──────────────────────────────────────────────── */}
          <div
            className="card"
            style={{
              borderStyle: 'dashed',
              borderColor: dragging ? 'var(--cyan)' : 'var(--border)',
              background: dragging ? 'var(--cyan-dim)' : undefined,
              textAlign: 'center', padding: '28px 24px', cursor: 'pointer',
              transition: 'all 0.15s',
            }}
            onClick={() => fileRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <div style={{ fontSize: 28, marginBottom: 8 }}>📂</div>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
              {uploading ? 'Uploading…' : 'Drop a file here or click to upload'}
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>PDF, DOCX, TXT · max 20 MB</div>
            {uploadOk && (
              <div style={{ color: 'var(--green)', fontSize: 13, marginTop: 8 }}>✓ Uploaded successfully</div>
            )}
            {uploadError && (
              <div style={{ color: 'var(--red)', fontSize: 13, marginTop: 8 }}>{uploadError}</div>
            )}
          </div>

          {/* Hidden file input */}
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.txt"
            style={{ display: 'none' }}
            onChange={e => {
              const file = e.target.files?.[0]
              if (file) { handleUpload(file); e.target.value = '' }
            }}
          />
        </>
      )}
    </div>
  )
}
