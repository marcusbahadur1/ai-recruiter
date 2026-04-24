'use client'
import { useTranslations } from 'next-intl'
import { useCallback, useEffect, useRef, useState } from 'react'
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import { chatApi } from '@/lib/api'

const queryClient = new QueryClient()

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  streaming?: boolean
}

function ChatContent() {
  const t = useTranslations('chat')
  const qc = useQueryClient()
  const [sessionIdParam, setSessionIdParam] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    setSessionIdParam(params.get('session_id'))
  }, [])

  const { data: session } = useQuery({
    queryKey: ['chat-session', sessionIdParam],
    queryFn: () =>
      sessionIdParam
        ? chatApi.getSession(sessionIdParam)
        : chatApi.getCurrentSession(),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

  useEffect(() => {
    if (session) {
      setSessionId(session.id)
      const visible = (session.messages ?? []).filter(
        (m) => typeof m.role === 'string' && !m.role.startsWith('_')
      )
      setMessages(visible)
    }
  }, [session])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = useCallback(async () => {
    if (!input.trim() || isStreaming || !sessionId) return

    const content = input
    setInput('')

    const userMsg: Message = { role: 'user', content, timestamp: new Date().toISOString() }
    setMessages(prev => [...prev, userMsg])

    // Placeholder assistant message shown while streaming
    const assistantMsg: Message = { role: 'assistant', content: '', timestamp: new Date().toISOString(), streaming: true }
    setMessages(prev => [...prev, assistantMsg])
    setIsStreaming(true)

    try {
      for await (const event of chatApi.sendMessageStream(sessionId, content)) {
        if (event.error) {
          setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              role: 'assistant',
              content: `⚠️ ${event.error}`,
              timestamp: new Date().toISOString(),
              streaming: false,
            }
            return updated
          })
          return
        }

        if (event.token) {
          setMessages(prev => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            updated[updated.length - 1] = { ...last, content: last.content + event.token }
            return updated
          })
        }

        if (event.done) {
          setMessages(prev => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            updated[updated.length - 1] = {
              ...last,
              // Use authoritative parsed message from backend (handles payment success text etc.)
              content: event.final_message ?? last.content,
              streaming: false,
            }
            return updated
          })
        }
      }
    } catch {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: '⚠️ Something went wrong. Please try again.',
          timestamp: new Date().toISOString(),
          streaming: false,
        }
        return updated
      })
    } finally {
      setIsStreaming(false)
    }
  }, [input, isStreaming, sessionId])

  const handleNewJob = async () => {
    const newSession = await chatApi.newSession()
    qc.setQueryData(['chat-session'], newSession)
    setSessionId(newSession.id)
    setMessages([])
  }

  const showWelcome = messages.length === 0

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
          {/* Welcome message — shown immediately, no waiting for session load */}
          {showWelcome && (
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
                      {msg.streaming && <span className="streaming-cursor">▋</span>}
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

          {/* Typing indicator — only shown before the first streaming token arrives */}
          {isStreaming && messages[messages.length - 1]?.content === '' && (
            <div className="msg bot" style={{ marginTop: -8 }}>
              <div className="msg-avatar bot">AI</div>
              <div>
                <div className="msg-bubble" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  {[0, 1, 2].map((i) => (
                    <div key={i} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--muted)', animation: 'bounce 1s infinite', animationDelay: `${i * 0.2}s` }} />
                  ))}
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
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
            <button className="send-btn" onClick={handleSend} disabled={!input.trim() || isStreaming}>➤</button>
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

      <style>{`
        @keyframes spin { to { transform: rotate(360deg) } }
        @keyframes bounce { 0%,100% { transform: translateY(0) } 50% { transform: translateY(-4px) } }
        @keyframes blink { 0%,100% { opacity: 1 } 50% { opacity: 0 } }
        .streaming-cursor { display: inline-block; animation: blink 1s step-start infinite; margin-left: 1px; }
      `}</style>
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
