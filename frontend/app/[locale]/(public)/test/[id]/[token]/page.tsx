'use client'
import { use, useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

interface QA { question: string; answer: string }

type Stage = 'landing' | 'active' | 'completed'

const s: Record<string, React.CSSProperties> = {
  page:        { minHeight: '100vh', background: '#f5f6fa', fontFamily: "'Inter', 'Segoe UI', sans-serif", color: '#1a1d23' },
  shell:       { maxWidth: 700, margin: '0 auto', padding: '0 20px 60px' },
  // Header
  header:      { textAlign: 'center', padding: '48px 0 32px' },
  firm:        { fontSize: 28, fontWeight: 800, color: '#1a1d23', marginBottom: 6, letterSpacing: '-0.5px' },
  role:        { fontSize: 15, color: '#6b7280', fontWeight: 400 },
  divider:     { height: 1, background: '#e5e7eb', margin: '28px 0' },
  // Progress
  progressWrap:{ marginBottom: 32 },
  progressLabel:{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  progressText:{ fontSize: 13, color: '#6b7280', fontWeight: 500 },
  progressPct: { fontSize: 13, color: '#00C2E0', fontWeight: 600 },
  progressBar: { height: 6, background: '#e5e7eb', borderRadius: 99, overflow: 'hidden' },
  progressFill:{ height: '100%', background: '#00C2E0', borderRadius: 99, transition: 'width 0.4s ease' },
  // Past QA cards
  pastCard:    { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '16px 20px', marginBottom: 12 },
  pastQ:       { fontSize: 12, color: '#9ca3af', fontWeight: 500, marginBottom: 6, textTransform: 'uppercase' as const, letterSpacing: '0.05em' },
  pastA:       { fontSize: 14, color: '#374151', lineHeight: 1.6 },
  // Current question
  qCard:       { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 16, padding: '32px 32px 28px', marginBottom: 20, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' },
  qBadge:      { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 36, height: 36, borderRadius: '50%', background: '#00C2E0', color: '#fff', fontSize: 13, fontWeight: 700, marginBottom: 20 },
  qText:       { fontSize: 18, fontWeight: 600, color: '#1a1d23', lineHeight: 1.55, margin: 0 },
  // Answer area
  textarea:    { width: '100%', minHeight: 130, border: '1px solid #d1d5db', borderRadius: 10, padding: '14px 16px', fontSize: 15, color: '#1a1d23', resize: 'vertical' as const, outline: 'none', fontFamily: 'inherit', lineHeight: 1.6, boxSizing: 'border-box' as const, background: '#fff', transition: 'border-color 0.15s' },
  charCount:   { textAlign: 'right' as const, fontSize: 12, color: '#9ca3af', marginTop: 6, marginBottom: 16 },
  submitBtn:   { width: '100%', padding: '14px 24px', background: '#00C2E0', color: '#fff', border: 'none', borderRadius: 10, fontSize: 15, fontWeight: 600, cursor: 'pointer', letterSpacing: '0.01em', transition: 'opacity 0.15s' },
  submitBtnDis:{ width: '100%', padding: '14px 24px', background: '#00C2E0', color: '#fff', border: 'none', borderRadius: 10, fontSize: 15, fontWeight: 600, cursor: 'not-allowed', opacity: 0.5, letterSpacing: '0.01em' },
  // Footer
  footer:      { textAlign: 'center' as const, marginTop: 40, paddingTop: 24, borderTop: '1px solid #e5e7eb' },
  footerPower: { fontSize: 12, color: '#9ca3af', marginBottom: 4 },
  footerPriv:  { fontSize: 11, color: '#c4c9d4' },
  // Landing
  landingWrap: { minHeight: '100vh', background: '#f5f6fa', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: "'Inter', 'Segoe UI', sans-serif" },
  landingCard: { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 20, padding: '48px 40px', maxWidth: 480, width: '100%', margin: '0 20px', textAlign: 'center' as const, boxShadow: '0 4px 24px rgba(0,0,0,0.06)' },
  landingFirm: { fontSize: 22, fontWeight: 800, color: '#1a1d23', marginBottom: 4 },
  landingRole: { fontSize: 14, color: '#6b7280', marginBottom: 32 },
  landingList: { textAlign: 'left' as const, marginBottom: 32, listStyle: 'none', padding: 0 },
  landingItem: { display: 'flex', alignItems: 'flex-start', gap: 10, fontSize: 14, color: '#374151', marginBottom: 12 },
  landingDot:  { width: 20, height: 20, borderRadius: '50%', background: '#00C2E033', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1 },
  landingBtn:  { width: '100%', padding: '14px', background: '#00C2E0', color: '#fff', border: 'none', borderRadius: 10, fontSize: 15, fontWeight: 600, cursor: 'pointer', letterSpacing: '0.01em' },
  // Completed
  doneWrap:    { minHeight: '100vh', background: '#f5f6fa', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: "'Inter', 'Segoe UI', sans-serif" },
  doneCard:    { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 20, padding: '56px 40px', maxWidth: 480, width: '100%', margin: '0 20px', textAlign: 'center' as const, boxShadow: '0 4px 24px rgba(0,0,0,0.06)' },
  doneIcon:    { width: 72, height: 72, borderRadius: '50%', background: '#d1fae5', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px' },
  doneTitle:   { fontSize: 24, fontWeight: 800, color: '#1a1d23', marginBottom: 12 },
  doneMsg:     { fontSize: 15, color: '#6b7280', lineHeight: 1.7, marginBottom: 28 },
  doneFirm:    { fontSize: 13, color: '#9ca3af' },
}

export default function PublicTestPage({ params }: { params: Promise<{ id: string; token: string }> }) {
  const { id, token } = use(params)

  const [stage, setStage] = useState<Stage>('landing')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [answer, setAnswer] = useState('')

  const [jobTitle, setJobTitle] = useState<string>('Competency Assessment')
  const [firmName, setFirmName] = useState<string>('')
  const [currentQuestion, setCurrentQuestion] = useState('')
  const [currentIndex, setCurrentIndex] = useState(0)
  const [totalQuestions, setTotalQuestions] = useState(0)
  const [pastQAs, setPastQAs] = useState<QA[]>([])

  const pct = totalQuestions > 0 ? Math.round((currentIndex / totalQuestions) * 100) : 0

  const startTest = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/api/v1/screener/test/${id}/${token}`)
      if (!res.ok) throw new Error(`Unable to load assessment (HTTP ${res.status})`)
      const data = await res.json()
      if (data.job_title) setJobTitle(data.job_title)
      if (data.firm_name) setFirmName(data.firm_name)
      setTotalQuestions(data.total_questions ?? 0)
      if (data.completed) { setStage('completed'); return }
      setCurrentIndex(data.current_question_index ?? 0)
      setCurrentQuestion(data.current_question ?? '')
      setStage('active')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load assessment. Please check your link.')
    } finally {
      setLoading(false)
    }
  }

  const submitAnswer = async () => {
    if (!answer.trim() || loading) return
    const submitted = answer.trim()
    setAnswer('')
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/api/v1/screener/test/${id}/${token}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer: submitted, question_index: currentIndex }),
      })
      if (!res.ok) throw new Error(`Submission failed (HTTP ${res.status})`)
      const data = await res.json()

      setPastQAs((prev) => [...prev, { question: currentQuestion, answer: submitted }])

      if (data.all_answered) {
        await fetch(`${API}/api/v1/screener/test/${id}/${token}/complete`, { method: 'POST' })
        setStage('completed')
      } else {
        setCurrentIndex(data.next_index)
        setCurrentQuestion(data.next_question)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not submit answer. Please try again.')
      setAnswer(submitted) // restore so user can retry
    } finally {
      setLoading(false)
    }
  }

  // ── Completed ──────────────────────────────────────────────────────────────
  if (stage === 'completed') {
    return (
      <div style={s.doneWrap}>
        <div style={s.doneCard}>
          <div style={s.doneIcon}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          </div>
          <h1 style={s.doneTitle}>Assessment Complete</h1>
          <p style={s.doneMsg}>
            Thank you for completing the assessment. Your responses have been submitted and are being reviewed. We will be in touch soon.
          </p>
          {firmName && <p style={s.doneFirm}>{firmName}</p>}
          <div style={{ marginTop: 40, paddingTop: 24, borderTop: '1px solid #f3f4f6' }}>
            <p style={{ fontSize: 11, color: '#c4c9d4' }}>Powered by AI Recruiter · Your responses are confidential and will only be reviewed by the hiring team</p>
          </div>
        </div>
      </div>
    )
  }

  // ── Landing ────────────────────────────────────────────────────────────────
  if (stage === 'landing') {
    return (
      <div style={s.landingWrap}>
        <div style={s.landingCard}>
          <div style={{ width: 56, height: 56, borderRadius: 14, background: '#00C2E0', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px' }}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          {firmName && <p style={s.landingFirm}>{firmName}</p>}
          <p style={s.landingRole}>{jobTitle}</p>
          <p style={{ fontSize: 14, color: '#6b7280', marginBottom: 28, lineHeight: 1.6 }}>
            You have been invited to complete a competency assessment. Answer each question thoughtfully — there are no trick questions.
          </p>
          <ul style={s.landingList}>
            {[
              'Answer each question in your own words',
              'Typically takes 15–30 minutes to complete',
              'Keep this tab open until finished',
              'Your responses are reviewed confidentially',
            ].map((item) => (
              <li key={item} style={s.landingItem}>
                <span style={s.landingDot}>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#00C2E0" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
                </span>
                {item}
              </li>
            ))}
          </ul>
          {error && <p style={{ fontSize: 13, color: '#ef4444', marginBottom: 16 }}>{error}</p>}
          <button style={s.landingBtn} onClick={startTest} disabled={loading}>
            {loading ? 'Loading…' : 'Begin Assessment →'}
          </button>
          <p style={{ fontSize: 11, color: '#c4c9d4', marginTop: 20 }}>Powered by AI Recruiter</p>
        </div>
      </div>
    )
  }

  // ── Active ─────────────────────────────────────────────────────────────────
  return (
    <div style={s.page}>
      <div style={s.shell}>
        {/* Header */}
        <div style={s.header}>
          {firmName && <div style={s.firm}>{firmName}</div>}
          <div style={s.role}>{jobTitle}</div>
        </div>
        <div style={s.divider}/>

        {/* Progress */}
        <div style={s.progressWrap}>
          <div style={s.progressLabel}>
            <span style={s.progressText}>Question {currentIndex + 1} of {totalQuestions}</span>
            <span style={s.progressPct}>{pct}% complete</span>
          </div>
          <div style={s.progressBar}>
            <div style={{ ...s.progressFill, width: `${pct}%` }}/>
          </div>
        </div>

        {/* Past Q&As */}
        {pastQAs.map((qa, i) => (
          <div key={i} style={s.pastCard}>
            <div style={s.pastQ}>Question {i + 1}</div>
            <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 8 }}>{qa.question}</div>
            <div style={s.pastA}>{qa.answer}</div>
          </div>
        ))}

        {/* Current question */}
        <div style={s.qCard}>
          <div style={s.qBadge}>Q{currentIndex + 1}</div>
          <p style={s.qText}>{currentQuestion}</p>
        </div>

        {/* Answer */}
        <textarea
          style={{ ...s.textarea, borderColor: answer.length > 0 ? '#00C2E0' : '#d1d5db' }}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && e.ctrlKey && submitAnswer()}
          placeholder="Type your answer here..."
          disabled={loading}
          rows={5}
        />
        <div style={s.charCount}>{answer.length} characters · Ctrl+Enter to submit</div>

        {error && <p style={{ fontSize: 13, color: '#ef4444', marginBottom: 12 }}>{error}</p>}

        <button
          style={!answer.trim() || loading ? s.submitBtnDis : s.submitBtn}
          onClick={submitAnswer}
          disabled={!answer.trim() || loading}
        >
          {loading ? 'Submitting…' : 'Submit Answer →'}
        </button>

        {/* Footer */}
        <div style={s.footer}>
          <p style={s.footerPower}>Powered by AI Recruiter</p>
          <p style={s.footerPriv}>Your responses are confidential and will only be reviewed by the hiring team</p>
        </div>
      </div>
    </div>
  )
}
