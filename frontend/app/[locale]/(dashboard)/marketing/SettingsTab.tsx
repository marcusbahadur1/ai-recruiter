'use client'
import { useState, useEffect, useRef, KeyboardEvent } from 'react'
import { useLocale } from 'next-intl'
import { marketingApi } from '@/lib/api'
import type {
  MarketingAccount,
  IcpConfig, ChannelConfig, SignalConfig, OutreachLimits, TenantModeConfig,
  TenantStatus, TenantUsageRow, AdminTenantUsage,
} from '@/lib/api'

// ── Defaults ───────────────────────────────────────────────────────────────────

const DEFAULT_ICP: IcpConfig = {
  target_titles: [], company_types: [],
  size_min: 5, size_max: 200, locations: [], min_score: 7,
}
const DEFAULT_SIGNAL: SignalConfig = {
  hiring_spike_threshold: 3, scrape_frequency_hours: 6,
  monitor_pain_posts: true, monitor_growth_signals: true,
  auto_enroll: false, require_approval: true,
}
const DEFAULT_OUTREACH: OutreachLimits = {
  linkedin_connects_per_day: 20, linkedin_dms_per_day: 30,
  emails_per_day: 50, window_start_utc: '08:00',
  window_end_utc: '17:00', skip_weekends: true,
}
const DEFAULT_TENANT_MODE: TenantModeConfig = {
  min_plan: 'agency_small', max_prospects_per_month: 500, max_sequences: 3,
}

// ── Shared style helpers ───────────────────────────────────────────────────────

const S = {
  card: {
    background: 'var(--card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: 16,
  } as React.CSSProperties,
  label: {
    display: 'block' as const, fontSize: 11, color: 'var(--muted)',
    marginBottom: 4, fontWeight: 500,
  } as React.CSSProperties,
  field: { marginBottom: 12 } as React.CSSProperties,
  input: {
    background: 'var(--navy-light)', border: '1px solid var(--border-mid)',
    borderRadius: 6, padding: '5px 8px', fontSize: 12,
    color: 'var(--white)', outline: 'none', width: '100%',
  } as React.CSSProperties,
  sectionHead: {
    fontSize: 12, fontWeight: 600 as const, marginBottom: 12,
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    color: 'var(--white)',
  } as React.CSSProperties,
  limitRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '7px 0', borderBottom: '1px solid var(--border)', fontSize: 12,
  } as React.CSSProperties,
  chRow: {
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '9px 0', borderBottom: '1px solid var(--border)',
  } as React.CSSProperties,
  chBtn: {
    fontSize: 11, padding: '4px 10px', borderRadius: 6,
    border: '1px solid var(--border-mid)', cursor: 'pointer',
    background: 'none', color: 'var(--muted)', whiteSpace: 'nowrap' as const,
    flexShrink: 0,
  } as React.CSSProperties,
}

// ── TagInput ───────────────────────────────────────────────────────────────────

