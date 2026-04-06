'use client'
import { useTranslations } from 'next-intl'
import { useQuery, useMutation } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { use, useState } from 'react'
import { applicationsApi } from '@/lib/api'

const qc = new QueryClient()

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

  if (isLoading) return <div className="flex justify-center py-16"><div className="w-6 h-6 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: 'var(--cyan)', borderTopColor: 'transparent' }}/></div>

  const tabs = [
    { key: 'resume', label: t('resume') },
    { key: 'screening', label: t('screeningResult') },
    { key: 'test', label: t('testTranscript') },
    { key: 'interview', label: t('interviewStatus') },
  ] as const

  return (
    <div className="space-y-5 max-w-3xl">
      <div>
        <p className="text-slate-400 text-sm mb-1">Applications / {app?.applicant_name}</p>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">{app?.applicant_name}</h1>
            <p className="text-slate-400 text-sm">{app?.applicant_email} · received {app?.received_at ? new Date(app.received_at).toLocaleDateString() : '—'}</p>
          </div>
          <div className="flex gap-2">
            {app?.test_status === 'not_started' && (
              <button
                onClick={() => triggerTestMutation.mutate()}
                disabled={triggerTestMutation.isPending}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-white disabled:opacity-50"
                style={{ background: 'var(--blue)' }}
              >
                {t('triggerTest')}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Status pills */}
      <div className="flex flex-wrap gap-3">
        {[
          { label: 'Screening', value: app?.screening_status, score: app?.screening_score },
          { label: 'Test', value: app?.test_status, score: app?.test_score },
          { label: 'Interview', value: app?.interview_invited ? 'invited' : 'pending' },
        ].map((item) => (
          <div key={item.label} className="rounded-lg border px-4 py-2.5" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
            <p className="text-slate-400 text-xs font-medium">{item.label}</p>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-white text-sm font-medium capitalize">{item.value ?? '—'}</span>
              {item.score != null && <span className="text-slate-400 text-xs">({item.score}/10)</span>}
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b" style={{ borderColor: 'var(--navy-border)' }}>
        {tabs.map(({ key, label }) => (
          <button key={key} onClick={() => setTab(key)}
            className="px-5 py-3 text-sm font-medium border-b-2 transition-colors"
            style={{ borderColor: tab === key ? 'var(--cyan)' : 'transparent', color: tab === key ? 'var(--cyan)' : '#94A3B8' }}>
            {label}
          </button>
        ))}
      </div>

      <div className="rounded-xl border p-6" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
        {tab === 'resume' && (
          <div>
            {app?.resume_storage_path ? (
              <div className="space-y-3">
                <a href={app.resume_storage_path} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white"
                  style={{ background: 'var(--blue)' }}>
                  Download Resume ↓
                </a>
                {app.resume_text && (
                  <pre className="text-slate-300 text-xs leading-relaxed whitespace-pre-wrap font-sans mt-4 p-4 rounded-lg" style={{ background: 'var(--navy)' }}>
                    {app.resume_text}
                  </pre>
                )}
              </div>
            ) : <p className="text-slate-400 text-sm">No resume available.</p>}
          </div>
        )}
        {tab === 'screening' && (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-3xl font-bold" style={{ color: (app?.screening_score ?? 0) >= 7 ? '#10B981' : '#F59E0B' }}>
                {app?.screening_score ?? '—'}
              </span>
              {app?.screening_score && <span className="text-slate-400">/10</span>}
              <span className="px-2.5 py-1 rounded-full text-xs font-medium capitalize"
                style={{ background: app?.screening_status === 'passed' ? '#10B98120' : '#EF444420', color: app?.screening_status === 'passed' ? '#10B981' : '#EF4444' }}>
                {app?.screening_status}
              </span>
            </div>
            {app?.screening_reasoning && <p className="text-slate-300 text-sm leading-relaxed">{app.screening_reasoning}</p>}
          </div>
        )}
        {tab === 'test' && (
          <div>
            {app?.test_answers ? (
              <div className="space-y-4">
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-3xl font-bold" style={{ color: (app?.test_score ?? 0) >= 7 ? '#10B981' : '#F59E0B' }}>{app.test_score ?? '—'}</span>
                  {app.test_score && <span className="text-slate-400">/10</span>}
                </div>
                {Object.entries(app.test_answers as Record<string, unknown>).map(([q, a], i) => (
                  <div key={i} className="border-b pb-3" style={{ borderColor: 'var(--navy-border)' }}>
                    <p className="text-slate-300 text-sm font-medium mb-1">Q{i+1}: {q}</p>
                    <p className="text-slate-400 text-sm">{String(a)}</p>
                  </div>
                ))}
              </div>
            ) : <p className="text-slate-400 text-sm">Test not yet completed.</p>}
          </div>
        )}
        {tab === 'interview' && (
          <div>
            {app?.interview_invited ? (
              <div>
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium" style={{ background: '#10B98120', color: '#10B981' }}>
                  ✓ Interview Invited
                </span>
                {app.interview_invited_at && <p className="text-slate-400 text-sm mt-2">Invited at {new Date(app.interview_invited_at).toLocaleString()}</p>}
              </div>
            ) : <p className="text-slate-400 text-sm">Interview invitation not yet sent.</p>}
          </div>
        )}
      </div>
    </div>
  )
}

export default function ApplicationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  return <QueryClientProvider client={qc}><ApplicationContent id={id} /></QueryClientProvider>
}
