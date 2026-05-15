'use client'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { marketingApi } from '@/lib/api'
import type {
  Sequence,
  SequenceAngle,
  SequenceStats,
  SequenceStep,
  SequenceStepType,
  SequenceStatus,
  GeneratedStep,
  Prospect,
} from '@/lib/api/types'

// ── Icons ─────────────────────────────────────────────────────────────────────

function LinkedInIcon() {
  return (
    <svg width={12} height={12} viewBox="0 0 24 24" fill="currentColor">
      <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/>
      <rect x="2" y="9" width="4" height="12"/>
      <circle cx="4" cy="4" r="2"/>
    </svg>
  )
}

function EmailIcon() {
  return (
    <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
      <polyline points="22,6 12,13 2,6"/>
    </svg>
  )
}

function WaitIcon() {
  return (
    <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <polyline points="12 6 12 12 16 14"/>
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
    </svg>
  )
}

function ArrowUpIcon() {
  return (
    <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="18 15 12 9 6 15"/>
    </svg>
  )
}

function ArrowDownIcon() {
  return (
    <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9"/>
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
    </svg>
  )
}

function SpinnerIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} style={{ animation: 'spin 1s linear infinite' }}>
      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
      <path d="M12 2a10 10 0 0 1 10 10"/>
    </svg>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<SequenceStatus, { dot: string; label: string }> = {
  live:   { dot: '#22c55e', label: 'Live' },
  paused: { dot: '#f59e0b', label: 'Paused' },
  draft:  { dot: '#6b7280', label: 'Draft' },
}

const STEP_TYPE_LABELS: Record<SequenceStepType, string> = {
  linkedin_connect: 'LI Connect',
  linkedin_dm:      'LI DM',
  email:            'Email',
  wait:             'Wait',
}

const STEP_CHAR_LIMITS: Partial<Record<SequenceStepType, number>> = {
  linkedin_connect: 240,
  linkedin_dm: 600,
}

function fmtRate(r: number) {
  return `${(r * 100).toFixed(0)}%`
}

// ── Channel pill ──────────────────────────────────────────────────────────────

function ChannelPill({ label }: { label: string }) {
  const colors: Record<string, { bg: string; color: string }> = {
    LI:    { bg: 'rgba(10,102,194,0.15)', color: '#0a66c2' },
    Email: { bg: 'rgba(34,197,94,0.12)',  color: '#22c55e' },
    Wait:  { bg: 'rgba(107,114,128,0.15)', color: '#9ca3af' },
  }
  const c = colors[label] || { bg: 'rgba(100,100,100,0.1)', color: '#9ca3af' }
  return (
    <span style={{
      padding: '2px 6px',
      borderRadius: 4,
      fontSize: 10,
      fontWeight: 600,
      background: c.bg,
      color: c.color,
      letterSpacing: '0.02em',
    }}>
      {label}
    </span>
  )
}

// ── New Sequence Modal ────────────────────────────────────────────────────────

const ANGLES: SequenceAngle[] = ['pain-led', 'ROI-led', 'curiosity/question', 'social proof']

interface NewSeqWizardProps {
  onClose: () => void
  onCreate: (seq: Sequence) => void
}

