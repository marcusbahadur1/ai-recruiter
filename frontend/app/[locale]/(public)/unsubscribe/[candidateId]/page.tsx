'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { apiClient } from '@/lib/api/client'

type State = 'loading' | 'success' | 'already' | 'error'

export default function UnsubscribePage() {
  const { candidateId } = useParams<{ candidateId: string }>()
  const [state, setState] = useState<State>('loading')

  useEffect(() => {
    apiClient
      .get(`/candidates/unsubscribe/${candidateId}`)
      .then((res) => {
        const data = res.data as { success: boolean; already_opted_out: boolean }
        setState(data.already_opted_out ? 'already' : 'success')
      })
      .catch(() => setState('error'))
  }, [candidateId])

  const content: Record<State, { icon: string; iconBg: string; iconColor: string; title: string; body: string }> = {
    loading: {
      icon: '…',
      iconBg: '#f3f4f6',
      iconColor: '#9ca3af',
      title: 'Processing…',
      body: 'Please wait a moment.',
    },
    success: {
      icon: '✓',
      iconBg: '#d1fae5',
      iconColor: '#10b981',
      title: 'You have been unsubscribed',
      body: 'You will no longer receive recruitment emails from us. We respect your decision and will not contact you again.',
    },
    already: {
      icon: '✓',
      iconBg: '#fef9c3',
      iconColor: '#ca8a04',
      title: 'Already unsubscribed',
      body: 'Your email address was already removed from our list. You will not receive any further emails from us.',
    },
    error: {
      icon: '!',
      iconBg: '#fee2e2',
      iconColor: '#ef4444',
      title: 'Something went wrong',
      body: 'We were unable to process your request. Please try again or contact support@airecruiterz.com.',
    },
  }

  const c = content[state]

  return (
    <div style={{
      minHeight: '100vh',
      background: '#f5f6fa',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: "'Inter', 'Segoe UI', sans-serif",
      padding: '0 20px',
    }}>
      <div style={{
        background: '#fff',
        border: '1px solid #e5e7eb',
        borderRadius: 20,
        padding: '56px 40px',
        maxWidth: 480,
        width: '100%',
        textAlign: 'center',
        boxShadow: '0 4px 24px rgba(0,0,0,0.06)',
      }}>
        <div style={{
          width: 72,
          height: 72,
          borderRadius: '50%',
          background: c.iconBg,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 24px',
          fontSize: state === 'loading' ? 20 : 28,
          color: c.iconColor,
          fontWeight: 700,
        }}>
          {c.icon}
        </div>

        <h1 style={{ fontSize: 24, fontWeight: 800, color: '#1a1d23', marginBottom: 12 }}>
          {c.title}
        </h1>

        <p style={{ fontSize: 15, color: '#6b7280', lineHeight: 1.7, marginBottom: 32 }}>
          {c.body}
        </p>

        <div style={{ paddingTop: 24, borderTop: '1px solid #f3f4f6' }}>
          <p style={{ fontSize: 11, color: '#c4c9d4', margin: 0 }}>Powered by AI Recruiter</p>
        </div>
      </div>
    </div>
  )
}
