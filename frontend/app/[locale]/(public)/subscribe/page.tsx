'use client'
import { useState } from 'react'
import { billingApi } from '@/lib/api'

const PLANS = [
  {
    key: 'recruiter',
    name: 'Recruiter',
    price: '$499',
    period: '/mo',
    jobs: 5,
    candidates: 20,
    resumes: 50,
    features: [
      '5 active jobs per month',
      '20 candidates per job',
      '50 resume screenings per job',
      'AI Talent Scout',
      'AI Resume Screener',
      'Email outreach',
      'Candidate evaluation reports',
    ],
    highlight: false,
  },
  {
    key: 'agency_small',
    name: 'Agency',
    badge: 'Small',
    price: '$999',
    period: '/mo',
    jobs: 20,
    candidates: 40,
    resumes: 75,
    features: [
      '20 active jobs per month',
      '40 candidates per job',
      '75 resume screenings per job',
      'Everything in Recruiter',
      'Chat Widget for your website',
      'Team members (up to 5)',
      'Priority support',
    ],
    highlight: true,
  },
  {
    key: 'agency_medium',
    name: 'Agency',
    badge: 'Medium',
    price: '$2,999',
    period: '/mo',
    jobs: 75,
    candidates: 60,
    resumes: 100,
    features: [
      '75 active jobs per month',
      '60 candidates per job',
      '100 resume screenings per job',
      'Everything in Agency Small',
      'Unlimited team members',
      'Advanced analytics',
      'Dedicated account manager',
    ],
    highlight: false,
  },
]

