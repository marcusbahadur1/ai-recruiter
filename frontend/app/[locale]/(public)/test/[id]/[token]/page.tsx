'use client'
import { use, useEffect, useRef, useState } from 'react'

interface Message { role: 'user' | 'assistant'; content: string }

export default function PublicTestPage({ params }: { params: Promise<{ id: string; token: string }> }) {
  const { id, token } = use(params)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [started, setStarted] = useState(false)
  const [completed, setCompleted] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (content: string) => {
    if (!content.trim() || loading) return
    setLoading(true)
    const userMsg: Message = { role: 'user', content }
    setMessages((prev) => [...prev, userMsg])
    setInput('')

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/test/${id}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, token }),
      })
      const data = await res.json()
      setMessages((prev) => [...prev, { role: 'assistant', content: data.content }])
      if (data.completed) setCompleted(true)
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: 'Sorry, there was an error. Please try again.' }])
    } finally {
      setLoading(false)
    }
  }

  const startTest = async () => {
    setStarted(true)
    setLoading(true)
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/test/${id}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: '__start__', token }),
      })
      const data = await res.json()
      setMessages([{ role: 'assistant', content: data.content }])
    } catch {
      setMessages([{ role: 'assistant', content: 'Welcome! I will be asking you a series of questions. When you are ready, please introduce yourself briefly.' }])
    } finally {
      setLoading(false)
    }
  }

  if (completed) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--navy)' }}>
        <div className="text-center max-w-md px-4">
          <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4" style={{ background: '#10B98120' }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Test Completed</h1>
          <p className="text-slate-400">Thank you for completing the assessment. We will review your answers and be in touch soon.</p>
        </div>
      </div>
    )
  }

  if (!started) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--navy)' }}>
        <div className="max-w-md w-full px-4 text-center">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6" style={{ background: 'var(--cyan)' }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#0D1B2A" strokeWidth="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">AI Competency Assessment</h1>
          <p className="text-slate-400 text-sm mb-8 leading-relaxed">
            You have been invited to complete an AI-powered competency assessment. The AI examiner will ask you several questions related to the role. Answer thoughtfully and honestly.
          </p>
          <ul className="text-left space-y-2 mb-8 text-sm text-slate-400">
            <li className="flex items-center gap-2"><span style={{ color: 'var(--cyan)' }}>✓</span> Answer each question in your own words</li>
            <li className="flex items-center gap-2"><span style={{ color: 'var(--cyan)' }}>✓</span> The AI may ask follow-up questions</li>
            <li className="flex items-center gap-2"><span style={{ color: 'var(--cyan)' }}>✓</span> Typically takes 15–30 minutes</li>
            <li className="flex items-center gap-2"><span style={{ color: 'var(--cyan)' }}>✓</span> Stay on the same browser tab</li>
          </ul>
          <button onClick={startTest} className="w-full py-3 rounded-xl text-sm font-semibold text-white" style={{ background: 'var(--blue)' }}>
            Start Assessment
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--navy)' }}>
      {/* Header */}
      <header className="px-6 py-4 border-b flex items-center gap-3" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
        <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'var(--cyan)' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0D1B2A" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        </div>
        <div>
          <p className="text-white text-sm font-semibold">AI Competency Assessment</p>
          <p className="text-slate-500 text-xs">Powered by AI Recruiter</p>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 max-w-2xl mx-auto w-full space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="w-7 h-7 rounded-lg flex items-center justify-center mr-2.5 flex-shrink-0 mt-0.5" style={{ background: 'var(--cyan)' }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#0D1B2A" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/></svg>
              </div>
            )}
            <div
              className="max-w-[80%] rounded-xl px-4 py-3 text-sm leading-relaxed"
              style={{
                background: msg.role === 'user' ? 'var(--blue)' : 'var(--navy-light)',
                color: 'white',
                borderRadius: msg.role === 'user' ? '18px 18px 4px 18px' : '4px 18px 18px 18px',
                border: msg.role === 'assistant' ? '1px solid var(--navy-border)' : 'none',
              }}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center mr-2.5" style={{ background: 'var(--cyan)' }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#0D1B2A" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/></svg>
            </div>
            <div className="px-4 py-3 rounded-xl flex items-center gap-1" style={{ background: 'var(--navy-light)', border: '1px solid var(--navy-border)' }}>
              {[0,1,2].map((i) => <div key={i} className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--cyan)', animationDelay: `${i*0.15}s` }}/>)}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t max-w-2xl mx-auto w-full" style={{ borderColor: 'var(--navy-border)' }}>
        <div className="flex gap-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
            placeholder="Type your answer..."
            className="flex-1 px-4 py-2.5 rounded-xl text-sm text-white placeholder-slate-500 border outline-none focus:border-cyan-500 transition-colors"
            style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            className="px-4 py-2.5 rounded-xl text-sm font-medium text-white transition-colors disabled:opacity-40"
            style={{ background: 'var(--blue)' }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
