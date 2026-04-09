'use client'
import { useTranslations } from 'next-intl'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, useRef } from 'react'
import { useForm } from 'react-hook-form'
import { settingsApi, ragApi, teamApi, billingApi, gdprApi } from '@/lib/api'
import type { RagDocument, TeamMember } from '@/lib/api'

const qc = new QueryClient()

const NAV_ITEMS = [
  'General',
  'API Keys',
  'AI Provider',
  'Email & Mailbox',
  'Knowledge Base',
  'Chat Widget',
  'AI Recruiter Prompt',
  'Team Members',
  'Billing',
  'Privacy & Data',
]
const NAV_KEYS = [
  'general', 'apiKeys', 'aiProvider', 'emailInbox', 'knowledgeBase',
  'chatWidget', 'aiRecruiter', 'team', 'billing', 'gdpr',
]

const WIDGET_PLANS = new Set(['small_firm', 'mid_firm', 'enterprise'])

const PLAN_DETAILS: Record<string, { label: string; price: string; credits: string; jobs: string; widget: boolean }> = {
  free:        { label: 'Free',        price: '$0/mo',    credits: '0',         jobs: '1 job',    widget: false },
  casual:      { label: 'Casual',      price: '$49/mo',   credits: '3/mo',      jobs: '3 jobs',   widget: false },
  individual:  { label: 'Individual',  price: '$99/mo',   credits: '10/mo',     jobs: '10 jobs',  widget: false },
  small_firm:  { label: 'Small Firm',  price: '$199/mo',  credits: '30/mo',     jobs: '30 jobs',  widget: true  },
  mid_firm:    { label: 'Mid Firm',    price: '$399/mo',  credits: '100/mo',    jobs: '100 jobs', widget: true  },
  enterprise:  { label: 'Enterprise',  price: 'Custom',   credits: 'Unlimited', jobs: 'Unlimited',widget: true  },
}

function fmt(date: string | null | undefined) {
  if (!date) return null
  return new Date(date).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })
}

