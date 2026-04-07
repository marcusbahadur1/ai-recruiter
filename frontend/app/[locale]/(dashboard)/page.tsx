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

function scorePillClass(score: number | null | undefined): string {
  if (score == null) return ''
  if (score >= 8) return 'score-high'
  if (score >= 6) return 'score-mid'
  return 'score-low'
}

function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    active: 'badge-active', paused: 'badge-paused', closed: 'badge-closed',
    draft: 'badge-draft', passed: 'badge-passed', failed: 'badge-failed',
    emailed: 'badge-emailed',
  }
  return map[status] ?? 'badge-discovered'
}

function DashboardContent() {
  const t = useTranslations('dashboard')

  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => dashboardApi.getStats(),
  })

  const pipeline = stats?.pipeline ?? {}
  const pipelineStages = [
    { key: 'discovered', label: 'Discovered', value: pipeline.discovered ?? 284 },
    { key: 'profiled',   label: 'Profiled',   value: pipeline.profiled   ?? 241 },
    { key: 'scored',     label: 'Scored',      value: pipeline.scored     ?? 198 },
    { key: 'passed',     label: 'Passed',      value: pipeline.passed     ?? 143 },
    { key: 'emailed',    label: 'Emailed',     value: pipeline.emailed    ?? 128 },
    { key: 'applied',    label: 'Applied',     value: pipeline.applied    ?? 63, active: true },
    { key: 'tested',     label: 'Tested',      value: pipeline.tested     ?? 31 },
    { key: 'invited',    label: 'Invited',     value: pipeline.invited    ?? 12 },
  ]

  const recentActivity = stats?.recent_activity ?? []

  return (
    <div style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', padding: '24px' }}>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16, marginBottom: 24 }}>
        <div className="stat-card">
          <div className="stat-label">{t('activeJobs')}</div>
          <div className="stat-value">{stats?.active_jobs ?? 7}</div>
          <div className="stat-change up">↑ 2 this week</div>
          <div className="stat-icon">💼</div>
        </div>
        <div className="stat-card green">
          <div className="stat-label">{t('candidatesToday')}</div>
          <div className="stat-value">{stats?.candidates_today ?? 284}</div>
          <div className="stat-change up">↑ 47 today</div>
          <div className="stat-icon">👥</div>
        </div>
        <div className="stat-card gold">
          <div className="stat-label">{t('applications')}</div>
          <div className="stat-value">{stats?.applications ?? 63}</div>
          <div className="stat-change up">↑ 8 today</div>
          <div className="stat-icon">📄</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">{t('creditsRemaining')}</div>
          <div className="stat-value">{stats?.credits_remaining ?? 186}</div>
          <div className="progress-bar" style={{ marginTop: 10 }}><div className="progress-fill" style={{ width: '62%' }}/></div>
          <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4 }}>186 / 300 monthly</div>
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
                <tr><th>Job</th><th>Candidates</th><th>Applications</th><th>Status</th></tr>
              </thead>
              <tbody>
                <tr><td className="td-name">Java Developer</td><td>47 <span style={{ color: 'var(--muted)', fontSize: 11 }}>/ 31 passed</span></td><td>12</td><td><span className="badge badge-active">● Active</span></td></tr>
                <tr><td className="td-name">Senior Accountant</td><td>38 <span style={{ color: 'var(--muted)', fontSize: 11 }}>/ 22 passed</span></td><td>9</td><td><span className="badge badge-active">● Active</span></td></tr>
                <tr><td className="td-name">UX Designer</td><td>61 <span style={{ color: 'var(--muted)', fontSize: 11 }}>/ 41 passed</span></td><td>17</td><td><span className="badge badge-active">● Active</span></td></tr>
                <tr><td className="td-name">DevOps Engineer</td><td>22 <span style={{ color: 'var(--muted)', fontSize: 11 }}>/ 14 passed</span></td><td>5</td><td><span className="badge badge-paused">⏸ Paused</span></td></tr>
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
            {recentActivity.length > 0 ? recentActivity.slice(0, 6).map((ev: { severity: string; event_category: string; summary: string; created_at: string }, i: number) => (
              <div key={i} className="audit-event">
                <div className={`audit-dot ${SEV_DOT[ev.severity] ?? 'info'}`}>{SEV_CHAR[ev.severity] ?? 'i'}</div>
                <div className="audit-content">
                  <div className="audit-summary">{ev.summary}</div>
                  <div className="audit-meta">
                    <span className={`badge ${CAT_CLASS[ev.event_category] ?? 'badge-system'}`} style={{ fontSize: 9, padding: '1px 6px' }}>
                      {ev.event_category === 'talent_scout' ? 'Scout' : ev.event_category === 'resume_screener' ? 'Screener' : ev.event_category}
                    </span>
                    <span className="audit-time">{new Date(ev.created_at).toLocaleTimeString()}</span>
                  </div>
                </div>
              </div>
            )) : (
              /* Fallback mock data matching mockup */
              <>
                <div className="audit-event">
                  <div className="audit-dot success">✓</div>
                  <div className="audit-content">
                    <div className="audit-summary">Outreach email sent to <span style={{ color: 'var(--cyan)' }}>Divesh Premdeep</span></div>
                    <div className="audit-meta"><span className="badge badge-scout" style={{ fontSize: 9, padding: '1px 6px' }}>Scout</span><span className="audit-time">2 min ago</span></div>
                  </div>
                </div>
                <div className="audit-event">
                  <div className="audit-dot success">✓</div>
                  <div className="audit-content">
                    <div className="audit-summary">John Smith scored 8/10 — passed screening</div>
                    <div className="audit-meta"><span className="badge badge-screener" style={{ fontSize: 9, padding: '1px 6px' }}>Screener</span><span className="audit-time">5 min ago</span></div>
                  </div>
                </div>
                <div className="audit-event">
                  <div className="audit-dot info">i</div>
                  <div className="audit-content">
                    <div className="audit-summary">BrightData profile received — Meng Zhou</div>
                    <div className="audit-meta"><span className="badge badge-scout" style={{ fontSize: 9, padding: '1px 6px' }}>Scout</span><span className="audit-time">8 min ago</span></div>
                  </div>
                </div>
                <div className="audit-event">
                  <div className="audit-dot warning">!</div>
                  <div className="audit-content">
                    <div className="audit-summary">No email found for Rebecca Chan — flagged</div>
                    <div className="audit-meta"><span className="badge badge-scout" style={{ fontSize: 9, padding: '1px 6px' }}>Scout</span><span className="audit-time">12 min ago</span></div>
                  </div>
                </div>
                <div className="audit-event">
                  <div className="audit-dot success">✓</div>
                  <div className="audit-content">
                    <div className="audit-summary">Linda Chen completed competency test — 7/10</div>
                    <div className="audit-meta"><span className="badge badge-screener" style={{ fontSize: 9, padding: '1px 6px' }}>Screener</span><span className="audit-time">18 min ago</span></div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Pipeline funnel */}
      <div className="card">
        <div className="card-header">
          <div><div className="card-title">Candidate Pipeline — This Week</div></div>
        </div>
        <div style={{ display: 'flex', gap: 0 }}>
          {pipelineStages.map((stage, i) => {
            const allDone = i < 5
            const isActiveStage = i === 5
            return (
              <div
                key={stage.key}
                className={`pipe-step${allDone ? ' done' : isActiveStage ? ' active' : ''}`}
              >
                <div className="pipe-num" style={!allDone && !isActiveStage ? { color: 'var(--muted)' } : undefined}>
                  {stage.value}
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
