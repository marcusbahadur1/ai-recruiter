'use client'
import { useTranslations } from 'next-intl'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { superAdminApi } from '@/lib/api'

const qc = new QueryClient()

function planBadgeClass(plan: string): string {
  const map: Record<string, string> = {
    trial: 'badge-discovered', trial_expired: 'badge-info',
    recruiter: 'badge-profiled', agency_small: 'badge-scout',
    agency_medium: 'badge-active', enterprise: 'badge-interviewed',
  }
  return map[plan] ?? 'badge-discovered'
}

function severityBadgeClass(severity: string): string {
  const map: Record<string, string> = {
    info: 'badge-discovered', success: 'badge-active',
    warning: 'badge-scout', error: 'badge-info',
  }
  return map[severity] ?? 'badge-discovered'
}

function SuperAdminContent() {
  const t = useTranslations('superAdmin')
  const queryClient = useQueryClient()
  const [section, setSection] = useState<'tenants' | 'platformKeys' | 'systemHealth' | 'promoCodes' | 'auditLog'>('tenants')

  // Platform stats — drives the 4 stat cards
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['super-admin-stats'],
    queryFn: () => superAdminApi.getStats(),
  })

  // Tenants list
  const { data: tenants, isLoading: tenantsLoading } = useQuery({
    queryKey: ['super-admin-tenants'],
    queryFn: () => superAdminApi.getTenants(),
    enabled: section === 'tenants',
  })

  // System health
  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => superAdminApi.getSystemHealth(),
    enabled: section === 'systemHealth',
  })

  // Promo codes
  const { data: promoCodes, isLoading: promoLoading } = useQuery({
    queryKey: ['super-admin-promo-codes'],
    queryFn: () => superAdminApi.getPromoCodes(),
    enabled: section === 'promoCodes',
  })

  // Audit log
  const [auditCategory, setAuditCategory] = useState<string>('')
  const { data: auditLog, isLoading: auditLoading } = useQuery({
    queryKey: ['super-admin-audit', auditCategory],
    queryFn: () => superAdminApi.getAuditLog({ limit: 50, event_category: auditCategory || undefined }),
    enabled: section === 'auditLog',
  })

  const impersonateMutation = useMutation({
    mutationFn: (tenantId: string) => superAdminApi.impersonate(tenantId),
    onSuccess: () => { window.location.href = '/en' },
  })

  // Promo code creation state
  const [promoForm, setPromoForm] = useState({ code: '', type: 'credits', value: '', expires_at: '', max_uses: '', is_active: true })
  const [promoError, setPromoError] = useState('')
  const createPromoMutation = useMutation({
    mutationFn: () => superAdminApi.createPromoCode({
      code: promoForm.code,
      type: promoForm.type,
      value: parseFloat(promoForm.value),
      expires_at: promoForm.expires_at || null,
      max_uses: promoForm.max_uses ? parseInt(promoForm.max_uses) : null,
      is_active: promoForm.is_active,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['super-admin-promo-codes'] })
      setPromoForm({ code: '', type: 'credits', value: '', expires_at: '', max_uses: '', is_active: true })
      setPromoError('')
    },
    onError: (e: Error) => setPromoError(e.message),
  })

  const tenantList = tenants?.items ?? []

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
          <div className="stat-value">{statsLoading ? '—' : stats?.total_tenants}</div>
        </div>
        <div className="stat-card green">
          <div className="stat-label">Active Subscriptions</div>
          <div className="stat-value">{statsLoading ? '—' : stats?.active_subscriptions}</div>
        </div>
        <div className="stat-card gold">
          <div className="stat-label">MRR (AUD)</div>
          <div className="stat-value">{statsLoading ? '—' : `$${(stats?.mrr_aud ?? 0).toLocaleString()}`}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Failed Tasks (24h)</div>
          <div className="stat-value" style={{ color: (stats?.failed_tasks_24h ?? 0) > 0 ? 'var(--red)' : undefined }}>
            {statsLoading ? '—' : stats?.failed_tasks_24h}
          </div>
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
        <div className="card">
          <div className="card-header">
            <div className="card-title">All Tenants</div>
            <span style={{ fontSize: 12, color: 'var(--muted)' }}>{tenants?.total ?? '—'} total</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Firm</th><th>Plan</th><th>Credits</th><th>Status</th><th>Joined</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {tenantsLoading && (
                  <tr><td colSpan={6} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>Loading tenants…</td></tr>
                )}
                {!tenantsLoading && tenantList.length === 0 && (
                  <tr><td colSpan={6} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>No tenants found.</td></tr>
                )}
                {tenantList.map((tenant) => (
                  <tr key={tenant.id}>
                    <td className="td-name">
                      <div>{tenant.name}</div>
                      <div style={{ fontSize: 11, color: 'var(--muted)' }}>{tenant.main_contact_email}</div>
                    </td>
                    <td><span className={`badge ${planBadgeClass(tenant.plan)}`}>{tenant.plan}</span></td>
                    <td>{tenant.credits_remaining ?? '—'}</td>
                    <td><span className={`badge ${tenant.is_active ? 'badge-active' : 'badge-paused'}`}>{tenant.is_active ? 'Active' : 'Inactive'}</span></td>
                    <td className="muted" style={{ fontSize: 12 }}>{new Date(tenant.created_at).toLocaleDateString()}</td>
                    <td style={{ display: 'flex', gap: 6 }} onClick={(e) => e.stopPropagation()}>
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
              { label: 'Celery Queue Depth', value: healthLoading ? '…' : (health?.celery_queue_depth ?? '—') },
              { label: 'Failed Tasks (24h)', value: healthLoading ? '…' : (stats?.failed_tasks_24h ?? '—') },
              { label: 'Active Workers',     value: healthLoading ? '…' : (health?.worker_count ?? '—') },
              { label: 'Redis Status',       value: healthLoading ? '…' : (health?.redis_status ?? '—') },
            ].map(({ label, value }) => (
              <div key={label} className="stat-card">
                <div className="stat-label">{label}</div>
                <div className="stat-value" style={{ fontSize: 24 }}>{String(value)}</div>
              </div>
            ))}
          </div>
          <div className="card">
            <div className="card-header">
              <div className="card-title">Worker Status</div>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                {health ? `Status: ${health.status}` : ''}
              </span>
            </div>
            <p style={{ padding: '16px 20px', color: 'var(--muted)', fontSize: 13 }}>
              Failed task details are visible in the Audit Log tab (filter by category).
              Celery task failures are recorded as error-severity audit events.
            </p>
          </div>
        </>
      )}

      {section === 'promoCodes' && (
        <>
          {/* Create form */}
          <div className="card" style={{ maxWidth: 560, marginBottom: 20 }}>
            <div className="card-header"><div className="card-title">Create Promo Code</div></div>
            <div style={{ padding: '0 20px 20px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label className="form-label">Code</label>
                  <input className="form-input" placeholder="LAUNCH50" value={promoForm.code}
                    onChange={e => setPromoForm(f => ({ ...f, code: e.target.value.toUpperCase() }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Type</label>
                  <select className="form-input" value={promoForm.type}
                    onChange={e => setPromoForm(f => ({ ...f, type: e.target.value }))}>
                    <option value="credits">Credits</option>
                    <option value="discount_pct">Discount %</option>
                    <option value="full_access">Full Access</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Value</label>
                  <input className="form-input" type="number" placeholder="100" value={promoForm.value}
                    onChange={e => setPromoForm(f => ({ ...f, value: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Max Uses (blank = unlimited)</label>
                  <input className="form-input" type="number" placeholder="—" value={promoForm.max_uses}
                    onChange={e => setPromoForm(f => ({ ...f, max_uses: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Expires At (optional)</label>
                  <input className="form-input" type="datetime-local" value={promoForm.expires_at}
                    onChange={e => setPromoForm(f => ({ ...f, expires_at: e.target.value }))} />
                </div>
              </div>
              {promoError && <p style={{ color: 'var(--red)', fontSize: 13, margin: '8px 0' }}>{promoError}</p>}
              <button className="btn btn-primary" style={{ marginTop: 8 }}
                onClick={() => createPromoMutation.mutate()}
                disabled={createPromoMutation.isPending || !promoForm.code || !promoForm.value}>
                {createPromoMutation.isPending ? 'Creating…' : 'Create Code'}
              </button>
            </div>
          </div>

          {/* Promo codes table */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">Platform Promo Codes</div>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>{promoCodes?.total ?? '—'} total</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Code</th><th>Type</th><th>Value</th><th>Uses</th><th>Max Uses</th><th>Expires</th><th>Status</th></tr>
                </thead>
                <tbody>
                  {promoLoading && (
                    <tr><td colSpan={7} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>Loading…</td></tr>
                  )}
                  {!promoLoading && (promoCodes?.items ?? []).length === 0 && (
                    <tr><td colSpan={7} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>No promo codes yet.</td></tr>
                  )}
                  {(promoCodes?.items ?? []).map(c => (
                    <tr key={c.id}>
                      <td style={{ fontFamily: 'DM Mono, monospace', fontWeight: 600 }}>{c.code}</td>
                      <td>{c.type}</td>
                      <td>{c.value}</td>
                      <td>{c.uses_count}</td>
                      <td>{c.max_uses ?? '∞'}</td>
                      <td className="muted" style={{ fontSize: 12 }}>{c.expires_at ? new Date(c.expires_at).toLocaleDateString() : '—'}</td>
                      <td><span className={`badge ${c.is_active ? 'badge-active' : 'badge-paused'}`}>{c.is_active ? 'Active' : 'Inactive'}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {section === 'auditLog' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">Platform Audit Log</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {(['', 'payment', 'system'] as const).map(cat => (
                <button key={cat} className={`btn btn-sm ${auditCategory === cat ? 'btn-primary' : 'btn-ghost'}`}
                  onClick={() => setAuditCategory(cat)}>
                  {cat || 'All'}
                </button>
              ))}
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Time</th><th>Category</th><th>Severity</th><th>Event</th><th>Summary</th></tr>
              </thead>
              <tbody>
                {auditLoading && (
                  <tr><td colSpan={5} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>Loading…</td></tr>
                )}
                {!auditLoading && (auditLog?.items ?? []).length === 0 && (
                  <tr><td colSpan={5} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>No audit events found.</td></tr>
                )}
                {(auditLog?.items ?? []).map(e => (
                  <tr key={e.id}>
                    <td className="muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                      {new Date(e.created_at).toLocaleString()}
                    </td>
                    <td><span className="badge badge-discovered">{e.event_category}</span></td>
                    <td><span className={`badge ${severityBadgeClass(e.severity)}`}>{e.severity}</span></td>
                    <td style={{ fontFamily: 'DM Mono, monospace', fontSize: 11 }}>{e.event_type}</td>
                    <td style={{ fontSize: 13 }}>{e.summary}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default function SuperAdminPage() {
  return <QueryClientProvider client={qc}><SuperAdminContent /></QueryClientProvider>
}
