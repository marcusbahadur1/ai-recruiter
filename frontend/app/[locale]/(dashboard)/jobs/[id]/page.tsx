'use client'
import { useTranslations } from 'next-intl'
import { useQuery } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { use, useState } from 'react'
import { useRouter, Link } from '@/i18n/navigation'
import { useAuditStream } from '@/hooks/useAuditStream'
import { jobsApi, auditApi, candidatesApi } from '@/lib/api'

const queryClient = new QueryClient()

function scorePillClass(score: number | null | undefined): string {
  if (score == null) return 'score-mid'
  if (score >= 8) return 'score-high'
  if (score >= 6) return 'score-mid'
  return 'score-low'
}
function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    active: 'badge-active', paused: 'badge-paused', closed: 'badge-closed',
    passed: 'badge-passed', failed: 'badge-failed', emailed: 'badge-emailed',
  }
  return map[status] ?? 'badge-discovered'
}
function statusLabel(status: string): string {
  const map: Record<string, string> = { active: '● Active', paused: '⏸ Paused', closed: '✕ Closed' }
  return map[status] ?? status
}
function sevDotClass(sev: string): string {
  const map: Record<string, string> = { success: 'success', error: 'error', warning: 'warning', info: 'info' }
  return map[sev] ?? 'info'
}
function sevChar(sev: string): string {
  const map: Record<string, string> = { success: '✓', error: '✕', warning: '!', info: 'i' }
  return map[sev] ?? 'i'
}
function catBadgeClass(cat: string): string {
  const map: Record<string, string> = {
    talent_scout: 'badge-scout', resume_screener: 'badge-screener',
    payment: 'badge-payment', system: 'badge-system',
  }
  return map[cat] ?? 'badge-system'
}
function catLabel(cat: string): string {
  const map: Record<string, string> = {
    talent_scout: 'Talent Scout', resume_screener: 'Resume Screener',
    payment: 'Payment', system: 'System',
  }
  return map[cat] ?? cat
}

const formatSalary = (amount: number) =>
  new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    maximumFractionDigits: 0,
  }).format(amount)

