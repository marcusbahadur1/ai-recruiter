'use client'
import { useTranslations } from 'next-intl'
import { useQuery } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { dashboardApi } from '@/lib/api'

const queryClient = new QueryClient()

function DashboardContent() {
  const t = useTranslations('dashboard')

  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => dashboardApi.getStats(),
  })

  const statCards = [
    { label: t('activeJobs'), value: stats?.active_jobs ?? '—', icon: '💼', color: 'var(--blue)' },
    { label: t('candidatesToday'), value: stats?.candidates_today ?? '—', icon: '👤', color: 'var(--cyan)' },
    { label: t('applications'), value: stats?.applications ?? '—', icon: '📄', color: '#8B5CF6' },
    { label: t('creditsRemaining'), value: stats?.credits_remaining ?? '—', icon: '⚡', color: '#F59E0B' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">{t('title')}</h1>
        <p className="text-slate-400 text-sm mt-1">Welcome back. Here&apos;s what&apos;s happening.</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {statCards.map((card) => (
          <div key={card.label} className="rounded-xl p-5 border" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
            <div className="flex items-start justify-between">
              <div>
                <p className="text-slate-400 text-xs font-medium uppercase tracking-wide">{card.label}</p>
                <p className="text-3xl font-bold text-white mt-2">{card.value}</p>
              </div>
              <div className="w-10 h-10 rounded-lg flex items-center justify-center text-lg" style={{ background: card.color + '20' }}>
                {card.icon}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Pipeline + Recent Activity */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Pipeline */}
        <div className="xl:col-span-2 rounded-xl border p-5" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          <h2 className="text-base font-semibold text-white mb-4">{t('pipeline')}</h2>
          <div className="space-y-3">
            {['discovered', 'profiled', 'scored', 'passed', 'emailed', 'applied'].map((stage, i) => {
              const count = stats?.pipeline?.[stage] ?? 0
              const max = stats?.pipeline?.discovered ?? 1
              const pct = Math.round((count / max) * 100)
              const colors = ['var(--blue)', 'var(--cyan)', '#8B5CF6', '#10B981', '#F59E0B', '#EF4444']
              return (
                <div key={stage} className="flex items-center gap-3">
                  <span className="text-slate-400 text-xs w-20 capitalize">{stage}</span>
                  <div className="flex-1 h-2 rounded-full" style={{ background: 'var(--navy)' }}>
                    <div
                      className="h-2 rounded-full transition-all"
                      style={{ width: `${pct}%`, background: colors[i] }}
                    />
                  </div>
                  <span className="text-white text-sm font-medium w-8 text-right">{count}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="rounded-xl border p-5" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          <h2 className="text-base font-semibold text-white mb-4">{t('recentActivity')}</h2>
          <div className="space-y-3">
            {(stats?.recent_activity ?? []).slice(0, 6).map((event, i: number) => (
              <div key={i} className="flex items-start gap-2.5">
                <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{
                  background: event.severity === 'success' ? '#10B981' : event.severity === 'error' ? '#EF4444' : event.severity === 'warning' ? '#F59E0B' : 'var(--blue)'
                }} />
                <div>
                  <p className="text-slate-300 text-xs">{event.summary}</p>
                  <p className="text-slate-500 text-xs mt-0.5">{new Date(event.created_at).toLocaleTimeString()}</p>
                </div>
              </div>
            ))}
            {(!stats?.recent_activity?.length) && (
              <p className="text-slate-500 text-sm">No recent activity</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  return (
    <QueryClientProvider client={queryClient}>
      <DashboardContent />
    </QueryClientProvider>
  )
}
