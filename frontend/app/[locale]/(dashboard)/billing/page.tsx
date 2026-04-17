'use client'
import { useEffect, useState } from 'react'
import { useRouter } from '@/i18n/navigation'
import { useTranslations } from 'next-intl'
import { settingsApi, billingApi } from '@/lib/api'
import type { Tenant } from '@/lib/api'

const PLAN_DETAILS: Record<string, {
  label: string; price: string; period: string
  jobs: string; candidates: string; resumes: string
  features: string[]
  highlight?: boolean
}> = {
  trial: {
    label: 'Free Trial', price: 'Free', period: '',
    jobs: '3', candidates: '10', resumes: '50',
    features: ['3 active jobs', '10 candidates per job', '50 resume screenings', 'AI Talent Scout', 'AI Resume Screener'],
  },
  trial_expired: {
    label: 'Trial Expired', price: '—', period: '',
    jobs: '0', candidates: '0', resumes: '0',
    features: [],
  },
  recruiter: {
    label: 'Recruiter', price: '$499', period: '/mo',
    jobs: '5', candidates: '20', resumes: '50',
    features: ['5 active jobs per month', '20 candidates per job', '50 resume screenings', 'AI Talent Scout', 'AI Resume Screener', 'Email outreach', 'Candidate evaluation reports'],
  },
  agency_small: {
    label: 'Agency Small', price: '$999', period: '/mo',
    jobs: '20', candidates: '40', resumes: '75',
    features: ['20 active jobs per month', '40 candidates per job', '75 resume screenings', 'Everything in Recruiter', 'Chat Widget for your website', 'Team members (up to 5)', 'Priority support'],
    highlight: true,
  },
  agency_medium: {
    label: 'Agency Medium', price: '$2,999', period: '/mo',
    jobs: '75', candidates: '60', resumes: '100',
    features: ['75 active jobs per month', '60 candidates per job', '100 resume screenings', 'Everything in Agency Small', 'Unlimited team members', 'Advanced analytics', 'Dedicated account manager'],
  },
  enterprise: {
    label: 'Enterprise', price: 'Custom', period: '',
    jobs: 'Unlimited', candidates: 'Unlimited', resumes: 'Unlimited',
    features: ['Unlimited everything', 'Custom SLA', 'Custom onboarding', 'Dedicated account manager', 'EU data residency available'],
  },
}

function fmt(date: string | null | undefined): string {
  if (!date) return '—'
  return new Date(date).toLocaleDateString('en-AU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function CreditsBar({ used, total, label }: { used: number; total: number; label: string }) {
  const pct = total === 0 ? 0 : Math.min(100, Math.round((used / total) * 100))
  const low = pct > 75
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 6 }}>
        <span style={{ color: 'var(--muted)' }}>{label}</span>
        <span style={{ fontWeight: 600 }}>{used} / {total}</span>
      </div>
      <div style={{ height: 6, background: 'var(--border)', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{
          height: '100%', borderRadius: 99,
          width: `${pct}%`,
          background: low ? 'var(--red)' : 'linear-gradient(90deg, var(--blue), var(--cyan))',
          transition: 'width 0.4s',
        }} />
      </div>
    </div>
  )
}

