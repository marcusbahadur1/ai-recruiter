'use client'
import { useTranslations } from 'next-intl'
import { useQuery, useMutation } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { settingsApi } from '@/lib/api'

const qc = new QueryClient()

const NAV_ITEMS = [
  'General',
  'API Keys',
  'AI Provider',
  'Email & Mailbox',
  'Knowledge Base',
  'AI Recruiter Prompt',
  'Team Members',
  'Billing',
  'GDPR & Privacy',
]
const NAV_KEYS = [
  'general', 'apiKeys', 'aiProvider', 'emailInbox', 'knowledgeBase',
  'aiRecruiter', 'team', 'billing', 'gdpr',
]

function SettingsContent() {
  const t = useTranslations('settings')
  const [section, setSection] = useState('general')
  const [saved, setSaved] = useState(false)

  const { data: tenant } = useQuery({
    queryKey: ['tenant'],
    queryFn: () => settingsApi.getTenant(),
  })

  const { register, handleSubmit } = useForm({ values: tenant })

  const saveMutation = useMutation({
    mutationFn: (data: Parameters<typeof settingsApi.updateTenant>[0]) => settingsApi.updateTenant(data),
    onSuccess: () => { setSaved(true); setTimeout(() => setSaved(false), 2000) },
  })

  return (
    <div className="settings-layout">
      {/* Left nav */}
      <div className="settings-nav">
        {NAV_ITEMS.map((label, i) => (
          <div
            key={NAV_KEYS[i]}
            className={`settings-nav-item${section === NAV_KEYS[i] ? ' active' : ''}`}
            onClick={() => setSection(NAV_KEYS[i])}
          >{label}</div>
        ))}
      </div>

      {/* Content */}
      <div className="settings-content">
        <form onSubmit={handleSubmit((d) => saveMutation.mutate(d))}>

          {section === 'general' && (
            <div className="settings-section">
              <div className="settings-section-title">Firm Profile</div>
              <div className="settings-section-sub">Your recruitment firm details</div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">Firm Name</label>
                  <input {...register('name')} className="form-input" placeholder="Acme Recruit"/>
                </div>
                <div className="form-group">
                  <label className="form-label">Phone</label>
                  <input {...register('phone')} className="form-input" placeholder="+61 7 3000 0000"/>
                </div>
                <div className="form-group">
                  <label className="form-label">Main Contact</label>
                  <input {...register('main_contact_name')} className="form-input"/>
                </div>
                <div className="form-group">
                  <label className="form-label">Contact Email</label>
                  <input {...register('main_contact_email')} className="form-input" type="email"/>
                </div>
                <div className="form-group" style={{ gridColumn: 'span 2' }}>
                  <label className="form-label">Address</label>
                  <input {...register('address')} className="form-input"/>
                </div>
                <div className="form-group" style={{ gridColumn: 'span 2' }}>
                  <label className="form-label">Website</label>
                  <input {...register('website_url')} className="form-input" placeholder="https://"/>
                </div>
              </div>
            </div>
          )}

          {section === 'apiKeys' && (
            <div className="settings-section">
              <div className="settings-section-title">API Keys</div>
              <div className="settings-section-sub">Your credentials for third-party services. Keys are encrypted at rest.</div>
              {[
                { name: 'brightdata_api_key', label: 'BrightData', placeholder: 'bd_•••••••••••••••' },
                { name: 'apollo_api_key', label: 'Apollo.io', placeholder: 'apollo_•••••••••••••' },
                { name: 'hunter_api_key', label: 'Hunter.io', placeholder: 'hunter_•••••••••••••' },
                { name: 'snov_api_key', label: 'Snov.io', placeholder: 'snov_•••••••••••••' },
                { name: 'sendgrid_api_key', label: 'SendGrid', placeholder: 'SG.•••••••••••••' },
                { name: 'ai_api_key', label: 'AI Provider Key', placeholder: 'sk-•••••••••••••' },
              ].map(({ name, label, placeholder }) => (
                <div key={name} className="api-key-row">
                  <div className="api-key-name">{label}</div>
                  <input {...register(name as never)} type="password"
                    placeholder={placeholder}
                    style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--muted)' }}/>
                  <div className="api-key-status missing">⚠ Not configured</div>
                  <button type="button" className="btn btn-ghost btn-sm">Edit</button>
                </div>
              ))}
            </div>
          )}

          {section === 'aiProvider' && (
            <div className="settings-section">
              <div className="settings-section-title">AI Provider</div>
              <div className="settings-section-sub">Choose which AI powers your recruiter and screening</div>
              <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
                <div style={{ flex: 1, background: 'var(--cyan-dim)', border: '1.5px solid var(--cyan)', borderRadius: 10, padding: 16, cursor: 'pointer' }}>
                  <div style={{ fontWeight: 700, marginBottom: 4 }}>Anthropic Claude</div>
                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>claude-sonnet-4 · Default</div>
                  <div style={{ marginTop: 8 }}><span className="badge badge-active">Selected</span></div>
                </div>
                <div style={{ flex: 1, background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: 16, cursor: 'pointer' }}>
                  <div style={{ fontWeight: 700, marginBottom: 4 }}>OpenAI</div>
                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>gpt-4o · Optional</div>
                  <div style={{ marginTop: 8 }}><span className="badge badge-closed">Not selected</span></div>
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Your API Key (optional — uses platform key if blank)</label>
                <input {...(register as (name: string) => object)('ai_api_key')} type="password" className="form-input" placeholder="sk-ant-•••••••"/>
              </div>
              <div className="form-group">
                <label className="form-label">Search Provider</label>
                <select {...register('search_provider')} className="form-select">
                  <option value="scrapingdog">ScrapingDog</option>
                  <option value="brightdata">BrightData</option>
                  <option value="both">Both</option>
                </select>
              </div>
            </div>
          )}

          {section === 'emailInbox' && (
            <div className="settings-section">
              <div className="settings-section-title">Email & Mailbox</div>
              <div className="settings-section-sub">Configure your IMAP inbox for receiving applications</div>
              <div className="form-group">
                <label className="form-label">Jobs Email Address</label>
                <input {...register('jobs_email' as never)} className="form-input" placeholder="jobs@airecruiterz.com" type="email"/>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>Candidates will be instructed to send resumes here</div>
              </div>
              {[
                { name: 'email_inbox', label: 'Platform Inbox', placeholder: 'jobs-acme@airecruiterz.com' },
                { name: 'email_inbox_host', label: 'Custom IMAP Host', placeholder: 'imap.gmail.com' },
                { name: 'email_inbox_port', label: 'IMAP Port', placeholder: '993' },
                { name: 'email_inbox_user', label: 'IMAP Username', placeholder: 'you@example.com' },
              ].map(({ name, label, placeholder }) => (
                <div key={name} className="form-group">
                  <label className="form-label">{label}</label>
                  <input {...register(name as never)} className="form-input" placeholder={placeholder}/>
                </div>
              ))}
            </div>
          )}

          {section === 'aiRecruiter' && (
            <div className="settings-section">
              <div className="settings-section-title">AI Recruiter Prompt</div>
              <div className="settings-section-sub">Customise the AI Recruiter&apos;s behaviour in plain English. Leave blank for platform defaults.</div>
              <textarea
                {...register('ai_recruiter_config' as never)}
                rows={10}
                className="form-textarea"
                style={{ minHeight: 200 }}
                placeholder="E.g. Always ask about team culture preferences. Focus on remote-friendly candidates..."
              />
            </div>
          )}

          {(section === 'knowledgeBase' || section === 'team' || section === 'billing' || section === 'gdpr') && (
            <div className="empty-state" style={{ paddingTop: 60 }}>
              <div className="empty-icon">🔧</div>
              <div className="empty-text">
                {section === 'knowledgeBase' && 'Knowledge base management coming soon.'}
                {section === 'team' && 'Team member management coming soon.'}
                {section === 'billing' && 'Billing management coming soon.'}
                {section === 'gdpr' && 'GDPR & Privacy settings coming soon.'}
              </div>
            </div>
          )}

          {['general', 'apiKeys', 'aiProvider', 'emailInbox', 'aiRecruiter'].includes(section) && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingTop: 8, borderTop: '1px solid var(--border)', marginTop: 8 }}>
              <button type="submit" className="btn btn-primary" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? 'Saving...' : t('save')}
              </button>
              {saved && <span style={{ color: 'var(--green)', fontSize: 13 }}>✓ Saved</span>}
            </div>
          )}
        </form>
      </div>
    </div>
  )
}

export default function SettingsPage() {
  return <QueryClientProvider client={qc}><SettingsContent /></QueryClientProvider>
}
