'use client'
import { useState, useEffect, useCallback, useRef, KeyboardEvent } from 'react'
import { marketingApi } from '@/lib/api'
import type { Prospect, ProspectStage, ProspectSource, OutreachLog, TenantStatus } from '@/lib/api'

// ── Constants ──────────────────────────────────────────────────────────────────

const PAGE_SIZE = 25

const STAGE_LABELS: Record<ProspectStage, string> = {
  identified: 'Identified',
  connected: 'Connected',
  messaged: 'Messaged',
  replied: 'Replied',
  demo_booked: 'Demo booked',
  trial: 'Trial',
  paid: 'Paid',
}

const STAGE_COLORS: Record<ProspectStage, { bg: string; color: string }> = {
  identified: { bg: 'rgba(150,150,170,0.18)', color: '#aaa' },
  connected:  { bg: 'rgba(96,165,250,0.18)',  color: '#60a5fa' },
  messaged:   { bg: 'rgba(59,130,246,0.22)',  color: '#3b82f6' },
  replied:    { bg: 'rgba(251,191,36,0.18)',  color: '#fbbf24' },
  demo_booked:{ bg: 'rgba(167,139,250,0.18)', color: '#a78bfa' },
  trial:      { bg: 'rgba(45,212,191,0.18)',  color: '#2dd4bf' },
  paid:       { bg: 'rgba(52,211,153,0.18)',  color: '#34d399' },
}

const ALL_STAGES: ProspectStage[] = [
  'identified', 'connected', 'messaged', 'replied', 'demo_booked', 'trial', 'paid',
]

type SortKey = 'icp_desc' | 'icp_asc' | 'date_desc' | 'stage'

// ── Helpers ────────────────────────────────────────────────────────────────────

function nameInitials(name: string | null): string {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function nameColor(name: string | null): string {
  const colors = ['#6366f1','#8b5cf6','#ec4899','#f59e0b','#10b981','#3b82f6','#ef4444','#14b8a6']
  if (!name) return colors[0]
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) & 0xffffffff
  return colors[Math.abs(h) % colors.length]
}

function icpColor(score: number | null): { bg: string; color: string } {
  if (score === null) return { bg: 'rgba(150,150,170,0.15)', color: '#aaa' }
  if (score >= 8) return { bg: 'rgba(52,211,153,0.2)', color: '#34d399' }
  if (score >= 6) return { bg: 'rgba(251,191,36,0.2)', color: '#fbbf24' }
  return { bg: 'rgba(239,68,68,0.2)', color: '#ef4444' }
}

function isAgencyOwner(title: string | null): boolean {
  if (!title) return false
  const t = title.toLowerCase()
  return ['md','owner','director','partner','managing'].some(k => t.includes(k))
}

function isHrDirector(title: string | null): boolean {
  if (!title) return false
  const t = title.toLowerCase()
  return ['hr','people','talent'].some(k => t.includes(k))
}

// ── Shared styles ──────────────────────────────────────────────────────────────

const S = {
  btn: (primary?: boolean): React.CSSProperties => ({
    padding: '5px 12px', fontSize: 12, borderRadius: 6, cursor: 'pointer',
    border: primary ? 'none' : '1px solid var(--border-mid)',
    background: primary ? 'var(--cyan)' : 'none',
    color: primary ? '#000' : 'var(--muted)',
    fontWeight: primary ? 600 : 400,
    whiteSpace: 'nowrap',
  }),
  chip: (active: boolean): React.CSSProperties => ({
    padding: '4px 10px', fontSize: 11, borderRadius: 20, cursor: 'pointer',
    border: active ? '1px solid var(--cyan)' : '1px solid var(--border-mid)',
    background: active ? 'rgba(0,212,255,0.1)' : 'none',
    color: active ? 'var(--cyan)' : 'var(--muted)',
    fontWeight: 500, whiteSpace: 'nowrap',
  }),
  input: {
    background: 'var(--navy-light)', border: '1px solid var(--border-mid)',
    borderRadius: 6, padding: '6px 10px', fontSize: 12,
    color: 'var(--white)', outline: 'none',
  } as React.CSSProperties,
  th: {
    textAlign: 'left' as const, fontSize: 11, color: 'var(--muted)',
    fontWeight: 600, padding: '8px 10px',
    borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' as const,
  } as React.CSSProperties,
  td: {
    padding: '10px 10px', fontSize: 12, color: 'var(--white)',
    borderBottom: '1px solid var(--border)',
    verticalAlign: 'middle' as const,
  } as React.CSSProperties,
}

