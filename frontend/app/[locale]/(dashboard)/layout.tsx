'use client'
import { useTranslations } from 'next-intl'
import { Link, usePathname } from '@/i18n/navigation'
import { useState } from 'react'

const NAV_ITEMS = [
  { key: 'dashboard', href: '/', icon: GridIcon },
  { key: 'chat', href: '/chat', icon: ChatIcon },
  { key: 'jobs', href: '/jobs', icon: BriefcaseIcon },
  { key: 'candidates', href: '/candidates', icon: UsersIcon },
  { key: 'settings', href: '/settings', icon: SettingsIcon },
]

function GridIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>
}
function ChatIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
}
function BriefcaseIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg>
}
function UsersIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>
}
function SettingsIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const t = useTranslations('nav')
  const pathname = usePathname()
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--navy)' }}>
      {/* Sidebar */}
      <aside
        className="flex flex-col transition-all duration-300 border-r"
        style={{
          width: sidebarOpen ? '220px' : '60px',
          background: 'var(--navy-light)',
          borderColor: 'var(--navy-border)',
          flexShrink: 0,
        }}
      >
        {/* Brand */}
        <div className="flex items-center gap-3 px-4 py-5 border-b" style={{ borderColor: 'var(--navy-border)' }}>
          <div className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0" style={{ background: 'var(--cyan)' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0D1B2A" strokeWidth="2.5">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
          </div>
          {sidebarOpen && <span className="text-sm font-bold text-white whitespace-nowrap">AI Recruiter</span>}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 space-y-1 px-2">
          {NAV_ITEMS.map(({ key, href, icon: Icon }) => {
            const isActive = href === '/' ? pathname === '/' : pathname.startsWith(href)
            return (
              <Link
                key={key}
                href={href}
                className="flex items-center gap-3 px-2.5 py-2 rounded-lg text-sm font-medium transition-colors group"
                style={{
                  color: isActive ? 'var(--cyan)' : '#94A3B8',
                  background: isActive ? 'var(--cyan)15' : 'transparent',
                }}
              >
                <span className="flex-shrink-0"><Icon /></span>
                {sidebarOpen && <span className="whitespace-nowrap">{t(key as any)}</span>}
              </Link>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="px-2 py-4 border-t" style={{ borderColor: 'var(--navy-border)' }}>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="w-full flex items-center gap-3 px-2.5 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors text-sm"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              {sidebarOpen
                ? <path d="M11 17l-5-5 5-5M18 17l-5-5 5-5"/>
                : <path d="M13 17l5-5-5-5M6 17l5-5-5-5"/>
              }
            </svg>
            {sidebarOpen && <span>Collapse</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Topbar */}
        <header
          className="flex items-center justify-between px-6 py-3.5 border-b flex-shrink-0"
          style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}
        >
          <div className="flex items-center gap-3">
            <div className="relative">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
              <input
                type="text"
                placeholder="Search..."
                className="pl-9 pr-4 py-1.5 text-sm rounded-lg border outline-none text-slate-300 placeholder-slate-500 focus:border-cyan-500 transition-colors w-56"
                style={{ background: 'var(--navy)', borderColor: 'var(--navy-border)' }}
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Notifications */}
            <button className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/5 text-slate-400 hover:text-white transition-colors relative">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0"/>
              </svg>
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full" style={{ background: 'var(--cyan)' }}></span>
            </button>
            {/* Avatar */}
            <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-navy" style={{ background: 'var(--cyan)' }}>
              AR
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
