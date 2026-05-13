'use client'
import { useState, useEffect, useCallback } from 'react'
import { marketingApi } from '@/lib/api'
import type {
  PipelineSummary, FunnelRow, MetricCard, Signal,
  SequenceSummary, Prospect, ProspectStage, ProspectSource,
} from '@/lib/api'

// ── Constants ──────────────────────────────────────────────────────────────────

const STAGE_LABELS: Record<ProspectStage, string> = {
  identified: 'Identified', connected: 'Connected', messaged: 'Messaged',
  replied: 'Replied', demo_booked: 'Demo booked', trial: 'Trial', paid: 'Paid',
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

// Blue ramp: darkening per funnel stage
const FUNNEL_COLORS = [
  '#bfdbfe', // lightest — Identified
  '#93c5fd',
  '#60a5fa',
  '#3b82f6',
  '#2563eb',
  '#1d4ed8', // darkest — Trial
]

const SIGNAL_TYPE_ICONS: Record<string, { icon: string; color: string; label: string }> = {
  hiring_spike:   { icon: '📈', color: '#f59e0b', label: 'Hiring spike'   },
  pain_post:      { icon: '💬', color: '#ef4444', label: 'Pain post'      },
  growth_signal:  { icon: '🚀', color: '#34d399', label: 'Growth signal'  },
}

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

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function MetricCardComp({
  label, card, accent,
}: { label: string; card: MetricCard; accent?: string }) {
  const deltaPositive = card.delta >= 0
  return (
    <div style={{
      flex: 1,
      background: 'var(--navy-mid)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: '16px 18px',
      display: 'flex',
      flexDirection: 'column',
      gap: 4,
    }}>
      <div style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <span style={{ fontSize: 28, fontWeight: 700, color: accent || 'var(--foreground)' }}>
          {card.value.toLocaleString()}
        </span>
        <span style={{
          fontSize: 11,
          fontWeight: 600,
          color: deltaPositive ? '#34d399' : '#ef4444',
        }}>
          {deltaPositive ? '+' : ''}{card.delta}
        </span>
      </div>
      {card.pct_label && (
        <div style={{ fontSize: 11, color: 'var(--muted)' }}>{card.pct_label}</div>
      )}
    </div>
  )
}

function FunnelChart({ rows }: { rows: FunnelRow[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {rows.map((row, i) => (
        <div key={row.stage} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 100, fontSize: 12, color: 'var(--foreground)', flexShrink: 0, textAlign: 'right' }}>
            {row.label}
          </div>
          <div style={{ flex: 1, background: 'rgba(255,255,255,0.05)', borderRadius: 4, height: 22, position: 'relative', overflow: 'hidden' }}>
            <div style={{
              position: 'absolute', left: 0, top: 0, bottom: 0,
              width: `${Math.max(row.percentage, 0.5)}%`,
              background: FUNNEL_COLORS[i] || FUNNEL_COLORS[FUNNEL_COLORS.length - 1],
              borderRadius: 4,
              transition: 'width 0.5s ease',
            }} />
          </div>
          <div style={{ width: 36, fontSize: 12, color: 'var(--foreground)', fontWeight: 600, flexShrink: 0 }}>
            {row.count}
          </div>
          <div style={{ width: 42, fontSize: 11, color: 'var(--muted)', flexShrink: 0 }}>
            {row.percentage.toFixed(1)}%
          </div>
        </div>
      ))}
    </div>
  )
}

function SignalCard({
  signal,
  onAction,
  onDismiss,
}: {
  signal: Signal
  onAction: (id: string, action: 'outreach_now' | 'add_to_prospects' | 'comment_connect') => void
  onDismiss: (id: string) => void
}) {
  const [actioned, setActioned] = useState(signal.actioned)
  const meta = SIGNAL_TYPE_ICONS[signal.type] || { icon: '🔔', color: '#6366f1', label: signal.type }

  async function handleAction(action: 'outreach_now' | 'add_to_prospects' | 'comment_connect') {
    if (actioned) return
    if (action === 'comment_connect' && signal.linkedin_url) {
      window.open(signal.linkedin_url, '_blank', 'noopener,noreferrer')
    }
    setActioned(true)
    onAction(signal.id, action)
  }

  const primaryLabel =
    signal.type === 'hiring_spike' ? 'Outreach now' :
    signal.linkedin_url ? 'Comment + connect' :
    'Add to prospects'

  const primaryAction: 'outreach_now' | 'add_to_prospects' | 'comment_connect' =
    signal.type === 'hiring_spike' ? 'outreach_now' :
    signal.linkedin_url ? 'comment_connect' :
    'add_to_prospects'

  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: '12px 14px',
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <div style={{
          fontSize: 18, flexShrink: 0,
          background: `${meta.color}22`,
          borderRadius: 6, padding: '4px 6px',
          lineHeight: 1,
        }}>
          {meta.icon}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--foreground)', lineHeight: 1.4 }}>
            {signal.company || signal.person_name || 'Unknown'}
          </div>
          {signal.summary && (
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2, lineHeight: 1.4, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
              {signal.summary}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
          <span style={{
            fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 10,
            background: signal.urgency === 'high' ? 'rgba(239,68,68,0.18)' : 'rgba(251,191,36,0.18)',
            color: signal.urgency === 'high' ? '#ef4444' : '#fbbf24',
          }}>
            {signal.urgency === 'high' ? 'HIGH' : 'MED'}
          </span>
          <span style={{ fontSize: 10, color: 'var(--muted)' }}>{timeAgo(signal.detected_at)}</span>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        {actioned ? (
          <span style={{ fontSize: 11, color: '#34d399', padding: '5px 10px', background: 'rgba(52,211,153,0.1)', borderRadius: 5 }}>
            Actioned ✓
          </span>
        ) : (
          <>
            <button
              onClick={() => handleAction(primaryAction)}
              style={{
                flex: 1, fontSize: 11, fontWeight: 600,
                background: 'var(--cyan)', color: '#000',
                border: 'none', borderRadius: 5,
                padding: '5px 10px', cursor: 'pointer',
              }}
            >
              {primaryLabel}
            </button>
            <button
              onClick={() => onDismiss(signal.id)}
              style={{
                fontSize: 11, color: 'var(--muted)',
                background: 'transparent', border: '1px solid var(--border)',
                borderRadius: 5, padding: '5px 8px', cursor: 'pointer',
              }}
            >
              Dismiss
            </button>
          </>
        )}
      </div>
    </div>
  )
}

