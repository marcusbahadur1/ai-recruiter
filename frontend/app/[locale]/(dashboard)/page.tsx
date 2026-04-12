'use client'
import { useTranslations } from 'next-intl'
import { useState, useEffect } from 'react'
import { useRouter } from '@/i18n/navigation'
import { dashboardApi, tenantApi, type DashboardStats, type DashboardPipeline } from '@/lib/api'

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
