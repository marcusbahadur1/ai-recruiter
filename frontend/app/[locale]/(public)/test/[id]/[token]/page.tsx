'use client'
import { use, useState, useRef, useEffect } from 'react'

const API = ''

interface QA { question: string; answer: string }

type Stage = 'landing' | 'active' | 'completed'
type RecordState = 'idle' | 'recording' | 'recorded' | 'uploading'

const s: Record<string, React.CSSProperties> = {
  page:        { minHeight: '100vh', background: '#f5f6fa', fontFamily: "'Inter', 'Segoe UI', sans-serif", color: '#1a1d23' },
  shell:       { maxWidth: 700, margin: '0 auto', padding: '0 20px 60px' },
  header:      { textAlign: 'center', padding: '48px 0 32px' },
  firm:        { fontSize: 28, fontWeight: 800, color: '#1a1d23', marginBottom: 6, letterSpacing: '-0.5px' },
  role:        { fontSize: 15, color: '#6b7280', fontWeight: 400 },
  divider:     { height: 1, background: '#e5e7eb', margin: '28px 0' },
  progressWrap:{ marginBottom: 32 },
  progressLabel:{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  progressText:{ fontSize: 13, color: '#6b7280', fontWeight: 500 },
  progressPct: { fontSize: 13, color: '#00C2E0', fontWeight: 600 },
  progressBar: { height: 6, background: '#e5e7eb', borderRadius: 99, overflow: 'hidden' },
  progressFill:{ height: '100%', background: '#00C2E0', borderRadius: 99, transition: 'width 0.4s ease' },
  pastCard:    { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '16px 20px', marginBottom: 12 },
  pastQ:       { fontSize: 12, color: '#9ca3af', fontWeight: 500, marginBottom: 6, textTransform: 'uppercase' as const, letterSpacing: '0.05em' },
  pastA:       { fontSize: 14, color: '#374151', lineHeight: 1.6 },
  qCard:       { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 16, padding: '32px 32px 28px', marginBottom: 20, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' },
  qBadge:      { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 36, height: 36, borderRadius: '50%', background: '#00C2E0', color: '#fff', fontSize: 13, fontWeight: 700, marginBottom: 20 },
  qText:       { fontSize: 18, fontWeight: 600, color: '#1a1d23', lineHeight: 1.55, margin: 0 },
  textarea:    { width: '100%', minHeight: 130, border: '1px solid #d1d5db', borderRadius: 10, padding: '14px 16px', fontSize: 15, color: '#1a1d23', resize: 'vertical' as const, outline: 'none', fontFamily: 'inherit', lineHeight: 1.6, boxSizing: 'border-box' as const, background: '#fff', transition: 'border-color 0.15s' },
  charCount:   { textAlign: 'right' as const, fontSize: 12, color: '#9ca3af', marginTop: 6, marginBottom: 16 },
  submitBtn:   { width: '100%', padding: '14px 24px', background: '#00C2E0', color: '#fff', border: 'none', borderRadius: 10, fontSize: 15, fontWeight: 600, cursor: 'pointer', letterSpacing: '0.01em', transition: 'opacity 0.15s' },
  submitBtnDis:{ width: '100%', padding: '14px 24px', background: '#00C2E0', color: '#fff', border: 'none', borderRadius: 10, fontSize: 15, fontWeight: 600, cursor: 'not-allowed', opacity: 0.5, letterSpacing: '0.01em' },
  footer:      { textAlign: 'center' as const, marginTop: 40, paddingTop: 24, borderTop: '1px solid #e5e7eb' },
  footerPower: { fontSize: 12, color: '#9ca3af', marginBottom: 4 },
  footerPriv:  { fontSize: 11, color: '#c4c9d4' },
  landingWrap: { minHeight: '100vh', background: '#f5f6fa', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: "'Inter', 'Segoe UI', sans-serif" },
  landingCard: { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 20, padding: '48px 40px', maxWidth: 480, width: '100%', margin: '0 20px', textAlign: 'center' as const, boxShadow: '0 4px 24px rgba(0,0,0,0.06)' },
  landingFirm: { fontSize: 22, fontWeight: 800, color: '#1a1d23', marginBottom: 4 },
  landingRole: { fontSize: 14, color: '#6b7280', marginBottom: 32 },
  landingList: { textAlign: 'left' as const, marginBottom: 32, listStyle: 'none', padding: 0 },
  landingItem: { display: 'flex', alignItems: 'flex-start', gap: 10, fontSize: 14, color: '#374151', marginBottom: 12 },
  landingDot:  { width: 20, height: 20, borderRadius: '50%', background: '#00C2E033', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1 },
  landingBtn:  { width: '100%', padding: '14px', background: '#00C2E0', color: '#fff', border: 'none', borderRadius: 10, fontSize: 15, fontWeight: 600, cursor: 'pointer', letterSpacing: '0.01em' },
  doneWrap:    { minHeight: '100vh', background: '#f5f6fa', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: "'Inter', 'Segoe UI', sans-serif" },
  doneCard:    { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 20, padding: '56px 40px', maxWidth: 480, width: '100%', margin: '0 20px', textAlign: 'center' as const, boxShadow: '0 4px 24px rgba(0,0,0,0.06)' },
  doneIcon:    { width: 72, height: 72, borderRadius: '50%', background: '#d1fae5', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px' },
  doneTitle:   { fontSize: 24, fontWeight: 800, color: '#1a1d23', marginBottom: 12 },
  doneMsg:     { fontSize: 15, color: '#6b7280', lineHeight: 1.7, marginBottom: 28 },
  doneFirm:    { fontSize: 13, color: '#9ca3af' },
  // Recording UI
  recorderWrap:{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '24px', marginBottom: 16 },
  recBtn:      { display: 'inline-flex', alignItems: 'center', gap: 8, padding: '12px 20px', borderRadius: 10, border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer' },
  recBtnRed:   { background: '#fee2e2', color: '#dc2626' },
  recBtnGreen: { background: '#dcfce7', color: '#16a34a' },
  recBtnCyan:  { background: '#00C2E0', color: '#fff' },
  recTimer:    { fontSize: 28, fontWeight: 800, color: '#1a1d23', fontVariantNumeric: 'tabular-nums' as const, letterSpacing: '-1px' },
  recDot:      { display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: '#dc2626', marginRight: 6, animation: 'pulse 1s infinite' },
  transcript:  { background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: '12px 14px', fontSize: 14, color: '#166534', lineHeight: 1.6, marginTop: 12, whiteSpace: 'pre-wrap' as const },
}

// ── Recording hook ────────────────────────────────────────────────────────────

function useRecorder(videoEnabled: boolean) {
  const [state, setState] = useState<RecordState>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [blob, setBlob] = useState<Blob | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const mediaRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)

  const start = async () => {
    chunksRef.current = []
    setBlob(null)
    setPreviewUrl(null)
    setElapsed(0)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: videoEnabled,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
      }
      const mr = new MediaRecorder(stream)
      mediaRef.current = mr
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = () => {
        const b = new Blob(chunksRef.current, { type: videoEnabled ? 'video/webm' : 'audio/webm' })
        setBlob(b)
        setPreviewUrl(URL.createObjectURL(b))
        setState('recorded')
        stream.getTracks().forEach(t => t.stop())
        streamRef.current = null
      }
      mr.start(250)
      setState('recording')
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000)
    } catch {
      alert('Could not access microphone' + (videoEnabled ? '/camera' : '') + '. Check browser permissions.')
    }
  }

  const stop = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    mediaRef.current?.stop()
  }

  const reset = () => {
    stop()
    setBlob(null)
    setPreviewUrl(null)
    setElapsed(0)
    setState('idle')
  }

  useEffect(() => () => { stop(); streamRef.current?.getTracks().forEach(t => t.stop()) }, [])

  return { state, setState, elapsed, blob, previewUrl, videoRef, start, stop, reset }
}

