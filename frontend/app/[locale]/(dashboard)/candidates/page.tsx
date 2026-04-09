'use client'
import { useTranslations } from 'next-intl'
import { useQuery } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { Link } from '@/i18n/navigation'
import { candidatesApi } from '@/lib/api'

const queryClient = new QueryClient()

function scorePillClass(score: number | null | undefined): string {
  if (score == null) return 'score-mid'
  if (score >= 8) return 'score-high'
  if (score >= 6) return 'score-mid'
  return 'score-low'
}
function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    discovered: 'badge-discovered', profiled: 'badge-profiled', scored: 'badge-profiled',
    passed: 'badge-passed', failed: 'badge-failed', emailed: 'badge-emailed',
    applied: 'badge-scout', tested: 'badge-info', interviewed: 'badge-interviewed',
  }
  return map[status] ?? 'badge-discovered'
}

const SCORE_RANGES: Record<string, { min?: number; max?: number }> = {
  '': {},
  '8-10': { min: 8, max: 10 },
  '6-7': { min: 6, max: 7 },
  'below-6': { max: 5 },
}

function CandidatesContent() {
  const t = useTranslations('candidates')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [scoreFilter, setScoreFilter] = useState('')

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  const scoreRange = SCORE_RANGES[scoreFilter] ?? {}

  const { data, isLoading } = useQuery({
    queryKey: ['candidates', debouncedSearch, statusFilter, scoreFilter],
    queryFn: () => candidatesApi.list({
      search: debouncedSearch || undefined,
      status: statusFilter || undefined,
      min_score: scoreRange.min,
      max_score: scoreRange.max,
    }),
  })

  return (
    <div style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', padding: '24px' }}>
      <div className="section-header">
        <div>
          <div className="section-title">{t('title')}</div>
          <div className="section-sub">{data?.total ?? 0} total across all jobs</div>
        </div>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <input
            className="form-input"
            placeholder={t('search')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ flex: 1, minWidth: 200 }}
          />
          <select
            className="form-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ width: 160 }}
          >
            <option value="">All Statuses</option>
            <option value="passed">Passed</option>
            <option value="emailed">Emailed</option>
            <option value="applied">Applied</option>
            <option value="failed">Failed</option>
          </select>
          <select
            className="form-select"
            value={scoreFilter}
            onChange={(e) => setScoreFilter(e.target.value)}
            style={{ width: 130 }}
          >
            <option value="">Any Score</option>
            <option value="8-10">8–10</option>
            <option value="6-7">6–7</option>
            <option value="below-6">Below 6</option>
          </select>
        </div>
      </div>

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t('name')}</th>
                <th>Current Title</th>
                <th>Company</th>
                <th>{t('location')}</th>
                <th>Job</th>
                <th>{t('score')}</th>
                <th>{t('status')}</th>
                <th>Email Source</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: 'var(--muted)' }}>Loading...</td></tr>
              )}
              {!isLoading && !data?.items?.length && (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: 'var(--muted)' }}>No candidates found.</td></tr>
              )}
              {data?.items?.map((c) => (
                <tr key={c.id} onClick={() => window.location.href = `/candidates/${c.id}`}>
                  <td className="td-name">{c.name}</td>
                  <td className="muted">{c.title}</td>
                  <td className="muted">{(c as { company?: string }).company ?? '—'}</td>
                  <td className="muted">{c.location}</td>
                  <td className="muted">{c.job_title ?? '—'}</td>
                  <td>
                    {c.suitability_score != null
                      ? <span className={`score-pill ${scorePillClass(c.suitability_score)}`}>{c.suitability_score}</span>
                      : <span style={{ color: 'var(--muted)' }}>—</span>}
                  </td>
                  <td><span className={`badge ${statusBadgeClass(c.status)}`}>{c.status}</span></td>
                  <td style={{ fontSize: 11, color: 'var(--muted)' }}>
                    {(c as { email_source?: string }).email_source ?? '—'}
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

export default function CandidatesPage() {
  return <QueryClientProvider client={queryClient}><CandidatesContent /></QueryClientProvider>
}
