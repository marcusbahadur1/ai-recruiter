'use client'
import { useTranslations } from 'next-intl'
import { useQuery } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Link } from '@/i18n/navigation'
import { jobsApi } from '@/lib/api'

const queryClient = new QueryClient()

const STATUS_COLORS: Record<string, string> = {
  active: '#10B981',
  draft: '#F59E0B',
  paused: '#94A3B8',
  closed: '#EF4444',
}

function JobsContent() {
  const t = useTranslations('jobs')
  const { data, isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.list(),
  })

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">{t('title')}</h1>
        <Link
          href="/chat"
          className="px-4 py-2 rounded-lg text-sm font-medium text-white flex items-center gap-2"
          style={{ background: 'var(--blue)' }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          {t('newJob')}
        </Link>
      </div>

      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
        <table className="w-full">
          <thead>
            <tr className="border-b" style={{ borderColor: 'var(--navy-border)' }}>
              {['Job Title', 'Ref', t('status'), t('candidates'), t('created'), t('actions')].map((h) => (
                <th key={h} className="text-left px-5 py-3.5 text-xs font-medium text-slate-400 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={6} className="px-5 py-8 text-center text-slate-400 text-sm">Loading jobs...</td></tr>
            )}
            {!isLoading && !data?.items?.length && (
              <tr><td colSpan={6} className="px-5 py-8 text-center text-slate-400 text-sm">No jobs yet. Create your first job in the AI Recruiter chat.</td></tr>
            )}
            {data?.items?.map((job) => (
              <tr key={job.id} className="border-b hover:bg-white/[0.02] transition-colors" style={{ borderColor: 'var(--navy-border)' }}>
                <td className="px-5 py-4">
                  <Link href={`/jobs/${job.id}`} className="text-white font-medium text-sm hover:underline" style={{ textDecorationColor: 'var(--cyan)' }}>
                    {job.title}
                  </Link>
                  <p className="text-slate-500 text-xs mt-0.5">{job.location} · {job.work_type}</p>
                </td>
                <td className="px-5 py-4">
                  <span className="font-mono text-xs text-slate-400">{job.job_ref}</span>
                </td>
                <td className="px-5 py-4">
                  <span
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
                    style={{ background: STATUS_COLORS[job.status] + '20', color: STATUS_COLORS[job.status] }}
                  >
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: STATUS_COLORS[job.status] }}/>
                    {job.status}
                  </span>
                </td>
                <td className="px-5 py-4 text-slate-300 text-sm">{job.candidate_count ?? 0}</td>
                <td className="px-5 py-4 text-slate-400 text-xs">{new Date(job.created_at).toLocaleDateString()}</td>
                <td className="px-5 py-4">
                  <div className="flex items-center gap-2">
                    <Link href={`/jobs/${job.id}`} className="px-3 py-1.5 rounded-md text-xs font-medium text-slate-300 hover:text-white hover:bg-white/5 border transition-colors" style={{ borderColor: 'var(--navy-border)' }}>
                      {t('view')}
                    </Link>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function JobsPage() {
  return <QueryClientProvider client={queryClient}><JobsContent /></QueryClientProvider>
}
