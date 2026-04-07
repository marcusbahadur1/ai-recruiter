'use client'
import { useTranslations } from 'next-intl'
import { useQuery } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Link } from '@/i18n/navigation'
import { jobsApi } from '@/lib/api'

const queryClient = new QueryClient()

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
function scorePillClass(score: number | null | undefined): string {
  if (score == null) return 'score-mid'
  if (score >= 8) return 'score-high'
  if (score >= 6) return 'score-mid'
  return 'score-low'
}

function JobsContent() {
  const t = useTranslations('jobs')
  const { data, isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.list(),
  })

  return (
    <div style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', padding: '24px' }}>
      <div className="section-header">
        <div>
          <div className="section-title">{t('title')}</div>
          <div className="section-sub">{data?.total ?? 0} active jobs across all pipelines</div>
        </div>
        <Link href="/chat" className="btn btn-cyan">+ Post New Job</Link>
      </div>

      <div className="card">
        {/* Filter bar */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          <button className="btn btn-ghost btn-sm" style={{ background: 'var(--cyan-dim)', color: 'var(--cyan)', borderColor: 'transparent' }}>All</button>
          <button className="btn btn-ghost btn-sm">Active</button>
          <button className="btn btn-ghost btn-sm">Paused</button>
          <button className="btn btn-ghost btn-sm">Closed</button>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Job Title</th>
                <th>Ref</th>
                <th>Location</th>
                <th>Candidates</th>
                <th>Apps</th>
                <th>Score Min</th>
                <th>{t('status')}</th>
                <th>{t('created')}</th>
                <th>{t('actions')}</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={9} style={{ textAlign: 'center', padding: '32px', color: 'var(--muted)' }}>Loading jobs...</td></tr>
              )}
              {!isLoading && !data?.items?.length && (
                <tr><td colSpan={9} style={{ textAlign: 'center', padding: '32px', color: 'var(--muted)' }}>No jobs yet. Create your first job in the AI Recruiter chat.</td></tr>
              )}
              {data?.items?.map((job) => (
                <tr key={job.id} onClick={() => window.location.href = `/jobs/${job.id}`}>
                  <td className="td-name">{job.title}</td>
                  <td style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--muted)' }}>{job.job_ref}</td>
                  <td className="muted">{job.location}</td>
                  <td>
                    {job.candidate_count ?? 0}
                    {(job as { passed_count?: number }).passed_count != null && (
                      <span style={{ color: 'var(--green)', fontSize: 11 }}> {(job as { passed_count?: number }).passed_count}✓</span>
                    )}
                  </td>
                  <td>{(job as { application_count?: number }).application_count ?? '—'}</td>
                  <td>
                    <span className={`score-pill ${scorePillClass(job.minimum_score)}`} style={{ width: 'auto', padding: '2px 8px' }}>
                      {job.minimum_score ?? '—'}
                    </span>
                  </td>
                  <td><span className={`badge ${statusBadgeClass(job.status)}`}>{statusLabel(job.status)}</span></td>
                  <td className="muted">{new Date(job.created_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <Link href={`/jobs/${job.id}`} className="btn btn-ghost btn-sm">{t('view')}</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default function JobsPage() {
  return <QueryClientProvider client={queryClient}><JobsContent /></QueryClientProvider>
}
