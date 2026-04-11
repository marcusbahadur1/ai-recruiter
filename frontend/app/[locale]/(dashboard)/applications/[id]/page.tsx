'use client'
import { useTranslations } from 'next-intl'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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

const RATING_COLORS: Record<string, string> = {
  strong: 'var(--green)',
  adequate: 'var(--amber)',
  weak: 'var(--red, #ef4444)',
}

const STATUS_LABELS: Record<string, string> = {
  received: 'Received',
  screened_passed: 'Screening Passed',
  screened_failed: 'Screening Failed',
  test_invited: 'Test Invited',
  test_passed: 'Test Passed',
  test_failed: 'Test Failed',
  hm_notified: 'HM Notified',
  interview_invited: 'Interview Invited',
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

function ApplicationContent({ id }: { id: string }) {
  const t = useTranslations('applications')
  const queryClient = useQueryClient()
  const [expandedQuestions, setExpandedQuestions] = useState(false)

  const { data: app, isLoading } = useQuery({
    queryKey: ['application', id],
    queryFn: () => applicationsApi.get(id),
  })

  const triggerTestMutation = useMutation({
    mutationFn: () => applicationsApi.triggerTest(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['application', id] }),
  })

  if (isLoading) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: 24, height: 24, borderRadius: '50%', border: '2px solid var(--cyan)', borderTopColor: 'transparent', animation: 'spin 0.8s linear infinite' }}/>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    )
  }

  if (!app) return null

  const evaluation = app.test_evaluation
  const isTestPassed = app.status === 'test_passed' || app.test_status === 'passed'
  const canTriggerTest = app.screening_status === 'passed' && app.test_status === 'not_started'

  return (
    <div style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', padding: '24px' }}>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <a onClick={() => window.location.href = '/applications'} style={{ cursor: 'pointer' }}>Applications</a>
        <span className="breadcrumb-sep">/</span>
        <span>{app.applicant_name}</span>
      </div>

      {/* Header */}
      <div className="section-header" style={{ marginBottom: 24 }}>
        <div>
          <div className="section-title">{app.applicant_name}</div>
          <div className="section-sub">
            {app.applicant_email}
            {app.received_at ? ` · Applied ${new Date(app.received_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}` : ''}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className={`badge ${STATUS_BADGE[app.status] ?? 'badge-discovered'}`}>
            {STATUS_LABELS[app.status] ?? app.status}
          </span>
          {canTriggerTest && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => triggerTestMutation.mutate()}
              disabled={triggerTestMutation.isPending}
            >
              {triggerTestMutation.isPending ? 'Sending…' : t('triggerTest')}
            </button>
          )}
        </div>
      </div>

      <div className="grid-2">
        {/* Left column — scoring */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Section 1 — Resume Score */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                📄 Resume Score
                {app.resume_score != null && (
                  <span className={`score-pill ${scorePillClass(app.resume_score)}`} style={{ marginLeft: 10 }}>
                    {app.resume_score}/10
                  </span>
                )}
              </div>
              {app.received_at && <div style={{ fontSize: 11, color: 'var(--muted)' }}>Source: Submitted Resume</div>}
            </div>
            {app.resume_reasoning ? (
              <>
                <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.7, marginBottom: 12 }}>
                  {app.resume_reasoning}
                </div>
                <div className="grid-2" style={{ gap: 12 }}>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--green)', fontWeight: 700, marginBottom: 6 }}>Strengths</div>
                    {(app.resume_strengths ?? []).map((s, i) => (
                      <div key={i} style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 3 }}>✓ {s}</div>
                    ))}
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--amber)', fontWeight: 700, marginBottom: 6 }}>Gaps</div>
                    {(app.resume_gaps ?? []).map((g, i) => (
                      <div key={i} style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 3 }}>△ {g}</div>
                    ))}
                  </div>
                </div>
                {app.screening_score != null && app.resume_score != null && app.screening_score !== app.resume_score && (
                  <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--navy-light)', borderRadius: 6, fontSize: 11, color: 'var(--muted)' }}>
                    Note: Resume score may differ from an earlier Scout score as the full resume provides more detail than a public profile.
                  </div>
                )}
              </>
            ) : (
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>Resume not yet screened.</div>
            )}
          </div>

          {/* Section 2 — Interview Score */}
          {evaluation && (
            <div className="card">
              <div className="card-header">
                <div className="card-title">
                  🎤 Interview Score
                  {evaluation.overall_score != null && (
                    <span className={`score-pill ${scorePillClass(evaluation.overall_score)}`} style={{ marginLeft: 10 }}>
                      {evaluation.overall_score}/10
                    </span>
                  )}
                </div>
                {app.test_completed_at && (
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                    Completed {new Date(app.test_completed_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}
                  </div>
                )}
              </div>
              {evaluation.overall_summary && (
                <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.7, marginBottom: 12 }}>
                  {evaluation.overall_summary}
                </div>
              )}
              {((evaluation.strengths ?? []).length > 0 || (evaluation.gaps ?? []).length > 0) && (
                <div className="grid-2" style={{ gap: 12, marginBottom: 16 }}>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--green)', fontWeight: 700, marginBottom: 6 }}>Strengths</div>
                    {(evaluation.strengths ?? []).map((s, i) => (
                      <div key={i} style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 3 }}>✓ {s}</div>
                    ))}
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--amber)', fontWeight: 700, marginBottom: 6 }}>Gaps</div>
                    {(evaluation.gaps ?? []).map((g, i) => (
                      <div key={i} style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 3 }}>△ {g}</div>
                    ))}
                  </div>
                </div>
              )}

              {/* Per-question breakdown */}
              {(evaluation.questions ?? []).length > 0 && (
                <div>
                  <button
                    onClick={() => setExpandedQuestions(!expandedQuestions)}
                    style={{ background: 'none', border: 'none', color: 'var(--cyan)', cursor: 'pointer', fontSize: 12, fontWeight: 600, padding: 0, marginBottom: 10 }}
                  >
                    {expandedQuestions ? '▲ Hide' : '▼ Show'} question-by-question breakdown ({evaluation.questions?.length} questions)
                  </button>
                  {expandedQuestions && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {(evaluation.questions ?? []).map((q, i) => (
                        <div key={i} style={{ background: 'var(--navy-light)', borderRadius: 8, padding: 12 }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--cyan)', marginBottom: 6 }}>
                            Q{i + 1}: {q.question}
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8, fontStyle: 'italic' }}>
                            "{q.candidate_answer}"
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 6 }}>{q.assessment}</div>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <span style={{
                              fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                              background: `${RATING_COLORS[q.rating] ?? 'var(--muted)'}22`,
                              color: RATING_COLORS[q.rating] ?? 'var(--muted)',
                              textTransform: 'uppercase',
                            }}>
                              {q.rating}
                            </span>
                            <span style={{ fontSize: 11, color: 'var(--muted)' }}>Score: {q.score}/10</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right column — details and actions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Actions */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 12 }}>Actions</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {app.resume_storage_path && (
                <a
                  href={app.resume_storage_path}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-ghost btn-sm"
                  style={{ textAlign: 'center' }}
                >
                  📄 Download Resume
                </a>
              )}
              {isTestPassed && !app.interview_invited && (
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => triggerTestMutation.mutate()}
                  disabled={triggerTestMutation.isPending}
                >
                  ✓ Invite to Interview
                </button>
              )}
            </div>
          </div>

          {/* Interview Status */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 12 }}>Interview Status</div>
            {app.interview_invited ? (
              <div style={{ background: 'var(--green-dim)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 8, padding: 12, fontSize: 12, color: 'var(--green)' }}>
                ✓ Interview invitation sent
                {app.interview_invited_at ? ` on ${new Date(app.interview_invited_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}` : ''}
              </div>
            ) : (
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>Interview invitation not yet sent.</div>
            )}
          </div>

          {/* Resume file */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 10 }}>Resume</div>
            {app.resume_storage_path ? (
              <div style={{ background: 'var(--navy-light)', border: '1px solid var(--border-mid)', borderRadius: 8, padding: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 24 }}>📄</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{app.resume_filename ?? 'Resume'}</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                    Received {app.received_at ? new Date(app.received_at).toLocaleDateString() : '—'}
                  </div>
                </div>
                <a href={app.resume_storage_path} target="_blank" rel="noopener noreferrer" className="btn btn-ghost btn-sm">View</a>
              </div>
            ) : (
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>No resume available.</div>
            )}
          </div>

          {/* Timeline */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 10 }}>Pipeline</div>
            <div className="audit-feed">
              {app.interview_invited && (
                <div className="audit-event">
                  <div className="audit-dot success" style={{ width: 14, height: 14, fontSize: 8 }}>✓</div>
                  <div className="audit-content">
                    <div style={{ fontSize: 12 }}>Interview invitation sent</div>
                    <div className="audit-time">{app.interview_invited_at ? new Date(app.interview_invited_at).toLocaleString() : '—'}</div>
                  </div>
                </div>
              )}
              {app.test_score != null && (
                <div className="audit-event">
                  <div className={`audit-dot ${app.test_status === 'passed' ? 'success' : 'warning'}`} style={{ width: 14, height: 14, fontSize: 8 }}>
                    {app.test_status === 'passed' ? '✓' : '✗'}
                  </div>
                  <div className="audit-content">
                    <div style={{ fontSize: 12 }}>Interview test — {app.test_score}/10 {app.test_status}</div>
                    <div className="audit-time">{app.test_completed_at ? new Date(app.test_completed_at).toLocaleString() : '—'}</div>
                  </div>
                </div>
              )}
              {app.test_status === 'invited' && (
                <div className="audit-event">
                  <div className="audit-dot info" style={{ width: 14, height: 14, fontSize: 8 }}>→</div>
                  <div className="audit-content">
                    <div style={{ fontSize: 12 }}>Test invitation sent</div>
                  </div>
                </div>
              )}
              {app.resume_score != null && (
                <div className="audit-event">
                  <div className={`audit-dot ${app.screening_status === 'passed' ? 'success' : 'info'}`} style={{ width: 14, height: 14, fontSize: 8 }}>
                    {app.screening_status === 'passed' ? '✓' : '✗'}
                  </div>
                  <div className="audit-content">
                    <div style={{ fontSize: 12 }}>Resume screened — {app.resume_score}/10 {app.screening_status}</div>
                  </div>
                </div>
              )}
              <div className="audit-event">
                <div className="audit-dot info" style={{ width: 14, height: 14, fontSize: 8 }}>i</div>
                <div className="audit-content">
                  <div style={{ fontSize: 12 }}>Resume received via email</div>
                  <div className="audit-time">{app.received_at ? new Date(app.received_at).toLocaleString() : '—'}</div>
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
