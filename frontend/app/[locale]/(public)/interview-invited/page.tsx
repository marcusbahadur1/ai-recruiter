'use client'
import { useSearchParams } from 'next/navigation'
import { Suspense } from 'react'

function InterviewInvitedContent() {
  const params = useSearchParams()
  const already = params.get('already') === '1'
  const name = params.get('name') || 'The candidate'
  const role = params.get('role') || 'the role'

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
          background: already ? '#fef9c3' : '#d1fae5',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 24px',
        }}>
          {already ? (
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#ca8a04" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
          ) : (
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          )}
        </div>

        <h1 style={{ fontSize: 24, fontWeight: 800, color: '#1a1d23', marginBottom: 12 }}>
          {already ? 'Already Sent' : 'Interview Invitation Sent ✓'}
        </h1>

        <p style={{ fontSize: 15, color: '#6b7280', lineHeight: 1.7, marginBottom: 28 }}>
          {already
            ? `An interview invitation for ${name} has already been sent.`
            : `${name} has been notified and will be in touch to arrange a suitable time for the ${role} interview.`}
        </p>

        {!already && (
          <div style={{
            background: '#f0fdf4',
            border: '1px solid #bbf7d0',
            borderRadius: 10,
            padding: '16px 20px',
            marginBottom: 28,
            textAlign: 'left',
          }}>
            <p style={{ fontSize: 13, color: '#166534', margin: 0, lineHeight: 1.6 }}>
              A confirmation email has been sent to the candidate. Please contact them directly to confirm the interview time and location.
            </p>
          </div>
        )}

        <div style={{ paddingTop: 24, borderTop: '1px solid #f3f4f6' }}>
          <p style={{ fontSize: 11, color: '#c4c9d4', margin: 0 }}>Powered by AI Recruiter</p>
        </div>
      </div>
    </div>
  )
}

export default function InterviewInvitedPage() {
  return (
    <Suspense>
      <InterviewInvitedContent />
    </Suspense>
  )
}
