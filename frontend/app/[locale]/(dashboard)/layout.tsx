'use client'
import { useEffect, useRef, useState } from 'react'
import { Link, usePathname, useRouter } from '@/i18n/navigation'
import { supabase, settingsApi, chatApi, searchApi } from '@/lib/api'
import type { SearchResults } from '@/lib/api'
import HelpPanel from '@/components/HelpPanel'

/* ── Icon Components ────────────────────────────────────────── */
function DashboardIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
      <path d="M3 4a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm0 8a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H4a1 1 0 01-1-1v-4zm8-8a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V4zm0 8a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"/>
    </svg>
  )
}
function ChatIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clipRule="evenodd"/>
    </svg>
  )
}
function HistoryIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd"/>
    </svg>
  )
}
function JobsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M6 6V5a3 3 0 013-3h2a3 3 0 013 3v1h2a2 2 0 012 2v3.57A22.952 22.952 0 0110 13a22.95 22.95 0 01-8-1.43V8a2 2 0 012-2h2zm2-1a1 1 0 011-1h2a1 1 0 011 1v1H8V5zm1 5a1 1 0 011-1h.01a1 1 0 110 2H10a1 1 0 01-1-1z" clipRule="evenodd"/>
    </svg>
  )
}
function CandidatesIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
      <path d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z"/>
    </svg>
  )
}
function ApplicationsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clipRule="evenodd"/>
    </svg>
  )
}
function SettingsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd"/>
    </svg>
  )
}
function SuperAdminIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
    </svg>
  )
}
function HelpIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd"/>
    </svg>
  )
}
function QuickStartIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-8.707l-3-3a1 1 0 00-1.414 1.414L10.586 9H7a1 1 0 100 2h3.586l-1.293 1.293a1 1 0 101.414 1.414l3-3a1 1 0 000-1.414z" clipRule="evenodd"/>
    </svg>
  )
}

/* ── Nav Structure ───────────────────────────────────────────── */
const NAV_SECTIONS = [
  {
    label: 'Main',
    items: [
      { key: 'dashboard',  href: '/',          label: 'Dashboard',        badge: null, badgeVariant: '' as const,    icon: <DashboardIcon /> },
      { key: 'chat',       href: '/chat',       label: 'AI Recruiter Chat',badge: null, badgeVariant: '' as const,    icon: <ChatIcon /> },
      { key: 'chat-history', href: '/chat/history', label: 'Chat History', badge: null, badgeVariant: '' as const, icon: <HistoryIcon /> },
      { key: 'jobs',       href: '/jobs',       label: 'Jobs',             badge: '7',  badgeVariant: 'blue' as const, icon: <JobsIcon /> },
      { key: 'candidates', href: '/candidates', label: 'Candidates',       badge: null, badgeVariant: '' as const,    icon: <CandidatesIcon /> },
    ],
  },
  {
    label: 'Screener',
    items: [
      { key: 'applications', href: '/applications', label: 'Applications', badge: '3', badgeVariant: 'amber' as 'amber', icon: <ApplicationsIcon /> },
    ],
  },
  {
    label: 'Account',
    items: [
      { key: 'quickstart',  href: '/quickstart',  label: 'Quick Start',  badge: null, badgeVariant: '' as const, icon: <QuickStartIcon /> },
      { key: 'help',        href: '/help',        label: 'Help',         badge: null, badgeVariant: '' as const, icon: <HelpIcon /> },
      { key: 'settings',    href: '/settings',    label: 'Settings',    badge: null, badgeVariant: '' as const, icon: <SettingsIcon /> },
      { key: 'super-admin', href: '/super-admin', label: 'Super Admin', badge: null, badgeVariant: '' as const, icon: <SuperAdminIcon /> },
    ],
  },
]

