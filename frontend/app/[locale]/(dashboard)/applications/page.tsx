'use client'
import { useTranslations } from 'next-intl'
import { useQuery } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { applicationsApi } from '@/lib/api'

const queryClient = new QueryClient()

const STATUS_LABELS: Record<string, string> = {
  received: 'Received',
  screened_passed: 'Screen ✓',
  screened_failed: 'Screen ✗',
  test_invited: 'Test Invited',
  test_passed: 'Test ✓',
  test_failed: 'Test ✗',
  hm_notified: 'HM Notified',
  interview_invited: 'Invited',
  rejected: 'Rejected',
}

const STATUS_BADGE: Record<string, string> = {
  received: 'badge-discovered',
  screened_passed: 'badge-passed',
  screened_failed: 'badge-failed',
  test_invited: 'badge-emailed',
  test_passed: 'badge-passed',
  test_failed: 'badge-failed',
  hm_notified: 'badge-scout',
  interview_invited: 'badge-interviewed',
  rejected: 'badge-failed',
}

function scorePillClass(score: number | null | undefined): string {
  if (score == null) return 'score-mid'
  if (score >= 8) return 'score-high'
  if (score >= 6) return 'score-mid'
  return 'score-low'
}

function ApplicationsContent() {
  const t = useTranslations('applications')
  const [jobFilter, setJobFilter] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['applications', jobFilter],
    queryFn: () => applicationsApi.list(jobFilter ? { job_id: jobFilter } : undefined),
  })

  return (
    <div style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', padding: '24px' }}>
      <div className="section-header">
        <div>
          <div className="section-title">{t('title')}</div>
          <div className="section-sub">{data?.total ?? 0} total applications</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <select
            className="form-select"
            value={jobFilter}
            onChange={(e) => setJobFilter(e.target.value)}
            style={{ width: 180 }}
          >
            <option value="">All Jobs</option>
          </select>
        </div>
      </div>

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t('applicant')}</th>
                <th>{t('email')}</th>
                <th>{t('received')}</th>
                <th>Resume Score</th>
                <th>Test Score</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32, color: 'var(--muted)' }}>Loading...</td></tr>
              )}
              {!isLoading && !data?.items?.length && (
                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32, color: 'var(--muted)' }}>No applications found.</td></tr>
              )}
              {data?.items?.map((a) => (
                <tr key={a.id} onClick={() => window.location.href = `/applications/${a.id}`} style={{ cursor: 'pointer' }}>
                  <td className="td-name">{a.applicant_name}</td>
                  <td className="muted">{a.applicant_email}</td>
                  <td className="muted" style={{ fontSize: 11 }}>
                    {a.received_at ? new Date(a.received_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}
                  </td>
                  <td>
                    {a.resume_score != null
                      ? <span className={`score-pill ${scorePillClass(a.resume_score)}`}>{a.resume_score}</span>
                      : <span style={{ color: 'var(--muted)', fontSize: 11 }}>—</span>}
                  </td>
                  <td>
                    {a.test_score != null
                      ? <span className={`score-pill ${scorePillClass(a.test_score)}`}>{a.test_score}</span>
                      : <span style={{ color: 'var(--muted)', fontSize: 11 }}>—</span>}
                  </td>
                  <td>
                    <span className={`badge ${STATUS_BADGE[a.status] ?? 'badge-discovered'}`}>
                      {STATUS_LABELS[a.status] ?? a.status}
                    </span>
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

export default function ApplicationsPage() {
  return <QueryClientProvider client={queryClient}><ApplicationsContent /></QueryClientProvider>
}
