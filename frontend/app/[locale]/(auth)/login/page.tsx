'use client'
import { useTranslations } from 'next-intl'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useState } from 'react'
import { Link } from '@/i18n/navigation'
import { authApi } from '@/lib/api'

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
})
type FormData = z.infer<typeof schema>

export default function LoginPage() {
  const t = useTranslations('auth')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (data: FormData) => {
    setLoading(true)
    setError(null)
    try {
      await authApi.login(data.email, data.password)
      window.location.href = '/en'
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--navy)' }}>
      <div style={{ width: '100%', maxWidth: 400, padding: '0 16px' }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <div style={{ width: 34, height: 34, background: 'linear-gradient(135deg,var(--blue),var(--cyan))', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, fontWeight: 700, color: '#fff', fontFamily: 'Playfair Display, serif' }}>A</div>
            <span style={{ fontSize: 20, fontWeight: 700, color: 'var(--white)' }}>AI Recruiter</span>
          </div>
          <p style={{ color: 'var(--muted)', fontSize: 13 }}>Sign in to your account</p>
        </div>

        <div className="card">
          <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">{t('email')}</label>
              <input
                {...register('email')}
                type="email"
                autoComplete="email"
                className="form-input"
                placeholder="you@example.com"
              />
              {errors.email && <p style={{ marginTop: 4, fontSize: 11, color: 'var(--red)' }}>{errors.email.message}</p>}
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <label className="form-label" style={{ marginBottom: 0 }}>{t('password')}</label>
                <a href="#" style={{ fontSize: 11, color: 'var(--cyan)' }}>{t('forgotPassword')}</a>
              </div>
              <input
                {...register('password')}
                type="password"
                autoComplete="current-password"
                className="form-input"
                placeholder="••••••••"
              />
              {errors.password && <p style={{ marginTop: 4, fontSize: 11, color: 'var(--red)' }}>{errors.password.message}</p>}
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
              {loading ? 'Signing in...' : t('signIn')}
            </button>
          </form>

          <div style={{ marginTop: 24, textAlign: 'center', fontSize: 13, color: 'var(--muted)' }}>
            {t('noAccount')}{' '}
            <Link href="/signup" style={{ color: 'var(--cyan)', fontWeight: 600 }}>
              {t('signup')}
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
