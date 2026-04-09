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

  const profile = (candidate?.brightdata_profile ?? {}) as Record<string, unknown>
  const score = candidate?.suitability_score ?? null
  const initials = (candidate?.name ?? '?').split(' ').map((w: string) => w[0]).join('').slice(0, 2).toUpperCase()
  const hasProfile = Object.keys(profile).length > 0

  // Extract structured fields from BrightData profile
  const positions = (profile.positions as Array<Record<string, unknown>> | undefined) ?? []
  const currentPos = positions[0] ?? {}
  const profileSkills = (profile.skills as Array<Record<string, unknown>> | undefined) ?? []
  const topSkills = profileSkills.slice(0, 5).map(s => String(s.name ?? '')).filter(Boolean)
  const education = (profile.educations as Array<Record<string, unknown>> | undefined) ?? []
  const certifications = (profile.certifications as Array<Record<string, unknown>> | undefined) ?? []
  const aboutText = String(profile.summary ?? profile.about ?? '')
  const headline = String(profile.headline ?? profile.occupation ?? '')

  const strengths: string[] = candidate?.strengths ?? []
  const gaps: string[] = candidate?.gaps ?? []
  const heroSkills = topSkills  // use BrightData skills in the hero card

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
          {heroSkills.length > 0 && (
            <div className="skill-tags">
              {heroSkills.map((skill: string) => <span key={skill} className="skill-tag match">{skill}</span>)}
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
                  {strengths.length > 0 ? (
                    <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
                      {strengths.map((s, i) => (
                        <li key={i} style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.8 }}>✓ {s}</li>
                      ))}
                    </ul>
                  ) : <div style={{ fontSize: 12, color: 'var(--muted)' }}>—</div>}
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--amber)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Gaps</div>
                  {gaps.length > 0 ? (
                    <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
                      {gaps.map((g, i) => (
                        <li key={i} style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.8 }}>△ {g}</li>
                      ))}
                    </ul>
                  ) : <div style={{ fontSize: 12, color: 'var(--muted)' }}>—</div>}
                </div>
              </div>
            </div>
          )}

          {/* LinkedIn profile */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-header"><div className="card-title">LinkedIn Profile</div></div>
            {!hasProfile ? (
              <div style={{ fontSize: 13, color: 'var(--muted)', padding: '8px 0' }}>No profile data available.</div>
            ) : (
              <>
                {/* Name / headline */}
                {headline && (
                  <div style={{ fontSize: 13, color: 'var(--cyan)', marginBottom: 8 }}>{headline}</div>
                )}

                {/* Current position */}
                {currentPos.title && (
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--white)' }}>
                      {String(currentPos.title)}{currentPos.company_name ? ` at ${String(currentPos.company_name)}` : ''}
                    </div>
                  </div>
                )}

                {/* About */}
                {aboutText && (
                  <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.7, marginBottom: 12 }}>{aboutText}</div>
                )}

                {/* Top skills */}
                {topSkills.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 700, marginBottom: 6 }}>Top Skills</div>
                    <div className="skill-tags">
                      {topSkills.map(s => <span key={s} className="skill-tag">{s}</span>)}
                    </div>
                  </div>
                )}

                {/* Work history */}
                {positions.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 700, marginBottom: 6 }}>Experience</div>
                    {positions.slice(0, 4).map((pos, i) => (
                      <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--white)' }}>{String(pos.title ?? '')}</div>
                        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                          {String(pos.company_name ?? pos.company ?? '')}
                          {pos.date_range ? ` · ${String(pos.date_range)}` : ''}
                          {pos.duration ? ` · ${String(pos.duration)}` : ''}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Education */}
                {education.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 700, marginBottom: 6 }}>Education</div>
                    {education.map((ed, i) => (
                      <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--white)' }}>{String(ed.school ?? ed.institution ?? '')}</div>
                        {(ed.degree || ed.field_of_study) && (
                          <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                            {[ed.degree, ed.field_of_study].filter(Boolean).map(String).join(' · ')}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Certifications */}
                {certifications.length > 0 && (
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 700, marginBottom: 6 }}>Certifications</div>
                    {certifications.map((cert, i) => (
                      <div key={i} style={{ fontSize: 12, color: 'var(--muted)', padding: '3px 0' }}>
                        {String(cert.name ?? cert.title ?? '')}
                        {cert.authority ? ` — ${String(cert.authority)}` : ''}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Outreach email */}
          {candidate?.outreach_email_content && (
            <div className="card">
              <div className="card-header">
                <div className="card-title">Outreach Email Sent</div>
                <span style={{ fontSize: 11, color: 'var(--muted)' }}>{candidate.outreach_email_sent_at ? new Date(candidate.outreach_email_sent_at).toLocaleString() : ''}</span>
              </div>
              <div style={{ background: '#fff', border: '1px solid var(--border-mid)', borderRadius: 8, padding: 20, fontFamily: 'sans-serif', color: '#111', lineHeight: 1.7 }}>
                <div dangerouslySetInnerHTML={{ __html: candidate.outreach_email_content }} />
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