function TagInput({
  tags, onChange, color = 'blue', placeholder = 'Type and press Enter',
}: {
  tags: string[]
  onChange: (tags: string[]) => void
  color?: 'blue' | 'purple' | 'green'
  placeholder?: string
}) {
  const [val, setVal] = useState('')
  const ref = useRef<HTMLInputElement>(null)

  const palette = {
    blue:   { bg: 'rgba(27,108,168,0.3)',    color: '#60a5fa' },
    purple: { bg: 'rgba(139,92,246,0.2)',     color: '#a78bfa' },
    green:  { bg: 'var(--green-dim)',          color: 'var(--green)' },
  }[color]

  function commit(v: string) {
    const t = v.trim()
    if (t && !tags.includes(t)) onChange([...tags, t])
    setVal('')
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault(); commit(val)
    } else if (e.key === 'Backspace' && !val && tags.length > 0) {
      onChange(tags.slice(0, -1))
    }
  }

  return (
    <div
      onClick={() => ref.current?.focus()}
      style={{
        display: 'flex', flexWrap: 'wrap', gap: 4,
        padding: '5px 8px', border: '1px solid var(--border-mid)',
        borderRadius: 8, minHeight: 36, cursor: 'text',
        background: 'var(--navy-light)',
      }}
    >
      {tags.map(tag => (
        <span key={tag} style={{
          display: 'inline-flex', alignItems: 'center', gap: 3,
          padding: '2px 8px', borderRadius: 20, fontSize: 11, fontWeight: 500,
          background: palette.bg, color: palette.color,
        }}>
          {tag}
          <button
            type="button"
            onClick={e => { e.stopPropagation(); onChange(tags.filter(t => t !== tag)) }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', opacity: 0.7, lineHeight: 1, color: 'inherit', padding: 0, fontSize: 13 }}
          >×</button>
        </span>
      ))}
      <input
        ref={ref}
        value={val}
        onChange={e => setVal(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => val.trim() && commit(val)}
        placeholder={tags.length === 0 ? placeholder : ''}
        style={{
          flex: 1, minWidth: 100, background: 'transparent', border: 'none',
          outline: 'none', fontSize: 11, color: 'var(--white)', padding: '2px 4px',
        }}
      />
    </div>
  )
}

// ── Toggle ─────────────────────────────────────────────────────────────────────

function Toggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={on}
      style={{
        width: 32, height: 18, borderRadius: 9,
        background: on ? 'var(--blue)' : 'rgba(255,255,255,0.15)',
        position: 'relative', cursor: 'pointer', border: 'none',
        flexShrink: 0, transition: 'background 0.2s',
      }}
    >
      <span style={{
        position: 'absolute', width: 12, height: 12, borderRadius: '50%',
        background: '#fff', top: 3, transition: 'left 0.2s',
        left: on ? 17 : 3,
      }} />
    </button>
  )
}

// ── Status badge ───────────────────────────────────────────────────────────────

function StatusBadge({ connected }: { connected: boolean }) {
  return (
    <span style={{
      fontSize: 10, padding: '2px 8px', borderRadius: 20, fontWeight: 600,
      background: connected ? 'var(--green-dim)' : 'rgba(255,255,255,0.08)',
      color: connected ? 'var(--green)' : 'var(--muted)',
      whiteSpace: 'nowrap', flexShrink: 0,
    }}>
      {connected ? 'Connected' : 'Not set'}
    </span>
  )
}

// ── Key-edit inline panel ──────────────────────────────────────────────────────

function KeyEditRow({
  value, placeholder, onDone, onCancel,
}: {
  value: string
  placeholder: string
  onDone: (key: string) => void
  onCancel: () => void
}) {
  const [v, setV] = useState(value)
  return (
    <div style={{ padding: '6px 0', display: 'flex', gap: 6 }}>
      <input
        autoFocus
        type="text"
        value={v}
        onChange={e => setV(e.target.value)}
        placeholder={placeholder}
        style={{ ...S.input, flex: 1 }}
      />
      <button style={{ ...S.chBtn, color: 'var(--cyan)' }} onClick={() => onDone(v)}>Done</button>
      <button style={S.chBtn} onClick={onCancel}>Cancel</button>
    </div>
  )
}

// ── Channel icon helper ────────────────────────────────────────────────────────

function ChIcon({ bg, color, children }: { bg: string; color: string; children: React.ReactNode }) {
  return (
    <div style={{
      width: 30, height: 30, borderRadius: 6, display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: bg, color, fontSize: 14, flexShrink: 0,
    }}>
      {children}
    </div>
  )
}

// ── ChMeta ─────────────────────────────────────────────────────────────────────

function ChMeta({ title, sub }: { title: string; sub: string }) {
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: 11, fontWeight: 500 }}>{title}</div>
      <div style={{ fontSize: 10, color: 'var(--muted)' }}>{sub}</div>
    </div>
  )
}

// ── Main component ──────────────────────────────────────────────────────────────

