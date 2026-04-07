'use client'
import { useTranslations } from 'next-intl'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useState } from 'react'
import { Link } from '@/i18n/navigation'
import { authApi } from '@/lib/api'

const schema = z.object({
  firmName: z.string().min(2),
  email: z.string().email(),
  password: z.string().min(8),
  confirmPassword: z.string(),
}).refine((d) => d.password === d.confirmPassword, {
  message: 'Passwords do not match',
  path: ['confirmPassword'],
})
type FormData = z.infer<typeof schema>

export default function SignupPage() {
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
      await authApi.signup(data.email, data.password, data.firmName)
      window.location.href = '/en'
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Sign up failed')
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
          <p style={{ color: 'var(--muted)', fontSize: 13 }}>Create your account</p>
        </div>

        <div className="card">
          <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {[
              { field: 'firmName',       label: t('firmName'),       type: 'text',     placeholder: 'Acme Recruiting' },
              { field: 'email',          label: t('email'),          type: 'email',    placeholder: 'you@example.com' },
              { field: 'password',       label: t('password'),       type: 'password', placeholder: '••••••••' },
              { field: 'confirmPassword', label: 'Confirm Password', type: 'password', placeholder: '••••••••' },
            ].map(({ field, label, type, placeholder }) => (
              <div key={field} className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">{label}</label>
                <input
                  {...register(field as keyof FormData)}
                  type={type}
                  className="form-input"
                  placeholder={placeholder}
                />
                {errors[field as keyof FormData] && (
                  <p style={{ marginTop: 4, fontSize: 11, color: 'var(--red)' }}>{errors[field as keyof FormData]?.message}</p>
                )}
              </div>
            ))}

            {error && (
              <div style={{ padding: '10px 12px', borderRadius: 8, background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.2)', fontSize: 13, color: 'var(--red)' }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn btn-cyan"
              style={{ justifyContent: 'center', padding: '10px 16px', opacity: loading ? 0.7 : 1 }}
            >
              {loading ? 'Creating account...' : t('createAccount')}
            </button>
          </form>

          <div style={{ marginTop: 24, textAlign: 'center', fontSize: 13, color: 'var(--muted)' }}>
            {t('hasAccount')}{' '}
            <Link href="/login" style={{ color: 'var(--cyan)', fontWeight: 600 }}>
              {t('signIn')}
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
