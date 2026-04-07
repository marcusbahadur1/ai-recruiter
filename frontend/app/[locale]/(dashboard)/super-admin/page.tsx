'use client'
import { useTranslations } from 'next-intl'
import { useQuery, useMutation } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { superAdminApi } from '@/lib/api'

const qc = new QueryClient()

function planBadgeClass(plan: string): string {
  const map: Record<string, string> = {
    free: 'badge-discovered', casual: 'badge-info', individual: 'badge-profiled',
    small_firm: 'badge-scout', mid_firm: 'badge-active', enterprise: 'badge-interviewed',
  }
  return map[plan] ?? 'badge-discovered'
}

function SuperAdminContent() {
  const t = useTranslations('superAdmin')
  const [section, setSection] = useState<'tenants' | 'platformKeys' | 'systemHealth' | 'promoCodes' | 'auditLog'>('tenants')

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

  return (
    <div style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', padding: '24px' }}>
      {/* Alert */}
      <div className="sa-alert">
        🛡 Super Admin Mode — you are viewing platform-wide data across all tenants. Actions here affect all customers.
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16, marginBottom: 20 }}>
        <div className="stat-card">
          <div className="stat-label">Total Tenants</div>
          <div className="stat-value">{tenants?.total ?? 34}</div>
          <div className="stat-change up">↑ 3 this week</div>
        </div>
        <div className="stat-card green">
          <div className="stat-label">Active Subscriptions</div>
          <div className="stat-value">{tenants?.items?.filter((t: { is_active: boolean }) => t.is_active).length ?? 28}</div>
        </div>
        <div className="stat-card gold">
          <div className="stat-label">MRR (AUD)</div>
          <div className="stat-value">$41k</div>
          <div className="stat-change up">↑ 12% MoM</div>
        </div>
        <div className="stat-card red">
          <div className="stat-label">Failed Tasks</div>
          <div className="stat-value">{String(health?.failed_tasks ?? 3)}</div>
          <div className="stat-change down">Needs attention</div>
        </div>
      </div>

      {/* Section tabs */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20 }}>
        {(['tenants', 'platformKeys', 'systemHealth', 'promoCodes', 'auditLog'] as const).map((s) => (
          <button key={s} onClick={() => setSection(s)} className={`btn ${section === s ? 'btn-primary' : 'btn-ghost'}`}>
            {t(s)}
          </button>
        ))}
      </div>

      {section === 'tenants' && (
        <div className="grid-2">
          {/* Platform Keys */}
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">Platform API Keys</div>
                <div className="card-sub">Used when tenants don&apos;t supply their own</div>
              </div>
            </div>
            {[
              { label: 'Anthropic', val: 'sk-ant-•••••••••••••••••••••••' },
              { label: 'OpenAI',    val: 'sk-•••••••••••••••••••••••' },
              { label: 'ScrapingDog', val: 'sd_live_•••••••••••••••••' },
              { label: 'BrightData', val: 'bd_•••••••••••••••••••••' },
              { label: 'SendGrid',  val: 'SG.•••••••••••••••••••••' },
            ].map(({ label, val }) => (
              <div key={label} className="api-key-row">
                <div className="api-key-name">{label}</div>
                <div className="api-key-val">{val}</div>
                <div className="api-key-status ok">✓</div>
                <button className="btn btn-ghost btn-sm">Edit</button>
              </div>
            ))}
            <div style={{ marginTop: 12 }}>
              <label className="form-label">Default AI Provider</label>
              <select className="form-select">
                <option>Anthropic Claude (claude-sonnet-4)</option>
                <option>OpenAI (gpt-4o)</option>
              </select>
            </div>
          </div>

          {/* All Tenants */}
          <div className="card">
            <div className="card-header"><div className="card-title">All Tenants</div></div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Firm</th><th>Plan</th><th>Credits</th><th>Status</th><th>Actions</th></tr>
                </thead>
                <tbody>
                  {tenantsLoading && (
                    <tr><td colSpan={5} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>Loading tenants...</td></tr>
                  )}
                  {tenants?.items?.map((tenant: { id: string; name: string; main_contact_email?: string; plan: string; credits_remaining?: number; is_active: boolean }) => (
                    <tr key={tenant.id}>
                      <td className="td-name">{tenant.name}</td>
                      <td><span className={`badge ${planBadgeClass(tenant.plan)}`}>{tenant.plan}</span></td>
                      <td>{tenant.credits_remaining ?? '—'}</td>
                      <td><span className={`badge ${tenant.is_active ? 'badge-active' : 'badge-paused'}`}>{tenant.is_active ? 'Active' : 'Paused'}</span></td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <button className="btn btn-ghost btn-sm"
                          onClick={() => impersonateMutation.mutate(tenant.id)}
                          disabled={impersonateMutation.isPending}>
                          {t('impersonate')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {section === 'platformKeys' && (
        <div className="card" style={{ maxWidth: 520 }}>
          <div className="card-header"><div className="card-title">{t('platformKeys')}</div></div>
          {[
            { label: 'Anthropic API Key',  placeholder: 'sk-ant-...' },
            { label: 'OpenAI API Key',     placeholder: 'sk-...' },
            { label: 'SendGrid API Key',   placeholder: 'SG...' },
            { label: 'ScrapingDog API Key', placeholder: 'sd_live_...' },
            { label: 'BrightData API Key', placeholder: 'bd_...' },
          ].map(({ label, placeholder }) => (
            <div key={label} className="form-group">
              <label className="form-label">{label}</label>
              <input type="password" placeholder={placeholder || '••••••••••••••••'} className="form-input"/>
            </div>
          ))}
          <button className="btn btn-primary">Save Platform Keys</button>
        </div>
      )}

      {section === 'systemHealth' && (
        <>
          <div className="grid-2" style={{ maxWidth: 640, marginBottom: 20 }}>
            {[
              { label: 'Celery Queue Depth', value: health?.queue_depth ?? '—' },
              { label: 'Failed Tasks (24h)', value: health?.failed_tasks ?? '—' },
              { label: 'Active Workers',     value: health?.active_workers ?? '—' },
              { label: 'Redis Status',       value: health?.redis_status ?? '—' },
            ].map(({ label, value }) => (
              <div key={label} className="stat-card">
                <div className="stat-label">{label}</div>
                <div className="stat-value" style={{ fontSize: 24 }}>{String(value)}</div>
              </div>
            ))}
          </div>

          <div className="card">
            <div className="card-header"><div className="card-title">System Health — Failed Tasks</div></div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Task</th><th>Tenant</th><th>Error</th><th>Attempts</th><th>Time</th><th>Action</th></tr>
                </thead>
                <tbody>
                  <tr>
                    <td style={{ fontFamily: 'DM Mono, monospace', fontSize: 11 }}>scout.send_outreach</td>
                    <td className="muted">Acme Recruit</td>
                    <td style={{ color: 'var(--red)', fontSize: 12 }}>SendGrid 422 invalid address</td>
                    <td>3/3</td>
                    <td className="muted">5 min ago</td>
                    <td onClick={(e) => e.stopPropagation()}><button className="btn btn-ghost btn-sm">Retry</button></td>
                  </tr>
                  <tr>
                    <td style={{ fontFamily: 'DM Mono, monospace', fontSize: 11 }}>screener.poll_mailboxes</td>
                    <td className="muted">TechHire AU</td>
                    <td style={{ color: 'var(--amber)', fontSize: 12 }}>IMAP auth timeout</td>
                    <td>2/3</td>
                    <td className="muted">12 min ago</td>
                    <td onClick={(e) => e.stopPropagation()}><button className="btn btn-ghost btn-sm">Retry</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {(section === 'promoCodes' || section === 'auditLog') && (
        <div className="empty-state">
          <div className="empty-icon">🔧</div>
          <div className="empty-text">{section === 'promoCodes' ? 'Promo code management' : 'Platform audit log'} — coming soon.</div>
        </div>
      )}
    </div>
  )
}

export default function SuperAdminPage() {
  return <QueryClientProvider client={qc}><SuperAdminContent /></QueryClientProvider>
}
