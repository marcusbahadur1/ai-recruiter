'use client'
import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useRouter } from '@/i18n/navigation'

const PLAN_LABELS: Record<string, string> = {
  recruiter:    'Recruiter ($499/mo)',
  agency_small: 'Agency Small ($999/mo)',
  agency_medium: 'Agency Medium ($2,999/mo)',
}

function BillingSuccessContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const plan = searchParams.get('plan') ?? ''
  const planLabel = PLAN_LABELS[plan] ?? 'your plan'

  const [countdown, setCountdown] = useState(5)

  useEffect(() => {
    if (countdown <= 0) {
      router.push('/')
      return
    }
    const t = setTimeout(() => setCountdown((c) => c - 1), 1000)
    return () => clearTimeout(t)
  }, [countdown, router])

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--navy)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '32px 16px',
      color: 'var(--white)',
    }}>
      <div style={{
        background: 'var(--card)',
        border: '1px solid var(--border)',
        borderRadius: 16,
        padding: 48,
        maxWidth: 480,
        width: '100%',
        textAlign: 'center',
      }}>
        <div style={{
          width: 64,
          height: 64,
          borderRadius: '50%',
          background: 'rgba(34,197,94,0.15)',
          border: '2px solid #22c55e',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 24px',
          fontSize: 28,
        }}>
          ✓
        </div>

        <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 12 }}>
          Subscription Activated!
        </h1>

        <p style={{ color: 'var(--muted)', fontSize: 15, lineHeight: 1.6, marginBottom: 32 }}>
          Welcome to <strong style={{ color: 'var(--white)' }}>{planLabel}</strong>.
          Your account is now active and you can start posting jobs and finding candidates.
        </p>

        <button
          onClick={() => router.push('/')}
          style={{
            display: 'inline-block',
            padding: '14px 36px',
            background: 'var(--blue)',
            color: '#fff',
            borderRadius: 8,
            border: 'none',
            fontWeight: 700,
            fontSize: 15,
            cursor: 'pointer',
            marginBottom: 16,
          }}
        >
          Go to Dashboard
        </button>

        <p style={{ color: 'var(--muted)', fontSize: 13 }}>
          Redirecting automatically in {countdown}s…
        </p>
      </div>
    </div>
  )
}

export default function BillingSuccessPage() {
  return (
    <Suspense fallback={
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--navy)',
        color: 'var(--white)',
      }}>
        Loading...
      </div>
    }>
      <BillingSuccessContent />
    </Suspense>
  )
}