export default function BillingPage() {
  const t = useTranslations('billing')
  const router = useRouter()
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [loading, setLoading] = useState(true)
  const [portalLoading, setPortalLoading] = useState(false)
  const [portalError, setPortalError] = useState<string | null>(null)
  const [upgradeLoading, setUpgradeLoading] = useState<string | null>(null)
  const [upgradeError, setUpgradeError] = useState<string | null>(null)

  useEffect(() => {
    settingsApi.getTenant()
      .then(setTenant)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  async function handlePortal() {
    setPortalLoading(true)
    setPortalError(null)
    try {
      const { url } = await billingApi.getPortal()
      window.location.href = url
    } catch (err: unknown) {
      setPortalError(err instanceof Error ? err.message : 'Could not open billing portal')
      setPortalLoading(false)
    }
  }

  async function handleUpgrade(plan: 'recruiter' | 'agency_small' | 'agency_medium') {
    setUpgradeLoading(plan)
    setUpgradeError(null)
    try {
      const { checkout_url } = await billingApi.createCheckoutSession(plan)
      window.location.href = checkout_url
    } catch (err: unknown) {
      setUpgradeError(err instanceof Error ? err.message : 'Could not start checkout')
      setUpgradeLoading(null)
    }
  }

  const plan = tenant?.plan ?? 'trial'
  const planInfo = PLAN_DETAILS[plan]
  const isActive = plan !== 'trial' && plan !== 'trial_expired'
  const trialDaysLeft = (() => {
    if (plan !== 'trial' || !tenant?.trial_ends_at) return null
    const ms = new Date(tenant.trial_ends_at).getTime() - Date.now()
    return Math.max(0, Math.ceil(ms / 86400000))
  })()

  // Credits: total = credits_remaining + used (we only have remaining; show as usage bar only when subscribed)
  const creditsRemaining = tenant?.credits_remaining ?? 0
  const planCredsTotal: Record<string, number> = {
    recruiter: 5, agency_small: 20, agency_medium: 75, enterprise: 0, trial: 3, trial_expired: 0,
  }
  const planTotal = planCredsTotal[plan] ?? 0
  const creditsUsed = Math.max(0, planTotal - creditsRemaining)

  if (loading) {
    return (
      <div style={{ padding: 32, color: 'var(--muted)', fontSize: 14 }}>{t('loading')}</div>
    )
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 24, maxWidth: 860 }}>

      {/* Trial expired banner */}
      {plan === 'trial_expired' && (
        <div style={{
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.35)',
          borderRadius: 10, padding: '14px 18px', marginBottom: 24,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
        }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--red)' }}>{t('trialEnded')}</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>{t('trialEndedSub')}</div>
          </div>
          <button className="btn btn-cyan btn-sm" onClick={() => router.push('/subscribe')} style={{ flexShrink: 0 }}>
            {t('subscribeNow')} →
          </button>
        </div>
      )}

      {/* Trial countdown banner */}
      {plan === 'trial' && trialDaysLeft !== null && (
        <div style={{
          background: 'rgba(27,108,168,0.12)', border: '1px solid var(--blue)',
          borderRadius: 10, padding: '14px 18px', marginBottom: 24,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
        }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--white)' }}>
              ⏰ {trialDaysLeft} day{trialDaysLeft !== 1 ? 's' : ''} left in your free trial
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>{t('trialKeepAccess')}</div>
          </div>
          <button className="btn btn-primary btn-sm" onClick={() => router.push('/subscribe')} style={{ flexShrink: 0 }}>
            {t('viewPlans')} →
          </button>
        </div>
      )}

      {/* Current plan + actions */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>{t('currentPlan')}</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span style={{ fontSize: 26, fontWeight: 700, color: 'var(--white)' }}>{planInfo?.label ?? plan}</span>
              {planInfo?.price && planInfo.price !== '—' && (
                <span style={{ fontSize: 16, color: 'var(--muted)' }}>
                  {planInfo.price}{planInfo.period}
                </span>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {isActive && (
              <button
                className="btn btn-primary"
                onClick={handlePortal}
                disabled={portalLoading}
              >
                {portalLoading ? t('redirecting') : t('manageBilling')}
              </button>
            )}
            {!isActive && (
              <button className="btn btn-cyan" onClick={() => router.push('/subscribe')}>
                {plan === 'trial_expired' ? t('subscribeNow') : t('viewPlans')}
              </button>
            )}
            {isActive && plan !== 'agency_medium' && plan !== 'enterprise' && (
              <button className="btn btn-ghost" onClick={() => router.push('/subscribe')}>
                {t('upgradePlan')}
              </button>
            )}
          </div>
        </div>

        {portalError && (
          <div style={{ color: 'var(--red)', fontSize: 13, marginTop: 10 }}>{portalError}</div>
        )}

        {/* Subscription dates */}
        {isActive && (
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: 16, marginTop: 20, paddingTop: 20, borderTop: '1px solid var(--border)',
          }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>{t('started')}</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{fmt(tenant?.subscription_started_at)}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>{t('nextRenewal')}</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{fmt(tenant?.subscription_ends_at)}</div>
            </div>
            {plan !== 'enterprise' && (
              <div>
                <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>{t('stripeCustomer')}</div>
                <div style={{ fontSize: 13, color: 'var(--muted)', fontFamily: 'DM Mono, monospace' }}>
                  {tenant?.stripe_customer_id ?? '—'}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Credits card — subscribed plans only */}
      {isActive && plan !== 'enterprise' && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header" style={{ marginBottom: 16 }}>
            <div>
              <div className="card-title">{t('talentScoutCredits')}</div>
              <div className="card-sub">{t('creditsRenew')}</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 26, fontWeight: 700, color: creditsRemaining === 0 ? 'var(--red)' : 'var(--white)' }}>
                {creditsRemaining}
              </div>
              <div style={{ fontSize: 11, color: 'var(--muted)' }}>{t('creditsRemaining')}</div>
            </div>
          </div>
          <CreditsBar used={creditsUsed} total={planTotal} label={t('creditsUsed')} />
          <div style={{ marginTop: 10, fontSize: 12, color: 'var(--muted)' }}>
            {t('creditsInfo')}
          </div>
        </div>
      )}

      {/* Enterprise unlimited credits note */}
      {plan === 'enterprise' && (
        <div className="card" style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ fontSize: 26 }}>∞</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{t('unlimitedCredits')}</div>
            <div style={{ fontSize: 13, color: 'var(--muted)' }}>{t('unlimitedDesc')}</div>
          </div>
        </div>
      )}

      {/* Plan comparison */}
      <div className="card">
        <div className="card-header" style={{ marginBottom: 16 }}>
          <div>
            <div className="card-title">{t('comparePlans')}</div>
            <div className="card-sub">{t('compareDesc')}</div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
          {(['recruiter', 'agency_small', 'agency_medium', 'enterprise'] as const).map((key) => {
            const p = PLAN_DETAILS[key]
            const isCurrent = key === plan
            const canUpgrade = !isCurrent && isActive && key !== 'enterprise' && key !== 'recruiter'
            const canSubscribe = !isActive && key !== 'enterprise'

            return (
              <div
                key={key}
                style={{
                  background: isCurrent ? 'var(--cyan-dim)' : p.highlight ? 'rgba(27,108,168,0.08)' : 'var(--card)',
                  border: `1px solid ${isCurrent ? 'var(--cyan)' : p.highlight ? 'var(--blue)' : 'var(--border)'}`,
                  borderRadius: 10, padding: 16,
                  position: 'relative',
                }}
              >
                {p.highlight && !isCurrent && (
                  <div style={{
                    position: 'absolute', top: -10, left: '50%', transform: 'translateX(-50%)',
                    background: 'var(--blue)', color: '#fff',
                    fontSize: 10, fontWeight: 700, padding: '2px 10px', borderRadius: 99,
                    letterSpacing: '0.05em', whiteSpace: 'nowrap',
                  }}>{t('popular')}</div>
                )}
                {isCurrent && (
                  <div style={{
                    position: 'absolute', top: -10, left: '50%', transform: 'translateX(-50%)',
                    background: 'var(--cyan)', color: '#fff',
                    fontSize: 10, fontWeight: 700, padding: '2px 10px', borderRadius: 99,
                    letterSpacing: '0.05em', whiteSpace: 'nowrap',
                  }}>{t('yourPlan')}</div>
                )}

                <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{p.label}</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: isCurrent ? 'var(--cyan)' : 'var(--white)', marginBottom: 2 }}>
                  {p.price}<span style={{ fontSize: 12, fontWeight: 400, color: 'var(--muted)' }}>{p.period}</span>
                </div>

                <div style={{ margin: '12px 0', borderTop: '1px solid var(--border)' }} />

                <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 14px', fontSize: 12, color: 'var(--muted)' }}>
                  {p.features.map((f, i) => (
                    <li key={i} style={{ display: 'flex', gap: 6, marginBottom: 5 }}>
                      <span style={{ color: 'var(--cyan)', flexShrink: 0 }}>✓</span>
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>

                {canUpgrade && (
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ width: '100%' }}
                    disabled={upgradeLoading === key}
                    onClick={() => handleUpgrade(key)}
                  >
                    {upgradeLoading === key ? t('redirecting') : t('upgrade')}
                  </button>
                )}
                {canSubscribe && (
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ width: '100%' }}
                    disabled={upgradeLoading === key}
                    onClick={() => handleUpgrade(key)}
                  >
                    {upgradeLoading === key ? t('redirecting') : t('subscribe')}
                  </button>
                )}
                {key === 'enterprise' && !isCurrent && (
                  <a
                    href="mailto:support@airecruiterz.com?subject=Enterprise%20Plan%20Enquiry"
                    className="btn btn-ghost btn-sm"
                    style={{ width: '100%', textAlign: 'center', textDecoration: 'none', display: 'block' }}
                  >
                    {t('contactSales')}
                  </a>
                )}
              </div>
            )
          })}
        </div>

        {upgradeError && (
          <div style={{ color: 'var(--red)', fontSize: 13 }}>{upgradeError}</div>
        )}

        <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8 }}>
          Subscriptions are managed via Stripe. To cancel or change payment details, use the{' '}
          {isActive ? (
            <span
              style={{ color: 'var(--cyan)', cursor: 'pointer', textDecoration: 'underline' }}
              onClick={handlePortal}
            >
              {t('billingPortal')}
            </span>
          ) : (
            t('billingPortalUnavailable')
          )}.
          All prices in AUD. Enterprise pricing on request at{' '}
          <a href="mailto:support@airecruiterz.com" style={{ color: 'var(--cyan)' }}>support@airecruiterz.com</a>.
        </div>
      </div>

    </div>
  )
}