function ProspectRow({
  prospect,
  onViewAll,
}: { prospect: Prospect; onViewAll?: () => void }) {
  const icp = icpColor(prospect.icp_score)
  const sc = STAGE_COLORS[prospect.stage] || STAGE_COLORS.identified
  const sourceLabel: Record<ProspectSource, string> = { brightdata: 'BrightData', hunter: 'Hunter', manual: 'Manual' }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '8px 0',
      borderBottom: '1px solid var(--border)',
    }}>
      {/* Avatar */}
      <div style={{
        width: 30, height: 30, borderRadius: '50%', flexShrink: 0,
        background: nameColor(prospect.name),
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 11, fontWeight: 700, color: '#fff',
      }}>
        {nameInitials(prospect.name)}
      </div>
      {/* Name + company */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--foreground)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {prospect.name || '—'}
        </div>
        <div style={{ fontSize: 11, color: 'var(--muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {prospect.company || '—'}
        </div>
      </div>
      {/* ICP circle */}
      <div style={{
        width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
        background: icp.bg, color: icp.color,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 700,
      }}>
        {prospect.icp_score ?? '—'}
      </div>
      {/* Source badge */}
      <div style={{
        fontSize: 10, padding: '2px 7px', borderRadius: 10,
        background: 'rgba(255,255,255,0.07)', color: 'var(--muted)',
        flexShrink: 0,
      }}>
        {sourceLabel[prospect.source]}
      </div>
      {/* Stage pill */}
      <div style={{
        fontSize: 10, padding: '2px 8px', borderRadius: 10,
        background: sc.bg, color: sc.color,
        fontWeight: 600, flexShrink: 0,
      }}>
        {STAGE_LABELS[prospect.stage]}
      </div>
    </div>
  )
}

