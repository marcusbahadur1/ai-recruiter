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
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--navy)' }}>
      <div className="w-full max-w-md px-4">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--cyan)' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0D1B2A" strokeWidth="2.5">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
            </div>
            <span className="text-xl font-bold text-white">AI Recruiter</span>
          </div>
          <p className="text-slate-400 text-sm">Create your account</p>
        </div>

        <div className="rounded-xl p-8 border" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">{t('firmName')}</label>
              <input
                {...register('firmName')}
                type="text"
                className="w-full px-3.5 py-2.5 rounded-lg text-sm text-white placeholder-slate-500 border outline-none focus:border-cyan-500 transition-colors"
                style={{ background: 'var(--navy)', borderColor: 'var(--navy-border)' }}
                placeholder="Acme Recruiting"
              />
              {errors.firmName && <p className="mt-1 text-xs text-red-400">{errors.firmName.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">{t('email')}</label>
              <input
                {...register('email')}
                type="email"
                className="w-full px-3.5 py-2.5 rounded-lg text-sm text-white placeholder-slate-500 border outline-none focus:border-cyan-500 transition-colors"
                style={{ background: 'var(--navy)', borderColor: 'var(--navy-border)' }}
                placeholder="you@example.com"
              />
              {errors.email && <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">{t('password')}</label>
              <input
                {...register('password')}
                type="password"
                className="w-full px-3.5 py-2.5 rounded-lg text-sm text-white placeholder-slate-500 border outline-none focus:border-cyan-500 transition-colors"
                style={{ background: 'var(--navy)', borderColor: 'var(--navy-border)' }}
                placeholder="••••••••"
              />
              {errors.password && <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">Confirm Password</label>
              <input
                {...register('confirmPassword')}
                type="password"
                className="w-full px-3.5 py-2.5 rounded-lg text-sm text-white placeholder-slate-500 border outline-none focus:border-cyan-500 transition-colors"
                style={{ background: 'var(--navy)', borderColor: 'var(--navy-border)' }}
                placeholder="••••••••"
              />
              {errors.confirmPassword && <p className="mt-1 text-xs text-red-400">{errors.confirmPassword.message}</p>}
            </div>

            {error && (
              <div className="px-3 py-2.5 rounded-lg bg-red-900/30 border border-red-800/50 text-sm text-red-400">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-colors disabled:opacity-50"
              style={{ background: 'var(--blue)' }}
            >
              {loading ? 'Creating account...' : t('createAccount')}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-400">
            {t('hasAccount')}{' '}
            <Link href="/login" className="font-medium" style={{ color: 'var(--cyan)' }}>
              {t('signIn')}
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
