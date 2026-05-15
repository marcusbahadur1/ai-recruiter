'use client'
import React, { useEffect, useRef, useState } from 'react'
import { marketingApi } from '@/lib/api'
import type { ContentPost, ContentPostType, ContentPostStatus, ContentStatsResponse } from '@/lib/api/types'

// ── Constants ──────────────────────────────────────────────────────────────────

const POST_TYPE_META: Record<ContentPostType, { label: string; bg: string; color: string }> = {
  roi_post:   { label: 'ROI post',   bg: '#e6f1fb', color: '#185FA5' },
  pain_post:  { label: 'Pain post',  bg: '#eeedfe', color: '#534AB7' },
  proof_post: { label: 'Proof post', bg: '#eaf3de', color: '#3B6D11' },
  tip_post:   { label: 'Tip',        bg: '#faeeda', color: '#854F0B' },
}

const MIX_COLORS: Record<ContentPostType, string> = {
  roi_post:   '#185FA5',
  pain_post:  '#534AB7',
  proof_post: '#3B6D11',
  tip_post:   '#B45309',
}

const TARGET_MIX: Record<ContentPostType, number> = {
  roi_post: 0.40, pain_post: 0.30, proof_post: 0.20, tip_post: 0.10,
}

type SubTab = 'draft' | 'scheduled' | 'posted' | 'failed'

// ── Icons ─────────────────────────────────────────────────────────────────────

function LinkedInIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/>
      <rect x="2" y="9" width="4" height="12"/>
      <circle cx="4" cy="4" r="2"/>
    </svg>
  )
}

function EyeIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>
  )
}

function HeartIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
    </svg>
  )
}

function ChatIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  )
}

function UserPlusIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
      <circle cx="8.5" cy="7" r="4"/>
      <line x1="20" y1="8" x2="20" y2="14"/>
      <line x1="23" y1="11" x2="17" y2="11"/>
    </svg>
  )
}

function RefreshIcon() {
  return (
    <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10"/>
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
    </svg>
  )
}

function SpinnerIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} style={{ animation: 'spin 1s linear infinite' }}>
      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
      <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
    </svg>
  )
}