/* ── Page title from pathname ────────────────────────────────── */
function getPageTitle(pathname: string): string {
  if (pathname === '/')               return 'Dashboard'
  if (pathname === '/chat/history')   return 'Chat History'
  if (pathname === '/chat')           return 'AI Recruiter Chat'
  if (pathname.startsWith('/jobs/'))  return 'Job Detail'
  if (pathname === '/jobs')           return 'Jobs'
  if (pathname.startsWith('/candidates/')) return 'Candidate Profile'
  if (pathname === '/candidates')     return 'Candidates'
  if (pathname.startsWith('/applications/')) return 'Application Detail'
  if (pathname === '/applications')   return 'Applications'
  if (pathname === '/quickstart')      return 'Quick Start'
  if (pathname === '/help')            return 'Help'
  if (pathname === '/settings')       return 'Settings'
  if (pathname === '/super-admin')    return 'Super Admin'
  return 'AI Recruiter'
}

/* ── Active link detection ───────────────────────────────────── */
function isActive(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/'
  return pathname === href || pathname.startsWith(href + '/')
}

/* ── Global Search ───────────────────────────────────────────── */
function GlobalSearch() {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [results, setResults] = useState<SearchResults | null>(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)

  // Debounce input
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(t)
  }, [query])

  // Fetch when debounced query reaches 3+ chars
  useEffect(() => {
    if (debouncedQuery.length < 3) {
      setResults(null)
      setOpen(false)
      return
    }
    let cancelled = false
    setLoading(true)
    searchApi.search(debouncedQuery)
      .then((r) => { if (!cancelled) { setResults(r); setOpen(true) } })
      .catch(() => { if (!cancelled) setResults(null) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [debouncedQuery])

  // Close on outside click
  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [])

  // Close on Escape
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])

  function handleResultClick() {
    setOpen(false)
    setQuery('')
    setDebouncedQuery('')
    setResults(null)
  }

  const hasResults = results && (results.candidates.length > 0 || results.jobs.length > 0)

  return (
    <div ref={wrapperRef} style={{ position: 'relative' }}>
      <div className="search-box">
        <svg width="14" height="14" viewBox="0 0 20 20" fill="#94A3B8">
          <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd"/>
        </svg>
        <input
          placeholder="Search candidates, jobs…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => { if (results && (results.candidates.length > 0 || results.jobs.length > 0)) setOpen(true) }}
        />
        {loading && (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" strokeWidth="2" style={{ animation: 'spin 1s linear infinite', flexShrink: 0 }}>
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
          </svg>
        )}
      </div>

      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 6px)', right: 0,
          width: 360, maxHeight: 420, overflowY: 'auto',
          background: 'var(--navy-mid)', border: '1px solid var(--border)',
          borderRadius: 10, boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          zIndex: 200,
        }}>
          {!hasResults ? (
            <div style={{ padding: '20px 16px', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
              No results found
            </div>
          ) : (
            <>
              {results!.candidates.length > 0 && (
                <div>
                  <div style={{
                    padding: '10px 14px 6px',
                    fontSize: 10, fontWeight: 700, color: 'var(--muted)',
                    letterSpacing: '0.08em', textTransform: 'uppercase',
                  }}>
                    Candidates
                  </div>
                  {results!.candidates.map((c) => (
                    <Link
                      key={c.id}
                      href={`/candidates/${c.id}`}
                      onClick={handleResultClick}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '9px 14px', textDecoration: 'none',
                        borderTop: '1px solid var(--border)',
                        transition: 'background 0.1s',
                      }}
                      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)' }}
                      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                    >
                      <div style={{
                        width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                        background: 'linear-gradient(135deg,var(--blue),var(--cyan))',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11, fontWeight: 700, color: '#fff',
                      }}>
                        {c.name.charAt(0).toUpperCase()}
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--white)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {c.name}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {[c.title, c.company].filter(Boolean).join(' at ')}
                        </div>
                      </div>
                      <span style={{
                        marginLeft: 'auto', flexShrink: 0,
                        fontSize: 10, padding: '2px 7px', borderRadius: 10,
                        background: 'var(--card)', color: 'var(--muted)',
                        border: '1px solid var(--border)',
                      }}>
                        {c.status}
                      </span>
                    </Link>
                  ))}
                </div>
              )}

              {results!.jobs.length > 0 && (
                <div>
                  <div style={{
                    padding: '10px 14px 6px',
                    fontSize: 10, fontWeight: 700, color: 'var(--muted)',
                    letterSpacing: '0.08em', textTransform: 'uppercase',
                    borderTop: results!.candidates.length > 0 ? '1px solid var(--border)' : undefined,
                  }}>
                    Jobs
                  </div>
                  {results!.jobs.map((j) => (
                    <Link
                      key={j.id}
                      href={`/jobs/${j.id}`}
                      onClick={handleResultClick}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '9px 14px', textDecoration: 'none',
                        borderTop: '1px solid var(--border)',
                        transition: 'background 0.1s',
                      }}
                      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)' }}
                      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                    >
                      <div style={{
                        width: 28, height: 28, borderRadius: 6, flexShrink: 0,
                        background: 'var(--blue-dim)', border: '1px solid var(--blue)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 14,
                      }}>
                        💼
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--white)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {j.title}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'DM Mono, monospace' }}>
                          {j.job_ref}
                        </div>
                      </div>
                      <span style={{
                        marginLeft: 'auto', flexShrink: 0,
                        fontSize: 10, padding: '2px 7px', borderRadius: 10,
                        background: 'var(--card)', color: 'var(--muted)',
                        border: '1px solid var(--border)',
                      }}>
                        {j.status}
                      </span>
                    </Link>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

