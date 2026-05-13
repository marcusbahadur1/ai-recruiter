'use client'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { marketingApi } from '@/lib/api'
import type { Signal, SignalListResponse, SignalType } from '@/lib/api/types'

// ── Icons ─────────────────────────────────────────────────────────────────────

function HiringSpikeIcon({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 17l4-8 4 4 4-6 4 3" />
      <circle cx="20" cy="14" r="2" fill="currentColor" stroke="none" />
    </svg>
  )
}

function PainPostIcon({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <line x1="9" y1="10" x2="15" y2="10" />
    </svg>
  )
}

function GrowthIcon({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
      <polyline points="17 6 23 6 23 12" />
    </svg>
  )
}

function RunIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  )
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const TYPE_META: Record<SignalType, { label: string; color: string; bg: string; Icon: React.FC<{ size?: number }> }> = {
  hiring_spike:  { label: 'Hiring spike',   color: '#3b82f6', bg: 'rgba(59,130,246,0.1)',  Icon: HiringSpikeIcon },
  pain_post:     { label: 'Pain post',      color: '#22c55e', bg: 'rgba(34,197,94,0.1)',   Icon: PainPostIcon },
  growth_signal: { label: 'Growth signal',  color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  Icon: GrowthIcon },
}

function fmtTimeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

type ActionState = 'idle' | 'actioning' | 'actioned' | 'dismissing' | 'dismissed'

// ── Signal Card ───────────────────────────────────────────────────────────────

function SignalCard({
  signal,
  onActioned,
  onDismissed,
}: {
  signal: Signal
  onActioned: (id: string) => void
  onDismissed: (id: string) => void
}) {
  const [state, setState] = useState<ActionState>('idle')
  const meta = TYPE_META[signal.type]
  const { Icon } = meta

  const title = signal.type === 'pain_post'
    ? `${signal.person_name || 'Someone'} — ${signal.company || 'Unknown company'}`
    : `${signal.company || 'Unknown company'}`

  const tags: string[] = [meta.label]
  if (signal.location) tags.push(signal.location)
  if (signal.company_type) tags.push(signal.company_type)

  async function handle(actionType: string) {
    if (state !== 'idle') return

    // View company: open LinkedIn without actioning the signal
    if (actionType === 'view_company') {
      if (signal.linkedin_url) window.open(signal.linkedin_url, '_blank', 'noopener')
      return
    }

    setState('actioning')
    try {
      if (actionType === 'dismiss') {
        setState('dismissing')
        await marketingApi.dismissSignalDirect(signal.id)
        setState('dismissed')
        setTimeout(() => onDismissed(signal.id), 1800)
      } else {
        // Open LinkedIn for social actions before waiting for API
        if (['comment_connect', 'comment_dm'].includes(actionType)) {
          if (signal.linkedin_url) window.open(signal.linkedin_url, '_blank', 'noopener')
        }
        await marketingApi.actionSignalDirect(signal.id, actionType as any)
        setState('actioned')
        setTimeout(() => onActioned(signal.id), 1800)
      }
    } catch {
      setState('idle')
    }
  }

  const isProcessed = state === 'actioned' || state === 'dismissed'

  return (
    <div style={{
      background: 'var(--navy-mid)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      padding: '16px 20px',
      display: 'flex',
      gap: 16,
      opacity: isProcessed ? 0.45 : 1,
      transition: 'opacity 0.4s',
    }}>
      {/* Left: icon */}
      <div style={{
        width: 52, height: 52, borderRadius: 12,
        background: meta.bg,
        color: meta.color,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon size={26} />
      </div>

      {/* Body */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Title row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
          <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--foreground)' }}>{title}</span>
          <span style={{
            fontSize: 11, fontWeight: 600, padding: '2px 7px', borderRadius: 10,
            background: signal.urgency === 'high' ? 'rgba(239,68,68,0.15)' : 'rgba(107,114,128,0.15)',
            color: signal.urgency === 'high' ? '#ef4444' : 'var(--muted)',
            textTransform: 'uppercase', letterSpacing: 0.5,
          }}>
            {signal.urgency === 'high' ? '🔥 High' : 'Medium'}
          </span>
          <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 'auto' }}>
            Detected {fmtTimeAgo(signal.detected_at)}
          </span>
        </div>

        {/* Summary */}
        {signal.summary && (
          <p style={{
            fontSize: 13, color: 'var(--muted)', margin: '0 0 10px',
            overflow: 'hidden', display: '-webkit-box',
            WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as any,
          }}>
            {signal.summary}
          </p>
        )}

        {/* Tags */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
          {tags.map(t => (
            <span key={t} style={{
              fontSize: 11, padding: '2px 8px', borderRadius: 8,
              background: 'var(--navy-dark)', color: 'var(--muted)',
              border: '1px solid var(--border)',
            }}>{t}</span>
          ))}
        </div>

        {/* Actions */}
        {isProcessed ? (
          <span style={{ fontSize: 12, color: 'var(--muted)', fontStyle: 'italic' }}>
            {state === 'actioned' ? 'Actioned ✓' : 'Dismissed'}
          </span>
        ) : (
          <ActionButtons
            signalType={signal.type}
            busy={state === 'actioning' || state === 'dismissing'}
            onAction={handle}
          />
        )}
      </div>
    </div>
  )
}

function ActionButtons({
  signalType,
  busy,
  onAction,
}: {
  signalType: SignalType
  busy: boolean
  onAction: (type: string) => void
}) {
  const btnStyle = (primary?: boolean): React.CSSProperties => ({
    fontSize: 12, fontWeight: 500, padding: '5px 11px', borderRadius: 6,
    border: primary ? 'none' : '1px solid var(--border)',
    cursor: busy ? 'not-allowed' : 'pointer',
    opacity: busy ? 0.6 : 1,
    background: primary ? 'var(--cyan)' : 'transparent',
    color: primary ? 'var(--navy-dark)' : 'var(--foreground)',
    transition: 'opacity 0.15s',
  })

  const dismiss = (
    <button style={btnStyle()} onClick={() => onAction('dismiss')} disabled={busy}>
      Dismiss
    </button>
  )

  if (signalType === 'hiring_spike') {
    return (
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <button style={btnStyle(true)} onClick={() => onAction('outreach_now')} disabled={busy}>
          Connect + outreach now
        </button>
        <button style={btnStyle()} onClick={() => onAction('add_to_prospects')} disabled={busy}>
          Add to prospects
        </button>
        <button style={btnStyle()} onClick={() => onAction('view_company')} disabled={busy}>
          View company
        </button>
        {dismiss}
      </div>
    )
  }

  if (signalType === 'pain_post') {
    return (
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <button style={btnStyle(true)} onClick={() => onAction('comment_connect')} disabled={busy}>
          Comment + connect
        </button>
        <button style={btnStyle()} onClick={() => onAction('comment_dm')} disabled={busy}>
          DM only
        </button>
        <button style={btnStyle()} onClick={() => onAction('add_to_prospects')} disabled={busy}>
          Add to prospects
        </button>
        {dismiss}
      </div>
    )
  }

  // growth_signal
  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      <button style={btnStyle(true)} onClick={() => onAction('add_to_prospects')} disabled={busy}>
        Add to prospects
      </button>
      <button style={btnStyle()} onClick={() => onAction('outreach_now')} disabled={busy}>
        Enroll in sequence
      </button>
      {dismiss}
    </div>
  )
}

