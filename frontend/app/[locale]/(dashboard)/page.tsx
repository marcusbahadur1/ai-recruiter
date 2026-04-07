'use client'
import { useTranslations } from 'next-intl'
import { useQuery } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { dashboardApi } from '@/lib/api'

const queryClient = new QueryClient()

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

function DashboardContent() {
  const t = useTranslations('dashboard')

  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => dashboardApi.getStats(),
  })

  const pipeline = stats?.pipeline ?? {}
  const pipelineStages = [
    { key: 'discovered', label: 'Discovered', value: pipeline.discovered ?? 0 },
    { key: 'profiled',   label: 'Profiled',   value: pipeline.profiled   ?? 0 },
    { key: 'scored',     label: 'Scored',      value: pipeline.scored     ?? 0 },
    { key: 'passed',     label: 'Passed',      value: pipeline.passed     ?? 0 },
    { key: 'emailed',    label: 'Emailed',     value: pipeline.emailed    ?? 0 },
    { key: 'applied',    label: 'Applied',     value: pipeline.applied    ?? 0, active: true },
    { key: 'tested',     label: 'Tested',      value: pipeline.tested     ?? 0 },
    { key: 'invited',    label: 'Invited',     value: pipeline.invited    ?? 0 },
  ]

  const recentActivity = stats?.recent_activity ?? []
  const activeJobs = stats?.active_jobs_list ?? []

  return (
    <div style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', padding: '24px' }}>

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
                  <tr key={job.id} onClick={() => window.location.href = `/jobs/${job.id}`} style={{ cursor: 'pointer' }}>
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

export default function DashboardPage() {
  return (
    <QueryClientProvider client={queryClient}>
      <DashboardContent />
    </QueryClientProvider>
  )
}
