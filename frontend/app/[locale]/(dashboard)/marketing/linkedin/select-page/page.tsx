'use client'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useRouter } from '@/i18n/navigation'
import { marketingApi } from '@/lib/api'

interface LinkedInPage {
  organizationId: string
  organizationName: string
}

export default function SelectLinkedInPagePage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const token = searchParams.get('token') ?? ''

  const [pages, setPages] = useState<LinkedInPage[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setError('Missing selection token. Please reconnect your LinkedIn account.')
      setLoading(false)
      return
    }
    marketingApi.getSelectPageOptions(token)
      .then((data) => {
        setPages(data.pages)
        if (data.pages.length > 0) setSelected(data.pages[0].organizationId)
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to load pages'
        if (msg.includes('404')) {
          setError('Selection token has expired. Please reconnect your LinkedIn account.')
        } else {
          setError(msg)
        }
      })
      .finally(() => setLoading(false))
  }, [token])

  async function handleSubmit() {
    if (!selected) return
    const page = pages.find((p) => p.organizationId === selected)
    if (!page) return

    setSubmitting(true)
    setError(null)
    try {
      await marketingApi.selectLinkedInPage(token, page.organizationId, page.organizationName)
      router.push('/marketing?connected=true')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to connect company page')
      setSubmitting(false)
    }
  }

  return (
    <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 32 }}>
      <div className="card" style={{ maxWidth: 480, width: '100%' }}>
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 6 }}>Select Company Page</div>
          <div style={{ fontSize: 13, color: 'var(--muted)' }}>
            Multiple LinkedIn company pages were found on your account. Choose which one to connect.
          </div>
        </div>

        {error && (
          <div style={{
            background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.35)',
            borderRadius: 8, padding: '10px 14px', marginBottom: 16,
            fontSize: 13, color: 'var(--red)',
          }}>
            {error}
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: 24, color: 'var(--muted)', fontSize: 13 }}>
            Loading pages…
          </div>
        ) : pages.length === 0 && !error ? (
          <div style={{ textAlign: 'center', padding: 24, color: 'var(--muted)', fontSize: 13 }}>
            No pages found.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 20 }}>
            {pages.map((page) => (
              <label
                key={page.organizationId}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '12px 14px', borderRadius: 8, cursor: 'pointer',
                  border: `1px solid ${selected === page.organizationId ? 'var(--cyan)' : 'var(--border)'}`,
                  background: selected === page.organizationId ? 'var(--cyan-dim)' : 'var(--navy)',
                  transition: 'all 0.15s',
                }}
              >
                <input
                  type="radio"
                  name="page"
                  value={page.organizationId}
                  checked={selected === page.organizationId}
                  onChange={() => setSelected(page.organizationId)}
                  style={{ accentColor: 'var(--cyan)', flexShrink: 0 }}
                />
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--white)' }}>
                    {page.organizationName}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1, fontFamily: 'DM Mono, monospace' }}>
                    {page.organizationId}
                  </div>
                </div>
              </label>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => router.push('/marketing')}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={!selected || submitting || loading || pages.length === 0}
          >
            {submitting ? 'Connecting…' : 'Connect Page'}
          </button>
        </div>
      </div>
    </div>
  )
}