function SettingsContent() {
  const t = useTranslations('settings')
  const queryClient = useQueryClient()
  const [section, setSection] = useState('general')
  const [saved, setSaved] = useState(false)
  const [scrapeResult, setScrapeResult] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('recruiter')
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteConfirmText, setDeleteConfirmText] = useState('')
  const [exportDone, setExportDone] = useState(false)
  const [widgetColor, setWidgetColor] = useState('#00C2E0')
  const [snippetCopied, setSnippetCopied] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── Tenant ────────────────────────────────────────────────────────────────
  const { data: tenant } = useQuery({
    queryKey: ['tenant'],
    queryFn: () => settingsApi.getTenant(),
  })

  const { register, handleSubmit } = useForm({ values: tenant })

  const saveMutation = useMutation({
    mutationFn: (data: Parameters<typeof settingsApi.updateTenant>[0]) => settingsApi.updateTenant(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    },
  })

  // ── Knowledge Base ────────────────────────────────────────────────────────
  const { data: ragDocs, refetch: refetchRag } = useQuery({
    queryKey: ['rag-docs'],
    queryFn: () => ragApi.getDocuments({ limit: 100 }),
    enabled: section === 'knowledgeBase',
    retry: false,
  })

  const scrapeMutation = useMutation({
    mutationFn: (url: string) => ragApi.scrapeWebsite(url),
    onSuccess: (data) => {
      setScrapeResult(`Scraped successfully — ${data.chunks_stored} chunks stored`)
      refetchRag()
    },
    onError: () => setScrapeResult('Scrape failed — check your website URL in General settings'),
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => ragApi.uploadDocument(file),
    onSuccess: () => { setUploadError(null); refetchRag() },
    onError: (e: Error) => setUploadError(e.message || 'Upload failed'),
  })

  const deleteDocMutation = useMutation({
    mutationFn: (id: string) => ragApi.deleteDocument(id),
    onSuccess: () => refetchRag(),
  })

  // Group RAG docs by source (filename or URL) for cleaner display
  const ragGroups = ragDocs?.items.reduce<Record<string, RagDocument[]>>((acc, doc) => {
    const key = doc.filename ?? doc.source_url ?? doc.id
    ;(acc[key] = acc[key] ?? []).push(doc)
    return acc
  }, {})

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setUploadError(null)
      uploadMutation.mutate(file)
      e.target.value = ''
    }
  }

  // ── Team ─────────────────────────────────────────────────────────────────
  const { data: teamMembers, refetch: refetchTeam } = useQuery({
    queryKey: ['team'],
    queryFn: () => teamApi.getMembers(),
    enabled: section === 'team',
  })

  const inviteMutation = useMutation({
    mutationFn: (data: { email: string; role: string }) => teamApi.invite(data),
    onSuccess: () => {
      setInviteEmail('')
      setInviteError(null)
      refetchTeam()
    },
    onError: (e: Error) => setInviteError(e.message || 'Invite failed'),
  })

  const removeMemberMutation = useMutation({
    mutationFn: (id: string) => teamApi.remove(id),
    onSuccess: () => refetchTeam(),
  })

  // ── Billing ───────────────────────────────────────────────────────────────
  const portalMutation = useMutation({
    mutationFn: () => billingApi.getPortal(),
    onSuccess: (data) => { window.location.href = data.url },
  })

  // ── GDPR ──────────────────────────────────────────────────────────────────
  const exportMutation = useMutation({
    mutationFn: () => gdprApi.exportData(),
    onSuccess: (data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'my-data-export.json'
      a.click()
      URL.revokeObjectURL(url)
      setExportDone(true)
      setTimeout(() => setExportDone(false), 3000)
    },
  })

  const deleteAllMutation = useMutation({
    mutationFn: () => gdprApi.deleteAll(),
    onSuccess: () => {
      setShowDeleteConfirm(false)
      setDeleteConfirmText('')
      queryClient.invalidateQueries({ queryKey: ['rag-docs'] })
    },
  })

  const currentPlan = tenant?.plan ?? 'free'
  const planInfo = PLAN_DETAILS[currentPlan]
  const creditsMax: Record<string, number> = {
    free: 0, casual: 3, individual: 10, small_firm: 30, mid_firm: 100, enterprise: 999,
  }
  const maxCredits = creditsMax[currentPlan] || 0

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

        {/* ── FORM-BACKED SECTIONS ────────────────────────────────────────── */}
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

          {['general', 'apiKeys', 'aiProvider', 'emailInbox', 'aiRecruiter'].includes(section) && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingTop: 8, borderTop: '1px solid var(--border)', marginTop: 8 }}>
              <button type="submit" className="btn btn-primary" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? 'Saving...' : t('save')}
              </button>
              {saved && <span style={{ color: 'var(--green)', fontSize: 13 }}>✓ Saved</span>}
            </div>
          )}
        </form>

        {/* ── KNOWLEDGE BASE ─────────────────────────────────────────────────── */}
        {section === 'knowledgeBase' && (
          <div className="settings-section">
            <div className="settings-section-title">Knowledge Base</div>
            <div className="settings-section-sub">Documents and website content used by your AI Chat Widget to answer candidate questions</div>

            {/* Website scraper */}
            <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: 16, marginBottom: 20 }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>Website Scraper</div>
              {tenant?.website_url ? (
                <>
                  <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 10 }}>
                    Will scrape: <span style={{ color: 'var(--fg)' }}>{tenant.website_url}</span>
                    <span style={{ color: 'var(--muted)', marginLeft: 8, fontSize: 12 }}>(set in General settings)</span>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={scrapeMutation.isPending}
                    onClick={() => { setScrapeResult(null); scrapeMutation.mutate(tenant.website_url!) }}
                  >
                    {scrapeMutation.isPending ? 'Scraping…' : 'Scrape Website Now'}
                  </button>
                </>
              ) : (
                <div style={{ fontSize: 13, color: 'var(--muted)' }}>
                  Add your website URL in <strong>General</strong> settings to enable scraping.
                </div>
              )}
              {scrapeResult && (
                <div style={{ marginTop: 10, fontSize: 13, color: scrapeMutation.isError ? 'var(--red)' : 'var(--green)' }}>
                  {scrapeResult}
                </div>
              )}
            </div>

            {/* Upload */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={uploadMutation.isPending}
                onClick={() => fileInputRef.current?.click()}
              >
                {uploadMutation.isPending ? 'Uploading…' : '+ Upload Document'}
              </button>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>PDF, DOCX, TXT · max 20 MB</span>
              {uploadMutation.isSuccess && <span style={{ color: 'var(--green)', fontSize: 13 }}>✓ Uploaded</span>}
              {uploadError && <span style={{ color: 'var(--red)', fontSize: 13 }}>{uploadError}</span>}
            </div>

            {/* Document list */}
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>
              Stored Documents {ragDocs ? `(${Object.keys(ragGroups ?? {}).length} sources)` : ''}
            </div>

            {!ragDocs && (
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>
                Loading… (requires Small Firm plan or above)
              </div>
            )}

            {ragDocs && Object.keys(ragGroups ?? {}).length === 0 && (
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>
                No documents yet. Upload a file or scrape your website to get started.
              </div>
            )}

            {ragGroups && Object.entries(ragGroups).map(([key, docs]) => {
              const first = docs[0]
              const label = first.filename ?? (first.source_url ? first.source_url.replace(/^https?:\/\//, '').slice(0, 60) : key.slice(0, 60))
              const isWebsite = first.source_type === 'website_scrape'
              return (
                <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 18 }}>{isWebsite ? '🌐' : '📄'}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{label}</div>
                    <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                      {docs.length} chunk{docs.length !== 1 ? 's' : ''} · added {fmt(first.created_at)}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    style={{ color: 'var(--red)' }}
                    disabled={deleteDocMutation.isPending}
                    onClick={() => {
                      docs.forEach(d => deleteDocMutation.mutate(d.id))
                    }}
                  >
                    Delete
                  </button>
                </div>
              )
            })}
          </div>
        )}

        {/* ── CHAT WIDGET ────────────────────────────────────────────────────── */}
        {section === 'chatWidget' && (() => {
          const hasWidget = WIDGET_PLANS.has(tenant?.plan ?? '')
          const slug = tenant?.slug ?? 'your-slug'
          const snippet = `<script>
  window.AIRecruiterConfig = {
    tenantSlug: '${slug}',
    primaryColor: '${widgetColor}'
  };
</script>
<script src="https://app.airecruiterz.com/widget/widget.js" async></script>`

          const handleCopy = () => {
            navigator.clipboard.writeText(snippet).then(() => {
              setSnippetCopied(true)
              setTimeout(() => setSnippetCopied(false), 2000)
            })
          }

          return (
            <div className="settings-section">
              <div className="settings-section-title">Chat Widget</div>
              <div className="settings-section-sub">Embed an AI-powered recruitment chat bubble on your website</div>

              {/* Plan gate notice */}
              {!hasWidget && (
                <div style={{ background: 'var(--blue-dim)', border: '1px solid var(--blue)', borderRadius: 10, padding: '12px 16px', marginBottom: 20, fontSize: 13 }}>
                  <strong>Small Firm plan or above required.</strong>
                  {' '}The Chat Widget is included in Small Firm ($199/mo), Mid Firm ($399/mo), and Enterprise plans.{' '}
                  <span style={{ color: 'var(--cyan)', cursor: 'pointer' }} onClick={() => setSection('billing')}>Upgrade →</span>
                </div>
              )}

              <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                {/* Left: snippet + controls */}
                <div style={{ flex: '1 1 400px' }}>

                  {/* Snippet */}
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>Embed Code</div>
                  <div style={{ position: 'relative', marginBottom: 16 }}>
                    <pre style={{
                      background: 'var(--navy-dark, #0d1117)',
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                      padding: '14px 16px',
                      fontSize: 12,
                      fontFamily: 'DM Mono, monospace',
                      color: 'var(--cyan)',
                      overflowX: 'auto',
                      margin: 0,
                      lineHeight: 1.6,
                      whiteSpace: 'pre',
                      opacity: hasWidget ? 1 : 0.5,
                    }}>{snippet}</pre>
                    <button
                      type="button"
                      onClick={handleCopy}
                      disabled={!hasWidget}
                      style={{
                        position: 'absolute', top: 10, right: 10,
                        background: snippetCopied ? 'var(--green)' : 'var(--card)',
                        border: '1px solid var(--border)',
                        borderRadius: 6, padding: '4px 10px',
                        fontSize: 11, cursor: hasWidget ? 'pointer' : 'not-allowed',
                        color: snippetCopied ? '#fff' : 'var(--fg)',
                        transition: 'background 0.2s',
                      }}
                    >
                      {snippetCopied ? '✓ Copied' : 'Copy'}
                    </button>
                  </div>

                  {/* Instructions */}
                  <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px', fontSize: 12, color: 'var(--muted)', marginBottom: 20 }}>
                    Paste this code into the <code style={{ color: 'var(--cyan)', background: 'rgba(0,194,224,0.1)', padding: '1px 5px', borderRadius: 3 }}>&lt;head&gt;</code> section of your website. The chat bubble will appear in the bottom-right corner.
                  </div>

                  {/* Colour picker */}
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>Brand Colour</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <input
                      type="color"
                      value={widgetColor}
                      onChange={e => setWidgetColor(e.target.value)}
                      style={{ width: 40, height: 40, border: 'none', borderRadius: 8, cursor: 'pointer', padding: 2, background: 'transparent' }}
                    />
                    <input
                      type="text"
                      value={widgetColor}
                      onChange={e => {
                        const v = e.target.value
                        if (/^#[0-9A-Fa-f]{0,6}$/.test(v)) setWidgetColor(v)
                      }}
                      className="form-input"
                      style={{ width: 110, fontFamily: 'DM Mono, monospace', fontSize: 13 }}
                      placeholder="#00C2E0"
                    />
                    <span style={{ fontSize: 12, color: 'var(--muted)' }}>Used for the chat bubble and send button</span>
                  </div>
                </div>

                {/* Right: live preview */}
                <div style={{ flex: '0 0 auto' }}>
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12 }}>Live Preview</div>
                  <div style={{
                    width: 220, height: 260,
                    background: 'var(--card)',
                    border: '1px solid var(--border)',
                    borderRadius: 12,
                    position: 'relative',
                    overflow: 'hidden',
                    display: 'flex',
                    alignItems: 'flex-end',
                    justifyContent: 'flex-end',
                    padding: 16,
                  }}>
                    {/* Faux browser chrome */}
                    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 28, background: 'var(--border)', display: 'flex', alignItems: 'center', paddingLeft: 10, gap: 5 }}>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff5f56' }}/>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#ffbd2e' }}/>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#27c93f' }}/>
                    </div>
                    {/* Chat bubble button */}
                    <div style={{
                      width: 48, height: 48,
                      borderRadius: '50%',
                      background: widgetColor,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      boxShadow: `0 4px 16px ${widgetColor}66`,
                      cursor: 'pointer',
                      fontSize: 22,
                      transition: 'background 0.2s, box-shadow 0.2s',
                    }}>
                      💬
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 8, textAlign: 'center' }}>
                    Bubble appears bottom-right
                  </div>
                </div>
              </div>
            </div>
          )
        })()}

        {/* ── TEAM MEMBERS ───────────────────────────────────────────────────── */}
        {section === 'team' && (
          <div className="settings-section">
            <div className="settings-section-title">Team Members</div>
            <div className="settings-section-sub">Invite colleagues to access your AI Recruiter account</div>

            {/* Invite form */}
            <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: 16, marginBottom: 24 }}>
              <div style={{ fontWeight: 600, marginBottom: 12 }}>Invite New Member</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <input
                  type="email"
                  className="form-input"
                  placeholder="colleague@example.com"
                  value={inviteEmail}
                  onChange={e => setInviteEmail(e.target.value)}
                  style={{ flex: 2, minWidth: 200 }}
                />
                <select
                  className="form-select"
                  value={inviteRole}
                  onChange={e => setInviteRole(e.target.value)}
                  style={{ flex: 1, minWidth: 140 }}
                >
                  <option value="admin">Admin</option>
                  <option value="recruiter">Recruiter</option>
                  <option value="hiring_manager">Hiring Manager</option>
                </select>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  disabled={inviteMutation.isPending || !inviteEmail}
                  onClick={() => inviteMutation.mutate({ email: inviteEmail, role: inviteRole })}
                >
                  {inviteMutation.isPending ? 'Inviting…' : 'Send Invite'}
                </button>
              </div>
              {inviteError && <div style={{ color: 'var(--red)', fontSize: 13, marginTop: 8 }}>{inviteError}</div>}
              {inviteMutation.isSuccess && <div style={{ color: 'var(--green)', fontSize: 13, marginTop: 8 }}>✓ Invitation sent</div>}
            </div>

            {/* Member list */}
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>
              Current Members ({teamMembers?.total ?? 0})
            </div>

            {teamMembers?.items.length === 0 && (
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>No team members yet. Invite someone above.</div>
            )}

            {teamMembers?.items.map((m: TeamMember) => (
              <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
                <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--cyan-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 700, color: 'var(--cyan)', flexShrink: 0 }}>
                  {(m.name ?? m.email)[0].toUpperCase()}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{m.name ?? m.email}</div>
                  {m.name && <div style={{ fontSize: 12, color: 'var(--muted)' }}>{m.email}</div>}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', textTransform: 'capitalize' }}>
                  {m.role.replace('_', ' ')}
                </div>
                <span className={`badge ${m.status === 'active' ? 'badge-active' : 'badge-pending'}`}>
                  {m.status}
                </span>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ color: 'var(--red)' }}
                  disabled={removeMemberMutation.isPending}
                  onClick={() => removeMemberMutation.mutate(m.id)}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}

        {/* ── BILLING ────────────────────────────────────────────────────────── */}
        {section === 'billing' && (
          <div className="settings-section">
            <div className="settings-section-title">Billing</div>
            <div className="settings-section-sub">Manage your subscription and usage</div>

            {/* Current plan */}
            <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12, padding: 20, marginBottom: 20 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
                <div>
                  <div style={{ fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Current Plan</div>
                  <div style={{ fontSize: 22, fontWeight: 700 }}>{planInfo?.label ?? currentPlan}</div>
                  <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 2 }}>{planInfo?.price}</div>
                </div>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  disabled={portalMutation.isPending}
                  onClick={() => portalMutation.mutate()}
                >
                  {portalMutation.isPending ? 'Redirecting…' : 'Manage Billing'}
                </button>
              </div>
              {portalMutation.isError && (
                <div style={{ color: 'var(--red)', fontSize: 13, marginTop: 10 }}>
                  {(portalMutation.error as Error)?.message ?? 'Could not open billing portal'}
                </div>
              )}

              {/* Credits bar */}
              {currentPlan !== 'enterprise' && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6 }}>
                    <span>Talent Scout Credits</span>
                    <span style={{ fontWeight: 600 }}>{tenant?.credits_remaining ?? 0} / {maxCredits || '—'}</span>
                  </div>
                  {maxCredits > 0 && (
                    <div style={{ height: 6, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${Math.min(100, ((tenant?.credits_remaining ?? 0) / maxCredits) * 100)}%`, background: 'var(--cyan)', borderRadius: 4, transition: 'width 0.3s' }}/>
                    </div>
                  )}
                  <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>Credits renew monthly. Each credit runs one Talent Scout job.</div>
                </div>
              )}
              {currentPlan === 'enterprise' && (
                <div style={{ marginTop: 12, fontSize: 13, color: 'var(--muted)' }}>Unlimited Talent Scout credits included.</div>
              )}
            </div>

            {/* Plan comparison table */}
            <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>Compare Plans</div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border)' }}>
                    <th style={{ textAlign: 'left', padding: '8px 12px', color: 'var(--muted)', fontWeight: 500 }}>Plan</th>
                    <th style={{ textAlign: 'center', padding: '8px 12px', color: 'var(--muted)', fontWeight: 500 }}>Price</th>
                    <th style={{ textAlign: 'center', padding: '8px 12px', color: 'var(--muted)', fontWeight: 500 }}>Credits/mo</th>
                    <th style={{ textAlign: 'center', padding: '8px 12px', color: 'var(--muted)', fontWeight: 500 }}>Active Jobs</th>
                    <th style={{ textAlign: 'center', padding: '8px 12px', color: 'var(--muted)', fontWeight: 500 }}>Chat Widget</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(PLAN_DETAILS).map(([key, p]) => (
                    <tr key={key} style={{
                      background: key === currentPlan ? 'var(--cyan-dim)' : 'transparent',
                      borderBottom: '1px solid var(--border)',
                    }}>
                      <td style={{ padding: '10px 12px', fontWeight: key === currentPlan ? 700 : 400 }}>
                        {p.label}
                        {key === currentPlan && <span className="badge badge-active" style={{ marginLeft: 8 }}>Current</span>}
                      </td>
                      <td style={{ textAlign: 'center', padding: '10px 12px' }}>{p.price}</td>
                      <td style={{ textAlign: 'center', padding: '10px 12px' }}>{p.credits}</td>
                      <td style={{ textAlign: 'center', padding: '10px 12px' }}>{p.jobs}</td>
                      <td style={{ textAlign: 'center', padding: '10px 12px' }}>{p.widget ? '✓' : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ marginTop: 12, fontSize: 12, color: 'var(--muted)' }}>
              To upgrade, click <strong>Manage Billing</strong> above or start a new job in the AI Recruiter chat. Enterprise pricing available on request.
            </div>
          </div>
        )}

        {/* ── PRIVACY & DATA ─────────────────────────────────────────────────── */}
        {section === 'gdpr' && (
          <div className="settings-section">
            <div className="settings-section-title">Privacy & Data</div>
            <div className="settings-section-sub">Data protection and privacy controls for your recruitment data</div>

            {/* DPA status */}
            <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: 16, marginBottom: 20 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Data Processing Agreement (DPA)</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                {tenant?.gdpr_dpa_signed_at ? (
                  <span style={{ color: 'var(--green)', fontSize: 13 }}>
                    ✓ Signed on {fmt(tenant.gdpr_dpa_signed_at)}
                  </span>
                ) : (
                  <span style={{ color: 'var(--muted)', fontSize: 13 }}>Not yet signed</span>
                )}
                <a
                  href="/dpa.pdf"
                  download="AI-Recruiter-DPA.pdf"
                  className="btn btn-ghost btn-sm"
                  style={{ textDecoration: 'none' }}
                >
                  Download DPA
                </a>
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8 }}>
                Our Data Processing Agreement governs how we handle candidate personal data on your behalf. Contact support to sign.
              </div>
            </div>

            {/* Data residency */}
            <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: 16, marginBottom: 20 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Data Residency</div>
              <div style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
                <div>
                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>Primary Region</div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>🇪🇺 EU (Frankfurt)</div>
                </div>
                <div>
                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>Backup Region</div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>🇦🇺 AU (Sydney)</div>
                </div>
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                Primary data is stored in EU (Frankfurt) in compliance with local privacy regulations including GDPR (EU), Privacy Act (AU), and CCPA (US).
              </div>
            </div>

            {/* Data retention */}
            <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: 16, marginBottom: 20 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Data Retention</div>
              <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 12 }}>
                How long candidate data is retained after they are no longer active.
              </div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <select
                  className="form-select"
                  style={{ width: 160 }}
                  defaultValue={tenant?.data_retention_months ?? 12}
                  onChange={e => saveMutation.mutate({ data_retention_months: Number(e.target.value) } as never)}
                >
                  {[3, 6, 12, 24, 36].map(m => (
                    <option key={m} value={m}>{m} months</option>
                  ))}
                </select>
                {saveMutation.isSuccess && <span style={{ color: 'var(--green)', fontSize: 13 }}>✓ Saved</span>}
              </div>
            </div>

            {/* Export & Delete */}
            <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>Your Data Rights</div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 24 }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={exportMutation.isPending}
                onClick={() => exportMutation.mutate()}
              >
                {exportMutation.isPending ? 'Preparing…' : 'Export My Data'}
              </button>
              {exportDone && <span style={{ color: 'var(--green)', fontSize: 13, alignSelf: 'center' }}>✓ Download started</span>}

              <button
                type="button"
                className="btn btn-ghost btn-sm"
                style={{ color: 'var(--red)', borderColor: 'var(--red)' }}
                onClick={() => setShowDeleteConfirm(true)}
              >
                Delete All My Data
              </button>
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>
              Export downloads a JSON file of your account data. &ldquo;Delete All My Data&rdquo; anonymises all candidate records and clears your knowledge base.
            </div>

            {/* Delete confirmation dialog */}
            {showDeleteConfirm && (
              <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
                <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12, padding: 28, maxWidth: 440, width: '90%' }}>
                  <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 8, color: 'var(--red)' }}>Delete All Data</div>
                  <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 16 }}>
                    This will anonymise all candidate records and delete your entire knowledge base. This action cannot be undone.
                  </div>
                  <div style={{ fontSize: 13, marginBottom: 8 }}>Type <strong>DELETE</strong> to confirm:</div>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="DELETE"
                    value={deleteConfirmText}
                    onChange={e => setDeleteConfirmText(e.target.value)}
                    style={{ marginBottom: 16 }}
                  />
                  <div style={{ display: 'flex', gap: 10 }}>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => { setShowDeleteConfirm(false); setDeleteConfirmText('') }}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm"
                      style={{ background: 'var(--red)', color: '#fff' }}
                      disabled={deleteConfirmText !== 'DELETE' || deleteAllMutation.isPending}
                      onClick={() => deleteAllMutation.mutate()}
                    >
                      {deleteAllMutation.isPending ? 'Deleting…' : 'Confirm Delete'}
                    </button>
                  </div>
                  {deleteAllMutation.isSuccess && (
                    <div style={{ color: 'var(--green)', fontSize: 13, marginTop: 10 }}>✓ All data has been anonymised</div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function SettingsPage() {
  return <QueryClientProvider client={qc}><SettingsContent /></QueryClientProvider>
}
