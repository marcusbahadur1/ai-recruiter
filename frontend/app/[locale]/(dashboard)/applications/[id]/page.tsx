'use client'
import { useTranslations } from 'next-intl'
import { useQuery, useMutation } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { use, useState } from 'react'
import { applicationsApi } from '@/lib/api'

const qc = new QueryClient()

function scorePillClass(score: number | null | undefined): string {
  if (score == null) return 'score-mid'
  if (score >= 8) return 'score-high'
  if (score >= 6) return 'score-mid'
  return 'score-low'
}

function ApplicationContent({ id }: { id: string }) {
  const t = useTranslations('applications')
  const [tab, setTab] = useState<'resume' | 'screening' | 'test' | 'interview'>('resume')

  const { data: app, isLoading } = useQuery({
    queryKey: ['application', id],
    queryFn: () => applicationsApi.get(id),
  })

  const triggerTestMutation = useMutation({
    mutationFn: () => applicationsApi.triggerTest(id),
  })

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
        <a onClick={() => window.location.href = '/applications'}>Applications</a>
        <span className="breadcrumb-sep">/</span>
        <span>{app?.applicant_name} — {(app as { job_title?: string })?.job_title ?? 'Application'}</span>
      </div>

      {/* Header */}
      <div className="section-header">
        <div>
          <div className="section-title">{app?.applicant_name}</div>
          <div className="section-sub">
            {(app as { job_title?: string })?.job_title ?? 'Job'} · Applied {app?.received_at ? new Date(app.received_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'} · {app?.applicant_email}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {app?.screening_score != null && (
            <span className={`badge badge-${app.screening_status === 'passed' ? 'passed' : 'failed'}`} style={{ fontSize: 12, padding: '6px 12px' }}>
              Screen {app.screening_score}/10 {app.screening_status === 'passed' ? '✓' : '✗'}
            </span>
          )}
          {app?.test_score != null && (
            <span className="badge" style={{ fontSize: 12, padding: '6px 12px', background: 'rgba(167,139,250,0.12)', color: '#a78bfa' }}>
              Test {app.test_score}/10 ✓
            </span>
          )}
          {app?.interview_invited && (
            <span className="badge badge-interviewed" style={{ fontSize: 12, padding: '6px 12px' }}>Interview Invited</span>
          )}
          {app?.test_status === 'not_started' && (
            <button className="btn btn-primary btn-sm" onClick={() => triggerTestMutation.mutate()} disabled={triggerTestMutation.isPending}>
              {t('triggerTest')}
            </button>
          )}
        </div>
      </div>

      <div className="grid-2">
        <div>
          {/* Resume Screening Result */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-header"><div className="card-title">Resume Screening Result</div></div>
            {app?.screening_reasoning ? (
              <>
                <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.7, marginBottom: 10 }}>{app.screening_reasoning}</div>
                <div className="grid-2">
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--green)', fontWeight: 700, marginBottom: 4 }}>Strengths</div>
                    <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                      {(app as { strengths?: string[] }).strengths?.map((s: string) => `✓ ${s}`).join('\n') ?? '—'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--amber)', fontWeight: 700, marginBottom: 4 }}>Gaps</div>
                    <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                      {(app as { gaps?: string[] }).gaps?.map((g: string) => `△ ${g}`).join('\n') ?? '—'}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>No screening result yet.</div>
            )}
          </div>

          {/* Competency Test Transcript */}
          <div className="card">
            <div className="card-header"><div className="card-title">Competency Test Transcript</div></div>
            {app?.test_answers ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 280, overflowY: 'auto' }}>
                {Object.entries(app.test_answers as Record<string, unknown>).map(([q, a], i) => (
                  <div key={i} style={{ background: 'var(--navy-light)', borderRadius: 8, padding: 10, fontSize: 12 }}>
                    <div style={{ color: 'var(--cyan)', fontWeight: 600, marginBottom: 4 }}>Q{i+1}: {q}</div>
                    <div style={{ color: 'var(--muted)' }}>{String(a)}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>Test not yet completed.</div>
            )}
          </div>
        </div>

        <div>
          {/* Interview Status */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-title" style={{ marginBottom: 12 }}>Interview Status</div>
            {app?.interview_invited ? (
              <>
                <div style={{ background: 'var(--green-dim)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 8, padding: 12, fontSize: 12, color: 'var(--green)', marginBottom: 12 }}>
                  ✓ Interview invitation sent{app.interview_invited_at ? ` on ${new Date(app.interview_invited_at).toLocaleString()}` : ''}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>Invitation email sent to {app.applicant_email} asking candidate to confirm availability.</div>
              </>
            ) : (
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>Interview invitation not yet sent.</div>
            )}
          </div>

          {/* Resume */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-title" style={{ marginBottom: 10 }}>Resume</div>
            {app?.resume_storage_path ? (
              <div style={{ background: 'var(--navy-light)', border: '1px solid var(--border-mid)', borderRadius: 8, padding: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 24 }}>📄</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>Resume</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>Uploaded {app.received_at ? new Date(app.received_at).toLocaleDateString() : '—'}</div>
                </div>
                <a href={app.resume_storage_path} target="_blank" rel="noopener noreferrer" className="btn btn-ghost btn-sm">View</a>
              </div>
            ) : (
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>No resume available.</div>
            )}
          </div>

          {/* Timeline */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 10 }}>Timeline</div>
            <div className="audit-feed">
              {app?.interview_invited && (
                <div className="audit-event">
                  <div className="audit-dot success" style={{ width: 14, height: 14, fontSize: 8 }}>✓</div>
                  <div className="audit-content">
                    <div style={{ fontSize: 12 }}>Interview invitation sent</div>
                    <div className="audit-time">{app.interview_invited_at ? new Date(app.interview_invited_at).toLocaleString() : '—'}</div>
                  </div>
                </div>
              )}
              {app?.test_score != null && (
                <div className="audit-event">
                  <div className="audit-dot success" style={{ width: 14, height: 14, fontSize: 8 }}>✓</div>
                  <div className="audit-content">
                    <div style={{ fontSize: 12 }}>Test completed — scored {app.test_score}/10</div>
                    <div className="audit-time">{app.received_at ? new Date(app.received_at).toLocaleDateString() : '—'}</div>
                  </div>
                </div>
              )}
              {app?.screening_score != null && (
                <div className="audit-event">
                  <div className="audit-dot success" style={{ width: 14, height: 14, fontSize: 8 }}>✓</div>
                  <div className="audit-content">
                    <div style={{ fontSize: 12 }}>Resume screened — {app.screening_score}/10 {app.screening_status}</div>
                    <div className="audit-time">{app.received_at ? new Date(app.received_at).toLocaleDateString() : '—'}</div>
                  </div>
                </div>
              )}
              <div className="audit-event">
                <div className="audit-dot info" style={{ width: 14, height: 14, fontSize: 8 }}>i</div>
                <div className="audit-content">
                  <div style={{ fontSize: 12 }}>Resume received via email</div>
                  <div className="audit-time">{app?.received_at ? new Date(app.received_at).toLocaleString() : '—'}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function ApplicationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  return <QueryClientProvider client={qc}><ApplicationContent id={id} /></QueryClientProvider>
}
