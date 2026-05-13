'use client'
import { useState, useEffect } from 'react'
import dynamic from 'next/dynamic'
import { marketingApi } from '@/lib/api'
import type { TenantStatus } from '@/lib/api'

const PipelineTab   = dynamic(() => import('./PipelineTab'),   { ssr: false })
const SettingsTab   = dynamic(() => import('./SettingsTab'),   { ssr: false })
const ProspectsTab  = dynamic(() => import('./ProspectsTab'),  { ssr: false })
const SignalsTab    = dynamic(() => import('./SignalsTab'),    { ssr: false })
const SequencesTab  = dynamic(() => import('./SequencesTab'), { ssr: false })
const ContentTab    = dynamic(() => import('./ContentTab'),   { ssr: false })

type Tab = 'pipeline' | 'prospects' | 'signals' | 'sequences' | 'content' | 'settings'

const TABS: { key: Tab; label: string }[] = [
  { key: 'pipeline',  label: 'Pipeline'  },
  { key: 'prospects', label: 'Prospects' },
  { key: 'signals',   label: 'Signals'   },
  { key: 'sequences', label: 'Sequences' },
  { key: 'content',   label: 'Content'   },
  { key: 'settings',  label: 'Settings'  },
]

export default function ClientPipelinePage() {
  const [activeTab, setActiveTab] = useState<Tab>('pipeline')
  const [tenantStatus, setTenantStatus] = useState<TenantStatus | null>(null)
  const [bannerDismissed, setBannerDismissed] = useState(false)

  useEffect(() => {
    marketingApi.getTenantStatus()
      .then(setTenantStatus)
      .catch(() => null)
  }, [])

  function navigateToTab(tab: string) {
    if (TABS.some(t => t.key === tab)) setActiveTab(tab as Tab)
  }

  const showOnboardingBanner = (
    !bannerDismissed
    && tenantStatus !== null
    && !tenantStatus.is_super_admin
    && tenantStatus.has_pipeline_access
    && tenantStatus.is_new_user
  )

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Onboarding banner — first visit for tenants with no data */}
      {showOnboardingBanner && (
        <div style={{
          background: 'linear-gradient(90deg, rgba(27,108,168,0.25), rgba(0,194,224,0.12))',
          border: '1px solid rgba(0,194,224,0.3)',
          borderRadius: 0,
          padding: '12px 24px',
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          flexShrink: 0,
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--white)', marginBottom: 2 }}>
              Set up your client pipeline
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>
              Connect your LinkedIn account and configure your target audience to start finding clients.
            </div>
          </div>
          <button
            onClick={() => { setActiveTab('settings'); setBannerDismissed(true) }}
            className="btn btn-cyan"
            style={{ whiteSpace: 'nowrap', flexShrink: 0 }}
          >
            Go to Settings →
          </button>
          <button
            onClick={() => setBannerDismissed(true)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--muted)', fontSize: 18, lineHeight: 1, padding: '0 4px', flexShrink: 0,
            }}
            title="Dismiss"
          >×</button>
        </div>
      )}

      {/* No LinkedIn warning for tenants without LinkedIn */}
      {tenantStatus && !tenantStatus.is_super_admin && tenantStatus.has_pipeline_access && !tenantStatus.has_linkedin && !showOnboardingBanner && (
        <div style={{
          background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)',
          padding: '9px 24px', display: 'flex', alignItems: 'center', gap: 10,
          flexShrink: 0,
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--amber)" strokeWidth="2" style={{ flexShrink: 0 }}>
            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4M12 17h.01"/>
          </svg>
          <span style={{ fontSize: 12, color: 'var(--amber)', flex: 1 }}>
            LinkedIn not connected — outreach actions are disabled until you connect your account.
          </span>
          <button
            onClick={() => setActiveTab('settings')}
            style={{
              background: 'none', border: '1px solid rgba(245,158,11,0.4)',
              borderRadius: 6, padding: '4px 10px', cursor: 'pointer',
              color: 'var(--amber)', fontSize: 11, whiteSpace: 'nowrap', flexShrink: 0,
            }}
          >
            Connect in Settings
          </button>
        </div>
      )}

      {/* Tab bar */}
      <div style={{
        display: 'flex', gap: 0,
        borderBottom: '1px solid var(--border)',
        padding: '0 24px',
        background: 'var(--navy-mid)',
        flexShrink: 0,
      }}>
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '14px 18px',
              fontSize: 13,
              fontWeight: 500,
              color: activeTab === key ? 'var(--cyan)' : 'var(--muted)',
              borderBottom: activeTab === key
                ? '2px solid var(--cyan)'
                : '2px solid transparent',
              marginBottom: -1,
              transition: 'color 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        <div style={{ padding: '0 24px', minHeight: '100%' }}>
          {activeTab === 'pipeline'   && <PipelineTab  onNavigate={navigateToTab} />}
          {activeTab === 'settings'   && <SettingsTab tenantStatus={tenantStatus} />}
          {activeTab === 'prospects'  && <ProspectsTab tenantStatus={tenantStatus} />}
          {activeTab === 'signals'    && <SignalsTab />}
          {activeTab === 'sequences'  && <SequencesTab />}
          {activeTab === 'content'    && <ContentTab />}
        </div>
      </div>
    </div>
  )
}
