'use client'
import { useTranslations } from 'next-intl'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { use, useState } from 'react'
import { candidatesApi } from '@/lib/api'

const qc = new QueryClient()

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

  if (isLoading) return <div className="flex justify-center py-16"><div className="w-6 h-6 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: 'var(--cyan)', borderTopColor: 'transparent' }}/></div>

  const profile = candidate?.brightdata_profile ?? {} as Record<string, unknown>

  return (
    <div className="space-y-5 max-w-4xl">
      {/* Breadcrumb + Header */}
      <div>
        <p className="text-slate-400 text-sm mb-1">
          <a href="/candidates" className="hover:text-white">Candidates</a> / {candidate?.name}
        </p>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full flex items-center justify-center text-lg font-bold flex-shrink-0" style={{ background: 'var(--cyan)', color: 'var(--navy)' }}>
              {candidate?.name?.charAt(0) ?? '?'}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">{candidate?.name}</h1>
              <p className="text-slate-400 text-sm">{candidate?.title} · {candidate?.company}</p>
              <p className="text-slate-500 text-xs mt-0.5">{candidate?.location}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {candidate?.linkedin_url && (
              <a href={candidate.linkedin_url} target="_blank" rel="noopener noreferrer"
                className="px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors hover:bg-white/5"
                style={{ borderColor: 'var(--navy-border)', color: 'var(--cyan)' }}>
                LinkedIn ↗
              </a>
            )}
            <button
              onClick={() => outreachMutation.mutate()}
              disabled={outreachMutation.isPending}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-white transition-colors disabled:opacity-50"
              style={{ background: 'var(--blue)' }}
            >
              {t('sendOutreach')}
            </button>
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-red-400 border border-red-800/50 hover:bg-red-900/20 transition-colors"
            >
              {t('gdprDelete')}
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Score card */}
        <div className="rounded-xl border p-5" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          <p className="text-slate-400 text-xs font-medium uppercase tracking-wide mb-2">Suitability Score</p>
          <div className="flex items-end gap-1">
            <span className="text-4xl font-bold" style={{ color: (candidate?.suitability_score ?? 0) >= 7 ? '#10B981' : '#F59E0B' }}>
              {candidate?.suitability_score ?? '—'}
            </span>
            {candidate?.suitability_score && <span className="text-slate-400 text-lg mb-1">/10</span>}
          </div>
          {candidate?.score_reasoning && (
            <p className="text-slate-400 text-xs mt-2 leading-relaxed">{candidate.score_reasoning}</p>
          )}
        </div>

        {/* Status card */}
        <div className="rounded-xl border p-5" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          <p className="text-slate-400 text-xs font-medium uppercase tracking-wide mb-2">Status</p>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium" style={{ background: 'var(--cyan)15', color: 'var(--cyan)' }}>
            {candidate?.status}
          </span>
          {candidate?.email && (
            <div className="mt-3">
              <p className="text-slate-500 text-xs">Email</p>
              <p className="text-slate-200 text-sm">{candidate.email}</p>
              <p className="text-slate-500 text-xs mt-0.5">via {candidate.email_source}</p>
            </div>
          )}
        </div>

        {/* Outreach card */}
        <div className="rounded-xl border p-5" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          <p className="text-slate-400 text-xs font-medium uppercase tracking-wide mb-2">Outreach</p>
          {candidate?.outreach_email_sent_at ? (
            <>
              <p className="text-slate-300 text-sm">Email sent</p>
              <p className="text-slate-500 text-xs mt-1">{new Date(candidate.outreach_email_sent_at).toLocaleString()}</p>
            </>
          ) : (
            <p className="text-slate-500 text-sm">No outreach sent</p>
          )}
        </div>
      </div>

      {/* BrightData Profile */}
      {Object.keys(profile).length > 0 && (
        <div className="rounded-xl border p-6" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          <h2 className="text-base font-semibold text-white mb-4">LinkedIn Profile</h2>
          <div className="space-y-3">
            {typeof profile.summary === 'string' && (
              <div>
                <p className="text-slate-400 text-xs font-medium uppercase tracking-wide mb-1">Summary</p>
                <p className="text-slate-300 text-sm leading-relaxed">{profile.summary}</p>
              </div>
            )}
            {Array.isArray(profile.positions) && (
              <div>
                <p className="text-slate-400 text-xs font-medium uppercase tracking-wide mb-2">Experience</p>
                <div className="space-y-2">
                  {(profile.positions as Array<{ title: string; company: string; date_range: string }>).slice(0, 4).map((pos, i: number) => (
                    <div key={i} className="flex items-start gap-3 py-2 border-b last:border-0" style={{ borderColor: 'var(--navy-border)' }}>
                      <div className="flex-1">
                        <p className="text-white text-sm font-medium">{pos.title}</p>
                        <p className="text-slate-400 text-xs">{pos.company} · {pos.date_range}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Outreach email preview */}
      {candidate?.outreach_email_content && (
        <div className="rounded-xl border p-6" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          <h2 className="text-base font-semibold text-white mb-3">Outreach Email</h2>
          <pre className="text-slate-300 text-sm leading-relaxed whitespace-pre-wrap font-sans">{candidate.outreach_email_content}</pre>
        </div>
      )}

      {/* GDPR Delete Confirm Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="rounded-xl border p-6 max-w-md w-full mx-4" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
            <h3 className="text-white font-semibold mb-2">GDPR Delete Candidate</h3>
            <p className="text-slate-400 text-sm mb-5">This will permanently anonymise all PII data for <strong className="text-white">{candidate?.name}</strong>. This cannot be undone.</p>
            <div className="flex gap-3">
              <button onClick={() => setShowDeleteConfirm(false)} className="flex-1 py-2 rounded-lg text-sm font-medium text-slate-300 border transition-colors hover:bg-white/5" style={{ borderColor: 'var(--navy-border)' }}>Cancel</button>
              <button onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending} className="flex-1 py-2 rounded-lg text-sm font-medium text-white bg-red-600 hover:bg-red-700 transition-colors disabled:opacity-50">
                {deleteMutation.isPending ? 'Deleting...' : 'Delete & Anonymise'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function CandidateDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  return <QueryClientProvider client={qc}><CandidateDetailContent id={id} /></QueryClientProvider>
}
