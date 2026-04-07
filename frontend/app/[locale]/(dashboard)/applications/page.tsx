'use client'
import { useTranslations } from 'next-intl'
import { useQuery } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from '@/i18n/navigation'
import { applicationsApi } from '@/lib/api'

const queryClient = new QueryClient()

function scorePillClass(score: number | null | undefined): string {
  if (score == null) return 'score-mid'
  if (score >= 8) return 'score-high'
  if (score >= 6) return 'score-mid'
  return 'score-low'
}

function screeningBadgeClass(status: string): string {
  const map: Record<string, string> = {
    passed: 'badge-passed',
    failed: 'badge-failed',
    pending: 'badge-discovered',
  }
  return map[status] ?? 'badge-discovered'
}

function testBadgeClass(status: string): string {
  const map: Record<string, string> = {
    completed: 'badge-passed',
    passed: 'badge-passed',
    failed: 'badge-failed',
    in_progress: 'badge-scout',
    invited: 'badge-emailed',
    not_started: 'badge-discovered',
  }
  return map[status] ?? 'badge-discovered'
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
                <th>{t('screen')}</th>
                <th>{t('test')}</th>
                <th>{t('interview')}</th>
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
                    {a.screening_score != null
                      ? <span className={`score-pill ${scorePillClass(a.screening_score)}`}>{a.screening_score}</span>
                      : <span className={`badge ${screeningBadgeClass(a.screening_status)}`}>{a.screening_status}</span>}
                  </td>
                  <td>
                    {a.test_score != null
                      ? <span className={`score-pill ${scorePillClass(a.test_score)}`}>{a.test_score}</span>
                      : <span className={`badge ${testBadgeClass(a.test_status)}`}>{a.test_status.replace('_', ' ')}</span>}
                  </td>
                  <td>
                    {a.interview_invited
                      ? <span className="badge badge-interviewed">Invited</span>
                      : <span style={{ color: 'var(--muted)', fontSize: 11 }}>—</span>}
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
