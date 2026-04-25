'use client'
import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Link } from '@/i18n/navigation'
import { superAdminApi, marketingApi } from '@/lib/api'
import type { Tenant, MarketingAccount } from '@/lib/api'

const qc = new QueryClient()

// ── Helpers ────────────────────────────────────────────────────────────────────

const MARKETING_PLANS = ['agency_small', 'agency_medium', 'enterprise']

function planBadgeClass(plan: string): string {
  const map: Record<string, string> = {
    trial: 'badge-discovered', trial_expired: 'badge-info',
    recruiter: 'badge-profiled', agency_small: 'badge-scout',
    agency_medium: 'badge-active', enterprise: 'badge-interviewed',
  }
  return map[plan] ?? 'badge-discovered'
}

function LinkedInIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" style={{ flexShrink: 0 }}>
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
    </svg>
  )
}

// ── Expandable tenant row ──────────────────────────────────────────────────────

function TenantMarketingRow({ tenant }: { tenant: Tenant }) {
  const [expanded, setExpanded] = useState(false)
  const [accounts, setAccounts] = useState<MarketingAccount[] | null>(null)
  const [loadingAccounts, setLoadingAccounts] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [toggleError, setToggleError] = useState<string | null>(null)
  // We don't have marketing settings per-tenant without impersonating,
  // so we track toggle state optimistically from a toggle action
  const [marketingActive, setMarketingActive] = useState<boolean | null>(null)

  const handleExpand = useCallback(async () => {
    if (expanded) { setExpanded(false); return }
    setExpanded(true)
    if (accounts !== null) return
    setLoadingAccounts(true)
    try {
      const data = await marketingApi.getAccounts(tenant.id)
      setAccounts(data)
    } catch {
      setAccounts([])
    } finally {
      setLoadingAccounts(false)
    }
  }, [expanded, accounts, tenant.id])

  const handleToggle = useCallback(async (activate: boolean) => {
    setToggling(true)
    setToggleError(null)
    try {
      await marketingApi.toggleActive(activate, tenant.id)
      setMarketingActive(activate)
    } catch (err: unknown) {
      setToggleError(err instanceof Error ? err.message : 'Toggle failed')
    } finally {
      setToggling(false)
    }
  }, [tenant.id])

  const isEligible = MARKETING_PLANS.includes(tenant.plan)

  return (
    <>
      <tr
        style={{ cursor: 'pointer' }}
        onClick={handleExpand}
      >
        <td className="td-name">
          <div>{tenant.name}</div>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>{tenant.main_contact_email}</div>
        </td>
        <td>
          <span className={`badge ${planBadgeClass(tenant.plan)}`}>{tenant.plan}</span>
        </td>
        <td>
          {!isEligible ? (
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>Not eligible</span>
          ) : marketingActive !== null ? (
            <span className={`badge ${marketingActive ? 'badge-active' : 'badge-paused'}`}>
              {marketingActive ? 'Active' : 'Paused'}
            </span>
          ) : (
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>—</span>
          )}
        </td>
        <td>
          {accounts !== null ? (
            accounts.length > 0 ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#0A66C2', fontSize: 13 }}>
                <LinkedInIcon /> {accounts.length} account{accounts.length !== 1 ? 's' : ''}
              </span>
            ) : (
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>None</span>
            )
          ) : (
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>{expanded ? 'Loading…' : '—'}</span>
          )}
        </td>
        <td onClick={(e) => e.stopPropagation()}>
          {isEligible && (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <button
                className="btn btn-ghost btn-sm"
                style={{ color: '#10b981' }}
                onClick={() => handleToggle(true)}
                disabled={toggling || marketingActive === true}
                title="Enable marketing for this tenant"
              >
                Enable
              </button>
              <button
                className="btn btn-ghost btn-sm"
                style={{ color: 'var(--amber)' }}
                onClick={() => handleToggle(false)}
                disabled={toggling || marketingActive === false}
                title="Pause marketing for this tenant"
              >
                Pause
              </button>
            </div>
          )}
          {toggleError && (
            <div style={{ fontSize: 11, color: 'var(--red)', marginTop: 4 }}>{toggleError}</div>
          )}
        </td>
      </tr>

      {expanded && (
        <tr>
          <td colSpan={5} style={{ background: 'var(--navy)', padding: 0 }}>
            <div style={{ padding: '12px 20px 16px' }}>
              <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
                Connected LinkedIn Accounts
              </div>
              {loadingAccounts ? (
                <div style={{ fontSize: 13, color: 'var(--muted)' }}>Loading accounts…</div>
              ) : !isEligible ? (
                <div style={{ fontSize: 13, color: 'var(--muted)' }}>Plan not eligible for marketing module (requires Agency Small+).</div>
              ) : accounts === null || accounts.length === 0 ? (
                <div style={{ fontSize: 13, color: 'var(--muted)' }}>No LinkedIn accounts connected.</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {accounts.map((acct) => (
                    <div key={acct.id} style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '8px 12px', background: 'var(--card)',
                      borderRadius: 6, border: '1px solid var(--border)',
                      maxWidth: 480,
                    }}>
                      <div style={{
                        width: 26, height: 26, borderRadius: 5, flexShrink: 0,
                        background: '#0A66C2', display: 'flex', alignItems: 'center',
                        justifyContent: 'center', color: '#fff',
                      }}>
                        <LinkedInIcon size={14} />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--white)' }}>{acct.account_name}</div>
                        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1 }}>
                          {acct.account_type_label}
                          {acct.is_token_expiring_soon && (
                            <span style={{ color: 'var(--amber)', marginLeft: 8 }}>⚠ Token expiring soon</span>
                          )}
                        </div>
                      </div>
                      <span className={`badge ${acct.is_active ? 'badge-active' : 'badge-paused'}`} style={{ flexShrink: 0 }}>
                        {acct.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ── Main content ───────────────────────────────────────────────────────────────

function SuperAdminMarketingContent() {
  const [planFilter, setPlanFilter] = useState<string>('')

  const { data: tenants, isLoading } = useQuery({
    queryKey: ['super-admin-tenants-marketing', planFilter],
    queryFn: () => superAdminApi.getTenants({ limit: 200, plan: planFilter || undefined }),
  })

  const allTenants = tenants?.items ?? []
  const eligible = allTenants.filter((t) => MARKETING_PLANS.includes(t.plan))
  const totalEligible = eligible.length

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 24 }}>

      {/* Back link + header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <Link
          href="/super-admin"
          style={{ fontSize: 13, color: 'var(--muted)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}
        >
          ← Super Admin
        </Link>
        <span style={{ color: 'var(--border)' }}>/</span>
        <span style={{ fontSize: 13, color: 'var(--white)', fontWeight: 600 }}>Marketing</span>
      </div>

      <div className="sa-alert" style={{ marginBottom: 20 }}>
        🛡 Viewing marketing module status across all tenants. You can enable or pause any tenant's automation from this page.
      </div>

      {/* Summary stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 20, maxWidth: 640 }}>
        <div className="stat-card">
          <div className="stat-label">Eligible Tenants</div>
          <div className="stat-value">{isLoading ? '—' : totalEligible}</div>
        </div>
        <div className="stat-card green">
          <div className="stat-label">Agency Small+</div>
          <div className="stat-value">{isLoading ? '—' : allTenants.filter(t => t.plan === 'agency_small').length}</div>
        </div>
        <div className="stat-card gold">
          <div className="stat-label">Agency Medium+</div>
          <div className="stat-value">{isLoading ? '—' : allTenants.filter(t => ['agency_medium', 'enterprise'].includes(t.plan)).length}</div>
        </div>
      </div>

      {/* Plan filter */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
        {(['', 'agency_small', 'agency_medium', 'enterprise'] as const).map((p) => (
          <button
            key={p}
            className={`btn btn-sm ${planFilter === p ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setPlanFilter(p)}
          >
            {p || 'All Plans'}
          </button>
        ))}
      </div>

      {/* Tenants table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Tenant Marketing Status</div>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>
            {isLoading ? '…' : `${planFilter ? eligible.length : allTenants.length} tenant${(planFilter ? eligible.length : allTenants.length) !== 1 ? 's' : ''}`}
          </span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Tenant</th>
                <th>Plan</th>
                <th>Marketing</th>
                <th>Accounts</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>Loading tenants…</td></tr>
              )}
              {!isLoading && allTenants.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>No tenants found.</td></tr>
              )}
              {allTenants.map((tenant) => (
                <TenantMarketingRow key={tenant.id} tenant={tenant} />
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ padding: '10px 20px', borderTop: '1px solid var(--border)', fontSize: 12, color: 'var(--muted)' }}>
          Click a row to expand and view connected LinkedIn accounts. Enable / Pause buttons update immediately via the API.
        </div>
      </div>
    </div>
  )
}

export default function SuperAdminMarketingPage() {
  return (
    <QueryClientProvider client={qc}>
      <SuperAdminMarketingContent />
    </QueryClientProvider>
  )
}
