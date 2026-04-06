'use client'
import { useTranslations } from 'next-intl'
import { useQuery } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from '@/i18n/navigation'
import { candidatesApi } from '@/lib/api'

const queryClient = new QueryClient()

const STATUS_COLORS: Record<string, string> = {
  discovered: '#94A3B8', profiled: '#3B82F6', scored: '#8B5CF6',
  passed: '#10B981', failed: '#EF4444', emailed: '#00C2E0',
  applied: '#F59E0B', tested: '#F97316', interviewed: '#6366F1', rejected: '#DC2626',
}

function CandidatesContent() {
  const t = useTranslations('candidates')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['candidates', search, statusFilter],
    queryFn: () => candidatesApi.list({ search, status: statusFilter }),
  })

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">{t('title')}</h1>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <div className="relative flex-1 max-w-xs">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          <input
            type="text"
            placeholder={t('search')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border outline-none text-slate-300 placeholder-slate-500 focus:border-cyan-500 transition-colors"
            style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 text-sm rounded-lg border text-slate-300 outline-none cursor-pointer"
          style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}
        >
          <option value="">All Statuses</option>
          {Object.keys(STATUS_COLORS).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
        <table className="w-full">
          <thead>
            <tr className="border-b" style={{ borderColor: 'var(--navy-border)' }}>
              {[t('name'), t('title_col'), t('location'), t('score'), t('status'), t('job'), ''].map((h, i) => (
                <th key={i} className="text-left px-5 py-3.5 text-xs font-medium text-slate-400 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={7} className="px-5 py-8 text-center text-slate-400 text-sm">Loading...</td></tr>
            )}
            {!isLoading && !data?.items?.length && (
              <tr><td colSpan={7} className="px-5 py-8 text-center text-slate-400 text-sm">No candidates found.</td></tr>
            )}
            {data?.items?.map((c) => (
              <tr key={c.id} className="border-b hover:bg-white/[0.02] transition-colors" style={{ borderColor: 'var(--navy-border)' }}>
                <td className="px-5 py-4">
                  <Link href={`/candidates/${c.id}`} className="text-white font-medium text-sm hover:underline">{c.name}</Link>
                  {c.email && <p className="text-slate-500 text-xs mt-0.5">{c.email}</p>}
                </td>
                <td className="px-5 py-4 text-slate-300 text-sm">{c.title}</td>
                <td className="px-5 py-4 text-slate-400 text-sm">{c.location}</td>
                <td className="px-5 py-4">
                  {c.suitability_score != null ? (
                    <span className="inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold"
                      style={{ background: c.suitability_score >= 7 ? '#10B98120' : '#EF444420',
                               color: c.suitability_score >= 7 ? '#10B981' : '#EF4444' }}>
                      {c.suitability_score}
                    </span>
                  ) : <span className="text-slate-500 text-sm">—</span>}
                </td>
                <td className="px-5 py-4">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
                    style={{ background: (STATUS_COLORS[c.status] ?? '#94A3B8') + '20', color: STATUS_COLORS[c.status] ?? '#94A3B8' }}>
                    {c.status}
                  </span>
                </td>
                <td className="px-5 py-4 text-slate-400 text-xs">{c.job_title ?? '—'}</td>
                <td className="px-5 py-4">
                  <Link href={`/candidates/${c.id}`} className="text-xs text-slate-400 hover:text-white transition-colors">View →</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function CandidatesPage() {
  return <QueryClientProvider client={queryClient}><CandidatesContent /></QueryClientProvider>
}