// ── TagInput ───────────────────────────────────────────────────────────────────

function TagInput({
  tags, onChange, placeholder = 'Type and press Enter',
}: { tags: string[]; onChange: (t: string[]) => void; placeholder?: string }) {
  const [val, setVal] = useState('')
  const handle = (e: KeyboardEvent<HTMLInputElement>) => {
    if ((e.key === 'Enter' || e.key === ',') && val.trim()) {
      e.preventDefault()
      const tag = val.trim().replace(/,$/, '')
      if (tag && !tags.includes(tag)) onChange([...tags, tag])
      setVal('')
    }
    if (e.key === 'Backspace' && !val && tags.length) {
      onChange(tags.slice(0, -1))
    }
  }
  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center',
      background: 'var(--navy-light)', border: '1px solid var(--border-mid)',
      borderRadius: 6, padding: '4px 6px', minHeight: 34,
    }}>
      {tags.map(t => (
        <span key={t} style={{
          display: 'flex', alignItems: 'center', gap: 4,
          background: 'rgba(96,165,250,0.15)', color: '#60a5fa',
          borderRadius: 4, padding: '2px 6px', fontSize: 11,
        }}>
          {t}
          <button onClick={() => onChange(tags.filter(x => x !== t))} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: '#60a5fa', padding: 0, lineHeight: 1, fontSize: 13,
          }}>×</button>
        </span>
      ))}
      <input
        value={val} onChange={e => setVal(e.target.value)} onKeyDown={handle}
        placeholder={tags.length ? '' : placeholder}
        style={{ background: 'none', border: 'none', outline: 'none', fontSize: 12, color: 'var(--white)', minWidth: 80, flex: 1 }}
      />
    </div>
  )
}

// ── StagePill ──────────────────────────────────────────────────────────────────

function StagePill({ stage }: { stage: ProspectStage }) {
  const c = STAGE_COLORS[stage]
  return (
    <span style={{
      padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 500,
      background: c.bg, color: c.color, whiteSpace: 'nowrap',
    }}>
      {STAGE_LABELS[stage]}
    </span>
  )
}

// ── SourceBadge ────────────────────────────────────────────────────────────────

function SourceBadge({ source }: { source: ProspectSource }) {
  const map: Record<ProspectSource, { icon: string; label: string; color: string }> = {
    brightdata: { icon: '🔗', label: 'BD', color: '#60a5fa' },
    hunter:     { icon: '✉', label: 'H',  color: '#a78bfa' },
    manual:     { icon: '👤', label: 'M',  color: '#94a3b8' },
  }
  const m = map[source]
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      padding: '2px 7px', borderRadius: 4, fontSize: 11,
      background: 'rgba(255,255,255,0.06)', color: m.color,
    }}>
      <span style={{ fontSize: 10 }}>{m.icon}</span>{m.label}
    </span>
  )
}

// ── IcpCircle ──────────────────────────────────────────────────────────────────

