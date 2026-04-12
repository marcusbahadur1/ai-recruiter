'use client'
import { useQuery } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useRouter } from '@/i18n/navigation'
import { tenantApi } from '@/lib/api'
import type { QuickStartStep } from '@/lib/api'

const qc = new QueryClient()

function CheckIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  )
}

function StepCircle({ index, completed, active }: { index: number; completed: boolean; active: boolean }) {
  if (completed) {
    return (
      <div style={{
        width: 40, height: 40, borderRadius: '50%', flexShrink: 0,
        background: 'var(--green)', display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#fff', boxShadow: '0 0 0 4px rgba(16,185,129,0.15)',
      }}>
        <CheckIcon />
      </div>
    )
  }
  if (active) {
    return (
      <div style={{
        width: 40, height: 40, borderRadius: '50%', flexShrink: 0,
        background: 'var(--blue)', display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#fff', fontWeight: 700, fontSize: 15,
        boxShadow: '0 0 0 4px rgba(27,108,168,0.25)',
      }}>
        {index + 1}
      </div>
    )
  }
  return (
    <div style={{
      width: 40, height: 40, borderRadius: '50%', flexShrink: 0,
      background: 'var(--card)', border: '2px solid var(--border)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: 'var(--muted)', fontWeight: 700, fontSize: 15,
    }}>
      {index + 1}
    </div>
  )
}

function QuickStartContent() {
  const router = useRouter()

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['quickstart-status'],
    queryFn: () => tenantApi.getQuickStartStatus(),
    refetchOnWindowFocus: true,
  })

  const steps = data?.steps ?? []
  const completedCount = data?.completed_count ?? 0
  const totalCount = data?.total_count ?? 0
  const allDone = data?.all_done ?? false
  const progressPct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0

  // First incomplete step is the "active" one
  const activeIndex = steps.findIndex(s => !s.completed)

  function handleStepClick(step: QuickStartStep) {
    router.push(step.href as Parameters<typeof router.push>[0])
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', padding: '32px 24px' }}>
      <div style={{ maxWidth: 680, margin: '0 auto' }}>

        {/* Header */}
        <div style={{ marginBottom: 32 }}>
          <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--white)', marginBottom: 8 }}>
            {allDone ? '🎉 You\'re all set!' : 'Quick Start'}
          </div>
          <div style={{ fontSize: 14, color: 'var(--muted)', marginBottom: 20 }}>
            {allDone
              ? 'Your AI Recruiter is fully configured and ready to find great candidates.'
              : 'Follow these steps to get your AI Recruiter up and running.'}
          </div>

          {/* Progress bar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ flex: 1, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{
                height: '100%', borderRadius: 3,
                width: `${progressPct}%`,
                background: allDone ? 'var(--green)' : 'var(--cyan)',
                transition: 'width 0.4s ease',
              }}/>
            </div>
            <div style={{ fontSize: 13, color: 'var(--muted)', whiteSpace: 'nowrap', flexShrink: 0 }}>
              {completedCount} / {totalCount} complete
            </div>
          </div>
        </div>

        {/* Steps */}
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: 48, color: 'var(--muted)' }}>Loading…</div>
        ) : (
          <div style={{ position: 'relative' }}>
            {/* Vertical connector line */}
            <div style={{
              position: 'absolute', left: 19, top: 40, bottom: 40,
              width: 2, background: 'var(--border)', zIndex: 0,
            }}/>

            {steps.map((step, i) => {
              const isActive = i === activeIndex
              const isCompleted = step.completed
              const isFuture = !isCompleted && !isActive

              return (
                <div key={step.key} style={{
                  display: 'flex', gap: 20, marginBottom: 12, position: 'relative', zIndex: 1,
                }}>
                  <StepCircle index={i} completed={isCompleted} active={isActive} />

                  <div style={{
                    flex: 1,
                    background: isActive ? 'var(--navy-mid)' : 'var(--card)',
                    border: `1px solid ${isActive ? 'var(--blue)' : isCompleted ? 'rgba(16,185,129,0.2)' : 'var(--border)'}`,
                    borderRadius: 12,
                    padding: '16px 20px',
                    opacity: isFuture ? 0.6 : 1,
                    transition: 'all 0.2s',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                          <span style={{
                            fontSize: 14, fontWeight: 700,
                            color: isCompleted ? 'var(--green)' : isActive ? 'var(--white)' : 'var(--muted)',
                          }}>
                            {step.title}
                          </span>
                          {isCompleted && (
                            <span style={{
                              fontSize: 10, fontWeight: 700, color: 'var(--green)',
                              background: 'rgba(16,185,129,0.1)', padding: '1px 7px', borderRadius: 10,
                              textTransform: 'uppercase', letterSpacing: '0.5px',
                            }}>Done</span>
                          )}
                        </div>
                        <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.5 }}>
                          {step.description}
                        </div>
                      </div>

                      {!isCompleted && (
                        <button
                          onClick={() => handleStepClick(step)}
                          className={isActive ? 'btn btn-primary btn-sm' : 'btn btn-ghost btn-sm'}
                          style={{ flexShrink: 0, whiteSpace: 'nowrap' }}
                        >
                          {isActive ? 'Go →' : 'Open →'}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* All done CTA */}
        {allDone && (
          <div style={{
            marginTop: 24, padding: '24px 28px',
            background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)',
            borderRadius: 12, textAlign: 'center',
          }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--green)', marginBottom: 8 }}>
              Your AI Recruiter is fully configured
            </div>
            <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 16 }}>
              Head to the dashboard to monitor your pipeline, or post a new job to keep the candidates coming.
            </div>
            <button className="btn btn-primary" onClick={() => router.push('/')}>
              Go to Dashboard →
            </button>
          </div>
        )}

        {/* Refresh hint */}
        <div style={{ marginTop: 20, textAlign: 'center' }}>
          <button className="btn btn-ghost btn-sm" onClick={() => refetch()}>
            ↻ Refresh status
          </button>
        </div>

      </div>
    </div>
  )
}

export default function QuickStartPage() {
  return <QueryClientProvider client={qc}><QuickStartContent /></QueryClientProvider>
}
