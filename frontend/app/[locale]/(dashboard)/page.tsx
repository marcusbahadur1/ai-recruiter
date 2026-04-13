'use client'
import { useTranslations } from 'next-intl'
import { useState, useEffect } from 'react'
import { useRouter } from '@/i18n/navigation'
import { dashboardApi, tenantApi, candidatesApi, type DashboardStats, type DashboardPipeline, type Candidate } from '@/lib/api'

// ── Kanban stage mapping ─────────────────────────────────────────────────────
// Maps Candidate.status (from the DB enum) to the five Kanban columns.
//
// Candidate.status enum values:
//   discovered | profiled | scored | passed | failed | emailed | applied
//   | tested | interviewed | rejected
//
// Column → status mapping:
//   NEW         → discovered, profiled, scored
//   SCREENED    → passed, emailed, applied          (passed AI scoring, outreach sent/responded)
//   INTERVIEWED → tested, interviewed               (completed competency test or live interview)
//   OFFERED     → (no current status value — column shows empty until schema is extended)
//   HIRED       → (no current status value — column shows empty until schema is extended)
//
// 'failed' and 'rejected' are excluded — they do not belong on the active board.

type KanbanStage = 'new' | 'screened' | 'interviewed' | 'offered' | 'hired'

const STATUS_TO_STAGE: Record<string, KanbanStage> = {
  discovered:  'new',
  profiled:    'new',
  scored:      'new',
  passed:      'screened',
  emailed:     'screened',
  applied:     'screened',
  tested:      'interviewed',
  interviewed: 'interviewed',
}

const KANBAN_COLS: { stage: KanbanStage; label: string; dot: string; tagColor?: string }[] = [
  { stage: 'new',         label: 'NEW',         dot: 'var(--cyan)' },
  { stage: 'screened',    label: 'SCREENED',    dot: 'var(--amber)' },
  { stage: 'interviewed', label: 'INTERVIEWED', dot: '#a78bfa' },
  { stage: 'offered',     label: 'OFFERED',     dot: 'var(--green)' },
  { stage: 'hired',       label: 'HIRED',       dot: '#0EA5A0', tagColor: '#0EA5A0' },
]

// Derive initials from a full name (e.g. "Sarah Chen" → "SC")
function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

// Derive a consistent avatar colour from candidate id (no randomness on re-render)
const AVATAR_COLORS = ['#00C2E0', '#22C55E', '#F59E0B', '#8b5cf6', '#0EA5A0', '#1B6CA8', '#EF4444', '#E8B84B']
function avatarColor(id: string): string {
  let hash = 0
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) & 0xffff
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

function scoreClass(score: number): string {
  if (score >= 8) return 'score-high'
  if (score >= 6) return 'score-mid'
  return 'score-low'
}

function KanbanBoard({ jobs }: { jobs: { id: string; title: string }[] }) {
  const [selectedJob, setSelectedJob] = useState('all')
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const params: Parameters<typeof candidatesApi.list>[0] = { limit: 200 }
    if (selectedJob !== 'all') params.job_id = selectedJob
    candidatesApi.list(params)
      .then(res => setCandidates(res.items))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [selectedJob])

  // Only show candidates whose status maps to a Kanban stage (exclude failed/rejected)
  const mapped = candidates.filter(c => STATUS_TO_STAGE[c.status])

  return (
    <div className="card" style={{ padding: 0, marginBottom: 20 }}>
      {/* Header */}
      <div className="card-header" style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
        <div>
          <div className="card-title">Candidate Pipeline</div>
          <div className="card-sub">Live view of all candidates across pipeline stages</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <select
            value={selectedJob}
            onChange={e => setSelectedJob(e.target.value)}
            className="form-select"
            style={{ fontSize: 12, padding: '5px 10px', height: 32 }}
          >
            <option value="all">All Jobs</option>
            {jobs.map(j => <option key={j.id} value={j.id}>{j.title}</option>)}
          </select>
          <a href="/candidates" className="btn btn-ghost btn-sm">View all →</a>
        </div>
      </div>

      {/* Board */}
      <div style={{ overflowX: 'auto', padding: '16px 20px' }}>
        {loading ? (
          <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
            Loading candidates…
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 12, minWidth: 'max-content' }}>
            {KANBAN_COLS.map(col => {
              const cards = mapped.filter(c => STATUS_TO_STAGE[c.status] === col.stage)
              return (
                <div key={col.stage} style={{ width: 192, flexShrink: 0 }}>
                  {/* Column header */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, letterSpacing: '.6px', color: 'var(--muted)' }}>
                      <div style={{ width: 7, height: 7, borderRadius: '50%', background: col.dot, flexShrink: 0 }} />
                      {col.label}
                    </div>
                    <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--muted)', background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border)', borderRadius: 10, padding: '1px 7px' }}>
                      {cards.length}
                    </div>
                  </div>

                  {/* Cards */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {cards.length === 0 && (
                      <div style={{ fontSize: 12, color: 'var(--muted)', textAlign: 'center', padding: '12px 0', opacity: 0.6 }}>
                        No candidates
                      </div>
                    )}
                    {cards.map(c => {
                      // Use job_title from candidate record if present, else look up from jobs list
                      const jobTitle = c.job_title ?? jobs.find(j => j.id === c.job_id)?.title ?? '—'
                      const score = c.suitability_score
                      return (
                        <a
                          key={c.id}
                          href={`/candidates/${c.id}`}
                          style={{
                            display: 'block', textDecoration: 'none',
                            background: 'rgba(30,51,80,0.7)', border: '1px solid var(--border-mid)',
                            borderRadius: 10, padding: '11px 12px',
                            cursor: 'pointer', transition: 'border-color .15s',
                          }}
                          onMouseEnter={e => (e.currentTarget.style.borderColor = col.dot)}
                          onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border-mid)')}
                        >
                          {/* Candidate professional title (their own role) */}
                          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--white)', marginBottom: 2 }}>{c.name}</div>
                          <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {c.title || jobTitle}
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <div style={{ width: 26, height: 26, borderRadius: '50%', background: avatarColor(c.id), display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: '#0D1B2A', flexShrink: 0 }}>
                              {initials(c.name)}
                            </div>
                            {score !== null && score !== undefined ? (
                              <span className={`score-pill ${scoreClass(score)}`}>{score}/10</span>
                            ) : (
                              <span style={{ fontSize: 10, color: 'var(--muted)' }}>No score</span>
                            )}
                          </div>
                        </a>
                      )
                    })}

                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

