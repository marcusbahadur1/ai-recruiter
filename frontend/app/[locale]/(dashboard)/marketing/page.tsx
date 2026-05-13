'use client'
import { useState } from 'react'

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
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <div style={{ padding: 24, height: '100%' }}>
          {/* Placeholder — each tab will be built in subsequent phases */}
          <div data-tab={activeTab} />
        </div>
      </div>
    </div>
  )
}
