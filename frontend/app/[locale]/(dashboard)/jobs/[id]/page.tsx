'use client'
import { useTranslations } from 'next-intl'
import { useQuery } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { use, useState } from 'react'
import { useAuditStream } from '@/hooks/useAuditStream'
import { jobsApi, auditApi } from '@/lib/api'

const queryClient = new QueryClient()

const SEV_COLORS: Record<string, string> = {
  success: '#10B981', error: '#EF4444', warning: '#F59E0B', info: '#1B6CA8',
}
const CAT_COLORS: Record<string, string> = {
  talent_scout: '#8B5CF6', resume_screener: '#00C2E0', payment: '#F59E0B', system: '#94A3B8',
}

function JobDetailContent({ id }: { id: string }) {
  const t = useTranslations('jobs')
  const [tab, setTab] = useState<'report' | 'audit' | 'spec'>('report')
  const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set())

  const { data: job, isLoading } = useQuery({
    queryKey: ['job', id],
    queryFn: () => jobsApi.get(id),
  })

  const { data: auditData } = useQuery({
    queryKey: ['audit-events', id],
    queryFn: () => auditApi.getEvents(id),
    enabled: tab === 'audit',
  })

  const { events: streamEvents } = useAuditStream(id)

  const candidates = job?.candidates ?? []
  const auditEvents = [...(auditData?.items ?? []), ...streamEvents]

  const toggleExpand = (eventId: string) => {
    setExpandedEvents((prev) => {
      const next = new Set(prev)
      next.has(eventId) ? next.delete(eventId) : next.add(eventId)
      return next
    })
  }

  if (isLoading) {
    return <div className="flex justify-center py-16"><div className="w-6 h-6 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: 'var(--cyan)', borderTopColor: 'transparent' }}/></div>
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
            <a href="/jobs" className="hover:text-white transition-colors">Jobs</a>
            <span>/</span>
            <span className="text-white">{job?.title}</span>
          </div>
          <h1 className="text-2xl font-bold text-white">{job?.title}</h1>
          <p className="text-slate-400 text-sm mt-0.5">{job?.location} · {job?.work_type} · <span className="font-mono">{job?.job_ref}</span></p>
        </div>
        <button
          className="px-4 py-2 rounded-lg text-sm font-medium text-white"
          style={{ background: 'var(--blue)' }}
        >
          {t('triggerScout')}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b" style={{ borderColor: 'var(--navy-border)' }}>
        {(['report', 'audit', 'spec'] as const).map((tabKey) => (
          <button
            key={tabKey}
            onClick={() => setTab(tabKey)}
            className="px-5 py-3 text-sm font-medium border-b-2 transition-colors"
            style={{
              borderColor: tab === tabKey ? 'var(--cyan)' : 'transparent',
              color: tab === tabKey ? 'var(--cyan)' : '#94A3B8',
            }}
          >
            {tabKey === 'report' ? t('evaluationReport') : tabKey === 'audit' ? t('auditTrail') : t('jobSpec')}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'report' && (
        <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          <div className="px-4 py-3 border-b flex items-center gap-2" style={{ borderColor: 'var(--navy-border)' }}>
            <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: 'var(--cyan)' }}/>
            <span className="text-xs text-slate-400">Live — receiving updates via SSE</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b" style={{ borderColor: 'var(--navy-border)' }}>
                  {['Name', 'Title', 'Location', 'Score', 'Status', 'Email', 'LinkedIn', 'Actions'].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-400 uppercase tracking-wide whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {candidates.length === 0 && (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-500 text-sm">No candidates yet. Trigger the Talent Scout to discover candidates.</td></tr>
                )}
                {candidates.map((c) => (
                  <tr key={c.id} className="border-b hover:bg-white/[0.02] transition-colors" style={{ borderColor: 'var(--navy-border)' }}>
                    <td className="px-4 py-3">
                      <a href={`/candidates/${c.id}`} className="text-white font-medium hover:underline">{c.name}</a>
                    </td>
                    <td className="px-4 py-3 text-slate-300">{c.title}</td>
                    <td className="px-4 py-3 text-slate-400">{c.location}</td>
                    <td className="px-4 py-3">
                      {c.suitability_score != null ? (
                        <span className="inline-flex items-center justify-center w-8 h-8 rounded-full text-xs font-bold"
                          style={{ background: c.suitability_score >= 7 ? '#10B98130' : c.suitability_score >= 5 ? '#F59E0B30' : '#EF444430',
                                   color: c.suitability_score >= 7 ? '#10B981' : c.suitability_score >= 5 ? '#F59E0B' : '#EF4444' }}>
                          {c.suitability_score}
                        </span>
                      ) : <span className="text-slate-500">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ background: '#1B6CA830', color: 'var(--cyan)' }}>
                        {c.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{c.email ?? '—'}</td>
                    <td className="px-4 py-3">
                      {c.linkedin_url && (
                        <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-xs" style={{ color: 'var(--cyan)' }}>
                          Profile ↗
                        </a>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <a href={`/candidates/${c.id}`} className="text-xs text-slate-400 hover:text-white transition-colors">View</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'audit' && (
        <div className="space-y-2">
          {auditEvents.length === 0 && (
            <div className="rounded-xl border p-8 text-center" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
              <p className="text-slate-400 text-sm">No audit events yet.</p>
            </div>
          )}
          {auditEvents.map((event) => (
            <div key={event.id} className="rounded-xl border overflow-hidden" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
              <div
                className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-white/[0.02] transition-colors"
                onClick={() => toggleExpand(event.id)}
              >
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: SEV_COLORS[event.severity] ?? '#94A3B8' }} />
                <span className="px-2 py-0.5 rounded text-xs font-medium flex-shrink-0" style={{ background: (CAT_COLORS[event.event_category] ?? '#94A3B8') + '20', color: CAT_COLORS[event.event_category] ?? '#94A3B8' }}>
                  {event.event_category}
                </span>
                <span className="text-sm text-slate-300 flex-1">{event.summary}</span>
                <span className="text-xs text-slate-500 flex-shrink-0">{new Date(event.created_at).toLocaleTimeString()}</span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-500 transition-transform flex-shrink-0" style={{ transform: expandedEvents.has(event.id) ? 'rotate(180deg)' : 'none' }}>
                  <polyline points="6 9 12 15 18 9"/>
                </svg>
              </div>
              {expandedEvents.has(event.id) && event.detail && (
                <div className="px-4 pb-3 pt-0 border-t" style={{ borderColor: 'var(--navy-border)' }}>
                  <pre className="text-xs text-slate-400 font-mono overflow-auto p-2 rounded" style={{ background: 'var(--navy)' }}>
                    {JSON.stringify(event.detail, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === 'spec' && (
        <div className="rounded-xl border p-6 space-y-4" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          {job && (
            <dl className="grid grid-cols-2 gap-4 text-sm">
              {[
                ['Title', job.title],
                ['Job Type', job.job_type],
                ['Location', job.location],
                ['Work Type', job.work_type],
                ['Experience', `${job.experience_years}+ years`],
                ['Salary', job.salary_min ? `$${job.salary_min}–$${job.salary_max}` : 'Not specified'],
                ['Minimum Score', `${job.minimum_score}/10`],
                ['Hiring Manager', `${job.hiring_manager_name} <${job.hiring_manager_email}>`],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-slate-400 text-xs font-medium uppercase tracking-wide mb-1">{label}</dt>
                  <dd className="text-white">{value}</dd>
                </div>
              ))}
              <div className="col-span-2">
                <dt className="text-slate-400 text-xs font-medium uppercase tracking-wide mb-1">Required Skills</dt>
                <dd className="flex flex-wrap gap-2">
                  {(job.required_skills ?? []).map((skill: string) => (
                    <span key={skill} className="px-2 py-0.5 rounded text-xs" style={{ background: 'var(--blue)20', color: 'var(--cyan)' }}>{skill}</span>
                  ))}
                </dd>
              </div>
              {job.description && (
                <div className="col-span-2">
                  <dt className="text-slate-400 text-xs font-medium uppercase tracking-wide mb-1">Description</dt>
                  <dd className="text-slate-300 leading-relaxed whitespace-pre-wrap">{job.description}</dd>
                </div>
              )}
            </dl>
          )}
        </div>
      )}
    </div>
  )
}

export default function JobDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  return <QueryClientProvider client={queryClient}><JobDetailContent id={id} /></QueryClientProvider>
}