export default function SettingsTab({ tenantStatus }: { tenantStatus?: TenantStatus | null }) {
  const locale = useLocale()
  const isSuperAdmin = tenantStatus?.is_super_admin ?? true  // default true if unknown (super admin view)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [adminUsage, setAdminUsage] = useState<TenantUsageRow[]>([])

  const [icp, setIcp] = useState<IcpConfig>(DEFAULT_ICP)
  const [channel, setChannel] = useState<ChannelConfig>({})
  const [signal, setSignal] = useState<SignalConfig>(DEFAULT_SIGNAL)
  const [outreach, setOutreach] = useState<OutreachLimits>(DEFAULT_OUTREACH)
  const [tenantModeEnabled, setTenantModeEnabled] = useState(false)
  const [tenantMode, setTenantMode] = useState<TenantModeConfig>(DEFAULT_TENANT_MODE)

  const [linkedInAccount, setLinkedInAccount] = useState<MarketingAccount | null>(null)

  // API key edit state
  const [bdEdit, setBdEdit] = useState(false)
  const [hunterEdit, setHunterEdit] = useState(false)

  // SMTP inline form
  const [smtpOpen, setSmtpOpen] = useState(false)
  const [smtp, setSmtp] = useState({ host: '', port: 587, username: '', password: '' })

  useEffect(() => {
    const settingsP = marketingApi.getSettings()
    const accountsP = marketingApi.getAccounts()
    const usageP = isSuperAdmin
      ? marketingApi.getAdminTenantUsage().catch(() => ({ rows: [] } as AdminTenantUsage))
      : Promise.resolve(null)

    Promise.all([settingsP, accountsP, usageP]).then(([s, accts, usageRaw]) => {
      if (s.icp_config) setIcp({ ...DEFAULT_ICP, ...s.icp_config })
      if (s.channel_config) {
        setChannel(s.channel_config)
        if (s.channel_config.smtp) setSmtp(s.channel_config.smtp as typeof smtp)
      }
      if (s.signal_config) setSignal({ ...DEFAULT_SIGNAL, ...s.signal_config })
      if (s.outreach_limits) setOutreach({ ...DEFAULT_OUTREACH, ...s.outreach_limits })
      if (s.tenant_mode_enabled != null) setTenantModeEnabled(s.tenant_mode_enabled)
      if (s.tenant_mode_config) setTenantMode({ ...DEFAULT_TENANT_MODE, ...s.tenant_mode_config })

      const li = accts.find(a => a.platform === 'linkedin')
      if (li) setLinkedInAccount(li)

      if (isSuperAdmin && usageRaw) {
        setAdminUsage(usageRaw.rows ?? [])
      }
    }).catch(console.error).finally(() => setLoading(false))
  }, [isSuperAdmin])

  async function handleSave() {
    setSaving(true)
    setSaved(false)
    setSaveError(null)
    try {
      const finalChannel: ChannelConfig = { ...channel, smtp }
      const payload: Record<string, unknown> = {
        icp_config: icp,
        channel_config: finalChannel,
        signal_config: signal,
        outreach_limits: outreach,
      }
      // Tenant mode is only editable by super admin
      if (isSuperAdmin) {
        payload.tenant_mode_enabled = tenantModeEnabled
        payload.tenant_mode_config = tenantMode
      }
      await marketingApi.updateSettings(payload as Parameters<typeof marketingApi.updateSettings>[0])
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function handleLinkedInReconnect() {
    try {
      const { authorization_url } = await marketingApi.connectLinkedIn('personal', locale)
      window.location.href = authorization_url
    } catch (err) {
      console.error('LinkedIn reconnect failed', err)
    }
  }

  function formatTokenExpiry(dateStr: string | null): string {
    if (!dateStr) return 'no expiry date'
    return `token expires ${new Date(dateStr).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })}`
  }

  function maskKey(key?: string): string {
    if (!key) return ''
    return key.length <= 6 ? '•'.repeat(key.length) : `${key.slice(0, 3)}${'•'.repeat(8)}${key.slice(-3)}`
  }

  // Typed updaters — avoids TS noImplicitAny on `p` inside JSX callbacks
  const updIcp = (patch: Partial<IcpConfig>) => setIcp((p: IcpConfig) => ({ ...p, ...patch }))
  const updSignal = (patch: Partial<SignalConfig>) => setSignal((p: SignalConfig) => ({ ...p, ...patch }))
  const updOutreach = (patch: Partial<OutreachLimits>) => setOutreach((p: OutreachLimits) => ({ ...p, ...patch }))
  const updTenantMode = (patch: Partial<TenantModeConfig>) => setTenantMode((p: TenantModeConfig) => ({ ...p, ...patch }))
  const updSmtp = (patch: Partial<typeof smtp>) => setSmtp(p => ({ ...p, ...patch }))
  const updChannel = (patch: Partial<ChannelConfig>) => setChannel((p: ChannelConfig) => ({ ...p, ...patch }))

  if (loading) {
    return <div style={{ padding: 24, color: 'var(--muted)', fontSize: 13 }}>Loading settings…</div>
  }

  const signalRows: Array<{ label: string; el: React.ReactNode }> = [
    {
      label: 'Hiring spike threshold (new jobs / 7 days)',
      el: <input type="number" value={signal.hiring_spike_threshold}
        onChange={e => updSignal({ hiring_spike_threshold: Number(e.target.value) })}
        style={{ ...S.input, width: 70, textAlign: 'right' }} />,
    },
    {
      label: 'Scrape frequency',
      el: <select value={signal.scrape_frequency_hours}
        onChange={e => updSignal({ scrape_frequency_hours: Number(e.target.value) })}
        style={{ ...S.input, width: 110, cursor: 'pointer' }}>
        {[1, 2, 6, 12, 24].map(h => <option key={h} value={h}>Every {h}h</option>)}
      </select>,
    },
    {
      label: 'Monitor pain keyword posts',
      el: <Toggle on={signal.monitor_pain_posts} onToggle={() => updSignal({ monitor_pain_posts: !signal.monitor_pain_posts })} />,
    },
    {
      label: 'Monitor agency growth signals',
      el: <Toggle on={signal.monitor_growth_signals} onToggle={() => updSignal({ monitor_growth_signals: !signal.monitor_growth_signals })} />,
    },
    {
      label: 'Auto-enroll signal prospects in sequence',
      el: <Toggle on={signal.auto_enroll} onToggle={() => updSignal({ auto_enroll: !signal.auto_enroll })} />,
    },
    {
      label: 'Require approval before outreach',
      el: <Toggle on={signal.require_approval} onToggle={() => updSignal({ require_approval: !signal.require_approval })} />,
    },
  ]

  const outreachRows: Array<{ label: string; el: React.ReactNode }> = [
    {
      label: 'Max LinkedIn connection requests / day',
      el: <input type="number" value={outreach.linkedin_connects_per_day}
        onChange={e => updOutreach({ linkedin_connects_per_day: Number(e.target.value) })}
        style={{ ...S.input, width: 70, textAlign: 'right' }} />,
    },
    {
      label: 'Max LinkedIn DMs / day',
      el: <input type="number" value={outreach.linkedin_dms_per_day}
        onChange={e => updOutreach({ linkedin_dms_per_day: Number(e.target.value) })}
        style={{ ...S.input, width: 70, textAlign: 'right' }} />,
    },
    {
      label: 'Max emails / day',
      el: <input type="number" value={outreach.emails_per_day}
        onChange={e => updOutreach({ emails_per_day: Number(e.target.value) })}
        style={{ ...S.input, width: 70, textAlign: 'right' }} />,
    },
    {
      label: 'Outreach window (UTC)',
      el: (
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <input type="time" value={outreach.window_start_utc}
            onChange={e => updOutreach({ window_start_utc: e.target.value })}
            style={{ ...S.input, width: 90 }} />
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>to</span>
          <input type="time" value={outreach.window_end_utc}
            onChange={e => updOutreach({ window_end_utc: e.target.value })}
            style={{ ...S.input, width: 90 }} />
        </div>
      ),
    },
    {
      label: 'Skip weekends',
      el: <Toggle on={outreach.skip_weekends} onToggle={() => updOutreach({ skip_weekends: !outreach.skip_weekends })} />,
    },
  ]

  return (
    <div style={{ padding: '4px 0 24px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>

        {/* ── ICP targeting ──────────────────────────────────────────────────── */}
        <div style={S.card}>
          <div style={S.sectionHead}>
            ICP targeting
            <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 400 }}>Who to prospect</span>
          </div>

          <div style={S.field}>
            <span style={S.label}>Target job titles</span>
            <TagInput
              tags={icp.target_titles}
              onChange={v => updIcp({ target_titles: v })}
              color="blue"
              placeholder="e.g. Managing Director"
            />
          </div>

          <div style={S.field}>
            <span style={S.label}>Company types</span>
            <TagInput
              tags={icp.company_types}
              onChange={v => updIcp({ company_types: v })}
              color="purple"
              placeholder="e.g. Recruitment agency"
            />
          </div>

          <div style={S.field}>
            <span style={S.label}>Company size (employees)</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="number" value={icp.size_min}
                onChange={e => updIcp({ size_min: Number(e.target.value) })}
                style={{ ...S.input, width: 70, textAlign: 'right' }} />
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>to</span>
              <input type="number" value={icp.size_max}
                onChange={e => updIcp({ size_max: Number(e.target.value) })}
                style={{ ...S.input, width: 70, textAlign: 'right' }} />
            </div>
          </div>

          <div style={S.field}>
            <span style={S.label}>Target locations</span>
            <TagInput
              tags={icp.locations}
              onChange={v => updIcp({ locations: v })}
              color="green"
              placeholder="e.g. Australia"
            />
          </div>

          <div style={{ ...S.field, marginBottom: 0 }}>
            <span style={S.label}>Min ICP score to add to pipeline</span>
            <select value={icp.min_score}
              onChange={e => updIcp({ min_score: Number(e.target.value) })}
              style={{ ...S.input, cursor: 'pointer' }}>
              {[6, 7, 8, 9].map(n => <option key={n} value={n}>{n} out of 10</option>)}
            </select>
          </div>
        </div>

        {/* ── Channels ───────────────────────────────────────────────────────── */}
        <div style={S.card}>
          <div style={S.sectionHead}>
            Channels
            <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 400 }}>Data sources + outreach</span>
          </div>

          {/* LinkedIn */}
          <div style={S.chRow}>
            <ChIcon bg="rgba(27,108,168,0.25)" color="#60a5fa">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
              </svg>
            </ChIcon>
            <ChMeta
              title={linkedInAccount ? `LinkedIn · ${linkedInAccount.account_name}` : 'LinkedIn'}
              sub={linkedInAccount ? `Personal profile · ${formatTokenExpiry(linkedInAccount.token_expires_at)}` : 'Not connected'}
            />
            <StatusBadge connected={!!linkedInAccount} />
            <button style={S.chBtn} onClick={handleLinkedInReconnect}>
              {linkedInAccount ? 'Reconnect' : 'Connect'}
            </button>
          </div>

          {/* BrightData — hidden for tenants (platform quota) */}
          {isSuperAdmin ? (
            <>
              <div style={S.chRow}>
                <ChIcon bg="rgba(245,158,11,0.15)" color="var(--amber)">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <ellipse cx="12" cy="5" rx="9" ry="3" />
                    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                  </svg>
                </ChIcon>
                <ChMeta
                  title="BrightData"
                  sub={channel.brightdata_api_key
                    ? `Prospect scraping + signals · ${maskKey(channel.brightdata_api_key)}`
                    : 'Prospect scraping + signals · No key set'}
                />
                {!bdEdit && (
                  <>
                    <StatusBadge connected={!!channel.brightdata_api_key} />
                    <button style={S.chBtn} onClick={() => setBdEdit(true)}>
                      {channel.brightdata_api_key ? 'Edit key' : 'Add key'}
                    </button>
                  </>
                )}
              </div>
              {bdEdit && (
                <KeyEditRow
                  value=""
                  placeholder="Enter BrightData API key"
                  onDone={key => {
                    setBdEdit(false)
                    if (key.trim()) updChannel({ brightdata_api_key: key.trim() })
                  }}
                  onCancel={() => setBdEdit(false)}
                />
              )}
            </>
          ) : (
            <div style={{ ...S.chRow, opacity: 0.6 }}>
              <ChIcon bg="rgba(245,158,11,0.15)" color="var(--amber)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <ellipse cx="12" cy="5" rx="9" ry="3" />
                  <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                  <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                </svg>
              </ChIcon>
              <ChMeta
                title="BrightData"
                sub="Prospect sourcing powered by the platform — no setup needed."
              />
              <span style={{ fontSize: 10, color: 'var(--muted)', fontStyle: 'italic' }}>Platform managed</span>
            </div>
          )}

          {/* Hunter.io */}
          <div style={S.chRow}>
            <ChIcon bg="rgba(34,197,94,0.15)" color="var(--green)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="4" width="20" height="16" rx="2" />
                <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
              </svg>
            </ChIcon>
            <ChMeta
              title="Hunter.io"
              sub={channel.hunter_api_key
                ? `Email enrichment · ${maskKey(channel.hunter_api_key)}`
                : 'Free tier: 25 enrichments/month · $49/mo paid'}
            />
            {!hunterEdit && (
              <>
                <StatusBadge connected={!!channel.hunter_api_key} />
                <button style={S.chBtn} onClick={() => setHunterEdit(true)}>
                  {channel.hunter_api_key ? 'Edit key' : 'Add key'}
                </button>
              </>
            )}
          </div>
          {hunterEdit && (
            <KeyEditRow
              value=""
              placeholder="Enter Hunter.io API key"
              onDone={key => {
                setHunterEdit(false)
                if (key.trim()) updChannel({ hunter_api_key: key.trim() })
              }}
              onCancel={() => setHunterEdit(false)}
            />
          )}

          {/* Sending mailbox */}
          <div style={{ ...S.chRow, borderBottom: 'none' }}>
            <ChIcon bg="rgba(255,255,255,0.08)" color="var(--muted)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 2 11 13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </ChIcon>
            <ChMeta
              title="Sending mailbox"
              sub={channel.smtp?.host
                ? `${channel.smtp.username || channel.smtp.host} · SMTP configured`
                : 'No SMTP configured'}
            />
            <StatusBadge connected={!!channel.smtp?.host} />
            <button style={S.chBtn} onClick={() => setSmtpOpen(v => !v)}>
              {smtpOpen ? 'Close' : 'Configure'}
            </button>
          </div>
          {smtpOpen && (
            <div style={{ paddingTop: 8, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div>
                <span style={S.label}>SMTP host</span>
                <input type="text" value={smtp.host}
                  onChange={e => updSmtp({ host: e.target.value })}
                  placeholder="smtp.gmail.com" style={S.input} />
              </div>
              <div>
                <span style={S.label}>Port</span>
                <input type="number" value={smtp.port}
                  onChange={e => updSmtp({ port: Number(e.target.value) })}
                  placeholder="587" style={S.input} />
              </div>
              <div>
                <span style={S.label}>Username / email</span>
                <input type="text" value={smtp.username}
                  onChange={e => updSmtp({ username: e.target.value })}
                  placeholder="you@company.com" style={S.input} />
              </div>
              <div>
                <span style={S.label}>Password</span>
                <input type="password" value={smtp.password}
                  onChange={e => updSmtp({ password: e.target.value })}
                  placeholder="•••••••••" style={S.input} />
              </div>
            </div>
          )}
        </div>

        {/* ── Signal configuration ───────────────────────────────────────────── */}
        <div style={S.card}>
          <div style={S.sectionHead}>
            Signal configuration
            <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 400 }}>BrightData scrape rules</span>
          </div>
          {signalRows.map(({ label, el }, i) => (
            <div key={label} style={{ ...S.limitRow, ...(i === signalRows.length - 1 ? { borderBottom: 'none' } : {}) }}>
              <span style={{ color: 'var(--muted)' }}>{label}</span>
              {el}
            </div>
          ))}
        </div>

        {/* ── Outreach limits ────────────────────────────────────────────────── */}
        <div style={S.card}>
          <div style={S.sectionHead}>
            Outreach limits
            <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 400 }}>Daily caps to stay safe</span>
          </div>
          {outreachRows.map(({ label, el }, i) => (
            <div key={label} style={{ ...S.limitRow, ...(i === outreachRows.length - 1 ? { borderBottom: 'none' } : {}) }}>
              <span style={{ color: 'var(--muted)' }}>{label}</span>
              {el}
            </div>
          ))}
        </div>

        {/* ── Prospect usage meter (tenants only) ───────────────────────────── */}
        {!isSuperAdmin && tenantStatus && tenantStatus.prospect_month_limit != null && (
          <div style={{ ...S.card, gridColumn: '1 / -1' }}>
            <div style={S.sectionHead}>
              Usage this month
              <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 400 }}>Plan limits</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <span style={S.label}>Prospects sourced</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.1)', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', borderRadius: 3,
                      background: tenantStatus.this_month_prospects >= tenantStatus.prospect_month_limit!
                        ? 'var(--red)' : 'var(--cyan)',
                      width: `${Math.min(100, (tenantStatus.this_month_prospects / tenantStatus.prospect_month_limit!) * 100)}%`,
                      transition: 'width 0.3s',
                    }} />
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                    {tenantStatus.this_month_prospects} / {tenantStatus.prospect_month_limit}
                  </span>
                </div>
              </div>
              {tenantStatus.sequence_limit != null && (
                <div>
                  <span style={S.label}>Sequences</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.1)', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%', borderRadius: 3,
                        background: tenantStatus.sequences_used >= tenantStatus.sequence_limit!
                          ? 'var(--red)' : 'var(--blue)',
                        width: `${Math.min(100, (tenantStatus.sequences_used / tenantStatus.sequence_limit!) * 100)}%`,
                        transition: 'width 0.3s',
                      }} />
                    </div>
                    <span style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                      {tenantStatus.sequences_used} / {tenantStatus.sequence_limit}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Tenant mode (super admin only) ─────────────────────────────────── */}
        {isSuperAdmin && <div style={{ ...S.card, gridColumn: '1 / -1' }}>
          <div style={S.sectionHead}>
            Tenant mode
            <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 400 }}>
              Allow tenants to use this module for their own client acquisition
            </span>
          </div>

          {/* Info banner */}
          <div style={{
            background: 'rgba(27,108,168,0.12)', border: '1px solid rgba(27,108,168,0.25)',
            borderRadius: 8, padding: '10px 12px', marginBottom: 12,
            display: 'flex', gap: 8, alignItems: 'flex-start',
          }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2" style={{ flexShrink: 0, marginTop: 1 }}>
              <circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" />
            </svg>
            <p style={{ fontSize: 11, color: '#93c5fd', lineHeight: 1.5 }}>
              When enabled, tenants on Agency Small and above can access their own Client pipeline module to find and win employer clients for their recruitment business. Each tenant uses their own LinkedIn account and email. BrightData and Hunter.io usage counts against your platform API quota. You can set per-tenant limits below.
            </p>
          </div>

          {/* Toggle row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <span style={{ fontSize: 12, fontWeight: 500 }}>Enable client pipeline for tenants</span>
            <Toggle on={tenantModeEnabled} onToggle={() => setTenantModeEnabled(v => !v)} />
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>
              {tenantModeEnabled
                ? 'Enabled · qualifying tenants can access this module'
                : 'Currently disabled · enable to unlock for qualifying tenants'}
            </span>
          </div>

          {/* Config fields — dimmed when off */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12,
            opacity: tenantModeEnabled ? 1 : 0.4,
            pointerEvents: tenantModeEnabled ? 'auto' : 'none',
            transition: 'opacity 0.2s',
          }}>
            <div>
              <span style={S.label}>Min plan to access</span>
              <select value={tenantMode.min_plan}
                onChange={e => updTenantMode({ min_plan: e.target.value })}
                disabled={!tenantModeEnabled}
                style={{ ...S.input, cursor: 'pointer' }}>
                <option value="agency_small">Agency Small ($999/mo)</option>
                <option value="agency_medium">Agency Medium ($2,999/mo)</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div>
              <span style={S.label}>Max prospects per tenant / month</span>
              <input type="number" value={tenantMode.max_prospects_per_month}
                disabled={!tenantModeEnabled}
                onChange={e => updTenantMode({ max_prospects_per_month: Number(e.target.value) })}
                style={S.input} />
            </div>
            <div>
              <span style={S.label}>Max sequences per tenant</span>
              <input type="number" value={tenantMode.max_sequences}
                disabled={!tenantModeEnabled}
                onChange={e => updTenantMode({ max_sequences: Number(e.target.value) })}
                style={S.input} />
            </div>
          </div>
        </div>}

        {/* ── Tenant usage table (super admin only) ─────────────────────────── */}
        {isSuperAdmin && adminUsage.length > 0 && (
          <div style={{ ...S.card, gridColumn: '1 / -1' }}>
            <div style={S.sectionHead}>
              Tenant usage
              <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 400 }}>Client pipeline activity this month</span>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr>
                    {['Tenant', 'Plan', 'Prospects (mo)', 'Sequences', 'LinkedIn', 'Last active'].map(h => (
                      <th key={h} style={{ textAlign: 'left', padding: '5px 10px', color: 'var(--muted)', fontWeight: 600, fontSize: 10, borderBottom: '1px solid var(--border)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {adminUsage.map((row) => (
                    <tr key={row.tenant_id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '7px 10px', color: 'var(--white)' }}>{row.tenant_name}</td>
                      <td style={{ padding: '7px 10px', color: 'var(--muted)' }}>
                        <span style={{
                          fontSize: 10, padding: '2px 6px', borderRadius: 8,
                          background: 'rgba(255,255,255,0.08)', color: 'var(--muted)',
                        }}>{row.plan.replace('_', ' ')}</span>
                      </td>
                      <td style={{ padding: '7px 10px', color: 'var(--white)' }}>{row.prospects_this_month}</td>
                      <td style={{ padding: '7px 10px', color: 'var(--white)' }}>{row.sequences_count}</td>
                      <td style={{ padding: '7px 10px' }}>
                        <span style={{ color: row.has_linkedin ? 'var(--green)' : 'var(--muted)', fontSize: 11 }}>
                          {row.has_linkedin ? '✓ Connected' : 'Not connected'}
                        </span>
                      </td>
                      <td style={{ padding: '7px 10px', color: 'var(--muted)' }}>
                        {row.last_active
                          ? new Date(row.last_active).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

      </div>

      {/* Save row */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12, marginTop: 16 }}>
        {saved && (
          <span style={{ fontSize: 12, color: 'var(--green)', display: 'flex', alignItems: 'center', gap: 5 }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M20 6 9 17l-5-5" />
            </svg>
            Settings saved
          </span>
        )}
        {saveError && (
          <span style={{ fontSize: 12, color: 'var(--red)' }}>{saveError}</span>
        )}
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saving}
          style={{ opacity: saving ? 0.7 : 1 }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
            <polyline points="17 21 17 13 7 13 7 21" />
            <polyline points="7 3 7 8 15 8" />
          </svg>
          {saving ? 'Saving…' : 'Save all settings'}
        </button>
      </div>
    </div>
  )
}