function fmtTime(s: number) {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
}

// ── Recorder UI ───────────────────────────────────────────────────────────────

function RecorderPanel({
  videoEnabled,
  loading,
  onSubmit,
  error,
}: {
  videoEnabled: boolean
  loading: boolean
  onSubmit: (blob: Blob) => void
  error: string | null
}) {
  const rec = useRecorder(videoEnabled)

  return (
    <div style={s.recorderWrap}>
      <style>{`@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}`}</style>

      {/* Live preview */}
      {videoEnabled && (
        <video
          ref={rec.videoRef}
          autoPlay
          muted
          playsInline
          style={{ width: '100%', borderRadius: 8, marginBottom: 16, background: '#000', maxHeight: 220, display: rec.state === 'recording' ? 'block' : 'none' }}
        />
      )}

      {/* Recorded playback */}
      {rec.previewUrl && rec.state === 'recorded' && (
        videoEnabled
          ? <video src={rec.previewUrl} controls style={{ width: '100%', borderRadius: 8, marginBottom: 16, maxHeight: 220 }} />
          : <audio src={rec.previewUrl} controls style={{ width: '100%', marginBottom: 16 }} />
      )}

      {/* Timer */}
      {rec.state === 'recording' && (
        <div style={{ marginBottom: 16, textAlign: 'center' as const }}>
          <span style={s.recDot} />
          <span style={s.recTimer}>{fmtTime(rec.elapsed)}</span>
        </div>
      )}

      {/* Controls */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' as const }}>
        {rec.state === 'idle' && (
          <button style={{ ...s.recBtn, ...s.recBtnRed }} onClick={rec.start}>
            <span style={{ ...s.recDot, animation: 'none' }} />
            {videoEnabled ? 'Record Video' : 'Record Audio'}
          </button>
        )}
        {rec.state === 'recording' && (
          <button style={{ ...s.recBtn, background: '#fee2e2', color: '#dc2626' }} onClick={rec.stop}>
            ■ Stop Recording
          </button>
        )}
        {rec.state === 'recorded' && (
          <>
            <button
              style={{ ...s.recBtn, ...s.recBtnCyan, opacity: loading ? 0.5 : 1, cursor: loading ? 'not-allowed' : 'pointer' }}
              onClick={() => { if (rec.blob) { rec.setState('uploading'); onSubmit(rec.blob) } }}
              disabled={loading}
            >
              {loading ? 'Uploading & transcribing…' : 'Submit Recording →'}
            </button>
            <button style={{ ...s.recBtn, background: '#f3f4f6', color: '#6b7280' }} onClick={rec.reset} disabled={loading}>
              Re-record
            </button>
          </>
        )}
        {rec.state === 'uploading' && (
          <div style={{ fontSize: 14, color: '#6b7280', padding: '12px 0' }}>
            Transcribing your answer…
          </div>
        )}
      </div>
      {error && <p style={{ fontSize: 13, color: '#ef4444', marginTop: 12 }}>{error}</p>}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PublicTestPage({ params }: { params: Promise<{ id: string; token: string }> }) {
  const { id, token } = use(params)

  const [stage, setStage] = useState<Stage>('landing')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [answer, setAnswer] = useState('')

  const [jobTitle, setJobTitle] = useState<string>('Competency Assessment')
  const [firmName, setFirmName] = useState<string>('')
  const [interviewType, setInterviewType] = useState<string>('text')
  const [currentQuestion, setCurrentQuestion] = useState('')
  const [currentIndex, setCurrentIndex] = useState(0)
  const [totalQuestions, setTotalQuestions] = useState(0)
  const [pastQAs, setPastQAs] = useState<QA[]>([])

  const pct = totalQuestions > 0 ? Math.round((currentIndex / totalQuestions) * 100) : 0
  const videoEnabled = interviewType === 'video' || interviewType === 'audio_video'
  const audioEnabled = interviewType === 'audio' || interviewType === 'audio_video' || interviewType === 'video'
  const useRecording = interviewType !== 'text'

  const startTest = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/api/v1/screener/test/${id}/${token}`)
      if (!res.ok) throw new Error(`Unable to load assessment (HTTP ${res.status})`)
      const data = await res.json()
      if (data.job_title) setJobTitle(data.job_title)
      if (data.firm_name) setFirmName(data.firm_name)
      if (data.interview_type) setInterviewType(data.interview_type)
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

  const submitTextAnswer = async () => {
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
      setAnswer(submitted)
    } finally {
      setLoading(false)
    }
  }

  const submitRecording = async (blob: Blob) => {
    setLoading(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('file', blob, `recording.webm`)
      const res = await fetch(
        `${API}/api/v1/screener/test/${id}/${token}/recording?question_index=${currentIndex}`,
        { method: 'POST', body: formData }
      )
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Upload failed' }))
        throw new Error(err.detail || `Upload failed (HTTP ${res.status})`)
      }
      const data = await res.json()
      const transcript = data.transcript || '[Recording submitted]'
      setPastQAs((prev) => [...prev, { question: currentQuestion, answer: transcript }])
      if (data.all_answered) {
        await fetch(`${API}/api/v1/screener/test/${id}/${token}/complete`, { method: 'POST' })
        setStage('completed')
      } else {
        setCurrentIndex(data.next_index)
        setCurrentQuestion(data.next_question)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not submit recording. Please try again.')
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
    const modeItems: string[] = useRecording
      ? [
          'Answer each question by recording your response',
          `${videoEnabled ? 'Video' : 'Audio'} will be transcribed automatically`,
          'Typically takes 15–30 minutes to complete',
          'Keep this tab open until finished',
          'Your responses are reviewed confidentially',
        ]
      : [
          'Answer each question in your own words',
          'Typically takes 15–30 minutes to complete',
          'Keep this tab open until finished',
          'Your responses are reviewed confidentially',
        ]

    return (
      <div style={s.landingWrap}>
        <div style={s.landingCard}>
          <div style={{ width: 56, height: 56, borderRadius: 14, background: '#00C2E0', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px' }}>
            {useRecording ? (
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8"/>
              </svg>
            ) : (
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
            )}
          </div>
          {firmName && <p style={s.landingFirm}>{firmName}</p>}
          <p style={s.landingRole}>{jobTitle}</p>
          <p style={{ fontSize: 14, color: '#6b7280', marginBottom: 28, lineHeight: 1.6 }}>
            You have been invited to complete a competency assessment.{' '}
            {useRecording
              ? `Please ${videoEnabled ? 'record a video' : 'record an audio message'} for each question.`
              : 'Answer each question thoughtfully — there are no trick questions.'}
          </p>
          <ul style={s.landingList}>
            {modeItems.map((item) => (
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
        <style>{`@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}`}</style>

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

        {/* Answer area — text or recorder */}
        {useRecording ? (
          <RecorderPanel
            key={currentIndex}
            videoEnabled={videoEnabled}
            loading={loading}
            onSubmit={submitRecording}
            error={error}
          />
        ) : (
          <>
            <textarea
              style={{ ...s.textarea, borderColor: answer.length > 0 ? '#00C2E0' : '#d1d5db' }}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && e.ctrlKey && submitTextAnswer()}
              placeholder="Type your answer here..."
              disabled={loading}
              rows={5}
            />
            <div style={s.charCount}>{answer.length} characters · Ctrl+Enter to submit</div>
            {error && <p style={{ fontSize: 13, color: '#ef4444', marginBottom: 12 }}>{error}</p>}
            <button
              style={!answer.trim() || loading ? s.submitBtnDis : s.submitBtn}
              onClick={submitTextAnswer}
              disabled={!answer.trim() || loading}
            >
              {loading ? 'Submitting…' : 'Submit Answer →'}
            </button>
          </>
        )}

        {/* Footer */}
        <div style={s.footer}>
          <p style={s.footerPower}>Powered by AI Recruiter</p>
          <p style={s.footerPriv}>Your responses are confidential and will only be reviewed by the hiring team</p>
        </div>
      </div>
    </div>
  )
}
