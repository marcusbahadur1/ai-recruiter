'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import { Link, useRouter } from '@/i18n/navigation'
import { chatApi, type ChatSessionListItem, type ChatSession } from '@/lib/api'

const queryClient = new QueryClient()

const ACTIVE_PHASES = new Set(['job_collection', 'payment', 'recruitment'])

function phaseLabel(phase: string): string {
  const map: Record<string, string> = {
    job_collection: 'Collecting job details',
    payment: 'Awaiting payment',
    recruitment: 'Recruiting',
    post_recruitment: 'Completed',
  }
  return map[phase] ?? phase
}

function phaseBadgeClass(phase: string): string {
  if (phase === 'post_recruitment') return 'badge-closed'
  if (phase === 'payment') return 'badge-payment'
  if (phase === 'recruitment') return 'badge-active'
  return 'badge-scout'
}

interface Message {
  role: 'user' | 'assistant' | 'system'
  // content may arrive as a string or as a structured object (e.g. collected job_fields)
  content: unknown
  timestamp?: string
}

function SessionDetailModal({
  session,
  jobTitle,
  onClose,
}: {
  session: ChatSession
  jobTitle?: string
  onClose: () => void
}) {
  const messages = (session.messages ?? []) as Message[]
  // Only surface user/assistant turns; skip hidden metadata roles
  const visibleMessages = messages.filter((m) => m.role === 'user' || m.role === 'assistant')

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%', maxWidth: 600, maxHeight: '80vh',
          background: 'var(--navy-mid)', border: '1px solid var(--border)',
          borderRadius: 12, display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--white)', fontSize: 14 }}>
              {jobTitle ?? 'New Job'}
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
              {visibleMessages.filter((m) => typeof m.content === 'string').length} messages · {phaseLabel(session.phase)}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 18, lineHeight: 1 }}
          >✕</button>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {visibleMessages.length === 0 && (
            <div style={{ textAlign: 'center', color: 'var(--muted)', fontSize: 13, padding: '32px 0' }}>
              No messages in this session.
            </div>
          )}
          {visibleMessages.map((msg, i) => {
            // If content is not a plain string it's a structured data object (e.g. job_fields).
            // Never render objects — show a neutral placeholder pill instead.
            if (typeof msg.content !== 'string') {
              return (
                <div key={i} style={{ display: 'flex', justifyContent: 'center' }}>
                  <span style={{ fontSize: 11, color: 'var(--muted)', background: 'var(--navy-light)', borderRadius: 12, padding: '3px 10px' }}>
                    📋 Job details collected
                  </span>
                </div>
              )
            }
            const text = msg.content
            return (
              <div
                key={i}
                style={{
                  display: 'flex',
                  flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                  gap: 10, alignItems: 'flex-start',
                }}
              >
                <div style={{
                  width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                  background: msg.role === 'user'
                    ? 'linear-gradient(135deg,#667eea,#764ba2)'
                    : 'linear-gradient(135deg,var(--blue),var(--cyan))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, fontWeight: 700, color: '#fff',
                }}>
                  {msg.role === 'user' ? 'YOU' : 'AI'}
                </div>
                <div style={{
                  maxWidth: '75%', padding: '8px 12px', borderRadius: 10, fontSize: 13,
                  background: msg.role === 'user' ? 'var(--blue-dim)' : 'var(--navy-light)',
                  color: 'var(--white)', lineHeight: 1.5,
                  borderTopRightRadius: msg.role === 'user' ? 2 : 10,
                  borderTopLeftRadius: msg.role === 'user' ? 10 : 2,
                }}>
                  {msg.role === 'assistant' ? (
                    <div className="md-content"><ReactMarkdown>{text}</ReactMarkdown></div>
                  ) : (
                    text
                  )}
                  {msg.timestamp && (
                    <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4 }}>
                      {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function HistoryContent() {
  const router = useRouter()
  const [selectedSession, setSelectedSession] = useState<ChatSession | null>(null)
  const [selectedItem, setSelectedItem] = useState<ChatSessionListItem | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['chat-sessions'],
    queryFn: () => chatApi.listSessions({ limit: 50 }),
  })

  const sessions = data?.items ?? []

  const handleView = async (item: ChatSessionListItem) => {
    setLoadingId(item.id)
    setSelectedItem(item)
    try {
      const full = await chatApi.getSession(item.id)
      setSelectedSession(full)
    } finally {
      setLoadingId(null)
    }
  }

  const handleResume = (item: ChatSessionListItem) => {
    router.push(`/chat?session_id=${item.id}`)
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '24px' }}>
      <div className="section-header">
        <div>
          <div className="section-title">Chat History</div>
          <div className="section-sub">{data?.total ?? 0} sessions</div>
        </div>
        <Link href="/chat" className="btn btn-cyan">+ New Job</Link>
      </div>

      <div className="card">
        {isLoading && (
          <div style={{ textAlign: 'center', padding: '48px', color: 'var(--muted)' }}>Loading...</div>
        )}

        {!isLoading && sessions.length === 0 && (
          <div style={{ textAlign: 'center', padding: '48px' }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>💬</div>
            <div style={{ color: 'var(--white)', fontWeight: 600, marginBottom: 6 }}>No sessions yet</div>
            <div style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 20 }}>
              Start a conversation to post your first job.
            </div>
            <Link href="/chat" className="btn btn-cyan">Start chatting</Link>
          </div>
        )}

        {sessions.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Status</th>
                  <th>Messages</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((item) => {
                  const isActive = ACTIVE_PHASES.has(item.phase)
                  return (
                    <tr key={item.id}>
                      <td style={{ maxWidth: 280 }}>
                        {item.job_id ? (
                          <Link
                            href={`/jobs/${item.job_id}`}
                            style={{ textDecoration: 'none' }}
                          >
                            <div className="td-name" style={{ cursor: 'pointer', color: 'var(--cyan)' }}>
                              {item.job_title ?? 'New Job'}
                            </div>
                          </Link>
                        ) : (
                          <div
                            className="td-name"
                            style={{ cursor: 'pointer', color: 'var(--cyan)' }}
                            onClick={() => router.push(`/chat?session_id=${item.id}`)}
                          >
                            New Job
                          </div>
                        )}
                        {item.preview && item.preview !== 'New session' && (
                          <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                            {item.preview}
                          </div>
                        )}
                      </td>
                      <td>
                        <span className={`badge ${phaseBadgeClass(item.phase)}`}>
                          {isActive ? '● ' : ''}{phaseLabel(item.phase)}
                        </span>
                      </td>
                      <td style={{ color: 'var(--muted)', fontSize: 13 }}>{item.message_count}</td>
                      <td style={{ color: 'var(--muted)', fontSize: 11 }}>
                        {new Date(item.created_at).toLocaleDateString('en-AU', {
                          day: 'numeric', month: 'short', year: 'numeric',
                        })}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => handleView(item)}
                            disabled={loadingId === item.id}
                          >
                            {loadingId === item.id ? '…' : 'View'}
                          </button>
                          {isActive && (
                            <button
                              className="btn btn-cyan btn-sm"
                              onClick={() => handleResume(item)}
                            >
                              Resume
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedSession && (
        <SessionDetailModal
          session={selectedSession}
          jobTitle={selectedItem?.job_title ?? undefined}
          onClose={() => { setSelectedSession(null); setSelectedItem(null) }}
        />
      )}
    </div>
  )
}

export default function ChatHistoryPage() {
  return (
    <QueryClientProvider client={queryClient}>
      <HistoryContent />
    </QueryClientProvider>
  )
}
