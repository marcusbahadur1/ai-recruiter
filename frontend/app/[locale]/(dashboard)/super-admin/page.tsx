'use client'
import { useTranslations } from 'next-intl'
import { useQuery, useMutation } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { superAdminApi } from '@/lib/api'

const qc = new QueryClient()

const SECTIONS = ['tenants', 'platformKeys', 'promoCodes', 'systemHealth', 'auditLog'] as const

function SuperAdminContent() {
  const t = useTranslations('superAdmin')
  const [section, setSection] = useState<typeof SECTIONS[number]>('tenants')

  const { data: tenants, isLoading: tenantsLoading } = useQuery({
    queryKey: ['super-admin-tenants'],
    queryFn: () => superAdminApi.getTenants(),
    enabled: section === 'tenants',
  })

  const { data: health } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => superAdminApi.getSystemHealth(),
    enabled: section === 'systemHealth',
  })

  const impersonateMutation = useMutation({
    mutationFn: (tenantId: string) => superAdminApi.impersonate(tenantId),
    onSuccess: () => { window.location.href = '/en' },
  })

  const PLAN_COLORS: Record<string, string> = {
    free: '#94A3B8', casual: '#3B82F6', individual: '#8B5CF6',
    small_firm: '#10B981', mid_firm: '#F59E0B', enterprise: '#00C2E0',
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: '#EF444420' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#EF4444" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        </div>
        <h1 className="text-2xl font-bold text-white">{t('title')}</h1>
      </div>

      {/* Section tabs */}
      <div className="flex flex-wrap gap-2">
        {SECTIONS.map((s) => (
          <button key={s} onClick={() => setSection(s)}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            style={{
              background: section === s ? 'var(--blue)' : 'var(--navy-light)',
              color: section === s ? 'white' : '#94A3B8',
              border: `1px solid ${section === s ? 'var(--blue)' : 'var(--navy-border)'}`,
            }}>
            {t(s)}
          </button>
        ))}
      </div>

      {section === 'tenants' && (
        <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          <table className="w-full">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--navy-border)' }}>
                {['Firm', 'Plan', 'Credits', 'Status', 'Created', 'Actions'].map((h) => (
                  <th key={h} className="text-left px-5 py-3.5 text-xs font-medium text-slate-400 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tenantsLoading && <tr><td colSpan={6} className="px-5 py-8 text-center text-slate-400 text-sm">Loading tenants...</td></tr>}
              {tenants?.items?.map((tenant) => (
                <tr key={tenant.id} className="border-b hover:bg-white/[0.02] transition-colors" style={{ borderColor: 'var(--navy-border)' }}>
                  <td className="px-5 py-4">
                    <p className="text-white font-medium text-sm">{tenant.name}</p>
                    <p className="text-slate-500 text-xs mt-0.5">{tenant.main_contact_email}</p>
                  </td>
                  <td className="px-5 py-4">
                    <span className="px-2.5 py-1 rounded-full text-xs font-medium"
                      style={{ background: (PLAN_COLORS[tenant.plan] ?? '#94A3B8') + '20', color: PLAN_COLORS[tenant.plan] ?? '#94A3B8' }}>
                      {tenant.plan}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-slate-300 text-sm">{tenant.credits_remaining}</td>
                  <td className="px-5 py-4">
                    <span className="px-2 py-0.5 rounded text-xs font-medium"
                      style={{ background: tenant.is_active ? '#10B98120' : '#EF444420', color: tenant.is_active ? '#10B981' : '#EF4444' }}>
                      {tenant.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-slate-400 text-xs">{new Date(tenant.created_at).toLocaleDateString()}</td>
                  <td className="px-5 py-4">
                    <button
                      onClick={() => impersonateMutation.mutate(tenant.id)}
                      disabled={impersonateMutation.isPending}
                      className="px-3 py-1.5 rounded-md text-xs font-medium text-slate-300 hover:text-white border transition-colors hover:bg-white/5 disabled:opacity-50"
                      style={{ borderColor: 'var(--navy-border)' }}>
                      {t('impersonate')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {section === 'platformKeys' && (
        <div className="rounded-xl border p-6 space-y-5 max-w-lg" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          <h2 className="text-base font-semibold text-white">{t('platformKeys')}</h2>
          {[
            { label: 'Anthropic API Key', placeholder: 'sk-ant-...' },
            { label: 'OpenAI API Key', placeholder: 'sk-...' },
            { label: 'SendGrid API Key', placeholder: 'SG...' },
            { label: 'ScrapingDog API Key', placeholder: '' },
            { label: 'BrightData API Key', placeholder: '' },
          ].map(({ label, placeholder }) => (
            <div key={label}>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">{label}</label>
              <input type="password" placeholder={placeholder || '••••••••••••••••'}
                className="w-full px-3.5 py-2.5 rounded-lg text-sm text-white placeholder-slate-500 border outline-none focus:border-cyan-500 transition-colors"
                style={{ background: 'var(--navy)', borderColor: 'var(--navy-border)' }}/>
            </div>
          ))}
          <button className="px-5 py-2.5 rounded-lg text-sm font-medium text-white" style={{ background: 'var(--blue)' }}>Save Platform Keys</button>
        </div>
      )}

      {section === 'systemHealth' && (
        <div className="grid grid-cols-2 gap-4 max-w-2xl">
          {[
            { label: 'Celery Queue Depth', value: health?.queue_depth ?? '—' },
            { label: 'Failed Tasks (24h)', value: health?.failed_tasks ?? '—' },
            { label: 'Active Workers', value: health?.active_workers ?? '—' },
            { label: 'Redis Status', value: health?.redis_status ?? '—' },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-xl border p-5" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
              <p className="text-slate-400 text-xs font-medium uppercase tracking-wide mb-2">{label}</p>
              <p className="text-2xl font-bold text-white">{String(value)}</p>
            </div>
          ))}
        </div>
      )}

      {(section === 'promoCodes' || section === 'auditLog') && (
        <div className="rounded-xl border p-8 text-center" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          <p className="text-slate-400 text-sm">{section === 'promoCodes' ? 'Promo code management' : 'Platform audit log'} — coming soon.</p>
        </div>
      )}
    </div>
  )
}

export default function SuperAdminPage() {
  return <QueryClientProvider client={qc}><SuperAdminContent /></QueryClientProvider>
}