const SEV_DOT: Record<string, string> = {
  success: 'success', error: 'error', warning: 'warning', info: 'info',
}
const SEV_CHAR: Record<string, string> = {
  success: '✓', error: '✕', warning: '!', info: 'i',
}
const CAT_CLASS: Record<string, string> = {
  talent_scout: 'badge-scout', resume_screener: 'badge-screener',
  payment: 'badge-payment', system: 'badge-system',
}

function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    active: 'badge-active', paused: 'badge-paused', closed: 'badge-closed', draft: 'badge-draft',
  }
  return map[status] ?? 'badge-draft'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    active: '● Active', paused: '⏸ Paused', closed: '✕ Closed', draft: 'Draft',
  }
  return map[status] ?? status
}

export default function DashboardPage() {
  const t = useTranslations('dashboard')
  const router = useRouter()

  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [quickStartDone, setQuickStartDone] = useState<boolean | null>(null)
  const [quickStartCompleted, setQuickStartCompleted] = useState(0)
  const [quickStartTotal, setQuickStartTotal] = useState(0)

  useEffect(() => {
    dashboardApi.getStats().then(setStats).catch(console.error).finally(() => setIsLoading(false))
    tenantApi.getQuickStartStatus().then(s => {
      setQuickStartDone(s.all_done)
      setQuickStartCompleted(s.completed_count)
      setQuickStartTotal(s.total_count)
    }).catch(() => setQuickStartDone(true))
  }, [])

  const pipeline: DashboardPipeline = stats?.pipeline ?? {
    discovered: 0, profiled: 0, scored: 0, passed: 0,
    emailed: 0, applied: 0, tested: 0, invited: 0,
  }
  const pipelineStages = [
    { key: 'discovered', label: 'Discovered', value: pipeline.discovered },
    { key: 'profiled',   label: 'Profiled',   value: pipeline.profiled   },
    { key: 'scored',     label: 'Scored',      value: pipeline.scored     },
    { key: 'passed',     label: 'Passed',      value: pipeline.passed     },
    { key: 'emailed',    label: 'Emailed',     value: pipeline.emailed    },
    { key: 'applied',    label: 'Applied',     value: pipeline.applied,    active: true },
    { key: 'tested',     label: 'Tested',      value: pipeline.tested     },
    { key: 'invited',    label: 'Invited',     value: pipeline.invited    },
  ]

  const recentActivity = stats?.recent_activity ?? []
  const activeJobs = stats?.active_jobs_list ?? []

  return (
    <div style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', padding: '24px' }}>

      {/* Quick Start banner */}
      {quickStartDone === false && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: 'rgba(27,108,168,0.12)', border: '1px solid var(--blue)',
          borderRadius: 10, padding: '12px 18px', marginBottom: 20, gap: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ fontSize: 18 }}>🚀</div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--white)' }}>
                Setup in progress — {quickStartCompleted}/{quickStartTotal} steps complete
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                Finish configuring your AI Recruiter to get the most out of it.
              </div>
            </div>
          </div>
          <button className="btn btn-primary btn-sm" style={{ flexShrink: 0 }}
            onClick={() => router.push('/quickstart')}>
            Continue Setup →
          </button>
        </div>
      )}

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16, marginBottom: 24 }}>
        <div className="stat-card">
          <div className="stat-label">{t('activeJobs')}</div>
          <div className="stat-value">{isLoading ? '—' : (stats?.active_jobs ?? 0)}</div>
          <div className="stat-icon">💼</div>
        </div>
        <div className="stat-card green">
          <div className="stat-label">{t('candidatesToday')}</div>
          <div className="stat-value">{isLoading ? '—' : (stats?.candidates_today ?? 0)}</div>
          <div className="stat-icon">👥</div>
        </div>
        <div className="stat-card gold">
          <div className="stat-label">{t('applications')}</div>
          <div className="stat-value">{isLoading ? '—' : (stats?.applications ?? 0)}</div>
          <div className="stat-icon">📄</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">{t('creditsRemaining')}</div>
          <div className="stat-value">{isLoading ? '—' : (stats?.credits_remaining ?? 0)}</div>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6 }}>Credits available</div>
        </div>
      </div>

      {/* Kanban pipeline board */}
      <KanbanBoard jobs={activeJobs.map(j => ({ id: j.id, title: j.title }))} />

      {/* 2-col grid */}
      <div className="grid-2" style={{ marginBottom: 20 }}>
        {/* Active Jobs table */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Active Jobs</div>
              <div className="card-sub">Click a job to view detail</div>
            </div>
            <a href="/jobs" className="btn btn-ghost btn-sm">View all</a>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Job</th><th>Candidates</th><th>Status</th></tr>
              </thead>
              <tbody>
                {isLoading && (
                  <tr><td colSpan={3} style={{ textAlign: 'center', padding: '24px', color: 'var(--muted)' }}>Loading...</td></tr>
                )}
                {!isLoading && activeJobs.length === 0 && (
                  <tr><td colSpan={3} style={{ textAlign: 'center', padding: '24px', color: 'var(--muted)' }}>
                    No active jobs yet — <a href="/chat" style={{ color: 'var(--cyan)' }}>post your first job</a>
                  </td></tr>
                )}
                {activeJobs.map((job) => (
                  <tr key={job.id} onClick={() => router.push(`/jobs/${job.id}`)} style={{ cursor: 'pointer' }}>
                    <td className="td-name">{job.title}</td>
                    <td>{job.candidate_count ?? 0}</td>
                    <td><span className={`badge ${statusBadgeClass(job.status)}`}>{statusLabel(job.status)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Recent Activity</div>
              <div className="card-sub">Live audit events</div>
            </div>
            <div className="live-badge"><div className="live-dot"/>Live</div>
          </div>
          <div className="audit-feed">
            {isLoading && (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>Loading...</div>
            )}
            {!isLoading && recentActivity.length === 0 && (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
                No activity yet. Activity will appear here once jobs are active.
              </div>
            )}
            {recentActivity.slice(0, 6).map((ev, i) => (
              <div key={i} className="audit-event">
                <div className={`audit-dot ${SEV_DOT[ev.severity] ?? 'info'}`}>{SEV_CHAR[ev.severity] ?? 'i'}</div>
                <div className="audit-content">
                  <div className="audit-summary">{ev.summary}</div>
                  <div className="audit-meta">
                    <span className={`badge ${CAT_CLASS[ev.event_category] ?? 'badge-system'}`} style={{ fontSize: 9, padding: '1px 6px' }}>
                      {ev.event_category === 'talent_scout' ? 'Scout'
                        : ev.event_category === 'resume_screener' ? 'Screener'
                        : ev.event_category}
                    </span>
                    <span className="audit-time">{new Date(ev.created_at).toLocaleTimeString()}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Pipeline funnel */}
      <div className="card">
        <div className="card-header">
          <div><div className="card-title">Candidate Pipeline</div></div>
        </div>
        <div style={{ display: 'flex', gap: 0 }}>
          {pipelineStages.map((stage, i) => {
            const totalInPipeline = pipelineStages.reduce((sum, s) => sum + s.value, 0)
            const allDone = totalInPipeline > 0 && i < 5 && stage.value > 0
            const isActiveStage = stage.active
            return (
              <div
                key={stage.key}
                className={`pipe-step${allDone ? ' done' : isActiveStage && stage.value > 0 ? ' active' : ''}`}
              >
                <div className="pipe-num" style={!allDone && !(isActiveStage && stage.value > 0) ? { color: 'var(--muted)' } : undefined}>
                  {isLoading ? '—' : stage.value}
                </div>
                <div className="pipe-label">{stage.label}</div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