function JobDetailContent({ id }: { id: string }) {
  const t = useTranslations('jobs')
  const router = useRouter()
  const [tab, setTab] = useState<'report' | 'applications' | 'audit' | 'spec' | 'instructions'>('report')
  const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set())

  const { data: job, isLoading } = useQuery({
    queryKey: ['job', id],
    queryFn: () => jobsApi.get(id),
  })

  const { data: candidatesData } = useQuery({
    queryKey: ['job-candidates', id],
    queryFn: () => candidatesApi.list({ job_id: id, limit: 100 }),
    enabled: tab === 'report',
  })

  const { data: auditData } = useQuery({
    queryKey: ['audit-events', id],
    queryFn: () => auditApi.getEvents(id),
    enabled: tab === 'audit',
  })

  const { events: streamEvents } = useAuditStream(id)

  const candidates = candidatesData?.items ?? []
  const totalCandidates = candidatesData?.total ?? candidates.length
  const minScore = job?.minimum_score ?? 6

  // Derive display status: treat 'passed' as 'emailed' when outreach was sent
  const effectiveStatus = (status: string, outreachSentAt: string | null) =>
    outreachSentAt && status === 'passed' ? 'emailed' : status

  // Cumulative pipeline counts
  const statPassed  = candidates.filter(c =>
    (c.suitability_score != null && c.suitability_score >= minScore) ||
    ['passed', 'emailed', 'applied', 'tested', 'interviewed'].includes(effectiveStatus(c.status ?? '', c.outreach_email_sent_at))
  ).length
  const statEmailed = candidates.filter(c =>
    c.outreach_email_sent_at != null ||
    ['emailed', 'applied', 'tested', 'interviewed'].includes(effectiveStatus(c.status ?? '', c.outreach_email_sent_at))
  ).length
  const statApplied = candidates.filter(c =>
    ['applied', 'tested', 'interviewed'].includes(c.status ?? '')
  ).length

  const auditEvents = [...(auditData?.items ?? []), ...streamEvents]

  const toggleExpand = (eventId: string) => {
    setExpandedEvents((prev) => {
      const next = new Set(prev)
      next.has(eventId) ? next.delete(eventId) : next.add(eventId)
      return next
    })
  }

  if (isLoading) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: 24, height: 24, borderRadius: '50%', border: '2px solid var(--cyan)', borderTopColor: 'transparent', animation: 'spin 0.8s linear infinite' }}/>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', padding: '24px' }}>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <a onClick={() => window.location.href = '/jobs'}>Jobs</a>
        <span className="breadcrumb-sep">/</span>
        <span>{job?.title}</span>
      </div>

      {/* Section header */}
      <div className="section-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <div className="section-title">{job?.title}</div>
            <span className={`badge ${statusBadgeClass(job?.status ?? '')}`}>{statusLabel(job?.status ?? '')}</span>
            <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 12, color: 'var(--muted)', background: 'var(--navy-light)', padding: '3px 8px', borderRadius: 6 }}>
              {job?.job_ref}
            </span>
          </div>
          <div className="section-sub">
            {job?.location} · {job?.work_type} · Min. Score {job?.minimum_score} · Hiring Mgr: {job?.hiring_manager_name}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm">⏸ Pause</button>
          <button className="btn btn-primary btn-sm">▶ Re-run Scout</button>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        {job?.mode !== 'screener_only' && (
          <div className={`tab${tab === 'report' ? ' active' : ''}`} onClick={() => setTab('report')}>📊 Evaluation Report</div>
        )}
        {job?.mode === 'screener_only' && (
          <div className={`tab${tab === 'applications' ? ' active' : ''}`} onClick={() => setTab('applications')}>📥 Applications</div>
        )}
        <div className={`tab${tab === 'audit'  ? ' active' : ''}`} onClick={() => setTab('audit')}>🔍 Audit Trail</div>
        <div className={`tab${tab === 'spec'   ? ' active' : ''}`} onClick={() => setTab('spec')}>📋 Job Spec</div>
        {job?.mode === 'screener_only' && (
          <div className={`tab${tab === 'instructions' ? ' active' : ''}`} onClick={() => setTab('instructions')}>📨 Application Instructions</div>
        )}
      </div>

      {/* ── Evaluation Report tab ── */}
      {tab === 'report' && (
        <>
          {/* Mini stat row */}
          <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
            {[
              { label: 'Discovered', value: totalCandidates, cls: '' },
              { label: 'Passed',     value: statPassed,      cls: 'green' },
              { label: 'Emailed',    value: statEmailed,     cls: 'gold' },
              { label: 'Applied',    value: statApplied,     cls: '' },
            ].map((s) => (
              <div key={s.label} className={`stat-card ${s.cls}`} style={{ flex: 1, minWidth: 100, padding: 14 }}>
                <div className="stat-label">{s.label}</div>
                <div className="stat-value" style={{ fontSize: 22 }}>{s.value}</div>
              </div>
            ))}
          </div>

          <div className="card">
            <div className="card-header">
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <div className="live-badge"><div className="live-dot"/>Live</div>
                <span style={{ fontSize: 12, color: 'var(--muted)' }}>{totalCandidates} candidates</span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <select className="form-select" style={{ width: 140, padding: '5px 10px', fontSize: 12 }}>
                  <option>All statuses</option><option>Passed</option><option>Emailed</option><option>Failed</option>
                </select>
                <button className="btn btn-ghost btn-sm">↓ Export CSV</button>
              </div>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Name</th><th>Title</th><th>Location</th><th>Score</th><th>Status</th><th>Email</th><th>Mailed</th><th>Summary</th><th>LinkedIn</th></tr>
                </thead>
                <tbody>
                  {candidates.length === 0 && (
                    <tr><td colSpan={9} style={{ textAlign: 'center', padding: 32, color: 'var(--muted)' }}>No candidates yet. Trigger the Talent Scout to discover candidates.</td></tr>
                  )}
                  {candidates.map((c) => (
                    <tr key={c.id} onClick={() => router.push(`/candidates/${c.id}`)}>
                      <td className="td-name">{c.name}</td>
                      <td className="muted">{c.title}</td>
                      <td className="muted">{c.location}</td>
                      <td>
                        {c.suitability_score != null
                          ? <span className={`score-pill ${scorePillClass(c.suitability_score)}`}>{c.suitability_score}</span>
                          : <span style={{ color: 'var(--muted)' }}>—</span>}
                      </td>
                      <td><span className={`badge ${statusBadgeClass(effectiveStatus(c.status ?? '', c.outreach_email_sent_at))}`}>{effectiveStatus(c.status ?? '', c.outreach_email_sent_at)}</span></td>
                      <td style={{ fontSize: 11, color: 'var(--muted)' }}>{c.email ?? '—'}</td>
                      <td><span style={{ color: c.outreach_email_sent_at ? 'var(--green)' : 'var(--muted)', fontSize: 12 }}>{c.outreach_email_sent_at ? '✓' : '—'}</span></td>
                      <td>
                        <Link href={`/candidates/${c.id}`} style={{ color: 'var(--cyan)', fontSize: 11 }} onClick={(e) => e.stopPropagation()}>View</Link>
                      </td>
                      <td>
                        {c.linkedin_url && <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--cyan)', fontSize: 11 }} onClick={(e) => e.stopPropagation()}>↗</a>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* ── Audit Trail tab ── */}
      {tab === 'audit' && (
        <div className="card">
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div className="live-badge"><div className="live-dot"/>Live stream</div>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>{auditEvents.length} events</span>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <select className="form-select" style={{ width: 130, padding: '5px 10px', fontSize: 12 }}>
                <option>All categories</option><option>Talent Scout</option><option>Resume Screener</option><option>System</option>
              </select>
              <select className="form-select" style={{ width: 120, padding: '5px 10px', fontSize: 12 }}>
                <option>All severity</option><option>Errors only</option><option>Warnings+</option>
              </select>
              <button className="btn btn-ghost btn-sm">↓ Export CSV</button>
            </div>
          </div>

          {auditEvents.length === 0 && (
            <div className="empty-state"><div className="empty-icon">🔍</div><div className="empty-text">No audit events yet.</div></div>
          )}

          <div className="audit-feed">
            {auditEvents.map((event) => (
              <div key={event.id}>
                <div className="audit-event" onClick={() => toggleExpand(event.id)} style={{ cursor: 'pointer' }}>
                  <div className={`audit-dot ${sevDotClass(event.severity)}`}>{sevChar(event.severity)}</div>
                  <div className="audit-content">
                    <div className="audit-summary">{event.summary}</div>
                    <div className="audit-meta">
                      <span className={`badge ${catBadgeClass(event.event_category)}`} style={{ fontSize: 9, padding: '1px 6px' }}>{catLabel(event.event_category)}</span>
                      <span className={`badge badge-${sevDotClass(event.severity)}`} style={{ fontSize: 9, padding: '1px 6px' }}>{event.severity}</span>
                      <span className="audit-time">{new Date(event.created_at).toLocaleTimeString()}{event.duration_ms ? ` · ${event.duration_ms}ms` : ''}</span>
                    </div>
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--muted)', cursor: 'pointer', marginLeft: 'auto', flexShrink: 0, transform: expandedEvents.has(event.id) ? 'rotate(180deg)' : 'none', display: 'inline-block' }}>▼</span>
                </div>
                {expandedEvents.has(event.id) && event.detail && (
                  <div style={{ paddingLeft: 30, paddingBottom: 10 }}>
                    <pre style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'DM Mono, monospace', background: 'var(--navy)', padding: '8px 12px', borderRadius: 6, overflow: 'auto' }}>
                      {JSON.stringify(event.detail, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Job Spec tab ── */}
      {tab === 'spec' && job && (
        <div className="card">
          <div className="spec-row"><span className="spec-key">Job Title</span><span className="spec-val">{job.title}</span></div>
          {(job as { title_variations?: string[] }).title_variations?.length && (
            <div className="spec-row"><span className="spec-key">Title Variations</span><span className="spec-val">{(job as { title_variations?: string[] }).title_variations?.join(', ')}</span></div>
          )}
          <div className="spec-row"><span className="spec-key">Location</span><span className="spec-val">{job.location}</span></div>
          <div className="spec-row"><span className="spec-key">Work Type</span><span className="spec-val">{job.work_type}</span></div>
          <div className="spec-row"><span className="spec-key">Experience</span><span className="spec-val">{job.experience_years}+ years</span></div>
          <div className="spec-row">
            <span className="spec-key">Salary Range</span>
            <span className="spec-val">
              {job.salary_min ? `${formatSalary(job.salary_min)} – ${formatSalary(job.salary_max ?? job.salary_min)}` : 'Not specified'}
            </span>
          </div>
          <div className="spec-row"><span className="spec-key">Min. Score</span><span className="spec-val">{job.minimum_score} / 10</span></div>
          <div className="spec-row">
            <span className="spec-key">Required Skills</span>
            <span className="spec-val">
              <div className="skill-tags">
                {(job.required_skills ?? []).map((skill: string) => (
                  <span key={skill} className="skill-tag match">{skill}</span>
                ))}
              </div>
            </span>
          </div>
          <div className="spec-row"><span className="spec-key">Hiring Manager</span><span className="spec-val">{job.hiring_manager_name} · {job.hiring_manager_email}</span></div>
          <div className="spec-row"><span className="spec-key">Job Reference</span><span className="spec-val" style={{ fontFamily: 'DM Mono, monospace' }}>{job.job_ref}</span></div>
          {job.description && (
            <div className="spec-row"><span className="spec-key">Description</span><span className="spec-val" style={{ whiteSpace: 'pre-wrap' }}>{job.description}</span></div>
          )}
        </div>
      )}

      {/* ── Applications tab (screener_only) ── */}
      {tab === 'applications' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">Incoming Applications</div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Name</th><th>Email</th><th>Resume Score</th><th>Status</th><th>Applied</th></tr>
              </thead>
              <tbody>
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: 32, color: 'var(--muted)' }}>
                  No applications yet. Share the application instructions with candidates.
                </td></tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Application Instructions tab (screener_only) ── */}
      {tab === 'instructions' && job && (
        <div className="card">
          <div style={{ padding: '8px 0 20px' }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>How to Apply</div>
            <div style={{ background: 'var(--navy)', border: '1px solid var(--border)', borderRadius: 8, padding: 16, fontFamily: 'DM Mono, monospace', fontSize: 13, marginBottom: 16 }}>
              Email your resume to jobs@aiworkerz.com with subject: {job.job_ref}            </div>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => navigator.clipboard.writeText(`Email your resume to jobs@aiworkerz.com with subject: ${job.job_ref} – Your Name`)}
            >
              📋 Copy Instructions
            </button>
          </div>
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 20 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Suggested Post Text</div>
            <div style={{ background: 'var(--navy)', border: '1px solid var(--border)', borderRadius: 8, padding: 16, fontSize: 13, lineHeight: 1.7, marginBottom: 12 }}>
              {`We're hiring a ${job.title}${job.location ? ` in ${job.location}` : ''}.\n\nTo apply, email your resume to jobs@aiworkerz.com with subject: ${job.job_ref} – Your Name`}
            </div>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => navigator.clipboard.writeText(`We're hiring a ${job.title}${job.location ? ` in ${job.location}` : ''}.\n\nTo apply, email your resume to jobs@aiworkerz.com with subject: ${job.job_ref} – Your Name`)}
            >
              📋 Copy Post Text
            </button>
          </div>
        </div>
      )}

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  )
}

export default function JobDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  return <QueryClientProvider client={queryClient}><JobDetailContent id={id} /></QueryClientProvider>
}