function SequenceRow({ seq, onSelect }: { seq: SequenceSummary; onSelect: (id: string) => void }) {
  const isLinkedIn = seq.name.toLowerCase().includes('linkedin') || seq.name.toLowerCase().includes('connect')
  const statusColor = seq.status === 'live' ? '#34d399' : '#f59e0b'
  const replyPct = Math.round(seq.reply_rate * 100)

  return (
    <div
      onClick={() => onSelect(seq.id)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '9px 0', borderBottom: '1px solid var(--border)',
        cursor: 'pointer',
      }}
    >
      {/* Channel icon */}
      <div style={{
        width: 28, height: 28, borderRadius: 6, flexShrink: 0,
        background: isLinkedIn ? 'rgba(10,102,194,0.18)' : 'rgba(99,102,241,0.18)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 13,
      }}>
        {isLinkedIn ? '💼' : '✉️'}
      </div>
      {/* Name + status */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--foreground)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {seq.name}
        </div>
        <div style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 4, marginTop: 1 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: statusColor, display: 'inline-block' }} />
          <span style={{ color: statusColor, fontWeight: 600 }}>{seq.status === 'live' ? 'Live' : 'Paused'}</span>
        </div>
      </div>
      {/* Stats */}
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--foreground)' }}>{seq.enrolled_count}</div>
        <div style={{ fontSize: 10, color: 'var(--muted)' }}>enrolled</div>
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0, width: 42 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: replyPct > 0 ? '#60a5fa' : 'var(--muted)' }}>{replyPct}%</div>
        <div style={{ fontSize: 10, color: 'var(--muted)' }}>reply</div>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function PipelineTab({
  onNavigate,
}: {
  onNavigate?: (tab: string, extra?: Record<string, unknown>) => void
}) {
  const [data, setData] = useState<PipelineSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const summary = await marketingApi.getPipelineSummary()
      setData(summary)
      setError(null)
    } catch (err: unknown) {
      setError('Failed to load pipeline data')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function handleSignalAction(id: string, action: 'outreach_now' | 'add_to_prospects' | 'comment_connect') {
    try {
      await marketingApi.actionSignal(id, action)
    } catch (err) {
      console.error('Signal action failed', err)
    }
  }

  async function handleSignalDismiss(id: string) {
    try {
      await marketingApi.dismissSignal(id)
      setData(prev => prev ? {
        ...prev,
        signals: prev.signals.filter(s => s.id !== id),
      } : prev)
    } catch (err) {
      console.error('Signal dismiss failed', err)
    }
  }

  if (loading) {
    return (
      <div style={{ padding: '32px 0', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
        Loading pipeline…
      </div>
    )
  }

  if (error || !data) {
    return (
      <div style={{ padding: '32px 0', textAlign: 'center', color: '#ef4444', fontSize: 13 }}>
        {error || 'No data'}
        <button
          onClick={load}
          style={{ marginLeft: 10, fontSize: 12, color: 'var(--cyan)', background: 'none', border: 'none', cursor: 'pointer' }}
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div style={{ padding: '20px 0', display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Metrics bar ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 12 }}>
        <MetricCardComp label="Prospects found"  card={data.prospects_found} accent="var(--foreground)" />
        <MetricCardComp label="Connected"        card={data.connected}       accent="#60a5fa" />
        <MetricCardComp label="Replied"          card={data.replied}         accent="#fbbf24" />
        <MetricCardComp label="Demos booked"     card={data.demos_booked}    accent="#a78bfa" />
        <MetricCardComp label="Trials started"   card={data.trials_started}  accent="#2dd4bf" />
      </div>

      {/* ── Middle row: Funnel + Live Signals ────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>

        {/* Funnel — 60% */}
        <div style={{
          flex: 3,
          background: 'var(--navy-mid)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: '16px 18px',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--foreground)', marginBottom: 14 }}>
            Conversion Funnel
          </div>
          {data.funnel.length === 0 || data.prospects_found.value === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--muted)', padding: '20px 0' }}>
              No prospects yet — add some from the Prospects tab.
            </div>
          ) : (
            <FunnelChart rows={data.funnel} />
          )}
        </div>

        {/* Live Signals — 40% */}
        <div style={{
          flex: 2,
          background: 'var(--navy-mid)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: '16px 18px',
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--foreground)' }}>
              Live Signals
            </div>
            <button
              onClick={() => onNavigate?.('signals')}
              style={{ fontSize: 11, color: 'var(--cyan)', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              View all →
            </button>
          </div>

          {data.signals.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--muted)', padding: '16px 0' }}>
              No unactioned signals — new signals appear here when detected.
            </div>
          ) : (
            data.signals.map(signal => (
              <SignalCard
                key={signal.id}
                signal={signal}
                onAction={handleSignalAction}
                onDismiss={handleSignalDismiss}
              />
            ))
          )}
        </div>
      </div>

      {/* ── Bottom row: Recent Prospects + Active Sequences ───────────────────── */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>

        {/* Recent prospects — 60% */}
        <div style={{
          flex: 3,
          background: 'var(--navy-mid)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: '16px 18px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--foreground)' }}>
              Recent Activity
            </div>
            <button
              onClick={() => onNavigate?.('prospects')}
              style={{ fontSize: 11, color: 'var(--cyan)', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              View all →
            </button>
          </div>
          {/* Column headers */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingBottom: 6, borderBottom: '1px solid var(--border)', marginBottom: 2 }}>
            <div style={{ width: 30, flexShrink: 0 }} />
            <div style={{ flex: 1, fontSize: 10, color: 'var(--muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Name / Company</div>
            <div style={{ width: 26, flexShrink: 0, fontSize: 10, color: 'var(--muted)', fontWeight: 600, textAlign: 'center' }}>ICP</div>
            <div style={{ width: 60, flexShrink: 0, fontSize: 10, color: 'var(--muted)', fontWeight: 600 }}>Source</div>
            <div style={{ width: 80, flexShrink: 0, fontSize: 10, color: 'var(--muted)', fontWeight: 600 }}>Stage</div>
          </div>
          {data.recent_prospects.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--muted)', padding: '16px 0' }}>No prospect activity yet.</div>
          ) : (
            data.recent_prospects.map(p => (
              <ProspectRow key={p.id} prospect={p} />
            ))
          )}
        </div>

        {/* Active sequences — 40% */}
        <div style={{
          flex: 2,
          background: 'var(--navy-mid)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: '16px 18px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--foreground)' }}>
              Active Sequences
            </div>
            <button
              onClick={() => onNavigate?.('sequences')}
              style={{ fontSize: 11, color: 'var(--cyan)', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              Manage →
            </button>
          </div>
          {data.sequences.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--muted)', padding: '16px 0' }}>
              No active sequences — create one in the Sequences tab.
            </div>
          ) : (
            data.sequences.map(seq => (
              <SequenceRow
                key={seq.id}
                seq={seq}
                onSelect={(id) => onNavigate?.('sequences', { selectedId: id })}
              />
            ))
          )}
        </div>
      </div>

    </div>
  )
}