// ── Type Tile ─────────────────────────────────────────────────────────────────

function TypeTile({
  type,
  count,
  active,
  onClick,
}: {
  type: SignalType | 'all'
  count: number
  active: boolean
  onClick: () => void
}) {
  const meta = type === 'all' ? null : TYPE_META[type]
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1, minWidth: 0,
        padding: '16px 20px',
        borderRadius: 10,
        border: active ? `2px solid ${meta?.color ?? 'var(--cyan)'}` : '2px solid var(--border)',
        background: active ? (meta ? meta.bg : 'rgba(6,182,212,0.08)') : 'var(--navy-mid)',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'all 0.15s',
        display: 'flex', alignItems: 'center', gap: 14,
      }}
    >
      {meta && (
        <div style={{ color: meta.color, flexShrink: 0 }}>
          <meta.Icon size={22} />
        </div>
      )}
      <div>
        <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--foreground)', lineHeight: 1 }}>
          {count}
        </div>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
          {type === 'all' ? 'All signals' : meta!.label}
        </div>
      </div>
    </button>
  )
}

// ── Main Tab ──────────────────────────────────────────────────────────────────

export default function SignalsTab() {
  const [data, setData] = useState<SignalListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeType, setActiveType] = useState<SignalType | 'all'>('all')
  const [running, setRunning] = useState(false)
  const [visibleIds, setVisibleIds] = useState<Set<string> | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const load = useCallback(async (type?: SignalType | 'all') => {
    try {
      const params = (type && type !== 'all') ? { type } : undefined
      const res = await marketingApi.listSignals(params)
      setData(res)
      setVisibleIds(new Set(res.items.map(s => s.id)))
    } catch {
      setError('Failed to load signals.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(activeType)
  }, [load, activeType])

  function handleTypeClick(type: SignalType | 'all') {
    setActiveType(type)
    setLoading(true)
    load(type)
  }

  function handleActioned(id: string) {
    setVisibleIds(prev => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
  }

  function handleDismissed(id: string) {
    setVisibleIds(prev => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
  }

  async function handleRunNow() {
    if (running) return
    setRunning(true)
    try {
      const run = await marketingApi.runSignalScrape()
      // Poll until completed_at is set (max 60 attempts × 3s = 3 min)
      let attempts = 0
      const poll = async () => {
        if (attempts++ > 60) {
          setRunning(false)
          return
        }
        try {
          const status = await marketingApi.getSignalRun(run.id)
          if (status.completed_at) {
            setRunning(false)
            load(activeType)
          } else {
            pollRef.current = setTimeout(poll, 3000)
          }
        } catch {
          setRunning(false)
        }
      }
      pollRef.current = setTimeout(poll, 3000)
    } catch {
      setRunning(false)
    }
  }

  // Cleanup poll on unmount
  useEffect(() => () => { if (pollRef.current) clearTimeout(pollRef.current) }, [])

  const allItems = data?.items ?? []
  const visible = visibleIds ? allItems.filter(s => visibleIds.has(s.id)) : allItems

  const counts: Record<SignalType, number> = {
    hiring_spike: allItems.filter(s => s.type === 'hiring_spike').length,
    pain_post: allItems.filter(s => s.type === 'pain_post').length,
    growth_signal: allItems.filter(s => s.type === 'growth_signal').length,
  }

  const freqHours = data?.scrape_frequency_hours ?? 6
  const lastRun = data?.last_run ?? null

  function lastRunLabel(): string {
    if (!lastRun) return 'Never'
    if (!lastRun.completed_at) return 'Running…'
    const mins = Math.floor((Date.now() - new Date(lastRun.completed_at).getTime()) / 60_000)
    if (mins < 1) return 'Just now'
    if (mins < 60) return `${mins} min ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    return `${Math.floor(hrs / 24)}d ago`
  }

  return (
    <div style={{ padding: '20px 0' }}>
      {/* ── Config bar ─────────────────────────────────────────────────────── */}
      <div style={{
        background: 'rgba(6,182,212,0.06)',
        border: '1px solid rgba(6,182,212,0.2)',
        borderRadius: 8,
        padding: '10px 16px',
        marginBottom: 20,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: 12.5, color: 'var(--foreground)' }}>
          BrightData scrapes run every <strong>{freqHours}h</strong>.
          {' '}Last run: <strong>{lastRunLabel()}</strong>.
        </span>
        <a
          href="#settings"
          onClick={e => { e.preventDefault(); document.querySelector('[data-tab="settings"]')?.scrollIntoView({ behavior: 'smooth' }) }}
          style={{ fontSize: 12, color: 'var(--cyan)', textDecoration: 'underline', cursor: 'pointer' }}
        >
          Change frequency →
        </a>
        <div style={{ marginLeft: 'auto' }}>
          <button
            onClick={handleRunNow}
            disabled={running}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              fontSize: 12, fontWeight: 600,
              padding: '6px 14px', borderRadius: 6,
              background: running ? 'var(--navy-light)' : 'var(--cyan)',
              color: running ? 'var(--muted)' : 'var(--navy-dark)',
              border: 'none', cursor: running ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {running ? (
              <>
                <Spinner />
                Running…
              </>
            ) : (
              <>
                <RunIcon />
                Run now
              </>
            )}
          </button>
        </div>
      </div>

      {/* ── Type tiles ─────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <TypeTile type="all" count={allItems.length} active={activeType === 'all'} onClick={() => handleTypeClick('all')} />
        <TypeTile type="hiring_spike" count={counts.hiring_spike} active={activeType === 'hiring_spike'} onClick={() => handleTypeClick('hiring_spike')} />
        <TypeTile type="pain_post" count={counts.pain_post} active={activeType === 'pain_post'} onClick={() => handleTypeClick('pain_post')} />
        <TypeTile type="growth_signal" count={counts.growth_signal} active={activeType === 'growth_signal'} onClick={() => handleTypeClick('growth_signal')} />
      </div>

      {/* ── Feed ───────────────────────────────────────────────────────────── */}
      {loading ? (
        <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
          Loading signals…
        </div>
      ) : error ? (
        <div style={{ padding: '40px 0', textAlign: 'center', color: '#ef4444', fontSize: 13 }}>{error}</div>
      ) : visible.length === 0 ? (
        <EmptyState type={activeType} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {visible.map(signal => (
            <SignalCard
              key={signal.id}
              signal={signal}
              onActioned={handleActioned}
              onDismissed={handleDismissed}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function EmptyState({ type }: { type: SignalType | 'all' }) {
  const meta = type !== 'all' ? TYPE_META[type] : null
  return (
    <div style={{
      padding: '48px 0',
      textAlign: 'center',
      color: 'var(--muted)',
    }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>
        {meta ? <meta.Icon size={36} /> : <HiringSpikeIcon size={36} />}
      </div>
      <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--foreground)', marginBottom: 6 }}>
        No signals yet
      </div>
      <div style={{ fontSize: 13 }}>
        {type === 'all'
          ? 'Click "Run now" to trigger a BrightData scrape, or wait for the next scheduled run.'
          : `No ${TYPE_META[type as SignalType]?.label.toLowerCase()} signals detected this week.`}
      </div>
    </div>
  )
}

function Spinner() {
  return (
    <svg
      width={12} height={12}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      style={{ animation: 'spin 0.8s linear infinite' }}
    >
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
    </svg>
  )
}