function IcpCircle({ score, breakdown }: { score: number | null; breakdown: Record<string, number> | null }) {
  const [tip, setTip] = useState(false)
  const c = icpColor(score)
  const keys: Record<string, string> = {
    title_match: '+3 title match',
    company_type_match: '+2 company type',
    company_size_in_range: '+1 company size',
    location_match: '+1 location',
    recent_linkedin_activity: '+2 LinkedIn active',
    hiring_spike_signal: '+1 hiring spike',
  }
  return (
    <div style={{ position: 'relative', display: 'inline-block' }}
      onMouseEnter={() => setTip(true)} onMouseLeave={() => setTip(false)}>
      <div style={{
        width: 30, height: 30, borderRadius: '50%',
        background: c.bg, color: c.color,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, fontWeight: 700, cursor: 'default',
      }}>
        {score ?? '—'}
      </div>
      {tip && breakdown && Object.keys(breakdown).length > 0 && (
        <div style={{
          position: 'absolute', left: 36, top: -4, zIndex: 99,
          background: 'var(--navy-mid)', border: '1px solid var(--border)',
          borderRadius: 6, padding: '8px 12px', fontSize: 11,
          color: 'var(--muted)', whiteSpace: 'nowrap', minWidth: 160,
          boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        }}>
          <div style={{ fontWeight: 600, color: 'var(--white)', marginBottom: 4 }}>ICP score breakdown</div>
          {Object.entries(breakdown).map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
              <span>{keys[k] ?? k}</span>
              <span style={{ color: 'var(--cyan)' }}>+{v}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── SlideOver ──────────────────────────────────────────────────────────────────

function SlideOver({
  prospect, onClose, onUpdate, hasHunter,
}: {
  prospect: Prospect
  onClose: () => void
  onUpdate: (p: Prospect) => void
  hasHunter?: boolean
}) {
  const [stage, setStage] = useState<ProspectStage>(prospect.stage)
  const [saving, setSaving] = useState(false)
  const [enriching, setEnriching] = useState(false)
  const [notes, setNotes] = useState(prospect.notes ?? '')
  const [sequences, setSequences] = useState<{ id: string; name: string }[]>([])
  const [enrollModal, setEnrollModal] = useState(false)
  const [selectedSeq, setSelectedSeq] = useState('')
  const [enrolling, setEnrolling] = useState(false)
  const [detail, setDetail] = useState<Prospect>(prospect)

  // Load full detail with outreach log
  useEffect(() => {
    marketingApi.getProspect(prospect.id).then(setDetail).catch(() => {})
    // Load sequences for enroll modal
    // We'll stub this for now — sequences API comes in a later phase
    setSequences([])
  }, [prospect.id])

  const changeStage = async (s: ProspectStage) => {
    setStage(s)
    setSaving(true)
    try {
      const updated = await marketingApi.updateProspect(prospect.id, { stage: s })
      onUpdate(updated)
    } finally {
      setSaving(false)
    }
  }

  const saveNotes = async () => {
    setSaving(true)
    try {
      const updated = await marketingApi.updateProspect(prospect.id, { notes })
      onUpdate(updated)
    } finally {
      setSaving(false)
    }
  }

  const findEmail = async () => {
    setEnriching(true)
    try {
      const updated = await marketingApi.enrichProspectEmail(prospect.id)
      setDetail(updated)
      onUpdate(updated)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Email not found'
      alert(msg)
    } finally {
      setEnriching(false)
    }
  }

  const enroll = async () => {
    if (!selectedSeq) return
    setEnrolling(true)
    try {
      await marketingApi.enrollProspect(prospect.id, selectedSeq)
      setEnrollModal(false)
    } catch {
      alert('Failed to enroll')
    } finally {
      setEnrolling(false)
    }
  }

  const formatDate = (d: string | null) => {
    if (!d) return '—'
    return new Date(d).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })
  }

  const formatDateTime = (d: string | null) => {
    if (!d) return '—'
    return new Date(d).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }) +
      ' ' + new Date(d).toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <>
      {/* Backdrop */}
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 200,
      }} />
      {/* Panel */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: 380,
        background: 'var(--navy-mid)', borderLeft: '1px solid var(--border)',
        zIndex: 201, overflowY: 'auto', display: 'flex', flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px', borderBottom: '1px solid var(--border)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 44, height: 44, borderRadius: '50%',
              background: nameColor(prospect.name),
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 15, fontWeight: 700, color: '#fff', flexShrink: 0,
            }}>
              {nameInitials(prospect.name)}
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{prospect.name ?? 'Unknown'}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1 }}>
                {prospect.title ?? '—'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                {prospect.company ?? '—'}
              </div>
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: 'var(--muted)',
            cursor: 'pointer', fontSize: 18, lineHeight: 1,
          }}>×</button>
        </div>

        {/* Body */}
        <div style={{ padding: '16px 20px', flex: 1, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Meta row */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <IcpCircle score={detail.icp_score} breakdown={detail.score_breakdown} />
            <SourceBadge source={detail.source} />
            <StagePill stage={stage} />
          </div>

          {/* Contact */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {detail.linkedin_url && (
              <a href={detail.linkedin_url} target="_blank" rel="noreferrer" style={{
                fontSize: 12, color: 'var(--cyan)', textDecoration: 'none',
              }}>
                🔗 LinkedIn profile
              </a>
            )}
            <div style={{ fontSize: 12, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 8 }}>
              {detail.email ? (
                <span style={{ color: 'var(--white)' }}>✉ {detail.email}</span>
              ) : (
                <>
                  <span>No email</span>
                  {hasHunter === false ? (
                    <span style={{ fontSize: 11, color: 'var(--muted)', fontStyle: 'italic' }}
                      title="Add a Hunter.io API key in Settings to enable email enrichment">
                      Hunter.io not configured
                    </span>
                  ) : (
                    <button onClick={findEmail} disabled={enriching} style={S.btn()}>
                      {enriching ? 'Finding…' : 'Find email'}
                    </button>
                  )}
                </>
              )}
            </div>
            {detail.location && <div style={{ fontSize: 12, color: 'var(--muted)' }}>📍 {detail.location}</div>}
            {detail.company_size && (
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                🏢 {detail.company_size.toLocaleString()} employees
              </div>
            )}
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
              Added {formatDate(detail.created_at)}
              {detail.last_activity_at && ` · Last activity ${formatDate(detail.last_activity_at)}`}
            </div>
          </div>

          {/* Stage selector */}
          <div>
            <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 6, fontWeight: 600 }}>
              Stage {saving && <span style={{ color: 'var(--cyan)' }}>saving…</span>}
            </label>
            <select
              value={stage}
              onChange={e => changeStage(e.target.value as ProspectStage)}
              style={{ ...S.input, width: '100%' }}
            >
              {ALL_STAGES.map(s => (
                <option key={s} value={s}>{STAGE_LABELS[s]}</option>
              ))}
            </select>
          </div>

          {/* Notes */}
          <div>
            <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 6, fontWeight: 600 }}>
              Notes
            </label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              onBlur={saveNotes}
              rows={3}
              placeholder="Add notes…"
              style={{ ...S.input, width: '100%', resize: 'vertical' }}
            />
          </div>

          {/* Outreach timeline */}
          <div>
            <div style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600, marginBottom: 8 }}>
              Outreach timeline
            </div>
            {detail.outreach_log.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--muted)', fontStyle: 'italic' }}>No outreach yet</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {detail.outreach_log.map((log: OutreachLog) => (
                  <div key={log.id} style={{
                    fontSize: 11, color: 'var(--muted)',
                    borderLeft: '2px solid var(--border-mid)',
                    paddingLeft: 8,
                  }}>
                    <span style={{ color: log.channel === 'linkedin' ? '#60a5fa' : '#a78bfa' }}>
                      {log.channel === 'linkedin' ? '🔗' : '✉'} {log.channel}
                    </span>
                    {' · '}Sent {formatDateTime(log.sent_at)}
                    {log.opened_at && <span style={{ color: '#34d399' }}> · Opened</span>}
                    {log.replied_at && <span style={{ color: '#fbbf24' }}> · Replied</span>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            <button onClick={() => setEnrollModal(true)} style={S.btn(true)}>
              Enroll in sequence
            </button>
          </div>
        </div>
      </div>

      {/* Enroll modal */}
      {enrollModal && (
        <>
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 300 }} onClick={() => setEnrollModal(false)} />
          <div style={{
            position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
            background: 'var(--navy-mid)', border: '1px solid var(--border)',
            borderRadius: 10, padding: 24, width: 340, zIndex: 301,
          }}>
            <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 16 }}>Enroll in sequence</div>
            {sequences.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
                No sequences yet. Create one in the Sequences tab first.
              </div>
            ) : (
              <select value={selectedSeq} onChange={e => setSelectedSeq(e.target.value)} style={{ ...S.input, width: '100%', marginBottom: 16 }}>
                <option value="">Select a sequence…</option>
                {sequences.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            )}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setEnrollModal(false)} style={S.btn()}>Cancel</button>
              {sequences.length > 0 && (
                <button onClick={enroll} disabled={!selectedSeq || enrolling} style={S.btn(true)}>
                  {enrolling ? 'Enrolling…' : 'Enroll'}
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </>
  )
}

