'use client'
import { useState, useEffect } from 'react'
import { settingsApi } from '@/lib/api'

const DEFAULT_PROMPT = `You are an expert AI Recruiter helping a recruiter create a new job listing. Guide them through these 16 steps in order, one or two at a time:

1. Greeting — invite the recruiter to paste a job description or describe the role.
2. Title extraction — normalise to a 1–2 word title + full display title; confirm both.
3. Title variations — suggest 3–5 similar titles for the recruiter to approve/edit.
4. Required Skills — extract from description; recruiter adds or removes.
5. Experience — confirm years required.
6. Salary Range — min/max (optional; skip gracefully if declined).
7. Location + Work Type — confirm location; ask onsite/hybrid/remote/remote_global.
8. Tech Stack — extract from description; recruiter can add more.
9. Team Size — optional.
10. Job Description — Write a clean 3–5 sentence job description from the collected details.
11. Hiring Manager — name and email.
12. Minimum Suitability Score — 1–10 scale; default 6.
13. Candidate Target — how many candidates should the Scout find? (default 20).
14. Email Outreach Prompt — show default; allow customisation.
15. Resume Evaluation Prompt — generate role-specific default; allow customisation. Ask for test question count and assessment format.
16. Confirmation — output full job summary, ask recruiter to confirm.

RULES: Never skip steps. Confirm data before advancing. When the recruiter confirms at step 16, set ready_for_payment=true.`

export default function AIRecruiterPromptPage() {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT)
  const [isCustom, setIsCustom] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    settingsApi.getTenant()
      .then((tenant) => {
        if (tenant.recruiter_system_prompt) {
          setPrompt(tenant.recruiter_system_prompt)
          setIsCustom(true)
        }
      })
      .catch(() => {/* keep DEFAULT_PROMPT */})
  }, [])

  async function handleSave() {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      await settingsApi.updateTenant({ recruiter_system_prompt: prompt })
      setIsCustom(true)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch {
      setError('Failed to save. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  async function handleReset() {
    if (!confirm('Reset to the default AI Recruiter prompt? Your customisation will be lost.')) return
    setSaving(true)
    setError(null)
    try {
      await settingsApi.updateTenant({ recruiter_system_prompt: null })
      setPrompt(DEFAULT_PROMPT)
      setIsCustom(false)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch {
      setError('Failed to reset. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ maxWidth: 800 }}>
      {/* Header */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h2 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 600, color: 'var(--white)' }}>
          AI Recruiter Prompt
        </h2>
        <p style={{ margin: 0, color: 'var(--muted)', fontSize: 14, lineHeight: 1.6 }}>
          This is the system prompt used by the AI Recruiter during job creation chat sessions.
          Edit it in plain English to change how the AI guides your recruiters. Changes take
          effect on the next new chat session.
        </p>
        {isCustom && (
          <div style={{
            marginTop: 12,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            background: 'rgba(0,194,224,0.12)',
            color: 'var(--cyan)',
            borderRadius: 6,
            padding: '4px 10px',
            fontSize: 12,
            fontWeight: 500,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--cyan)', display: 'inline-block' }} />
            Custom prompt active
          </div>
        )}
      </div>

      {/* Tips */}
      <div className="card" style={{ marginBottom: 24, background: 'rgba(0,194,224,0.06)', border: '1px solid rgba(0,194,224,0.2)' }}>
        <p style={{ margin: '0 0 8px', fontSize: 13, fontWeight: 600, color: 'var(--cyan)' }}>Tips for customising</p>
        <ul style={{ margin: 0, paddingLeft: 20, color: 'var(--muted)', fontSize: 13, lineHeight: 1.8 }}>
          <li>Keep the 16-step structure — the AI uses it to guide the conversation.</li>
          <li>Add company-specific instructions, e.g. &ldquo;always ask about visa sponsorship after step 7&rdquo;.</li>
          <li>The JSON output format at the end must stay intact or job creation will break.</li>
          <li>Use Reset to Default to restore the original prompt at any time.</li>
        </ul>
      </div>

      {/* Editor */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <label style={{ fontSize: 14, fontWeight: 500, color: 'var(--white)' }}>System Prompt</label>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>{prompt.length} chars</span>
        </div>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={22}
          style={{
            width: '100%',
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            color: 'var(--white)',
            fontSize: 13,
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
            lineHeight: 1.6,
            padding: '12px 14px',
            resize: 'vertical',
            outline: 'none',
            boxSizing: 'border-box',
          }}
          onFocus={(e) => { e.target.style.borderColor = 'var(--cyan)' }}
          onBlur={(e) => { e.target.style.borderColor = 'var(--border)' }}
        />
      </div>

      {error && (
        <div style={{
          marginBottom: 16, padding: '10px 14px', borderRadius: 8,
          background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)',
          color: '#f87171', fontSize: 13,
        }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving…' : 'Save Prompt'}
        </button>
        <button
          className="btn btn-ghost"
          onClick={handleReset}
          disabled={saving || !isCustom}
          style={{ color: isCustom ? 'var(--white)' : 'var(--muted)', opacity: isCustom ? 1 : 0.4 }}
        >
          Reset to Default
        </button>
        {saved && <span style={{ fontSize: 13, color: 'var(--cyan)' }}>Saved successfully</span>}
      </div>
    </div>
  )
}