/* ── Layout ──────────────────────────────────────────────────── */
function initials(email: string): string {
  const parts = email.split('@')[0].split(/[._-]/)
  return parts.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? '').join('') || '?'
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const pageTitle = getPageTitle(pathname)
  const router = useRouter()
  const [ready, setReady] = useState(false)
  const [userEmail, setUserEmail] = useState('')
  const [userInitials, setUserInitials] = useState('?')
  const [tenantName, setTenantName] = useState('')
  const [trialDaysLeft, setTrialDaysLeft] = useState<number | null>(null)
  const [helpOpen, setHelpOpen] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) {
        router.replace('/login')
        return
      }
      const email = session.user.email ?? ''
      setUserEmail(email)
      setUserInitials(initials(email))
      setReady(true)

      // Check tenant plan — redirect expired trials, show banner for active trials
      try {
        const t = await settingsApi.getTenant()
        setTenantName(t.name)
        if (t.plan === 'trial_expired') {
          router.replace('/subscribe')
          return
        }
        if (t.plan === 'trial' && t.trial_ends_at) {
          const msLeft = new Date(t.trial_ends_at).getTime() - Date.now()
          const daysLeft = Math.max(0, Math.ceil(msLeft / 86400000))
          if (daysLeft === 0) {
            router.replace('/subscribe')
            return
          }
          setTrialDaysLeft(daysLeft)
        }
      } catch (err: unknown) {
        // If we get a 402, the trial has expired
        if (err instanceof Error && err.message.includes('402')) {
          router.replace('/subscribe')
          return
        }
      }
    })
  }, [router])

  const handleLogout = async () => {
    await supabase.auth.signOut()
    router.replace('/login')
  }

  const handleNewJob = () => {
    router.push('/jobs/new')
  }

  if (!ready) return null

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>

      {/* ── Sidebar ── */}
      <aside style={{
        width: 'var(--sidebar-w)', flexShrink: 0,
        background: 'var(--navy-mid)',
        borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden', position: 'relative', zIndex: 10,
      }}>
        {/* Logo */}
        <div style={{ padding: '20px 20px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <div style={{
            width: 34, height: 34,
            background: 'linear-gradient(135deg,var(--blue),var(--cyan))',
            borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16, fontWeight: 700, color: '#fff',
            fontFamily: 'Playfair Display, serif', flexShrink: 0,
          }}>A</div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--white)', letterSpacing: '-0.3px' }}>AI Recruiter</div>
            <div style={{ fontSize: 10, color: 'var(--muted)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>airecruiterz.com</div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, overflowY: 'auto', padding: '12px 10px' }}>
          {NAV_SECTIONS.map((section, si) => (
            <div key={section.label}>
              <div style={{
                fontSize: 10, color: 'var(--muted)', letterSpacing: '0.8px',
                textTransform: 'uppercase', padding: '8px 10px 4px', fontWeight: 600,
                marginTop: si > 0 ? 8 : 0,
              }}>{section.label}</div>
              {section.items.map((item) => {
                const active = isActive(pathname, item.href)
                return (
                  <Link
                    key={item.key}
                    href={item.href}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '9px 12px', borderRadius: 8,
                      color: active ? 'var(--cyan)' : 'var(--muted)',
                      fontSize: 13, fontWeight: 500,
                      background: active ? 'var(--cyan-dim)' : 'transparent',
                      marginBottom: 2, position: 'relative', cursor: 'pointer',
                      transition: 'all 0.15s', textDecoration: 'none',
                    }}
                  >
                    {active && (
                      <div style={{
                        position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
                        width: 3, height: '60%', background: 'var(--cyan)', borderRadius: '0 3px 3px 0',
                      }}/>
                    )}
                    <span style={{ opacity: active ? 1 : 0.7, width: 18, height: 18, flexShrink: 0, display: 'flex' }}>
                      {item.icon}
                    </span>
                    <span>{item.label}</span>
                    {item.badge && (
                      <span style={{
                        marginLeft: 'auto',
                        background: item.badgeVariant === 'amber' ? 'var(--amber)' : 'var(--blue)',
                        color: '#fff', fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 10,
                      }}>{item.badge}</span>
                    )}
                  </Link>
                )
              })}
            </div>
          ))}
        </nav>

        {/* User card */}
        <div style={{ padding: '12px 10px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', borderRadius: 8 }}>
            <div style={{
              width: 30, height: 30, borderRadius: '50%',
              background: 'linear-gradient(135deg,#667eea,#764ba2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12, fontWeight: 600, color: '#fff', flexShrink: 0,
            }}>{userInitials}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--white)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{userEmail}</div>
              <div style={{ fontSize: 10, color: 'var(--muted)' }}>{tenantName || 'Loading…'}</div>
            </div>
            <button
              onClick={handleLogout}
              title="Sign out"
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--muted)', padding: 4, borderRadius: 4,
                display: 'flex', alignItems: 'center', flexShrink: 0,
                transition: 'color 0.15s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--red)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--muted)')}
            >
              <svg width="15" height="15" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M3 3a1 1 0 011 1v12a1 1 0 11-2 0V4a1 1 0 011-1zm10.293 4.293a1 1 0 011.414 0l3 3a1 1 0 010 1.414l-3 3a1 1 0 01-1.414-1.414L14.586 11H7a1 1 0 110-2h7.586l-1.293-1.293a1 1 0 010-1.414z" clipRule="evenodd"/>
              </svg>
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>

        {/* Topbar */}
        <header style={{
          height: 'var(--topbar-h)', flexShrink: 0,
          background: 'var(--navy-mid)',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center',
          padding: '0 24px', gap: 16,
        }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--white)', flex: 1 }}>{pageTitle}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {/* Search */}
            <GlobalSearch />
            {/* Help */}
            <button
              onClick={() => setHelpOpen(true)}
              title="Help"
              style={{
                width: 32, height: 32, borderRadius: '50%',
                background: 'var(--card)', border: '1px solid var(--border)',
                color: 'var(--muted)', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 13, fontWeight: 700, flexShrink: 0,
              }}
            >?</button>
            {/* Notification */}
            <div className="notif-btn">
              🔔
              <div className="notif-dot"/>
            </div>
            {/* New Job */}
            <button onClick={handleNewJob} className="btn btn-cyan">
              + New Job
            </button>
          </div>
        </header>

        {/* Trial countdown banner */}
        {trialDaysLeft !== null && (
          <div style={{
            background: 'linear-gradient(90deg, #1B6CA8, #00C2E0)',
            color: '#fff',
            padding: '8px 24px',
            fontSize: 13,
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 12,
            flexShrink: 0,
          }}>
            <span>⏰ Trial: <strong>{trialDaysLeft} day{trialDaysLeft !== 1 ? 's' : ''} remaining</strong> — Subscribe now to keep access</span>
            <a href="/subscribe" style={{ color: '#fff', fontWeight: 700, textDecoration: 'underline', whiteSpace: 'nowrap' }}>
              Subscribe now →
            </a>
          </div>
        )}

        {/* Content */}
        <main style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
          {children}
        </main>
      </div>

      <HelpPanel pathname={pathname} open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