// ── AddProspectsModal ──────────────────────────────────────────────────────────

function AddProspectsModal({
  onClose, onComplete,
}: { onClose: () => void; onComplete: (count: number) => void }) {
  const [titles, setTitles] = useState<string[]>([])
  const [locations, setLocations] = useState<string[]>([])
  const [companyTypes, setCompanyTypes] = useState<string[]>([])
  const [sizeMin, setSizeMin] = useState('')
  const [sizeMax, setSizeMax] = useState('')
  const [maxProspects, setMaxProspects] = useState<50 | 100 | 250 | 500>(100)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<string | null>(null)

  const submit = async () => {
    setLoading(true)
    setResult(null)
    try {
      const res = await marketingApi.scrapeProspects({
        titles,
        locations,
        company_types: companyTypes,
        company_size_min: sizeMin ? Number(sizeMin) : undefined,
        company_size_max: sizeMax ? Number(sizeMax) : undefined,
        max_prospects: maxProspects,
      })
      setResult(res.message)
      onComplete(res.inserted)
    } catch {
      setResult('Scrape failed — check your BrightData API key in Settings → Channels')
    } finally {
      setLoading(false)
    }
  }

  const fieldStyle: React.CSSProperties = { marginBottom: 14 }
  const labelStyle: React.CSSProperties = { display: 'block', fontSize: 11, color: 'var(--muted)', marginBottom: 4, fontWeight: 500 }

  return (
    <>
      <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 300 }} onClick={onClose} />
      <div style={{
        position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        background: 'var(--navy-mid)', border: '1px solid var(--border)',
        borderRadius: 10, padding: 24, width: 460, zIndex: 301, maxHeight: '90vh', overflowY: 'auto',
      }}>
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 20 }}>Add prospects via BrightData</div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Job titles to target</label>
          <TagInput tags={titles} onChange={setTitles} placeholder="e.g. HR Director, MD, Owner" />
        </div>
        <div style={fieldStyle}>
          <label style={labelStyle}>Locations</label>
          <TagInput tags={locations} onChange={setLocations} placeholder="e.g. Sydney, Melbourne" />
        </div>
        <div style={fieldStyle}>
          <label style={labelStyle}>Company types</label>
          <TagInput tags={companyTypes} onChange={setCompanyTypes} placeholder="e.g. Staffing Agency, Consultancy" />
        </div>
        <div style={{ display: 'flex', gap: 12, marginBottom: 14 }}>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>Company size min</label>
            <input type="number" value={sizeMin} onChange={e => setSizeMin(e.target.value)}
              placeholder="e.g. 10" style={{ ...S.input, width: '100%' }} />
          </div>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>Company size max</label>
            <input type="number" value={sizeMax} onChange={e => setSizeMax(e.target.value)}
              placeholder="e.g. 500" style={{ ...S.input, width: '100%' }} />
          </div>
        </div>
        <div style={fieldStyle}>
          <label style={labelStyle}>Max prospects to find</label>
          <select value={maxProspects} onChange={e => setMaxProspects(Number(e.target.value) as 50 | 100 | 250 | 500)}
            style={{ ...S.input, width: '100%' }}>
            {[50, 100, 250, 500].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>

        {loading && (
          <div style={{
            background: 'rgba(0,212,255,0.08)', border: '1px solid var(--border)',
            borderRadius: 6, padding: '10px 14px', fontSize: 12, color: 'var(--cyan)',
            marginBottom: 14,
          }}>
            Scraping BrightData… this may take up to 2 minutes
          </div>
        )}

        {result && (
          <div style={{
            background: 'rgba(52,211,153,0.08)', border: '1px solid rgba(52,211,153,0.3)',
            borderRadius: 6, padding: '10px 14px', fontSize: 12, color: '#34d399',
            marginBottom: 14,
          }}>
            {result}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={S.btn()} disabled={loading}>
            {result ? 'Close' : 'Cancel'}
          </button>
          {!result && (
            <button onClick={submit} disabled={loading} style={S.btn(true)}>
              {loading ? 'Scraping…' : 'Find prospects'}
            </button>
          )}
        </div>
      </div>
    </>
  )
}

// ── MoreFiltersDropdown ────────────────────────────────────────────────────────

interface MoreFilters {
  stages: ProspectStage[]
  location: string
  source: ProspectSource | ''
  sizeMin: string
  sizeMax: string
}

function MoreFiltersDropdown({
  filters, onChange, onClose,
}: { filters: MoreFilters; onChange: (f: MoreFilters) => void; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  const toggleStage = (s: ProspectStage) => {
    const next = filters.stages.includes(s)
      ? filters.stages.filter(x => x !== s)
      : [...filters.stages, s]
    onChange({ ...filters, stages: next })
  }

  return (
    <div ref={ref} style={{
      position: 'absolute', top: '100%', left: 0, zIndex: 100, marginTop: 4,
      background: 'var(--navy-mid)', border: '1px solid var(--border)',
      borderRadius: 8, padding: 16, width: 280,
      boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
    }}>
      <div style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600, marginBottom: 8 }}>Stage</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 12 }}>
        {ALL_STAGES.map(s => (
          <button key={s} onClick={() => toggleStage(s)}
            style={S.chip(filters.stages.includes(s))}>
            {STAGE_LABELS[s]}
          </button>
        ))}
      </div>

      <div style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600, marginBottom: 4 }}>Location</div>
      <input value={filters.location} onChange={e => onChange({ ...filters, location: e.target.value })}
        placeholder="e.g. Sydney" style={{ ...S.input, width: '100%', marginBottom: 12 }} />

      <div style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600, marginBottom: 4 }}>Source</div>
      <select value={filters.source} onChange={e => onChange({ ...filters, source: e.target.value as ProspectSource | '' })}
        style={{ ...S.input, width: '100%', marginBottom: 12 }}>
        <option value="">Any</option>
        <option value="brightdata">LinkedIn (BrightData)</option>
        <option value="hunter">Email (Hunter.io)</option>
        <option value="manual">Manual</option>
      </select>

      <div style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600, marginBottom: 4 }}>Company size</div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input type="number" value={filters.sizeMin} onChange={e => onChange({ ...filters, sizeMin: e.target.value })}
          placeholder="Min" style={{ ...S.input, flex: 1 }} />
        <input type="number" value={filters.sizeMax} onChange={e => onChange({ ...filters, sizeMax: e.target.value })}
          placeholder="Max" style={{ ...S.input, flex: 1 }} />
      </div>

      <button onClick={() => onChange({ stages: [], location: '', source: '', sizeMin: '', sizeMax: '' })}
        style={{ ...S.btn(), marginTop: 12, fontSize: 11 }}>
        Clear all
      </button>
    </div>
  )
}

