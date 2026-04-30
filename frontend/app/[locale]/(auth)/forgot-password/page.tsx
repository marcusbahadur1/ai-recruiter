'use client'
import { useState } from 'react'
import { Link } from '@/i18n/navigation'
import { supabase } from '@/lib/api'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/en/reset-password`,
    })
    if (error) {
      setError(error.message)
    } else {
      setSubmitted(true)
    }
    setLoading(false)
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--navy)' }}>
      <div style={{ width: '100%', maxWidth: 400, padding: '0 16px' }}>
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <div style={{ width: 34, height: 34, background: 'linear-gradient(135deg,var(--blue),var(--cyan))', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, fontWeight: 700, color: '#fff', fontFamily: 'Playfair Display, serif' }}>A</div>
            <span style={{ fontSize: 20, fontWeight: 700, color: 'var(--white)' }}>AI Recruiter</span>
          </div>
          <p style={{ color: 'var(--muted)', fontSize: 13 }}>Reset your password</p>
        </div>

        <div className="card">
          {submitted ? (
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 40, marginBottom: 16 }}>📧</div>
              <p style={{ color: 'var(--white)', fontWeight: 600, marginBottom: 8 }}>Check your email</p>
              <p style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 24 }}>
                We sent a password reset link to <strong style={{ color: 'var(--white)' }}>{email}</strong>
              </p>
              <Link href="/login" style={{ fontSize: 13, color: 'var(--cyan)' }}>
                Back to sign in
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <p style={{ color: 'var(--muted)', fontSize: 13, margin: 0 }}>
                Enter your email and we&apos;ll send you a link to reset your password.
              </p>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="form-input"
                  placeholder="you@example.com"
                  autoComplete="email"
                />
              </div>

              {error && (
                <div style={{ padding: '10px 12px', borderRadius: 8, background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.2)', fontSize: 13, color: 'var(--red)' }}>
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary"
                style={{ justifyContent: 'center', padding: '10px 16px', opacity: loading ? 0.7 : 1 }}
              >
                {loading ? 'Sending...' : 'Send reset link'}
              </button>

              <div style={{ textAlign: 'center', fontSize: 13, color: 'var(--muted)' }}>
                <Link href="/login" style={{ color: 'var(--cyan)' }}>
                  Back to sign in
                </Link>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
