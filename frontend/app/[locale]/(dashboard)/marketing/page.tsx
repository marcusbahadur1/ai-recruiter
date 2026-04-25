'use client'
import { useEffect, useState, useCallback } from 'react'
import { useSearchParams, useRouter as useNextRouter } from 'next/navigation'
import { useLocale } from 'next-intl'
import { marketingApi } from '@/lib/api'
import type { MarketingAccount, MarketingSettings, MarketingPost, MarketingAnalyticsSummary } from '@/lib/api'

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function fmtShortDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })
}

const POST_TYPE_LABELS: Record<string, string> = {
  thought_leadership: 'Thought Leadership',
  industry_stat: 'Industry Stat',
  success_story: 'Success Story',
  tip: 'Tip',
  poll: 'Poll',
  carousel: 'Carousel',
}

const STATUS_COLORS: Record<string, string> = {
  draft:     'var(--muted)',
  scheduled: 'var(--blue)',
  posted:    'var(--cyan)',
  failed:    'var(--red)',
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function LinkedInIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
    </svg>
  )
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div style={{
      background: 'var(--card)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '14px 18px',
    }}>
      <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--white)' }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

type PostTab = 'draft' | 'scheduled' | 'posted' | 'failed'

export default function MarketingPage() {
  const searchParams = useSearchParams()
  const nextRouter = useNextRouter()
  const locale = useLocale()

  // OAuth feedback
  const connected = searchParams.get('connected')
  const oauthError = searchParams.get('error')

  // Data
  const [accounts, setAccounts] = useState<MarketingAccount[]>([])
  const [settings, setSettings] = useState<MarketingSettings | null>(null)
  const [summary, setSummary] = useState<MarketingAnalyticsSummary | null>(null)
  const [posts, setPosts] = useState<MarketingPost[]>([])
  const [postsTotal, setPostsTotal] = useState(0)
  const [postsPage, setPostsPage] = useState(1)
  const [activeTab, setActiveTab] = useState<PostTab>('draft')

  // UI state
  const [loading, setLoading] = useState(true)
  const [forbidden, setForbidden] = useState(false)
  const [connectingPersonal, setConnectingPersonal] = useState(false)
  const [connectingCompany, setConnectingCompany] = useState(false)
  const [disconnecting, setDisconnecting] = useState<string | null>(null)
  const [toggling, setToggling] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Settings edit
  const [editingSettings, setEditingSettings] = useState(false)
  const [settingsDraft, setSettingsDraft] = useState<Partial<MarketingSettings>>({})
  const [savingSettings, setSavingSettings] = useState(false)

  // Load data
  const loadAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [accts, sett] = await Promise.all([
        marketingApi.getAccounts(),
        marketingApi.getSettings(),
      ])
      setAccounts(accts)
      setSettings(sett)
      // Load summary (non-fatal)
      marketingApi.getAnalyticsSummary()
        .then(setSummary)
        .catch(() => {})
    } catch (err: unknown) {
      if (err instanceof Error && err.message.includes('403')) {
        setForbidden(true)
      } else {
        setError('Failed to load marketing data')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  const loadPosts = useCallback(async (tab: PostTab, page: number) => {
    try {
      const res = await marketingApi.listPosts({ status: tab, page, page_size: 10 })
      setPosts(res.items)
      setPostsTotal(res.total)
    } catch {
      setPosts([])
      setPostsTotal(0)
    }
  }, [])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  useEffect(() => {
    loadPosts(activeTab, postsPage)
  }, [activeTab, postsPage, loadPosts])

  // Clear query params after reading oauth feedback
  useEffect(() => {
    if (connected || oauthError) {
      if (connected === 'true') setSuccess('LinkedIn account connected successfully.')
      if (oauthError) {
        const msgs: Record<string, string> = {
          auth_failed: 'LinkedIn authorisation failed. Please try again.',
          state_expired: 'OAuth session expired. Please try again.',
          no_pages: 'No LinkedIn company pages found on that account.',
        }
        setError(msgs[oauthError] ?? `LinkedIn error: ${oauthError}`)
      }
      // Remove query params
      nextRouter.replace(`/${locale}/marketing`)
      loadAll()
    }
  }, [connected, oauthError, locale, nextRouter, loadAll])

  // ── Actions ─────────────────────────────────────────────────────────────────

  async function handleConnect(type: 'personal' | 'company') {
    const setLoading = type === 'personal' ? setConnectingPersonal : setConnectingCompany
    setLoading(true)
    setError(null)
    try {
      const { authorization_url } = await marketingApi.connectLinkedIn(type, locale)
      window.location.href = authorization_url
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not start LinkedIn connection')
      setLoading(false)
    }
  }

  async function handleDisconnect(id: string) {
    setDisconnecting(id)
    setError(null)
    try {
      await marketingApi.disconnectAccount(id)
      setSuccess('Account disconnected.')
      await loadAll()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect account')
    } finally {
      setDisconnecting(null)
    }
  }

  async function handleToggle() {
    if (!settings) return
    setToggling(true)
    setError(null)
    try {
      const updated = await marketingApi.toggleActive(!settings.is_active)
      setSettings(updated)
      setSuccess(updated.is_active ? 'Marketing automation enabled.' : 'Marketing automation paused.')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to toggle marketing')
    } finally {
      setToggling(false)
    }
  }

  async function handleGenerate() {
    setGenerating(true)
    setError(null)
    try {
      await marketingApi.generatePost()
      setSuccess('AI-generated draft post created.')
      if (activeTab === 'draft') {
        await loadPosts('draft', 1)
        setPostsPage(1)
      } else {
        setActiveTab('draft')
        setPostsPage(1)
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Content generation failed')
    } finally {
      setGenerating(false)
    }
  }

  async function handleApprove(id: string) {
    setActionLoading(id + ':approve')
    setError(null)
    try {
      await marketingApi.approvePost(id)
      setSuccess('Post approved and scheduled.')
      await loadPosts(activeTab, postsPage)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to approve post')
    } finally {
      setActionLoading(null)
    }
  }

  async function handleReject(id: string) {
    setActionLoading(id + ':reject')
    setError(null)
    try {
      await marketingApi.rejectPost(id)
      setSuccess('Post returned to draft.')
      await loadPosts(activeTab, postsPage)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to reject post')
    } finally {
      setActionLoading(null)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this post?')) return
    setActionLoading(id + ':delete')
    setError(null)
    try {
      await marketingApi.deletePost(id)
      setSuccess('Post deleted.')
      await loadPosts(activeTab, postsPage)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete post')
    } finally {
      setActionLoading(null)
    }
  }

  async function handleSaveSettings() {
    setSavingSettings(true)
    setError(null)
    try {
      const updated = await marketingApi.updateSettings(settingsDraft)
      setSettings(updated)
      setEditingSettings(false)
      setSettingsDraft({})
      setSuccess('Settings saved.')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setSavingSettings(false)
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  if (loading) {
    return <div style={{ padding: 32, color: 'var(--muted)', fontSize: 14 }}>Loading marketing data…</div>
  }

  if (forbidden) {
    return (
      <div style={{ padding: 32, maxWidth: 520 }}>
        <div className="card" style={{ textAlign: 'center', padding: 40 }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>📢</div>
          <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>AI Marketing Module</div>
          <div style={{ fontSize: 14, color: 'var(--muted)', marginBottom: 20 }}>
            The AI Marketing Module is available on Agency Small plans and above. Upgrade to automate your LinkedIn presence with AI-generated content.
          </div>
          <a href="/subscribe" className="btn btn-cyan">Upgrade Plan →</a>
        </div>
      </div>
    )
  }

  const hasAccount = accounts.length > 0

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 24, maxWidth: 960 }}>

      {/* Feedback banners */}
      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.35)',
          borderRadius: 8, padding: '10px 14px', marginBottom: 16,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
          fontSize: 13, color: 'var(--red)',
        }}>
          {error}
          <button onClick={() => setError(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--red)', fontSize: 16, lineHeight: 1 }}>×</button>
        </div>
      )}
      {success && (
        <div style={{
          background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.35)',
          borderRadius: 8, padding: '10px 14px', marginBottom: 16,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
          fontSize: 13, color: '#10b981',
        }}>
          {success}
          <button onClick={() => setSuccess(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#10b981', fontSize: 16, lineHeight: 1 }}>×</button>
        </div>
      )}

      {/* Analytics summary — only when data exists */}
      {summary && summary.total_posts > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 20 }}>
          <StatCard label="Total Posts" value={summary.total_posts} />
          <StatCard label="Impressions" value={summary.total_impressions.toLocaleString()} />
          <StatCard label="Avg Engagement" value={`${summary.avg_engagement_rate}%`} />
          {summary.top_post && (
            <StatCard
              label="Top Post"
              value={POST_TYPE_LABELS[summary.top_post.post_type] ?? summary.top_post.post_type}
              sub={`${summary.top_post.impressions.toLocaleString()} impressions`}
            />
          )}
        </div>
      )}

      {/* Connected accounts */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header" style={{ marginBottom: 16 }}>
          <div>
            <div className="card-title">LinkedIn Accounts</div>
            <div className="card-sub">Connect your personal profile or company page to post from</div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => handleConnect('personal')}
              disabled={connectingPersonal}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <LinkedInIcon />
              {connectingPersonal ? 'Redirecting…' : 'Connect Personal'}
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => handleConnect('company')}
              disabled={connectingCompany}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <LinkedInIcon />
              {connectingCompany ? 'Redirecting…' : 'Connect Company Page'}
            </button>
          </div>
        </div>

        {accounts.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--muted)', fontSize: 13 }}>
            No LinkedIn accounts connected. Connect one above to get started.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {accounts.map((acct) => (
              <div key={acct.id} style={{
                display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px',
                background: 'var(--navy)', borderRadius: 8, border: '1px solid var(--border)',
              }}>
                <div style={{
                  width: 32, height: 32, borderRadius: 6, flexShrink: 0,
                  background: '#0A66C2', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff',
                }}>
                  <LinkedInIcon size={18} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--white)' }}>{acct.account_name}</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1 }}>
                    {acct.account_type_label}
                    {acct.token_expires_at && (
                      <span style={{ marginLeft: 8 }}>
                        · Token expires {fmtShortDate(acct.token_expires_at)}
                        {acct.is_token_expiring_soon && (
                          <span style={{ color: 'var(--amber)', marginLeft: 4 }}>⚠ Expiring soon</span>
                        )}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  className="btn btn-ghost btn-sm"
                  style={{ color: 'var(--red)', flexShrink: 0 }}
                  onClick={() => handleDisconnect(acct.id)}
                  disabled={disconnecting === acct.id}
                >
                  {disconnecting === acct.id ? 'Disconnecting…' : 'Disconnect'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Settings */}
      {settings && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header" style={{ marginBottom: editingSettings ? 16 : 0 }}>
            <div>
              <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                Automation Settings
                <span style={{
                  fontSize: 11, padding: '2px 8px', borderRadius: 20, fontWeight: 600,
                  background: settings.is_active ? 'rgba(16,185,129,0.15)' : 'rgba(148,163,184,0.15)',
                  color: settings.is_active ? '#10b981' : 'var(--muted)',
                  border: `1px solid ${settings.is_active ? 'rgba(16,185,129,0.4)' : 'var(--border)'}`,
                }}>
                  {settings.is_active ? 'Active' : 'Paused'}
                </span>
              </div>
              <div className="card-sub">Control how AI generates and publishes your LinkedIn content</div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
              {!editingSettings && (
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => { setEditingSettings(true); setSettingsDraft({}) }}
                >
                  Edit
                </button>
              )}
              <button
                className={`btn btn-sm ${settings.is_active ? 'btn-ghost' : 'btn-primary'}`}
                style={settings.is_active ? { color: 'var(--red)' } : {}}
                onClick={handleToggle}
                disabled={toggling || !hasAccount}
                title={!hasAccount ? 'Connect a LinkedIn account first' : undefined}
              >
                {toggling ? '…' : settings.is_active ? 'Pause' : 'Enable'}
              </button>
            </div>
          </div>

          {/* Settings read view */}
          {!editingSettings && (
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: 12, paddingTop: 12, borderTop: '1px solid var(--border)',
            }}>
              {[
                { label: 'Frequency', value: settings.post_frequency.replace('_', ' ') },
                { label: 'Post Time (UTC)', value: settings.post_time_utc.slice(0, 5) },
                { label: 'Tone', value: settings.tone },
                { label: 'Requires Approval', value: settings.requires_approval ? 'Yes' : 'No' },
                { label: 'Include Images', value: settings.include_images ? 'Yes' : 'No' },
                { label: 'Post Types', value: settings.post_types_enabled.map(t => POST_TYPE_LABELS[t] ?? t).join(', ') },
              ].map(({ label, value }) => (
                <div key={label}>
                  <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>{label}</div>
                  <div style={{ fontSize: 13, color: 'var(--white)', fontWeight: 500 }}>{value}</div>
                </div>
              ))}
              {settings.target_audience && (
                <div style={{ gridColumn: '1 / -1' }}>
                  <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>Target Audience</div>
                  <div style={{ fontSize: 13, color: 'var(--white)' }}>{settings.target_audience}</div>
                </div>
              )}
              {settings.topics.length > 0 && (
                <div style={{ gridColumn: '1 / -1' }}>
                  <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>Topics</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {settings.topics.map((t) => (
                      <span key={t} style={{
                        fontSize: 11, padding: '2px 8px', borderRadius: 20,
                        background: 'var(--blue-dim)', border: '1px solid var(--blue)',
                        color: 'var(--white)',
                      }}>{t}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Settings edit form */}
          {editingSettings && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
                <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Frequency</span>
                  <select
                    className="input"
                    value={settingsDraft.post_frequency ?? settings.post_frequency}
                    onChange={(e) => setSettingsDraft(d => ({ ...d, post_frequency: e.target.value as MarketingSettings['post_frequency'] }))}
                  >
                    <option value="daily">Daily</option>
                    <option value="twice_weekly">Twice Weekly</option>
                    <option value="weekly">Weekly</option>
                  </select>
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Post Time (UTC)</span>
                  <input
                    type="time"
                    className="input"
                    value={settingsDraft.post_time_utc ?? settings.post_time_utc.slice(0, 5)}
                    onChange={(e) => setSettingsDraft(d => ({ ...d, post_time_utc: e.target.value }))}
                  />
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Tone</span>
                  <select
                    className="input"
                    value={settingsDraft.tone ?? settings.tone}
                    onChange={(e) => setSettingsDraft(d => ({ ...d, tone: e.target.value as MarketingSettings['tone'] }))}
                  >
                    <option value="professional">Professional</option>
                    <option value="conversational">Conversational</option>
                    <option value="bold">Bold</option>
                    <option value="educational">Educational</option>
                  </select>
                </label>
              </div>

              <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Target Audience</span>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g. Tech hiring managers and recruiters in Australia"
                  value={settingsDraft.target_audience ?? settings.target_audience ?? ''}
                  onChange={(e) => setSettingsDraft(d => ({ ...d, target_audience: e.target.value }))}
                />
              </label>

              <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Topics (comma-separated)</span>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g. AI recruiting, talent acquisition, hiring trends"
                  value={settingsDraft.topics !== undefined ? settingsDraft.topics.join(', ') : settings.topics.join(', ')}
                  onChange={(e) => setSettingsDraft(d => ({
                    ...d,
                    topics: e.target.value.split(',').map(t => t.trim()).filter(Boolean),
                  }))}
                />
              </label>

              <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                {([
                  { key: 'requires_approval', label: 'Require Approval Before Posting' },
                  { key: 'include_images', label: 'Include Images (Unsplash)' },
                ] as const).map(({ key, label }) => (
                  <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={(settingsDraft[key] !== undefined ? settingsDraft[key] : settings[key]) as boolean}
                      onChange={(e) => setSettingsDraft(d => ({ ...d, [key]: e.target.checked }))}
                    />
                    <span style={{ fontSize: 13, color: 'var(--white)' }}>{label}</span>
                  </label>
                ))}
              </div>

              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', paddingTop: 4 }}>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => { setEditingSettings(false); setSettingsDraft({}) }}
                  disabled={savingSettings}
                >
                  Cancel
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={handleSaveSettings}
                  disabled={savingSettings}
                >
                  {savingSettings ? 'Saving…' : 'Save Settings'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Post queue */}
      <div className="card">
        <div className="card-header" style={{ marginBottom: 16 }}>
          <div>
            <div className="card-title">Post Queue</div>
            <div className="card-sub">Review, approve, and manage your LinkedIn posts</div>
          </div>
          <button
            className="btn btn-cyan btn-sm"
            onClick={handleGenerate}
            disabled={generating || !hasAccount}
            title={!hasAccount ? 'Connect a LinkedIn account first' : undefined}
            style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}
          >
            {generating ? (
              <>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: 'spin 1s linear infinite' }}>
                  <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                </svg>
                Generating…
              </>
            ) : '✦ AI Generate Post'}
          </button>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid var(--border)', paddingBottom: 0 }}>
          {(['draft', 'scheduled', 'posted', 'failed'] as PostTab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => { setActiveTab(tab); setPostsPage(1) }}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                padding: '8px 14px', fontSize: 13, fontWeight: 500,
                color: activeTab === tab ? 'var(--cyan)' : 'var(--muted)',
                borderBottom: activeTab === tab ? '2px solid var(--cyan)' : '2px solid transparent',
                marginBottom: -1,
                textTransform: 'capitalize',
              }}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Posts list */}
        {posts.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--muted)', fontSize: 13 }}>
            No {activeTab} posts.
            {activeTab === 'draft' && hasAccount && (
              <span> Click <strong>AI Generate Post</strong> to create one.</span>
            )}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {posts.map((post) => (
              <div key={post.id} style={{
                background: 'var(--navy)', borderRadius: 8, border: '1px solid var(--border)',
                padding: '14px 16px',
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  {/* Platform icon */}
                  <div style={{
                    width: 32, height: 32, borderRadius: 6, flexShrink: 0,
                    background: '#0A66C2', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: '#fff', marginTop: 2,
                  }}>
                    <LinkedInIcon size={16} />
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    {/* Header row */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                      <span style={{
                        fontSize: 10, padding: '2px 8px', borderRadius: 20, fontWeight: 600,
                        background: 'var(--card)', border: '1px solid var(--border)',
                        color: 'var(--muted)',
                      }}>
                        {POST_TYPE_LABELS[post.post_type] ?? post.post_type}
                      </span>
                      <span style={{
                        fontSize: 10, padding: '2px 8px', borderRadius: 20, fontWeight: 600,
                        color: STATUS_COLORS[post.status] ?? 'var(--muted)',
                        border: `1px solid ${STATUS_COLORS[post.status] ?? 'var(--border)'}`,
                        background: 'var(--card)',
                      }}>
                        {post.status}
                      </span>
                      {post.topic && (
                        <span style={{ fontSize: 11, color: 'var(--muted)' }}>· {post.topic}</span>
                      )}
                      <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 'auto' }}>
                        {post.status === 'posted'
                          ? `Posted ${fmtDate(post.posted_at)}`
                          : `Scheduled ${fmtDate(post.scheduled_at)}`}
                      </span>
                    </div>

                    {/* Content */}
                    <div style={{
                      fontSize: 13, color: 'var(--white)', lineHeight: 1.55,
                      display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}>
                      {post.content}
                    </div>

                    {/* Hashtags */}
                    {post.hashtags.length > 0 && (
                      <div style={{ marginTop: 6, fontSize: 11, color: 'var(--blue)' }}>
                        {post.hashtags.slice(0, 5).join(' ')}
                        {post.hashtags.length > 5 && ` +${post.hashtags.length - 5} more`}
                      </div>
                    )}

                    {/* Stats for posted */}
                    {post.status === 'posted' && (post.impressions > 0 || post.likes > 0) && (
                      <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
                        {[
                          { label: 'Impressions', value: post.impressions },
                          { label: 'Likes', value: post.likes },
                          { label: 'Comments', value: post.comments },
                        ].filter(s => s.value > 0).map(s => (
                          <div key={s.label} style={{ fontSize: 11, color: 'var(--muted)' }}>
                            <span style={{ color: 'var(--white)', fontWeight: 600 }}>{s.value.toLocaleString()}</span> {s.label}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Actions */}
                    <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                      {post.status === 'draft' && (
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => handleApprove(post.id)}
                          disabled={actionLoading === post.id + ':approve'}
                        >
                          {actionLoading === post.id + ':approve' ? '…' : 'Approve'}
                        </button>
                      )}
                      {post.status === 'scheduled' && (
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => handleReject(post.id)}
                          disabled={actionLoading === post.id + ':reject'}
                        >
                          {actionLoading === post.id + ':reject' ? '…' : 'Return to Draft'}
                        </button>
                      )}
                      {post.status !== 'posted' && (
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ color: 'var(--red)' }}
                          onClick={() => handleDelete(post.id)}
                          disabled={actionLoading === post.id + ':delete'}
                        >
                          {actionLoading === post.id + ':delete' ? '…' : 'Delete'}
                        </button>
                      )}
                      {post.image_url && (
                        <a
                          href={post.image_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-ghost btn-sm"
                        >
                          View Image
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {postsTotal > 10 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
            <span style={{ fontSize: 12, color: 'var(--muted)' }}>
              {(postsPage - 1) * 10 + 1}–{Math.min(postsPage * 10, postsTotal)} of {postsTotal}
            </span>
            <div style={{ display: 'flex', gap: 6 }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setPostsPage(p => p - 1)} disabled={postsPage === 1}>← Prev</button>
              <button className="btn btn-ghost btn-sm" onClick={() => setPostsPage(p => p + 1)} disabled={postsPage * 10 >= postsTotal}>Next →</button>
            </div>
          </div>
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