// ── Main ProspectsTab ──────────────────────────────────────────────────────────

export default function ProspectsTab({ tenantStatus }: { tenantStatus?: TenantStatus | null }) {
  // Data
  const [prospects, setProspects] = useState<Prospect[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  // Pagination
  const [page, setPage] = useState(1)

  // Search
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Filter chips
  const [chipAgency, setChipAgency] = useState(false)
  const [chipHr, setChipHr] = useState(false)
  const [chipHighFit, setChipHighFit] = useState(false)
  const [chipLinkedin, setChipLinkedin] = useState(false)

  // More filters
  const [moreOpen, setMoreOpen] = useState(false)
  const [moreFilters, setMoreFilters] = useState<MoreFilters>({
    stages: [], location: '', source: '', sizeMin: '', sizeMax: '',
  })

  // Sort
  const [sort, setSort] = useState<SortKey>('icp_desc')

  // UI state
  const [selected, setSelected] = useState<Prospect | null>(null)
  const [addModal, setAddModal] = useState(false)
  const moreRef = useRef<HTMLDivElement>(null)

  // ── Load from API (server-side filters where possible) ─────────────────────

  const load = useCallback(async (pg: number) => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = {
        page: pg, page_size: PAGE_SIZE, sort,
      }
      if (moreFilters.stages.length > 0) params.stage = moreFilters.stages.join(',')
      if (moreFilters.source) params.source = moreFilters.source
      if (moreFilters.location) params.location = moreFilters.location
      if (moreFilters.sizeMin) params.company_size_min = Number(moreFilters.sizeMin)
      if (moreFilters.sizeMax) params.company_size_max = Number(moreFilters.sizeMax)

      const res = await marketingApi.listProspects(params as Parameters<typeof marketingApi.listProspects>[0])
      setProspects(res.items)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [sort, moreFilters])

  useEffect(() => { load(page) }, [load, page])

  // ── Client-side filtering (search + chips applied on top of API results) ────

  const filtered = prospects.filter(p => {
    if (search) {
      const q = search.toLowerCase()
      const hit = [p.name, p.company, p.title].some(v => v?.toLowerCase().includes(q))
      if (!hit) return false
    }
    if (chipAgency && !isAgencyOwner(p.title)) return false
    if (chipHr && !isHrDirector(p.title)) return false
    if (chipHighFit && (p.icp_score ?? 0) < 8) return false
    if (chipLinkedin && p.source !== 'brightdata') return false
    return true
  })

  // ── Debounce search ────────────────────────────────────────────────────────

  const onSearchChange = (v: string) => {
    setSearchInput(v)
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => setSearch(v), 300)
  }

  // ── Active filter label ────────────────────────────────────────────────────

  const activeChips = [
    chipAgency && 'Agency owner',
    chipHr && 'HR director',
    chipHighFit && 'High fit (8+)',
    chipLinkedin && 'LinkedIn only',
    moreFilters.stages.length > 0 && `Stage: ${moreFilters.stages.map(s => STAGE_LABELS[s]).join(', ')}`,
    moreFilters.location && `Location: ${moreFilters.location}`,
    moreFilters.source && `Source: ${moreFilters.source}`,
    (moreFilters.sizeMin || moreFilters.sizeMax) && `Size: ${moreFilters.sizeMin || '0'}–${moreFilters.sizeMax || '∞'}`,
  ].filter(Boolean) as string[]

  // ── Row actions ────────────────────────────────────────────────────────────

  const stageActions: Record<ProspectStage, { label: string; nextStage: ProspectStage | null }[]> = {
    identified:  [{ label: 'Connect',     nextStage: 'connected'   }],
    connected:   [{ label: 'Message',     nextStage: 'messaged'    }],
    messaged:    [{ label: 'Follow up',   nextStage: null          }],
    replied:     [{ label: 'Book demo',   nextStage: 'demo_booked' }],
    demo_booked: [{ label: 'Mark trial',  nextStage: 'trial'       }],
    trial:       [],
    paid:        [],
  }

  const handleAction = async (p: Prospect, nextStage: ProspectStage | null) => {
    if (!nextStage) return
    try {
      const updated = await marketingApi.updateProspect(p.id, { stage: nextStage })
      setProspects(prev => prev.map(x => x.id === updated.id ? updated : x))
    } catch {
      // ignore
    }
  }

  const onUpdate = (updated: Prospect) => {
    setProspects(prev => prev.map(x => x.id === updated.id ? updated : x))
    if (selected?.id === updated.id) setSelected(updated)
  }

  const onScrapeComplete = (count: number) => {
    if (count > 0) load(1)
  }

  // ── Pagination helpers ─────────────────────────────────────────────────────

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div style={{ paddingTop: 20 }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
        {/* Search */}
        <input
          value={searchInput}
          onChange={e => onSearchChange(e.target.value)}
          placeholder="Search name, company, title…"
          style={{ ...S.input, width: 220 }}
        />

        {/* Filter chips */}
        <button onClick={() => setChipAgency(!chipAgency)} style={S.chip(chipAgency)}>
          Agency owner
        </button>
        <button onClick={() => setChipHr(!chipHr)} style={S.chip(chipHr)}>
          HR director
        </button>
        <button onClick={() => setChipHighFit(!chipHighFit)} style={S.chip(chipHighFit)}>
          High fit (8+)
        </button>
        <button onClick={() => setChipLinkedin(!chipLinkedin)} style={S.chip(chipLinkedin)}>
          LinkedIn only
        </button>

        {/* More filters */}
        <div style={{ position: 'relative' }} ref={moreRef}>
          <button onClick={() => setMoreOpen(!moreOpen)}
            style={S.chip(moreFilters.stages.length > 0 || !!moreFilters.location || !!moreFilters.source || !!moreFilters.sizeMin || !!moreFilters.sizeMax)}>
            More filters ▾
          </button>
          {moreOpen && (
            <MoreFiltersDropdown
              filters={moreFilters}
              onChange={f => { setMoreFilters(f); setPage(1) }}
              onClose={() => setMoreOpen(false)}
            />
          )}
        </div>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Sort */}
        <select value={sort} onChange={e => { setSort(e.target.value as SortKey); setPage(1) }}
          style={{ ...S.input, width: 180 }}>
          <option value="icp_desc">ICP fit: high → low</option>
          <option value="icp_asc">ICP fit: low → high</option>
          <option value="date_desc">Date added: newest</option>
          <option value="stage">Stage (pipeline order)</option>
        </select>

        {/* Add button */}
        <button onClick={() => setAddModal(true)} style={S.btn(true)}>
          + Add prospects
        </button>
      </div>

      {/* Results count */}
      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 12 }}>
        {loading ? 'Loading…' : (
          <>
            Showing {filtered.length} of {total} prospect{total !== 1 ? 's' : ''}
            {activeChips.length > 0 && (
              <span> · filtered by <span style={{ color: 'var(--cyan)' }}>{activeChips.join(' · ')}</span></span>
            )}
          </>
        )}
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
          <colgroup>
            <col style={{ width: '22%' }} />
            <col style={{ width: '18%' }} />
            <col style={{ width: '14%' }} />
            <col style={{ width: '8%' }} />
            <col style={{ width: '10%' }} />
            <col style={{ width: '13%' }} />
            <col style={{ width: '15%' }} />
          </colgroup>
          <thead>
            <tr>
              <th style={S.th}>Name</th>
              <th style={S.th}>Company</th>
              <th style={S.th}>Title</th>
              <th style={S.th}>ICP fit</th>
              <th style={S.th}>Source</th>
              <th style={S.th}>Stage</th>
              <th style={S.th}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && !loading && (
              <tr>
                <td colSpan={7} style={{ ...S.td, textAlign: 'center', color: 'var(--muted)', padding: '32px 0', fontStyle: 'italic' }}>
                  {total === 0 ? 'No prospects yet — click "+ Add prospects" to get started' : 'No prospects match the current filters'}
                </td>
              </tr>
            )}
            {filtered.map(p => {
              const actions = stageActions[p.stage] ?? []
              return (
                <tr
                  key={p.id}
                  onClick={() => setSelected(p)}
                  style={{ cursor: 'pointer', transition: 'background 0.1s' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
                  onMouseLeave={e => (e.currentTarget.style.background = '')}
                >
                  {/* Name */}
                  <td style={S.td}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{
                        width: 30, height: 30, borderRadius: '50%', flexShrink: 0,
                        background: nameColor(p.name),
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11, fontWeight: 700, color: '#fff',
                      }}>
                        {nameInitials(p.name)}
                      </div>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {p.name ?? '—'}
                      </span>
                    </div>
                  </td>
                  {/* Company */}
                  <td style={{ ...S.td, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.company ?? '—'}
                  </td>
                  {/* Title */}
                  <td style={{ ...S.td, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--muted)' }}>
                    {p.title ?? '—'}
                  </td>
                  {/* ICP */}
                  <td style={S.td}>
                    <IcpCircle score={p.icp_score} breakdown={p.score_breakdown} />
                  </td>
                  {/* Source */}
                  <td style={S.td}>
                    <SourceBadge source={p.source} />
                  </td>
                  {/* Stage */}
                  <td style={S.td}>
                    <StagePill stage={p.stage} />
                  </td>
                  {/* Actions */}
                  <td style={{ ...S.td }} onClick={e => e.stopPropagation()}>
                    <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                      <button onClick={() => setSelected(p)} style={S.btn()}>View</button>
                      {actions.map(a => (
                        <button key={a.label} onClick={() => handleAction(p, a.nextStage)} style={S.btn()}>
                          {a.label}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 16, justifyContent: 'center' }}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{ ...S.btn(), opacity: page === 1 ? 0.4 : 1 }}
          >
            ← Prev
          </button>
          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
            let pg = i + 1
            if (totalPages > 7) {
              if (page <= 4) pg = i + 1
              else if (page >= totalPages - 3) pg = totalPages - 6 + i
              else pg = page - 3 + i
            }
            return (
              <button
                key={pg}
                onClick={() => setPage(pg)}
                style={{
                  ...S.btn(pg === page),
                  minWidth: 30, padding: '5px 8px',
                }}
              >
                {pg}
              </button>
            )
          })}
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            style={{ ...S.btn(), opacity: page === totalPages ? 0.4 : 1 }}
          >
            Next →
          </button>
        </div>
      )}

      {/* Slide-over */}
      {selected && (
        <SlideOver prospect={selected} onClose={() => setSelected(null)} onUpdate={onUpdate} hasHunter={tenantStatus?.has_hunter} />
      )}

      {/* Add prospects modal */}
      {addModal && (
        <AddProspectsModal onClose={() => setAddModal(false)} onComplete={onScrapeComplete} />
      )}
    </div>
  )
}
