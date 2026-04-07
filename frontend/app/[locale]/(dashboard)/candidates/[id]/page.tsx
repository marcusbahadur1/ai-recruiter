'use client'
import { useTranslations } from 'next-intl'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { use, useState } from 'react'
import { candidatesApi } from '@/lib/api'

const qc = new QueryClient()

function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    discovered: 'badge-discovered', profiled: 'badge-profiled',
    passed: 'badge-passed', failed: 'badge-failed', emailed: 'badge-emailed',
    applied: 'badge-scout', interviewed: 'badge-interviewed',
  }
  return map[status] ?? 'badge-discovered'
}

function CandidateDetailContent({ id }: { id: string }) {
  const t = useTranslations('candidates')
  const queryClient = useQueryClient()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const { data: candidate, isLoading } = useQuery({
    queryKey: ['candidate', id],
    queryFn: () => candidatesApi.get(id),
  })

  const deleteMutation = useMutation({
    mutationFn: () => candidatesApi.gdprDelete(id),
    onSuccess: () => { window.location.href = '/candidates' },
  })

  const outreachMutation = useMutation({
    mutationFn: () => candidatesApi.sendOutreach(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['candidate', id] }),
  })

  if (isLoading) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: 24, height: 24, borderRadius: '50%', border: '2px solid var(--cyan)', borderTopColor: 'transparent', animation: 'spin 0.8s linear infinite' }}/>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    )
  }

  const profile = candidate?.brightdata_profile ?? {} as Record<string, unknown>
  const score = candidate?.suitability_score ?? null
  const initials = (candidate?.name ?? '?').split(' ').map((w: string) => w[0]).join('').slice(0, 2).toUpperCase()
  const skills: string[] = (candidate as { skills?: string[] } | undefined)?.skills ?? []

  return (
    <div style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', padding: '24px' }}>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <a onClick={() => window.location.href = '/candidates'}>Candidates</a>
        <span className="breadcrumb-sep">/</span>
        <span>{candidate?.name}</span>
      </div>

      {/* Hero card */}
      <div className="profile-hero">
        <div className="profile-avatar-lg">{initials}</div>
        <div style={{ flex: 1 }}>
          <div className="profile-name">{candidate?.name}</div>
          <div className="profile-title">{candidate?.title}{candidate?.company ? ` at ${candidate.company}` : ''}{candidate?.location ? ` · ${candidate.location}` : ''}</div>
          <div className="profile-meta">
            {candidate?.email && <span className="pmeta-item">✉ {candidate.email}</span>}
            {(candidate as { email_source?: string })?.email_source && (
              <span className="pmeta-item" style={{ fontSize: 11 }}>via {(candidate as { email_source?: string }).email_source}</span>
            )}
            {candidate?.linkedin_url && (
              <a href={candidate.linkedin_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--cyan)', fontSize: 12 }}>LinkedIn ↗</a>
            )}
          </div>
          {skills.length > 0 && (
            <div className="skill-tags">
              {skills.map((skill: string) => <span key={skill} className="skill-tag match">{skill}</span>)}
            </div>
          )}
        </div>
        {score != null && (
          <div className="score-big">
            <div className="score-big-num">{score}</div>
            <div className="score-big-label">/ 10 Suitability</div>
            <div style={{ marginTop: 8 }}>
              <span className={`badge ${statusBadgeClass(candidate?.status ?? '')}`}>{candidate?.status}</span>
            </div>
          </div>
        )}
      </div>

      <div className="flex-row">
        <div className="col-main">
          {/* AI Score Reasoning */}
          {candidate?.score_reasoning && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-header"><div className="card-title">AI Score Reasoning</div></div>
              <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.7, marginBottom: 12 }}>{candidate.score_reasoning}</div>
              <div className="grid-2">
                <div>
                  <div style={{ fontSize: 11, color: 'var(--green)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Strengths</div>
                  <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.8 }}>
                    {(candidate as { strengths?: string[] }).strengths?.map((s: string) => `✓ ${s}`).join('\n') ?? '—'}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--amber)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Gaps</div>
                  <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.8 }}>
                    {(candidate as { gaps?: string[] }).gaps?.map((g: string) => `△ ${g}`).join('\n') ?? '—'}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* LinkedIn profile */}
          {Object.keys(profile).length > 0 && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-header"><div className="card-title">LinkedIn Profile</div></div>
              {typeof profile.summary === 'string' && (
                <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.7, marginBottom: 12 }}>{profile.summary}</div>
              )}
              {Array.isArray(profile.positions) && (
                <div>
                  {(profile.positions as Array<{ title: string; company: string; date_range: string }>).slice(0, 4).map((pos, i: number) => (
                    <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)', display: 'flex', gap: 8 }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 500 }}>{pos.title}</div>
                        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{pos.company} · {pos.date_range}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Outreach email */}
          {candidate?.outreach_email_content && (
            <div className="card">
              <div className="card-header">
                <div className="card-title">Outreach Email Sent</div>
                <span style={{ fontSize: 11, color: 'var(--muted)' }}>{candidate.outreach_email_sent_at ? new Date(candidate.outreach_email_sent_at).toLocaleString() : ''}</span>
              </div>
              <div style={{ background: 'var(--navy-light)', border: '1px solid var(--border-mid)', borderRadius: 8, padding: 14, fontSize: 12, color: 'var(--muted)', lineHeight: 1.8 }}>
                <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{candidate.outreach_email_content}</pre>
              </div>
            </div>
          )}
        </div>

        <div className="col-side">
          {/* Actions */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-title" style={{ marginBottom: 12 }}>Actions</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button className="btn btn-primary" style={{ justifyContent: 'center' }}
                onClick={() => outreachMutation.mutate()} disabled={outreachMutation.isPending}>
                📧 {outreachMutation.isPending ? 'Sending...' : t('sendOutreach')}
              </button>
              <button className="btn btn-ghost" style={{ justifyContent: 'center' }}>✏️ Edit Notes</button>
              <button className="btn btn-danger" style={{ justifyContent: 'center' }} onClick={() => setShowDeleteConfirm(true)}>
                🗑 {t('gdprDelete')}
              </button>
            </div>
          </div>

          {/* Job info */}
          {candidate?.job_title && (
            <div className="card">
              <div className="card-title" style={{ marginBottom: 10 }}>Job Applied To</div>
              <div style={{ fontSize: 13, color: 'var(--white)', marginBottom: 4 }}>{candidate.job_title}</div>
              <div style={{ marginTop: 8 }}>
                <span className={`badge ${statusBadgeClass(candidate?.status ?? '')}`}>{candidate?.status}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* GDPR Delete Confirm */}
      {showDeleteConfirm && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.6)' }}>
          <div className="card" style={{ maxWidth: 400, width: '100%', margin: '0 16px' }}>
            <h3 style={{ color: 'var(--white)', fontWeight: 600, marginBottom: 8 }}>GDPR Delete Candidate</h3>
            <p style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 20, lineHeight: 1.6 }}>
              This will permanently anonymise all PII data for <strong style={{ color: 'var(--white)' }}>{candidate?.name}</strong>. This cannot be undone.
            </p>
            <div style={{ display: 'flex', gap: 12 }}>
              <button className="btn btn-ghost" style={{ flex: 1, justifyContent: 'center' }} onClick={() => setShowDeleteConfirm(false)}>Cancel</button>
              <button className="btn btn-danger" style={{ flex: 1, justifyContent: 'center', background: 'var(--red)', color: '#fff' }}
                onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
                {deleteMutation.isPending ? 'Deleting...' : 'Delete & Anonymise'}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  )
}

export default function CandidateDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  return <QueryClientProvider client={qc}><CandidateDetailContent id={id} /></QueryClientProvider>
}