function ExternalLinkIcon() {
  return (
    <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
      <polyline points="15 3 21 3 21 9"/>
      <line x1="10" y1="14" x2="21" y2="3"/>
    </svg>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(dt: string | null): string {
  if (!dt) return '—'
  const d = new Date(dt)
  return d.toLocaleString('en-AU', {
    weekday: 'short', day: 'numeric', month: 'short',
    hour: 'numeric', minute: '2-digit', hour12: true,
  })
}

function fmtShort(dt: string | null): string {
  if (!dt) return '—'
  const d = new Date(dt)
  return d.toLocaleString('en-AU', {
    weekday: 'short', day: 'numeric', month: 'short',
    hour: 'numeric', minute: '2-digit', hour12: true,
  })
}

// ── Schedule Popover ──────────────────────────────────────────────────────────

function SchedulePopover({
  onConfirm, onClose,
}: {
  onConfirm: (isoDate: string) => void
  onClose: () => void
}) {
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  tomorrow.setHours(9, 0, 0, 0)
  const defaultVal = tomorrow.toISOString().slice(0, 16)
  const [val, setVal] = useState(defaultVal)

  return (
    <div style={{
      position: 'absolute', zIndex: 100, top: 36, left: 0,
      background: 'var(--navy-mid)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '12px 14px', minWidth: 240, boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>Schedule for</div>
      <input
        type="datetime-local"
        value={val}
        onChange={e => setVal(e.target.value)}
        style={{
          width: '100%', padding: '6px 8px', borderRadius: 6,
          border: '1px solid var(--border)', background: 'var(--navy-deep)',
          color: 'var(--text)', fontSize: 13, marginBottom: 10,
        }}
      />
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={onClose} style={btnStyle('ghost')}>Cancel</button>
        <button
          onClick={() => {
            const d = new Date(val)
            onConfirm(d.toISOString())
          }}
          style={btnStyle('primary')}
        >
          Confirm
        </button>
      </div>
    </div>
  )
}

// ── Post Card ─────────────────────────────────────────────────────────────────

function PostCard({
  post, onRefresh,
}: {
  post: ContentPost
  onRefresh: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editBody, setEditBody] = useState(post.content)
  const [showSchedule, setShowSchedule] = useState(false)
  const [busy, setBusy] = useState(false)
  const meta = POST_TYPE_META[post.post_type as ContentPostType]
  const preview = post.content.length > 200
    ? post.content.slice(0, 200)
    : post.content

  async function doApproveSchedule(isoDate: string) {
    setBusy(true)
    try {
      await marketingApi.updateContent(post.id, { status: 'scheduled', scheduled_at: isoDate })
      onRefresh()
    } finally { setBusy(false); setShowSchedule(false) }
  }

  async function doSaveEdit() {
    setBusy(true)
    try {
      await marketingApi.updateContent(post.id, { content: editBody })
      onRefresh()
      setEditing(false)
    } finally { setBusy(false) }
  }

  async function doRegenerate() {
    setBusy(true)
    try {
      const fresh = await marketingApi.generateContent({ post_type: post.post_type })
      await marketingApi.updateContent(post.id, { content: fresh.content })
      onRefresh()
    } finally { setBusy(false) }
  }

  async function doDiscard() {
    setBusy(true)
    try {
      await marketingApi.discardContent(post.id)
      onRefresh()
    } finally { setBusy(false) }
  }

  async function doUnschedule() {
    setBusy(true)
    try {
      await marketingApi.updateContent(post.id, { status: 'draft' })
      onRefresh()
    } finally { setBusy(false) }
  }

  async function doPostNow() {
    setBusy(true)
    try {
      const now = new Date().toISOString()
      await marketingApi.updateContent(post.id, { scheduled_at: now })
      onRefresh()
    } finally { setBusy(false) }
  }

  async function doRetry() {
    setBusy(true)
    try {
      await marketingApi.updateContent(post.id, { status: 'scheduled' })
      onRefresh()
    } finally { setBusy(false) }
  }

  return (
    <div style={{
      background: 'var(--navy-mid)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '14px 16px', marginBottom: 10,
      opacity: busy ? 0.7 : 1, transition: 'opacity 0.15s',
    }}>
      {/* Row 1 — meta */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span style={{ color: '#0077B5' }}><LinkedInIcon size={16} /></span>
        {meta && (
          <span style={{
            fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 20,
            background: meta.bg, color: meta.color,
          }}>
            {meta.label}
          </span>
        )}
        <span style={{
          fontSize: 11, padding: '2px 8px', borderRadius: 20,
          background: post.status === 'draft' ? '#2d2d3a'
            : post.status === 'scheduled' ? '#1a2e1a'
            : post.status === 'posted' ? '#1a2e1a'
            : '#2e1a1a',
          color: post.status === 'draft' ? 'var(--muted)'
            : post.status === 'scheduled' ? '#4ade80'
            : post.status === 'posted' ? '#86efac'
            : '#f87171',
          fontWeight: 600,
        }}>
          {post.status.charAt(0).toUpperCase() + post.status.slice(1)}
        </span>
        <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 'auto' }}>
          {post.status === 'posted' && post.posted_at
            ? `Posted ${fmt(post.posted_at)}`
            : post.status === 'scheduled' && post.scheduled_at
            ? `Scheduled ${fmt(post.scheduled_at)}`
            : `Created ${fmt(post.created_at)}`}
        </span>
      </div>

      {/* Row 2 — body */}
      {editing ? (
        <div style={{ marginBottom: 10 }}>
          <textarea
            value={editBody}
            onChange={e => setEditBody(e.target.value)}
            rows={8}
            style={{
              width: '100%', padding: '8px 10px', borderRadius: 6,
              border: '1px solid var(--border)', background: 'var(--navy-deep)',
              color: 'var(--text)', fontSize: 13, resize: 'vertical',
              fontFamily: 'inherit',
            }}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
            <button onClick={() => setEditing(false)} style={btnStyle('ghost')}>Cancel</button>
            <button onClick={doSaveEdit} disabled={busy} style={btnStyle('primary')}>
              {busy ? <SpinnerIcon /> : 'Save'}
            </button>
          </div>
        </div>
      ) : (
        <p style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.6, marginBottom: 8, whiteSpace: 'pre-wrap' }}>
          {expanded ? post.content : preview}
          {post.content.length > 200 && (
            <button
              onClick={() => setExpanded(x => !x)}
              style={{ background: 'none', border: 'none', color: 'var(--cyan)', cursor: 'pointer', fontSize: 12, padding: '0 4px' }}
            >
              {expanded ? ' show less' : '…show more'}
            </button>
          )}
        </p>
      )}

      {/* Row 3 — metrics (posted only) */}
      {post.status === 'posted' && (
        <div style={{ display: 'flex', gap: 16, marginBottom: 8, fontSize: 12, color: 'var(--muted)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <EyeIcon /> {post.impressions.toLocaleString()} views
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <HeartIcon /> {post.likes.toLocaleString()} likes
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <ChatIcon /> {post.comments.toLocaleString()} comments
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <UserPlusIcon /> {post.connections_attributed.toLocaleString()} connections
          </span>
        </div>
      )}

      {/* Row 4 — attribution (posted only) */}
      {post.status === 'posted' && (post.connections_attributed > 0 || post.demos_attributed > 0) && (
        <div style={{
          fontSize: 12, color: '#60a5fa', background: 'rgba(59,130,246,0.08)',
          borderRadius: 6, padding: '5px 10px', marginBottom: 10,
        }}>
          Led to {post.connections_attributed} prospect connection{post.connections_attributed !== 1 ? 's' : ''}
          {post.demos_attributed > 0 && ` · ${post.demos_attributed} demo${post.demos_attributed !== 1 ? 's' : ''} booked`}
        </div>
      )}

      {/* Row 5 — actions */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', position: 'relative' }}>
        {post.status === 'draft' && (
          <>
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setShowSchedule(x => !x)}
                disabled={busy}
                style={btnStyle('primary')}
              >
                Approve + schedule
              </button>
              {showSchedule && (
                <SchedulePopover
                  onConfirm={doApproveSchedule}
                  onClose={() => setShowSchedule(false)}
                />
              )}
            </div>
            <button onClick={() => { setEditing(true); setEditBody(post.content) }} style={btnStyle('ghost')}>Edit</button>
            <button onClick={doRegenerate} disabled={busy} style={btnStyle('ghost')}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                {busy ? <SpinnerIcon /> : <RefreshIcon />} Regenerate
              </span>
            </button>
            <button onClick={doDiscard} disabled={busy} style={btnStyle('danger')}>Discard</button>
          </>
        )}
        {post.status === 'scheduled' && (
          <>
            <button onClick={() => { setEditing(true); setEditBody(post.content) }} style={btnStyle('ghost')}>Edit</button>
            <button onClick={doUnschedule} disabled={busy} style={btnStyle('ghost')}>Unschedule</button>
            <button onClick={doPostNow} disabled={busy} style={btnStyle('primary')}>
              {busy ? <SpinnerIcon /> : 'Post now'}
            </button>
          </>
        )}
        {post.status === 'posted' && post.platform_post_id && (
          <a
            href={`https://www.linkedin.com/feed/update/${post.platform_post_id}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{ ...btnStyle('ghost'), textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4 }}
          >
            View on LinkedIn <ExternalLinkIcon />
          </a>
        )}
        {post.status === 'failed' && (
          <>
            <button onClick={doRetry} disabled={busy} style={btnStyle('primary')}>
              {busy ? <SpinnerIcon /> : 'Retry'}
            </button>
            <button onClick={() => { setEditing(true); setEditBody(post.content) }} style={btnStyle('ghost')}>Edit</button>
            <button onClick={doDiscard} disabled={busy} style={btnStyle('danger')}>Discard</button>
          </>
        )}
      </div>
    </div>
  )
}

// ── Right Panel ───────────────────────────────────────────────────────────────

function StatsPanel({ stats }: { stats: ContentStatsResponse | null }) {
  if (!stats) return (
    <div style={{ color: 'var(--muted)', fontSize: 13, padding: 24 }}>Loading stats…</div>
  )

  const mixTypes: ContentPostType[] = ['roi_post', 'pain_post', 'proof_post', 'tip_post']
  const mixTotal = mixTypes.reduce((s, t) => s + (stats.mix[t] ?? 0), 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Card 1 — Performance */}
      <div style={{ background: 'var(--navy-mid)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12 }}>
          Content performance · last 30 days
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <StatRow label="Avg views / post" value={stats.avg_views.toLocaleString('en', { maximumFractionDigits: 0 })} />
          <StatRow label="Avg connections / post" value={stats.avg_connections.toFixed(1)} />
          <StatRow label="Post → demo rate" value={`${(stats.post_demo_rate * 100).toFixed(1)}%`} />
          {stats.best_post_type && (
            <StatRow
              label="Best post type"
              value={POST_TYPE_META[stats.best_post_type]?.label ?? stats.best_post_type}
            />
          )}
        </div>
      </div>

      {/* Card 2 — Content mix */}
      <div style={{ background: 'var(--navy-mid)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12 }}>
          Content mix · last 30 days
        </div>
        {/* Segmented bar */}
        <div style={{ display: 'flex', borderRadius: 6, overflow: 'hidden', height: 12, marginBottom: 10 }}>
          {mixTotal > 0 ? mixTypes.map(t => {
            const pct = (stats.mix[t] ?? 0) / mixTotal * 100
            return (
              <div
                key={t}
                style={{ width: `${pct}%`, background: MIX_COLORS[t], transition: 'width 0.3s' }}
                title={`${POST_TYPE_META[t].label}: ${Math.round(pct)}%`}
              />
            )
          }) : (
            <div style={{ width: '100%', background: 'var(--border)' }} />
          )}
        </div>
        {/* Legend */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {mixTypes.map(t => {
            const pct = mixTotal > 0 ? Math.round((stats.mix[t] ?? 0) / mixTotal * 100) : 0
            return (
              <div key={t} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                <div style={{ width: 10, height: 10, borderRadius: 2, background: MIX_COLORS[t], flexShrink: 0 }} />
                <span style={{ color: 'var(--muted)', flex: 1 }}>{POST_TYPE_META[t].label}</span>
                <span style={{ color: 'var(--text)', fontWeight: 600 }}>{pct}%</span>
              </div>
            )
          })}
        </div>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
          Target: 40% ROI · 30% Pain · 20% Proof · 10% Tip
        </div>
      </div>

      {/* Card 3 — Upcoming schedule */}
      <div style={{ background: 'var(--navy-mid)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12 }}>
          Upcoming schedule
        </div>
        {stats.upcoming.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>No scheduled posts</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {stats.upcoming.map(p => (
              <div key={p.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                <span style={{ color: '#0077B5', marginTop: 1 }}><LinkedInIcon size={13} /></span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.content.slice(0, 50)}{p.content.length > 50 ? '…' : ''}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                    {fmtShort(p.scheduled_at)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ fontSize: 12, color: 'var(--muted)' }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{value}</span>
    </div>
  )
}

// ── Generate Modal ─────────────────────────────────────────────────────────────

function GenerateModal({
  suggestedType,
  onGenerate,
  onClose,
}: {
  suggestedType: ContentPostType
  onGenerate: (postType: ContentPostType, topicHint: string) => Promise<void>
  onClose: () => void
}) {
  const [postType, setPostType] = useState<ContentPostType>(suggestedType)
  const [topicHint, setTopicHint] = useState('')
  const [busy, setBusy] = useState(false)
  const [genError, setGenError] = useState('')
  const types: ContentPostType[] = ['roi_post', 'pain_post', 'proof_post', 'tip_post']

  async function handleSubmit() {
    setBusy(true)
    setGenError('')
    try {
      await onGenerate(postType, topicHint)
      onClose()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setGenError(detail || 'Generation failed — please try again')
    } finally { setBusy(false) }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div
        style={{
          background: 'var(--navy-mid)', borderRadius: 12, padding: 24, width: 420,
          border: '1px solid var(--border)',
        }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', marginBottom: 18 }}>
          Generate post
        </div>

        <div style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 6 }}>Post type</label>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {types.map(t => {
              const m = POST_TYPE_META[t]
              const sel = t === postType
              return (
                <button
                  key={t}
                  onClick={() => setPostType(t)}
                  style={{
                    padding: '5px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                    border: sel ? `2px solid ${m.color}` : '2px solid transparent',
                    background: sel ? m.bg : 'var(--navy-deep)',
                    color: sel ? m.color : 'var(--muted)',
                    transition: 'all 0.15s',
                  }}
                >
                  {m.label}
                </button>
              )
            })}
          </div>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6 }}>
            Pre-selected based on content mix balance
          </div>
        </div>

        <div style={{ marginBottom: 20 }}>
          <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 6 }}>
            Topic hint <span style={{ fontWeight: 400 }}>(optional)</span>
          </label>
          <input
            value={topicHint}
            onChange={e => setTopicHint(e.target.value)}
            placeholder='e.g. "focus on time-to-hire"'
            style={{
              width: '100%', padding: '8px 10px', borderRadius: 6,
              border: '1px solid var(--border)', background: 'var(--navy-deep)',
              color: 'var(--text)', fontSize: 13,
            }}
          />
        </div>

        {genError && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 6, padding: '8px 12px', marginBottom: 14, color: '#ef4444', fontSize: 12 }}>
            {genError}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={btnStyle('ghost')}>Cancel</button>
          <button onClick={handleSubmit} disabled={busy} style={btnStyle('primary')}>
            {busy ? <><SpinnerIcon /> Generating…</> : 'Generate'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Button style helper ───────────────────────────────────────────────────────

function btnStyle(variant: 'primary' | 'ghost' | 'danger'): React.CSSProperties {
  const base: React.CSSProperties = {
    padding: '6px 12px', borderRadius: 6, fontSize: 12, fontWeight: 600,
    cursor: 'pointer', border: 'none', display: 'inline-flex', alignItems: 'center', gap: 4,
    transition: 'opacity 0.15s',
  }
  if (variant === 'primary') return { ...base, background: 'var(--cyan)', color: '#0a0f1e' }
  if (variant === 'danger')  return { ...base, background: '#3b1a1a', color: '#f87171', border: '1px solid #7f1d1d' }
  return { ...base, background: 'var(--navy-deep)', color: 'var(--muted)', border: '1px solid var(--border)' }
}

// ── Pick the underrepresented type for pre-selection ─────────────────────────

function pickSuggestedType(posts: ContentPost[]): ContentPostType {
  const counts: Record<ContentPostType, number> = {
    roi_post: 0, pain_post: 0, proof_post: 0, tip_post: 0,
  }
  posts.forEach(p => {
    if (p.post_type in counts) counts[p.post_type as ContentPostType]++
  })
  const total = Math.max(Object.values(counts).reduce((a, b) => a + b, 0), 1)
  const actuals: Record<ContentPostType, number> = {
    roi_post:   counts.roi_post / total,
    pain_post:  counts.pain_post / total,
    proof_post: counts.proof_post / total,
    tip_post:   counts.tip_post / total,
  }
  const types: ContentPostType[] = ['roi_post', 'pain_post', 'proof_post', 'tip_post']
  return types.reduce((best, t) =>
    (actuals[t] - TARGET_MIX[t]) < (actuals[best] - TARGET_MIX[best]) ? t : best
  , types[0])
}

// ── Main ContentTab ───────────────────────────────────────────────────────────

export default function ContentTab() {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>('draft')
  const [allPosts, setAllPosts] = useState<ContentPost[]>([])
  const [stats, setStats] = useState<ContentStatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [showGenerate, setShowGenerate] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadAll() {
    try {
      const [posts, s] = await Promise.all([
        marketingApi.listContent(),
        marketingApi.getContentStats().catch(() => null),
      ])
      setAllPosts(posts)
      setStats(s)
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status === 403) {
        setError('upgrade')
      } else {
        setError(e instanceof Error ? e.message : String(e))
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadAll() }, [])

  const subTabs: SubTab[] = ['draft', 'scheduled', 'posted', 'failed']
  const byStatus = (s: SubTab) => allPosts.filter(p => p.status === s)

  const visiblePosts = byStatus(activeSubTab)
  const suggestedType = pickSuggestedType(allPosts)

  async function handleGenerate(postType: ContentPostType, topicHint: string) {
    await marketingApi.generateContent({ post_type: postType, topic_hint: topicHint || undefined })
    await loadAll()
    setActiveSubTab('draft')
  }

  return (
    <div style={{ padding: '20px 0' }}>
      {/* Topbar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', margin: 0 }}>Content</h2>
        <button
          onClick={() => setShowGenerate(true)}
          style={{ ...btnStyle('primary'), fontSize: 13, padding: '7px 16px' }}
        >
          + Generate post
        </button>
      </div>

      {error === 'upgrade' ? (
        <div style={{
          background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.25)',
          borderRadius: 10, padding: '32px 24px', textAlign: 'center', marginTop: 16,
        }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>🔒</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', marginBottom: 6 }}>
            Agency Small plan required
          </div>
          <div style={{ fontSize: 13, color: 'var(--muted)' }}>
            Upgrade your plan to generate and schedule LinkedIn content posts.
          </div>
        </div>
      ) : error ? (
        <div style={{ background: '#3b1a1a', color: '#f87171', borderRadius: 8, padding: '10px 14px', fontSize: 13, marginBottom: 16 }}>
          {error}
        </div>
      ) : null}

      {/* Two-column layout */}
      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
        {/* Left — post queue (65%) */}
        <div style={{ flex: '0 0 65%', minWidth: 0 }}>
          {/* Sub-tabs */}
          <div style={{
            display: 'flex', borderBottom: '1px solid var(--border)', marginBottom: 14,
          }}>
            {subTabs.map(tab => {
              const count = byStatus(tab).length
              return (
                <button
                  key={tab}
                  onClick={() => setActiveSubTab(tab)}
                  style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    padding: '8px 14px', fontSize: 13, fontWeight: 500,
                    color: activeSubTab === tab ? 'var(--cyan)' : 'var(--muted)',
                    borderBottom: activeSubTab === tab ? '2px solid var(--cyan)' : '2px solid transparent',
                    marginBottom: -1,
                    transition: 'color 0.15s',
                  }}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                  {count > 0 && (
                    <span style={{
                      marginLeft: 6, fontSize: 11, background: 'var(--border)',
                      borderRadius: 10, padding: '1px 6px', color: 'var(--muted)',
                    }}>
                      {count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Post list */}
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--muted)', fontSize: 13, padding: 16 }}>
              <SpinnerIcon size={16} /> Loading…
            </div>
          ) : visiblePosts.length === 0 ? (
            <div style={{ color: 'var(--muted)', fontSize: 13, padding: '24px 0', textAlign: 'center' }}>
              No {activeSubTab} posts.
              {activeSubTab === 'draft' && (
                <span>
                  {' '}
                  <button
                    onClick={() => setShowGenerate(true)}
                    style={{ background: 'none', border: 'none', color: 'var(--cyan)', cursor: 'pointer', fontSize: 13 }}
                  >
                    Generate one →
                  </button>
                </span>
              )}
            </div>
          ) : (
            visiblePosts.map(post => (
              <PostCard key={post.id} post={post} onRefresh={loadAll} />
            ))
          )}
        </div>

        {/* Right — stats panel (35%) */}
        <div style={{ flex: '0 0 35%', minWidth: 0 }}>
          <StatsPanel stats={stats} />
        </div>
      </div>

      {showGenerate && (
        <GenerateModal
          suggestedType={suggestedType}
          onGenerate={handleGenerate}
          onClose={() => setShowGenerate(false)}
        />
      )}
    </div>
  )
}
