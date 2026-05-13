'use client'
import { useState } from 'react'
import dynamic from 'next/dynamic'

const PipelineTab  = dynamic(() => import('./PipelineTab'),  { ssr: false })
const SettingsTab  = dynamic(() => import('./SettingsTab'),  { ssr: false })
const ProspectsTab = dynamic(() => import('./ProspectsTab'), { ssr: false })

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

  function navigateToTab(tab: string) {
    if (TABS.some(t => t.key === tab)) setActiveTab(tab as Tab)
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
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
          {activeTab === 'pipeline'  && <PipelineTab  onNavigate={navigateToTab} />}
          {activeTab === 'settings'  && <SettingsTab />}
          {activeTab === 'prospects' && <ProspectsTab />}
          {activeTab !== 'pipeline' && activeTab !== 'settings' && activeTab !== 'prospects' && (
            <div data-tab={activeTab} style={{ padding: '24px 0', color: 'var(--muted)', fontSize: 13 }}>
              {/* Placeholder — built in subsequent phases */}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