export default function SubscribePage() {
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSubscribe(planKey: 'recruiter' | 'agency_small' | 'agency_medium') {
    setLoading(planKey)
    setError(null)
    try {
      const { checkout_url } = await billingApi.createCheckoutSession(planKey)
      window.location.href = checkout_url
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
      setLoading(null)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--navy)',
      padding: '48px 16px',
      color: 'var(--white)',
    }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <div style={{
            width: 36, height: 36,
            background: 'linear-gradient(135deg,var(--blue),var(--cyan))',
            borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18, fontWeight: 700, color: '#fff', fontFamily: 'Playfair Display, serif',
          }}>A</div>
          <span style={{ fontSize: 22, fontWeight: 700 }}>AI Recruiter</span>
        </div>
        <h1 style={{ fontSize: 32, fontWeight: 800, marginBottom: 12 }}>
          Choose your plan
        </h1>
        <p style={{ color: 'var(--muted)', fontSize: 16, maxWidth: 480, margin: '0 auto' }}>
          Your free trial has ended. Subscribe to keep finding great candidates on autopilot.
        </p>
      </div>

      {/* Plan cards */}
      <div style={{
        display: 'flex',
        gap: 24,
        justifyContent: 'center',
        flexWrap: 'wrap',
        maxWidth: 1100,
        margin: '0 auto 48px',
      }}>
        {PLANS.map((plan) => (
          <div
            key={plan.key}
            style={{
              flex: '1 1 280px',
              maxWidth: 320,
              background: plan.highlight ? 'var(--navy-mid)' : 'var(--card)',
              border: plan.highlight ? '2px solid var(--cyan)' : '1px solid var(--border)',
              borderRadius: 16,
              padding: 28,
              position: 'relative',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {plan.highlight && (
              <div style={{
                position: 'absolute',
                top: -12,
                left: '50%',
                transform: 'translateX(-50%)',
                background: 'var(--cyan)',
                color: '#fff',
                fontSize: 11,
                fontWeight: 700,
                padding: '3px 12px',
                borderRadius: 20,
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}>
                Most Popular
              </div>
            )}

            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 13, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
                {plan.name}
                {plan.badge && (
                  <span style={{ marginLeft: 6, color: 'var(--cyan)' }}>— {plan.badge}</span>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                <span style={{ fontSize: 36, fontWeight: 800 }}>{plan.price}</span>
                <span style={{ fontSize: 14, color: 'var(--muted)' }}>{plan.period}</span>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 24 }}>
              {[
                { label: 'Jobs / month', value: plan.jobs },
                { label: 'Candidates / job', value: plan.candidates },
                { label: 'Resumes / month', value: plan.resumes },
              ].map(({ label, value }) => (
                <div key={label} style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: 13,
                  padding: '6px 0',
                  borderBottom: '1px solid var(--border)',
                }}>
                  <span style={{ color: 'var(--muted)' }}>{label}</span>
                  <span style={{ fontWeight: 600 }}>{value}</span>
                </div>
              ))}
            </div>

            <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 24px', flex: 1 }}>
              {plan.features.map((f) => (
                <li key={f} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13, color: 'var(--muted)', marginBottom: 8 }}>
                  <span style={{ color: 'var(--cyan)', flexShrink: 0, marginTop: 1 }}>✓</span>
                  {f}
                </li>
              ))}
            </ul>

            <button
              onClick={() => handleSubscribe(plan.key as 'recruiter' | 'agency_small' | 'agency_medium')}
              disabled={loading === plan.key}
              style={{
                padding: '12px 20px',
                borderRadius: 8,
                border: 'none',
                cursor: loading === plan.key ? 'not-allowed' : 'pointer',
                fontWeight: 700,
                fontSize: 14,
                background: plan.highlight ? 'var(--cyan)' : 'var(--blue)',
                color: '#fff',
                opacity: loading === plan.key ? 0.7 : 1,
                transition: 'opacity 0.15s',
              }}
              onMouseEnter={(e) => { if (loading !== plan.key) e.currentTarget.style.opacity = '0.85' }}
              onMouseLeave={(e) => { if (loading !== plan.key) e.currentTarget.style.opacity = '1' }}
            >
              {loading === plan.key ? 'Redirecting...' : 'Start Plan'}
            </button>
          </div>
        ))}

        {/* Enterprise card */}
        <div style={{
          flex: '1 1 280px',
          maxWidth: 320,
          background: 'var(--card)',
          border: '1px solid var(--border)',
          borderRadius: 16,
          padding: 28,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ fontSize: 13, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
              Enterprise
            </div>
            <div style={{ fontSize: 28, fontWeight: 800, marginBottom: 8 }}>Custom</div>
            <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.6, marginBottom: 20 }}>
              Unlimited jobs, candidates, and resumes. Dedicated support, custom integrations, and SLA.
            </p>
            <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 24px' }}>
              {[
                'Unlimited everything',
                'Custom integrations',
                'Dedicated account manager',
                'SLA guarantees',
                'On-premise option',
              ].map((f) => (
                <li key={f} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13, color: 'var(--muted)', marginBottom: 8 }}>
                  <span style={{ color: 'var(--cyan)', flexShrink: 0, marginTop: 1 }}>✓</span>
                  {f}
                </li>
              ))}
            </ul>
          </div>
          <a
            href="mailto:support@airecruiterz.com?subject=Enterprise%20Enquiry"
            style={{
              display: 'block',
              textAlign: 'center',
              padding: '12px 20px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              fontWeight: 700,
              fontSize: 14,
              color: 'var(--white)',
              textDecoration: 'none',
            }}
          >
            Contact Us
          </a>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div style={{
          textAlign: 'center',
          color: '#f87171',
          fontSize: 14,
          marginBottom: 16,
          padding: '12px 20px',
          background: 'rgba(248,113,113,0.1)',
          borderRadius: 8,
          maxWidth: 480,
          margin: '0 auto 24px',
        }}>
          {error}
        </div>
      )}

      {/* Back to login */}
      <div style={{ textAlign: 'center', fontSize: 13, color: 'var(--muted)' }}>
        Already subscribed?{' '}
        <a href="/login" style={{ color: 'var(--cyan)', fontWeight: 600 }}>Sign in</a>
      </div>
    </div>
  )
}