function NewSeqWizard({ onClose, onCreate }: NewSeqWizardProps) {
  const [step, setStep] = useState<1 | 2>(1)
  const [name, setName] = useState('')
  const [persona, setPersona] = useState('')
  const [angle, setAngle] = useState<SequenceAngle>('pain-led')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [generatedSteps, setGeneratedSteps] = useState<GeneratedStep[]>([])
  const [editableSteps, setEditableSteps] = useState<GeneratedStep[]>([])

  async function handleGenerate() {
    if (!name.trim() || !persona.trim()) {
      setError('Name and persona are required')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await marketingApi.generateSequenceSteps({ name, persona, angle })
      setGeneratedSteps(res.steps)
      setEditableSteps(res.steps.map(s => ({ ...s })))
      setStep(2)
    } catch {
      setError('Failed to generate steps — please try again')
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    setLoading(true)
    setError('')
    try {
      // Create sequence
      const seq = await marketingApi.createSequence({ name, persona_target: persona, angle })
      // Add steps
      for (let i = 0; i < editableSteps.length; i++) {
        const s = editableSteps[i]
        await marketingApi.addStep(seq.id, {
          step_type: s.step_type,
          day_offset: s.day_offset,
          message_template: s.message_template,
          condition: s.condition,
          sort_order: i,
        } as Partial<SequenceStep>)
      }
      // Reload sequence with steps
      const sequences = await marketingApi.listSequences()
      const fresh = sequences.find(sq => sq.id === seq.id) || seq
      onCreate(fresh)
      onClose()
    } catch {
      setError('Failed to save sequence — please try again')
    } finally {
      setLoading(false)
    }
  }

  function updateEditableStep(idx: number, field: keyof GeneratedStep, value: string | number | null) {
    setEditableSteps(prev => prev.map((s, i) => i === idx ? { ...s, [field]: value } : s))
  }

  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000,
    }}>
      <div style={{
        background: 'var(--navy-mid)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        width: 560,
        maxHeight: '85vh',
        overflowY: 'auto',
        padding: 28,
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg)' }}>
              {step === 1 ? 'New sequence' : 'Review AI-generated steps'}
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
              Step {step} of 2
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)', fontSize: 20 }}>×</button>
        </div>

        {error && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 6, padding: '8px 12px', marginBottom: 16, color: '#ef4444', fontSize: 12 }}>
            {error}
          </div>
        )}

        {step === 1 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--muted)', display: 'block', marginBottom: 6 }}>Sequence name *</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="e.g. Agency Owner Outreach Q3"
                style={{ width: '100%', boxSizing: 'border-box', background: 'var(--navy-dark)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', color: 'var(--fg)', fontSize: 13 }}
              />
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--muted)', display: 'block', marginBottom: 6 }}>Persona target *</label>
              <input
                value={persona}
                onChange={e => setPersona(e.target.value)}
                placeholder="e.g. Agency owners, MDs, directors"
                style={{ width: '100%', boxSizing: 'border-box', background: 'var(--navy-dark)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', color: 'var(--fg)', fontSize: 13 }}
              />
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--muted)', display: 'block', marginBottom: 6 }}>Angle</label>
              <select
                value={angle}
                onChange={e => setAngle(e.target.value as SequenceAngle)}
                style={{ width: '100%', background: 'var(--navy-dark)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', color: 'var(--fg)', fontSize: 13, cursor: 'pointer' }}
              >
                {ANGLES.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
            <button
              onClick={handleGenerate}
              disabled={loading || !name.trim() || !persona.trim()}
              style={{
                marginTop: 8,
                padding: '10px 20px',
                background: 'var(--cyan)',
                color: '#000',
                border: 'none',
                borderRadius: 6,
                fontWeight: 600,
                fontSize: 13,
                cursor: loading ? 'default' : 'pointer',
                opacity: loading || !name.trim() || !persona.trim() ? 0.6 : 1,
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              }}
            >
              {loading && <SpinnerIcon size={14} />}
              {loading ? 'Generating…' : 'Generate steps with AI →'}
            </button>
          </div>
        )}

        {step === 2 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>
              Review and edit the AI-generated steps before saving.
            </div>
            {editableSteps.map((s, idx) => (
              <div key={idx} style={{ background: 'var(--navy-dark)', border: '1px solid var(--border)', borderRadius: 8, padding: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{
                    width: 22, height: 22, borderRadius: '50%',
                    background: 'var(--cyan)', color: '#000',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11, fontWeight: 700, flexShrink: 0,
                  }}>{idx + 1}</span>
                  <select
                    value={s.step_type}
                    onChange={e => updateEditableStep(idx, 'step_type', e.target.value)}
                    style={{ background: 'var(--navy-mid)', border: '1px solid var(--border)', borderRadius: 4, padding: '3px 8px', color: 'var(--fg)', fontSize: 11, cursor: 'pointer' }}
                  >
                    <option value="linkedin_connect">LI Connect</option>
                    <option value="linkedin_dm">LI DM</option>
                    <option value="email">Email</option>
                    <option value="wait">Wait</option>
                  </select>
                  <span style={{ fontSize: 11, color: 'var(--muted)' }}>Day</span>
                  <input
                    type="number"
                    min={0}
                    value={s.day_offset}
                    onChange={e => updateEditableStep(idx, 'day_offset', parseInt(e.target.value) || 0)}
                    style={{ width: 48, background: 'var(--navy-mid)', border: '1px solid var(--border)', borderRadius: 4, padding: '3px 6px', color: 'var(--fg)', fontSize: 11, textAlign: 'center' }}
                  />
                </div>
                {s.step_type !== 'wait' && (
                  <textarea
                    value={s.message_template || ''}
                    onChange={e => updateEditableStep(idx, 'message_template', e.target.value)}
                    rows={3}
                    style={{ width: '100%', boxSizing: 'border-box', background: 'var(--navy-mid)', border: '1px solid var(--border)', borderRadius: 4, padding: '6px 10px', color: 'var(--fg)', fontSize: 12, resize: 'vertical', lineHeight: 1.5 }}
                  />
                )}
                {s.condition && (
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4, fontStyle: 'italic' }}>
                    Condition: {s.condition}
                  </div>
                )}
              </div>
            ))}
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button
                onClick={() => setStep(1)}
                style={{ flex: 1, padding: '9px 0', background: 'transparent', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--muted)', fontSize: 13, cursor: 'pointer' }}
              >
                ← Back
              </button>
              <button
                onClick={handleSave}
                disabled={loading}
                style={{
                  flex: 2,
                  padding: '9px 0',
                  background: 'var(--cyan)',
                  color: '#000',
                  border: 'none',
                  borderRadius: 6,
                  fontWeight: 600,
                  fontSize: 13,
                  cursor: loading ? 'default' : 'pointer',
                  opacity: loading ? 0.7 : 1,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                }}
              >
                {loading && <SpinnerIcon size={14} />}
                {loading ? 'Saving…' : 'Save sequence'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Enroll Modal ──────────────────────────────────────────────────────────────

function EnrollModal({
  sequence,
  onClose,
  onEnrolled,
}: {
  sequence: Sequence
  onClose: () => void
  onEnrolled: (count: number) => void
}) {
  const [prospects, setProspects] = useState<Prospect[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [error, setError] = useState('')

  useEffect(() => {
    marketingApi.listProspects({ stage: 'identified', page_size: 100 })
      .then(r => {
        // Also load connected prospects
        return marketingApi.listProspects({ stage: 'connected', page_size: 100 })
          .then(r2 => setProspects([...r.items, ...r2.items]))
          .catch(() => setProspects(r.items))
      })
      .catch(() => setProspects([]))
      .finally(() => setLoading(false))
  }, [])

  function toggle(id: string) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  async function handleEnroll() {
    if (selected.size === 0) return
    setSaving(true)
    setError('')
    try {
      const res = await marketingApi.enrollProspects(sequence.id, Array.from(selected))
      onEnrolled(res.enrolled)
      onClose()
    } catch {
      setError('Failed to enroll prospects — please try again')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000,
    }}>
      <div style={{
        background: 'var(--navy-mid)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        width: 500,
        maxHeight: '80vh',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg)' }}>Enroll prospects</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>into "{sequence.name}"</div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)', fontSize: 20 }}>×</button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '12px 24px' }}>
          {loading ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
              Loading prospects…
            </div>
          ) : prospects.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
              No eligible prospects (stage: identified or connected)
            </div>
          ) : (
            prospects.map(p => (
              <div
                key={p.id}
                onClick={() => toggle(p.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '10px 0',
                  borderBottom: '1px solid var(--border)',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  checked={selected.has(p.id)}
                  onChange={() => toggle(p.id)}
                  style={{ cursor: 'pointer' }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg)' }}>
                    {p.name || 'Unknown'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                    {[p.title, p.company].filter(Boolean).join(' · ')}
                  </div>
                </div>
                <span style={{
                  fontSize: 10, fontWeight: 600, padding: '2px 6px',
                  borderRadius: 4,
                  background: p.stage === 'connected' ? 'rgba(34,197,94,0.1)' : 'rgba(107,114,128,0.1)',
                  color: p.stage === 'connected' ? '#22c55e' : '#9ca3af',
                }}>
                  {p.stage}
                </span>
              </div>
            ))
          )}
        </div>

        <div style={{ padding: '14px 24px', borderTop: '1px solid var(--border)' }}>
          {error && (
            <div style={{ fontSize: 12, color: '#ef4444', marginBottom: 8 }}>{error}</div>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={onClose} style={{ flex: 1, padding: '8px 0', background: 'transparent', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--muted)', fontSize: 13, cursor: 'pointer' }}>
              Cancel
            </button>
            <button
              onClick={handleEnroll}
              disabled={saving || selected.size === 0}
              style={{
                flex: 2,
                padding: '8px 0',
                background: 'var(--cyan)',
                color: '#000',
                border: 'none',
                borderRadius: 6,
                fontWeight: 600,
                fontSize: 13,
                cursor: saving || selected.size === 0 ? 'default' : 'pointer',
                opacity: saving || selected.size === 0 ? 0.6 : 1,
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              }}
            >
              {saving && <SpinnerIcon size={13} />}
              {saving ? 'Enrolling…' : `Enroll ${selected.size} prospect${selected.size !== 1 ? 's' : ''}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Step Card ─────────────────────────────────────────────────────────────────

function StepCard({
  step,
  index,
  total,
  sequenceId,
  onUpdate,
  onDelete,
  onMoveUp,
  onMoveDown,
}: {
  step: SequenceStep
  index: number
  total: number
  sequenceId: string
  onUpdate: (updated: SequenceStep) => void
  onDelete: () => void
  onMoveUp: () => void
  onMoveDown: () => void
}) {
  const [hovering, setHovering] = useState(false)
  const [localStep, setLocalStep] = useState<SequenceStep>(step)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => { setLocalStep(step) }, [step])

  function patch(field: keyof SequenceStep, value: string | number | null) {
    const updated = { ...localStep, [field]: value } as SequenceStep
    setLocalStep(updated)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      try {
        const saved = await marketingApi.updateStep(sequenceId, step.id, { [field]: value } as Partial<SequenceStep>)
        onUpdate(saved)
      } catch {
        // revert on error
        setLocalStep(step)
      }
    }, 1000)
  }

  const charLimit = STEP_CHAR_LIMITS[localStep.step_type]
  const charCount = (localStep.message_template || '').length
  const isOverLimit = charLimit !== undefined && charCount > charLimit

  return (
    <div
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      style={{
        background: 'var(--navy-dark)',
        border: `1px solid ${hovering ? 'var(--cyan)' : 'var(--border)'}`,
        borderRadius: 8,
        padding: '14px 16px',
        transition: 'border-color 0.15s',
        position: 'relative',
      }}
    >
      {/* Step header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        {/* Step number circle */}
        <div style={{
          width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 700,
          background: localStep.has_been_sent ? 'var(--cyan)' : 'transparent',
          border: localStep.has_been_sent ? 'none' : '2px solid var(--border)',
          color: localStep.has_been_sent ? '#000' : 'var(--muted)',
        }}>
          {index + 1}
        </div>

        {/* Step type badge */}
        <select
          value={localStep.step_type}
          onChange={e => patch('step_type', e.target.value)}
          style={{ background: 'var(--navy-mid)', border: '1px solid var(--border)', borderRadius: 4, padding: '3px 8px', color: 'var(--fg)', fontSize: 11, cursor: 'pointer' }}
        >
          <option value="linkedin_connect">LI Connect</option>
          <option value="linkedin_dm">LI DM</option>
          <option value="email">Email</option>
          <option value="wait">Wait</option>
        </select>

        {/* Step name inline */}
        <input
          value={localStep.step_name || ''}
          onChange={e => patch('step_name', e.target.value || null)}
          placeholder={STEP_TYPE_LABELS[localStep.step_type]}
          style={{ flex: 1, background: 'transparent', border: 'none', borderBottom: '1px solid var(--border)', padding: '2px 4px', color: 'var(--fg)', fontSize: 12, outline: 'none' }}
        />

        {/* Day offset */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--muted)', fontSize: 11 }}>
          Day
          <input
            type="number"
            min={0}
            value={localStep.day_offset}
            onChange={e => patch('day_offset', parseInt(e.target.value) || 0)}
            style={{ width: 44, background: 'var(--navy-mid)', border: '1px solid var(--border)', borderRadius: 4, padding: '3px 6px', color: 'var(--fg)', fontSize: 11, textAlign: 'center' }}
          />
        </div>

        {/* Up/Down/Delete — visible on hover */}
        <div style={{
          display: 'flex', gap: 2,
          opacity: hovering ? 1 : 0,
          transition: 'opacity 0.15s',
        }}>
          <button onClick={onMoveUp} disabled={index === 0} title="Move up" style={{ background: 'none', border: 'none', cursor: index === 0 ? 'default' : 'pointer', color: index === 0 ? 'var(--border)' : 'var(--muted)', padding: '2px 3px', borderRadius: 3 }}><ArrowUpIcon /></button>
          <button onClick={onMoveDown} disabled={index === total - 1} title="Move down" style={{ background: 'none', border: 'none', cursor: index === total - 1 ? 'default' : 'pointer', color: index === total - 1 ? 'var(--border)' : 'var(--muted)', padding: '2px 3px', borderRadius: 3 }}><ArrowDownIcon /></button>
          <button onClick={onDelete} title="Delete step" style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: '2px 3px', borderRadius: 3 }}><TrashIcon /></button>
        </div>
      </div>

      {/* Message template (not for wait steps) */}
      {localStep.step_type !== 'wait' && (
        <div style={{ position: 'relative' }}>
          <textarea
            value={localStep.message_template || ''}
            onChange={e => patch('message_template', e.target.value)}
            rows={4}
            placeholder="Message template…"
            style={{
              width: '100%',
              boxSizing: 'border-box',
              background: 'var(--navy-mid)',
              border: `1px solid ${isOverLimit ? '#ef4444' : 'var(--border)'}`,
              borderRadius: 6,
              padding: '8px 10px',
              color: 'var(--fg)',
              fontSize: 12,
              resize: 'vertical',
              lineHeight: 1.5,
              fontFamily: 'inherit',
            }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
            <div style={{ fontSize: 10, color: 'var(--muted)' }}>
              Tokens: <code style={{ color: 'var(--cyan)', fontSize: 10 }}>{'{first_name}'}</code>{' '}
              <code style={{ color: 'var(--cyan)', fontSize: 10 }}>{'{company}'}</code>{' '}
              <code style={{ color: 'var(--cyan)', fontSize: 10 }}>{'{company_niche}'}</code>
            </div>
            {charLimit && (
              <div style={{ fontSize: 10, color: isOverLimit ? '#ef4444' : 'var(--muted)' }}>
                {charCount} / {charLimit}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Condition */}
      <div style={{ marginTop: localStep.step_type !== 'wait' ? 8 : 0 }}>
        <input
          value={localStep.condition || ''}
          onChange={e => patch('condition', e.target.value || null)}
          placeholder="Condition (e.g. Only if step 2 accepted)"
          style={{ width: '100%', boxSizing: 'border-box', background: 'var(--navy-mid)', border: '1px solid var(--border)', borderRadius: 4, padding: '5px 10px', color: 'var(--muted)', fontSize: 11, fontStyle: 'italic' }}
        />
      </div>

      {/* Step-level stats */}
      {localStep.sent_count > 0 && (
        <div style={{ marginTop: 8, fontSize: 11, color: 'var(--muted)' }}>
          {localStep.sent_count} sent · {fmtRate(localStep.accept_open_rate)} accept/open rate · {fmtRate(localStep.reply_rate)} reply rate
        </div>
      )}
    </div>
  )
}

// ── Right Panel — Sequence Detail ─────────────────────────────────────────────

function SequenceDetail({
  sequence: initial,
  onUpdated,
  onDeleted,
}: {
  sequence: Sequence
  onUpdated: (seq: Sequence) => void
  onDeleted: () => void
}) {
  const [seq, setSeq] = useState<Sequence>(initial)
  const [stats, setStats] = useState<SequenceStats | null>(null)
  const [editingName, setEditingName] = useState(false)
  const [nameVal, setNameVal] = useState(initial.name)
  const [showEnroll, setShowEnroll] = useState(false)
  const [savingStatus, setSavingStatus] = useState(false)

  useEffect(() => {
    setSeq(initial)
    setNameVal(initial.name)
    marketingApi.getSequenceStats(initial.id)
      .then(setStats)
      .catch(() => setStats(null))
  }, [initial.id])

  async function saveName() {
    setEditingName(false)
    if (nameVal === seq.name) return
    try {
      const updated = await marketingApi.updateSequence(seq.id, { name: nameVal })
      setSeq(updated)
      onUpdated(updated)
    } catch {
      setNameVal(seq.name)
    }
  }

  async function changeStatus(newStatus: SequenceStatus) {
    setSavingStatus(true)
    try {
      const updated = await marketingApi.updateSequence(seq.id, { status: newStatus })
      setSeq(updated)
      onUpdated(updated)
    } catch {}
    setSavingStatus(false)
  }

  async function addStep() {
    const newOrder = seq.steps.length
    try {
      const step = await marketingApi.addStep(seq.id, {
        step_type: 'linkedin_dm',
        day_offset: newOrder,
        sort_order: newOrder,
      } as Partial<SequenceStep>)
      setSeq(prev => ({ ...prev, steps: [...prev.steps, step] }))
    } catch {}
  }

  async function deleteStep(stepId: string) {
    try {
      await marketingApi.deleteStep(seq.id, stepId)
      setSeq(prev => ({
        ...prev,
        steps: prev.steps.filter(s => s.id !== stepId).map((s, i) => ({ ...s, sort_order: i })),
      }))
    } catch {}
  }

  function updateStep(updated: SequenceStep) {
    setSeq(prev => ({ ...prev, steps: prev.steps.map(s => s.id === updated.id ? updated : s) }))
  }

  async function moveStep(idx: number, dir: 'up' | 'down') {
    const steps = [...seq.steps]
    const swapIdx = dir === 'up' ? idx - 1 : idx + 1
    if (swapIdx < 0 || swapIdx >= steps.length) return
    const a = { ...steps[idx], sort_order: swapIdx }
    const b = { ...steps[swapIdx], sort_order: idx }
    steps[idx] = b
    steps[swapIdx] = a
    setSeq(prev => ({ ...prev, steps }))
    try {
      await Promise.all([
        marketingApi.updateStep(seq.id, a.id, { sort_order: a.sort_order } as Partial<SequenceStep>),
        marketingApi.updateStep(seq.id, b.id, { sort_order: b.sort_order } as Partial<SequenceStep>),
      ])
    } catch {}
  }

  const statusDot = STATUS_COLORS[seq.status]

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '20px 24px' }}>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        {/* Name */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          {editingName ? (
            <input
              autoFocus
              value={nameVal}
              onChange={e => setNameVal(e.target.value)}
              onBlur={saveName}
              onKeyDown={e => { if (e.key === 'Enter') saveName(); if (e.key === 'Escape') { setEditingName(false); setNameVal(seq.name) } }}
              style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg)', background: 'transparent', border: 'none', borderBottom: '2px solid var(--cyan)', outline: 'none', padding: '2px 0', flex: 1 }}
            />
          ) : (
            <h2
              onClick={() => setEditingName(true)}
              title="Click to edit name"
              style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg)', margin: 0, cursor: 'text', flex: 1 }}
            >
              {seq.name}
            </h2>
          )}
          <button
            onClick={() => { if (confirm(`Delete "${seq.name}"?`)) onDeleted() }}
            title="Delete sequence"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)', padding: '4px', borderRadius: 4, flexShrink: 0 }}
            onMouseEnter={e => (e.currentTarget.style.color = '#ef4444')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted)')}
          >
            <TrashIcon />
          </button>
        </div>

        {/* Chips row */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          {/* Status dropdown */}
          <select
            value={seq.status}
            onChange={e => changeStatus(e.target.value as SequenceStatus)}
            disabled={savingStatus}
            style={{
              background: 'var(--navy-dark)',
              border: '1px solid var(--border)',
              borderRadius: 20,
              padding: '4px 12px',
              fontSize: 12,
              fontWeight: 500,
              color: statusDot.dot,
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            <option value="live">● Live</option>
            <option value="paused">● Paused</option>
            <option value="draft">● Draft</option>
          </select>

          {/* Enrolled count */}
          <span style={{ fontSize: 12, color: 'var(--muted)', background: 'var(--navy-dark)', padding: '4px 12px', borderRadius: 20, border: '1px solid var(--border)' }}>
            {seq.enrolled_count} enrolled
          </span>

          {/* Persona */}
          {seq.persona_target && (
            <span style={{ fontSize: 12, color: 'var(--muted)', background: 'var(--navy-dark)', padding: '4px 12px', borderRadius: 20, border: '1px solid var(--border)' }}>
              {seq.persona_target}
            </span>
          )}

          {/* Angle */}
          {seq.angle && (
            <span style={{ fontSize: 12, color: 'var(--cyan)', background: 'rgba(0,229,255,0.08)', padding: '4px 12px', borderRadius: 20, border: '1px solid rgba(0,229,255,0.2)' }}>
              {seq.angle}
            </span>
          )}
        </div>
      </div>

      {/* Performance grid */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 20 }}>
          {[
            { label: 'Sent', value: stats.sent.toString() },
            { label: 'Accept/open rate', value: fmtRate(stats.accept_open_rate) },
            { label: 'Reply rate', value: fmtRate(stats.reply_rate) },
            { label: 'Demos booked', value: stats.demos_booked.toString() },
          ].map(({ label, value }) => (
            <div key={label} style={{ background: 'var(--navy-dark)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px' }}>
              <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--fg)' }}>{value}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Steps editor */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {seq.steps.map((step, idx) => (
            <React.Fragment key={step.id}>
              <StepCard
                step={step}
                index={idx}
                total={seq.steps.length}
                sequenceId={seq.id}
                onUpdate={updateStep}
                onDelete={() => deleteStep(step.id)}
                onMoveUp={() => moveStep(idx, 'up')}
                onMoveDown={() => moveStep(idx, 'down')}
              />
              {idx < seq.steps.length - 1 && (
                <div style={{ width: 2, height: 12, background: 'var(--border)', margin: '0 auto' }} />
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Add step */}
        <button
          onClick={addStep}
          style={{
            marginTop: 14,
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'none', border: 'none',
            color: 'var(--cyan)', fontSize: 13, cursor: 'pointer',
            padding: '6px 0',
          }}
        >
          <PlusIcon /> Add step
        </button>
      </div>

      {/* Enroll Prospects button */}
      <div style={{ paddingTop: 16, borderTop: '1px solid var(--border)', marginTop: 16 }}>
        <button
          onClick={() => setShowEnroll(true)}
          style={{
            width: '100%',
            padding: '10px 0',
            background: 'var(--cyan)',
            color: '#000',
            border: 'none',
            borderRadius: 6,
            fontWeight: 600,
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          Enroll prospects →
        </button>
      </div>

      {showEnroll && (
        <EnrollModal
          sequence={seq}
          onClose={() => setShowEnroll(false)}
          onEnrolled={(count) => {
            setSeq(prev => ({ ...prev, enrolled_count: prev.enrolled_count + count }))
            onUpdated({ ...seq, enrolled_count: seq.enrolled_count + count })
          }}
        />
      )}
    </div>
  )
}

// ── Main Sequences Tab ────────────────────────────────────────────────────────

export default function SequencesTab() {
  const [sequences, setSequences] = useState<Sequence[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showNewWizard, setShowNewWizard] = useState(false)

  useEffect(() => {
    marketingApi.listSequences()
      .then(seqs => {
        setSequences(seqs)
        if (seqs.length > 0 && !selectedId) setSelectedId(seqs[0].id)
      })
      .finally(() => setLoading(false))
  }, [])

  const selected = sequences.find(s => s.id === selectedId) ?? null

  function handleCreated(seq: Sequence) {
    setSequences(prev => [...prev, seq])
    setSelectedId(seq.id)
  }

  function handleUpdated(updated: Sequence) {
    setSequences(prev => prev.map(s => s.id === updated.id ? updated : s))
  }

  async function handleDeleted(id: string) {
    try {
      await marketingApi.deleteSequence(id)
    } catch {}
    setSequences(prev => {
      const next = prev.filter(s => s.id !== id)
      setSelectedId(next.length > 0 ? next[0].id : null)
      return next
    })
  }

  return (
    <div style={{ display: 'flex', height: '100%', minHeight: 500 }}>
      {/* Left panel — sequence list */}
      <div style={{
        width: 260,
        flexShrink: 0,
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        paddingTop: 16,
      }}>
        {/* Header */}
        <div style={{ padding: '0 16px 12px', fontSize: 12, fontWeight: 600, color: 'var(--muted)', borderBottom: '1px solid var(--border)', marginBottom: 0 }}>
          {sequences.length} sequence{sequences.length !== 1 ? 's' : ''}
        </div>

        {/* Sequence rows */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {loading ? (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
              <SpinnerIcon size={20} />
            </div>
          ) : sequences.length === 0 ? (
            <div style={{ padding: '16px', fontSize: 12, color: 'var(--muted)', textAlign: 'center', lineHeight: 1.6 }}>
              No sequences yet.<br />Create your first below.
            </div>
          ) : (
            sequences.map(seq => {
              const sc = STATUS_COLORS[seq.status]
              const isSelected = seq.id === selectedId
              return (
                <div
                  key={seq.id}
                  onClick={() => setSelectedId(seq.id)}
                  style={{
                    padding: '12px 16px',
                    cursor: 'pointer',
                    borderLeft: `3px solid ${isSelected ? 'var(--cyan)' : 'transparent'}`,
                    background: isSelected ? 'rgba(0,229,255,0.05)' : 'transparent',
                    borderBottom: '1px solid var(--border)',
                    transition: 'background 0.1s',
                  }}
                >
                  {/* Name */}
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg)', marginBottom: 4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {seq.name}
                  </div>
                  {/* Status + enrolled */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: sc.dot, display: 'inline-block', flexShrink: 0 }} />
                    <span style={{ fontSize: 11, color: 'var(--muted)' }}>{sc.label}</span>
                    <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 2 }}>· {seq.enrolled_count} enrolled</span>
                  </div>
                  {/* Channel tags */}
                  {seq.channel_tags.length > 0 && (
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {seq.channel_tags.map(tag => <ChannelPill key={tag} label={tag} />)}
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>

        {/* New sequence dashed row */}
        <div
          onClick={() => setShowNewWizard(true)}
          style={{
            padding: '13px 16px',
            cursor: 'pointer',
            borderTop: '1px dashed var(--border)',
            display: 'flex', alignItems: 'center', gap: 8,
            color: 'var(--muted)',
            fontSize: 13,
            transition: 'color 0.15s',
          }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--cyan)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted)')}
        >
          <PlusIcon /> New sequence
        </div>
      </div>

      {/* Right panel — detail */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {selected ? (
          <SequenceDetail
            key={selected.id}
            sequence={selected}
            onUpdated={handleUpdated}
            onDeleted={() => handleDeleted(selected.id)}
          />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--muted)', fontSize: 13 }}>
            {loading ? <SpinnerIcon size={24} /> : 'Select or create a sequence to get started'}
          </div>
        )}
      </div>

      {/* New sequence wizard modal */}
      {showNewWizard && (
        <NewSeqWizard
          onClose={() => setShowNewWizard(false)}
          onCreate={handleCreated}
        />
      )}
    </div>
  )
}
