'use client'
import { useState } from 'react'
import { useRouter } from '@/i18n/navigation'
import { screenerApi } from '@/lib/api'

type Tab = 'paste' | 'url'
type Stage = 'input' | 'preview' | 'success'

interface ExtractedJob {
  title: string
  job_type: string
  location: string
  work_type: string
  salary_min: number | null
  salary_max: number | null
  experience_years: number
  required_skills: string[]
  tech_stack: string[]
  description: string
  evaluation_prompt: string
  interview_questions_count: number
  interview_type: string
}

interface CreatedJob {
  job: { id: string; job_ref: string; title: string; location: string }
  jobs_email: string
  application_instructions: string
}

export default function ScreenerJobPage() {
  const router = useRouter()
  const [tab, setTab] = useState<Tab>('paste')
  const [stage, setStage] = useState<Stage>('input')
  const [pasteText, setPasteText] = useState('')
  const [urlInput, setUrlInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [extracted, setExtracted] = useState<ExtractedJob | null>(null)
  const [created, setCreated] = useState<CreatedJob | null>(null)
  const [copied, setCopied] = useState(false)
  const [postCopied, setPostCopied] = useState(false)

  // Editable form state (populated from extracted)
  const [form, setForm] = useState<ExtractedJob>({
    title: '', job_type: 'permanent', location: '', work_type: 'onsite',
    salary_min: null, salary_max: null, experience_years: 3,
    required_skills: [], tech_stack: [], description: '',
    evaluation_prompt: '', interview_questions_count: 5,
    interview_type: 'text',
  })
  const [minimumScore, setMinimumScore] = useState(6)
  const [skillInput, setSkillInput] = useState('')
  const [techInput, setTechInput] = useState('')

  async function handleExtract() {
    setLoading(true)
    setError(null)
    try {
      let data: Record<string, unknown>
      if (tab === 'paste') {
        if (!pasteText.trim()) throw new Error('Please paste a job description')
        data = await screenerApi.extractFromText(pasteText)
      } else {
        if (!urlInput.trim()) throw new Error('Please enter a URL')
        data = await screenerApi.extractFromUrl(urlInput)
      }
      const ext = data as unknown as ExtractedJob
      setExtracted(ext)
      setForm({
        title: ext.title ?? '',
        job_type: ext.job_type ?? 'permanent',
        location: ext.location ?? '',
        work_type: ext.work_type ?? 'onsite',
        salary_min: ext.salary_min ?? null,
        salary_max: ext.salary_max ?? null,
        experience_years: ext.experience_years ?? 3,
        required_skills: Array.isArray(ext.required_skills) ? ext.required_skills : [],
        tech_stack: Array.isArray(ext.tech_stack) ? ext.tech_stack : [],
        description: ext.description ?? '',
        evaluation_prompt: ext.evaluation_prompt ?? '',
        interview_questions_count: ext.interview_questions_count ?? 5,
        interview_type: 'text',
      })
      setStage('preview')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Extraction failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate() {
    setLoading(true)
    setError(null)
    try {
      const result = await screenerApi.createJob({
        ...form,
        minimum_score: minimumScore,
      })
      setCreated(result as unknown as CreatedJob)
      setStage('success')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Job creation failed')
    } finally {
      setLoading(false)
    }
  }

  function copyInstructions() {
    if (!created) return
    navigator.clipboard.writeText(created.application_instructions)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  function copyPostText() {
    if (!created) return
    const text = `We're hiring a ${created.job.title}${created.job.location ? ` in ${created.job.location}` : ''}.\n\nTo apply, email your resume to ${created.jobs_email} with subject: ${created.job.job_ref}`
    navigator.clipboard.writeText(text)
    setPostCopied(true)
    setTimeout(() => setPostCopied(false), 2000)
  }

  function addSkill(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && skillInput.trim()) {
      setForm(f => ({ ...f, required_skills: [...f.required_skills, skillInput.trim()] }))
      setSkillInput('')
    }
  }
  function removeSkill(s: string) {
    setForm(f => ({ ...f, required_skills: f.required_skills.filter(x => x !== s) }))
  }
  function addTech(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && techInput.trim()) {
      setForm(f => ({ ...f, tech_stack: [...f.tech_stack, techInput.trim()] }))
      setTechInput('')
    }
  }
  function removeTech(t: string) {
    setForm(f => ({ ...f, tech_stack: f.tech_stack.filter(x => x !== t) }))
  }

  // ── Success screen ────────────────────────────────────────────────────────
  if (stage === 'success' && created) {
    return (
      <div style={{ height: '100%', overflowY: 'auto', padding: '48px 24px', display: 'flex', justifyContent: 'center' }}>
        <div style={{ maxWidth: 600, width: '100%' }}>
          <div style={{ textAlign: 'center', marginBottom: 32 }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
            <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 8 }}>Job Created Successfully!</h1>
            <p style={{ color: 'var(--muted)', fontSize: 14 }}>
              <strong style={{ color: 'var(--white)' }}>{created.job.title}</strong>
              {created.job.location && ` · ${created.job.location}`}
              {' · '}
              <span style={{ fontFamily: 'DM Mono, monospace' }}>{created.job.job_ref}</span>
            </p>
          </div>

          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12, padding: 20, marginBottom: 20 }}>
            <div style={{ fontWeight: 600, marginBottom: 10 }}>Share with applicants</div>
            <div style={{ background: 'var(--navy)', borderRadius: 8, padding: 14, fontFamily: 'DM Mono, monospace', fontSize: 13, marginBottom: 12, lineHeight: 1.6 }}>
              {created.application_instructions}
            </div>
            <button className="btn btn-primary btn-sm" onClick={copyInstructions}>
              {copied ? '✓ Copied!' : '📋 Copy Instructions'}
            </button>
          </div>

          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12, padding: 20, marginBottom: 28 }}>
            <div style={{ fontWeight: 600, marginBottom: 10 }}>Suggested post text</div>
            <div style={{ background: 'var(--navy)', borderRadius: 8, padding: 14, fontSize: 13, lineHeight: 1.7, marginBottom: 12, whiteSpace: 'pre-line' }}>
              {`We're hiring a ${created.job.title}${created.job.location ? ` in ${created.job.location}` : ''}.\n\nTo apply, email your resume to ${created.jobs_email} with subject: ${created.job.job_ref}`}
            </div>
            <button className="btn btn-ghost btn-sm" onClick={copyPostText}>
              {postCopied ? '✓ Copied!' : '📋 Copy Post Text'}
            </button>
          </div>

          <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
            <button className="btn btn-primary" onClick={() => router.push(`/jobs/${created.job.id}`)}>
              View Job →
            </button>
            <button className="btn btn-ghost" onClick={() => { setStage('input'); setExtracted(null); setCreated(null); setPasteText(''); setUrlInput('') }}>
              + Post Another Job
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Preview / edit screen ─────────────────────────────────────────────────
  if (stage === 'preview') {
    return (
      <div style={{ height: '100%', overflowY: 'auto', padding: '32px 24px', display: 'flex', justifyContent: 'center' }}>
        <div style={{ maxWidth: 640, width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => setStage('input')}>← Back</button>
            <h2 style={{ fontSize: 20, fontWeight: 700 }}>Review Extracted Job Details</h2>
          </div>

          {error && <div style={{ color: 'var(--red)', fontSize: 13, marginBottom: 16, padding: '10px 14px', background: 'rgba(239,68,68,0.1)', borderRadius: 8 }}>{error}</div>}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Job Title *</label>
              <input className="form-input" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Job Type</label>
                <select className="form-select" value={form.job_type} onChange={e => setForm(f => ({ ...f, job_type: e.target.value }))}>
                  <option value="permanent">Permanent</option>
                  <option value="contract">Contract</option>
                  <option value="casual">Casual</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Work Type</label>
                <select className="form-select" value={form.work_type} onChange={e => setForm(f => ({ ...f, work_type: e.target.value }))}>
                  <option value="onsite">On-site</option>
                  <option value="hybrid">Hybrid</option>
                  <option value="remote">Remote</option>
                </select>
              </div>
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Location</label>
              <input className="form-input" value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
              <div>
                <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Salary Min</label>
                <input className="form-input" type="number" value={form.salary_min ?? ''} onChange={e => setForm(f => ({ ...f, salary_min: e.target.value ? Number(e.target.value) : null }))} />
              </div>
              <div>
                <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Salary Max</label>
                <input className="form-input" type="number" value={form.salary_max ?? ''} onChange={e => setForm(f => ({ ...f, salary_max: e.target.value ? Number(e.target.value) : null }))} />
              </div>
              <div>
                <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Exp. Years</label>
                <input className="form-input" type="number" value={form.experience_years} onChange={e => setForm(f => ({ ...f, experience_years: Number(e.target.value) }))} />
              </div>
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Required Skills (press Enter to add)</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
                {form.required_skills.map(s => (
                  <span key={s} style={{ background: 'var(--cyan-dim)', color: 'var(--cyan)', fontSize: 12, padding: '3px 10px', borderRadius: 20, display: 'flex', alignItems: 'center', gap: 4 }}>
                    {s}<button onClick={() => removeSkill(s)} style={{ background: 'none', border: 'none', color: 'var(--cyan)', cursor: 'pointer', padding: 0, lineHeight: 1 }}>×</button>
                  </span>
                ))}
              </div>
              <input className="form-input" value={skillInput} onChange={e => setSkillInput(e.target.value)} onKeyDown={addSkill} placeholder="Type skill and press Enter" />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Tech Stack (press Enter to add)</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
                {form.tech_stack.map(t => (
                  <span key={t} style={{ background: 'rgba(139,92,246,0.15)', color: '#a78bfa', fontSize: 12, padding: '3px 10px', borderRadius: 20, display: 'flex', alignItems: 'center', gap: 4 }}>
                    {t}<button onClick={() => removeTech(t)} style={{ background: 'none', border: 'none', color: '#a78bfa', cursor: 'pointer', padding: 0, lineHeight: 1 }}>×</button>
                  </span>
                ))}
              </div>
              <input className="form-input" value={techInput} onChange={e => setTechInput(e.target.value)} onKeyDown={addTech} placeholder="Type technology and press Enter" />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Job Description</label>
              <textarea className="form-input" rows={5} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} style={{ resize: 'vertical' }} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Minimum Score (1–10)</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <input type="range" min={1} max={10} value={minimumScore} onChange={e => setMinimumScore(Number(e.target.value))} style={{ flex: 1 }} />
                <span style={{ fontWeight: 700, minWidth: 24, textAlign: 'center' }}>{minimumScore}</span>
              </div>
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Interview Questions Count</label>
              <input className="form-input" type="number" min={1} max={20} value={form.interview_questions_count} onChange={e => setForm(f => ({ ...f, interview_questions_count: Number(e.target.value) }))} style={{ width: 80 }} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Assessment Format</label>
              <select className="form-select" value={form.interview_type} onChange={e => setForm(f => ({ ...f, interview_type: e.target.value }))}>
                <option value="text">Text only</option>
                <option value="audio">Audio recording</option>
                <option value="video">Video recording</option>
                <option value="audio_video">Audio + Video</option>
              </select>
              <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
                {form.interview_type === 'text' && 'Candidates type written answers to each question.'}
                {form.interview_type === 'audio' && 'Candidates record audio answers. Whisper AI transcribes responses.'}
                {form.interview_type === 'video' && 'Candidates record video answers. Audio is transcribed by Whisper AI.'}
                {form.interview_type === 'audio_video' && 'Candidates may use audio or video. All recordings are transcribed.'}
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 12, marginTop: 28 }}>
            <button
              className="btn btn-primary"
              disabled={loading || !form.title.trim()}
              onClick={handleCreate}
              style={{ flex: 1 }}
            >
              {loading ? 'Creating Job…' : 'Create Job →'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Input screen ──────────────────────────────────────────────────────────
  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '48px 24px', display: 'flex', justifyContent: 'center' }}>
      <div style={{ maxWidth: 640, width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 32 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => router.push('/jobs/new')}>← Back</button>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 2 }}>Resume Screener Only</h1>
            <p style={{ color: 'var(--muted)', fontSize: 14 }}>Paste or link to your job description and we'll extract all the details.</p>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="tabs" style={{ marginBottom: 24 }}>
          <div className={`tab${tab === 'paste' ? ' active' : ''}`} onClick={() => setTab('paste')}>📝 Paste Job Description</div>
          <div className={`tab${tab === 'url' ? ' active' : ''}`} onClick={() => setTab('url')}>🔗 Job URL</div>
        </div>

        {error && <div style={{ color: 'var(--red)', fontSize: 13, marginBottom: 16, padding: '10px 14px', background: 'rgba(239,68,68,0.1)', borderRadius: 8 }}>{error}</div>}

        {tab === 'paste' && (
          <div>
            <textarea
              className="form-input"
              rows={14}
              value={pasteText}
              onChange={e => setPasteText(e.target.value)}
              placeholder="Paste your full job description here..."
              style={{ resize: 'vertical', width: '100%', fontFamily: 'inherit', fontSize: 14 }}
            />
            <button
              className="btn btn-primary"
              disabled={loading || !pasteText.trim()}
              onClick={handleExtract}
              style={{ marginTop: 16, width: '100%', padding: '14px' }}
            >
              {loading
                ? <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                    <span style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid #fff', borderTopColor: 'transparent', display: 'inline-block', animation: 'spin 0.7s linear infinite' }}/>
                    Extracting job details…
                  </span>
                : 'Extract Job Details →'
              }
            </button>
          </div>
        )}

        {tab === 'url' && (
          <div>
            <input
              className="form-input"
              type="url"
              value={urlInput}
              onChange={e => setUrlInput(e.target.value)}
              placeholder="https://example.com/jobs/senior-developer"
              style={{ width: '100%', marginBottom: 16 }}
            />
            <button
              className="btn btn-primary"
              disabled={loading || !urlInput.trim()}
              onClick={handleExtract}
              style={{ width: '100%', padding: '14px' }}
            >
              {loading
                ? <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                    <span style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid #fff', borderTopColor: 'transparent', display: 'inline-block', animation: 'spin 0.7s linear infinite' }}/>
                    Fetching and extracting…
                  </span>
                : 'Extract from URL →'
              }
            </button>
          </div>
        )}

        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    </div>
  )
}
