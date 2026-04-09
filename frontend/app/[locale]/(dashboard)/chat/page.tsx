'use client'
import { useTranslations } from 'next-intl'
import { useEffect, useRef, useState } from 'react'
import { QueryClient, QueryClientProvider, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import { chatApi } from '@/lib/api'

const queryClient = new QueryClient()

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

function scorePillClass(score: number): string {
  if (score >= 8) return 'score-high'
  if (score >= 6) return 'score-mid'
  return 'score-low'
}

function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    passed: 'badge-passed', failed: 'badge-failed', emailed: 'badge-emailed',
  }
  return map[status] ?? 'badge-discovered'
}

function ChatContent() {
  const t = useTranslations('chat')
  const qc = useQueryClient()
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { data: session, isLoading } = useQuery({
    queryKey: ['chat-session'],
    queryFn: () => chatApi.getCurrentSession(),
  })

  useEffect(() => {
    if (session) {
      setSessionId(session.id)
      // Filter out hidden metadata entries (role starts with '_', e.g. _job_data)
      // whose content is an object, not a string — rendering them crashes React.
      const visible = (session.messages ?? []).filter(
        (m) => typeof m.role === 'string' && !m.role.startsWith('_')
      )
      setMessages(visible)
    }
  }, [session])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      if (!sessionId) return
      return chatApi.sendMessage(sessionId, content)
    },
    onSuccess: (data) => {
      if (data) setMessages((prev) => [...prev, data as Message])
    },
  })

  const handleSend = () => {
    if (!input.trim() || sendMutation.isPending) return
    const userMsg: Message = { role: 'user', content: input, timestamp: new Date().toISOString() }
    setMessages((prev) => [...prev, userMsg])
    sendMutation.mutate(input)
    setInput('')
  }

  const handleNewJob = async () => {
    const newSession = await chatApi.newSession()
    // Update the query cache immediately so the useEffect seeing `session`
    // reflects the new empty session rather than the old one.
    qc.setQueryData(['chat-session'], newSession)
    setSessionId(newSession.id)
    setMessages([])
  }

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>

      {/* ── Chat panel (480px) ── */}
      <div className="chat-panel">
        {/* Header */}
        <div className="chat-header">
          <div className="chat-avatar">AI</div>
          <div>
            <div className="chat-bot-name">AI Recruiter</div>
            <div className="chat-bot-status">
              <span className="status-dot"/>
              Online{session ? ' · Active session' : ''}
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" style={{ marginLeft: 'auto' }} onClick={handleNewJob}>
            + New Job
          </button>
        </div>

        {/* Messages */}
        <div className="chat-messages">
          {isLoading && (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
              <div style={{ width: 20, height: 20, borderRadius: '50%', border: '2px solid var(--cyan)', borderTopColor: 'transparent', animation: 'spin 0.8s linear infinite' }}/>
            </div>
          )}

          {!isLoading && messages.length === 0 && (
            <div className="msg bot">
              <div className="msg-avatar bot">AI</div>
              <div>
                <div className="msg-bubble">
                  Hi! I&apos;m your AI Recruiter. I can help you post a new job and start sourcing candidates immediately. You can paste a job description or just describe the role — I&apos;ll take it from there.
                </div>
                <span className="msg-time">{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`msg ${msg.role === 'user' ? 'user' : 'bot'}`}>
              <div className={`msg-avatar ${msg.role === 'user' ? 'user' : 'bot'}`}>
                {msg.role === 'user' ? 'MB' : 'AI'}
              </div>
              <div>
                <div className="msg-bubble">
                  {msg.role === 'assistant' ? (
                    <div className="md-content">
                      <ReactMarkdown>{typeof msg.content === 'string' ? msg.content : ''}</ReactMarkdown>
                    </div>
                  ) : (
                    typeof msg.content === 'string' ? msg.content : null
                  )}
                </div>
                <span className="msg-time" style={msg.role === 'user' ? { textAlign: 'right', display: 'block' } : {}}>
                  {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
          ))}

          {sendMutation.isPending && (
            <div className="msg bot">
              <div className="msg-avatar bot">AI</div>
              <div>
                <div className="msg-bubble" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  {[0,1,2].map((i) => (
                    <div key={i} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--muted)', animation: 'bounce 1s infinite', animationDelay: `${i*0.2}s` }}/>
                  ))}
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef}/>
        </div>

        {/* Input */}
        <div className="chat-input-area">
          <div className="chat-input-wrap">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder={t('placeholder')}
            />
            <button className="send-btn" onClick={handleSend} disabled={!input.trim() || sendMutation.isPending}>➤</button>
          </div>
        </div>
      </div>

      {/* ── Eval report panel ── */}
      <div className="eval-panel">
        <div className="eval-header">
          <div className="eval-title">📊 Evaluation Report{session ? ` — Active Job` : ''}</div>
          <div className="live-badge"><div className="live-dot"/>Live</div>
        </div>
        <div className="eval-body">
          {!session ? (
            <div className="empty-state">
              <div className="empty-icon">📊</div>
              <div className="empty-text">Start a job search to see candidates scored in real-time.</div>
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">📊</div>
              <div className="empty-text">Candidates will appear here as the Talent Scout discovers them.</div>
            </div>
          )}
        </div>
      </div>

      <style>{`@keyframes spin{to{transform:rotate(360deg)}} @keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}`}</style>
    </div>
  )
}

export default function ChatPage() {
  return (
    <QueryClientProvider client={queryClient}>
      <ChatContent />
    </QueryClientProvider>
  )
}
