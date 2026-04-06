'use client'
import { useTranslations } from 'next-intl'
import { useEffect, useRef, useState } from 'react'
import { QueryClient, QueryClientProvider, useQuery, useMutation } from '@tanstack/react-query'
import { chatApi } from '@/lib/api'

const queryClient = new QueryClient()

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

function ChatContent() {
  const t = useTranslations('chat')
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [activeTab, setActiveTab] = useState<'chat' | 'report'>('chat')

  const { data: session, isLoading } = useQuery({
    queryKey: ['chat-session'],
    queryFn: () => chatApi.getCurrentSession(),
  })

  useEffect(() => {
    if (session) {
      setSessionId(session.id)
      setMessages(session.messages ?? [])
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
      if (data) {
        setMessages((prev) => [...prev, data as Message])
      }
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
    setSessionId(newSession.id)
    setMessages([])
  }

  return (
    <div className="h-full flex flex-col" style={{ height: 'calc(100vh - 120px)' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-white">{t('title')}</h1>
        <button
          onClick={handleNewJob}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white flex items-center gap-2"
          style={{ background: 'var(--blue)' }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          {t('newJob')}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 p-1 rounded-lg w-fit" style={{ background: 'var(--navy-light)' }}>
        {(['chat', 'report'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className="px-4 py-1.5 rounded-md text-sm font-medium transition-colors"
            style={{
              background: activeTab === tab ? 'var(--blue)' : 'transparent',
              color: activeTab === tab ? 'white' : '#94A3B8',
            }}
          >
            {tab === 'chat' ? 'Chat' : t('evaluationReport')}
          </button>
        ))}
      </div>

      {activeTab === 'chat' ? (
        <div className="flex-1 flex flex-col rounded-xl border overflow-hidden" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {isLoading && (
              <div className="flex justify-center py-8">
                <div className="w-5 h-5 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: 'var(--cyan)', borderTopColor: 'transparent' }} />
              </div>
            )}
            {!isLoading && messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center py-16">
                <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4" style={{ background: 'var(--cyan)20' }}>
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" strokeWidth="1.5">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                  </svg>
                </div>
                <p className="text-slate-300 font-medium">{t('noMessages')}</p>
                <p className="text-slate-500 text-sm mt-1">Describe a role or paste a job description to get started.</p>
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'assistant' && (
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center mr-2.5 flex-shrink-0 mt-0.5" style={{ background: 'var(--cyan)' }}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#0D1B2A" strokeWidth="2.5">
                      <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                    </svg>
                  </div>
                )}
                <div
                  className="max-w-[75%] rounded-xl px-4 py-3 text-sm leading-relaxed"
                  style={{
                    background: msg.role === 'user' ? 'var(--blue)' : 'var(--navy)',
                    color: 'white',
                    borderRadius: msg.role === 'user' ? '18px 18px 4px 18px' : '4px 18px 18px 18px',
                  }}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {sendMutation.isPending && (
              <div className="flex justify-start">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center mr-2.5 flex-shrink-0" style={{ background: 'var(--cyan)' }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#0D1B2A" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/></svg>
                </div>
                <div className="px-4 py-3 rounded-xl flex items-center gap-1" style={{ background: 'var(--navy)' }}>
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--cyan)', animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t" style={{ borderColor: 'var(--navy-border)' }}>
            <div className="flex gap-3">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                placeholder={t('placeholder')}
                className="flex-1 px-4 py-2.5 rounded-xl text-sm text-white placeholder-slate-500 border outline-none focus:border-cyan-500 transition-colors"
                style={{ background: 'var(--navy)', borderColor: 'var(--navy-border)' }}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || sendMutation.isPending}
                className="px-4 py-2.5 rounded-xl text-sm font-medium text-white transition-colors disabled:opacity-40"
                style={{ background: 'var(--blue)' }}
              >
                {t('send')}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 rounded-xl border overflow-auto" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          <div className="p-4">
            <p className="text-slate-400 text-sm">Evaluation report will appear here when a Talent Scout job is running.</p>
          </div>
        </div>
      )}
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
