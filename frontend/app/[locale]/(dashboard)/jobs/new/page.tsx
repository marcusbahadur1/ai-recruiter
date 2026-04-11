'use client'
import { useRouter } from '@/i18n/navigation'

export default function NewJobPage() {
  const router = useRouter()

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '48px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <div style={{ maxWidth: 800, width: '100%' }}>
        <div style={{ marginBottom: 40, textAlign: 'center' }}>
          <h1 style={{ fontSize: 28, fontWeight: 800, marginBottom: 8 }}>Create a New Job</h1>
          <p style={{ color: 'var(--muted)', fontSize: 15 }}>Choose how you want to find candidates for this role.</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
          {/* Card 1 — AI Talent Scout + Resume Screener */}
          <div style={{
            background: 'var(--card)',
            border: '2px solid var(--blue)',
            borderRadius: 16,
            padding: 32,
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
            cursor: 'pointer',
            transition: 'border-color 0.15s, box-shadow 0.15s',
          }}
            onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.boxShadow = '0 0 0 3px rgba(59,130,246,0.2)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.boxShadow = 'none' }}
          >
            <div style={{ fontSize: 36, lineHeight: 1 }}>🤖</div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 6 }}>AI Talent Scout + Resume Screener</div>
              <div style={{ color: 'var(--muted)', fontSize: 14, lineHeight: 1.6 }}>
                AI finds passive candidates on LinkedIn, contacts them, then screens their resumes automatically.
              </div>
            </div>
            <div style={{ background: 'var(--navy)', borderRadius: 8, padding: '10px 14px', fontSize: 12, color: 'var(--muted)' }}>
              <span style={{ color: 'var(--cyan)', fontWeight: 600 }}>Best for:</span> Hard to fill roles, senior positions, passive talent
            </div>
            <button
              onClick={() => router.push('/chat')}
              style={{
                marginTop: 'auto',
                padding: '12px 20px',
                background: 'var(--blue)',
                color: '#fff',
                border: 'none',
                borderRadius: 8,
                fontWeight: 700,
                fontSize: 14,
                cursor: 'pointer',
                textAlign: 'center',
              }}
            >
              Start with AI Scout →
            </button>
          </div>

          {/* Card 2 — Resume Screener Only */}
          <div style={{
            background: 'var(--card)',
            border: '2px solid var(--cyan)',
            borderRadius: 16,
            padding: 32,
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
            cursor: 'pointer',
            transition: 'border-color 0.15s, box-shadow 0.15s',
          }}
            onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.boxShadow = '0 0 0 3px rgba(0,194,224,0.2)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.boxShadow = 'none' }}
          >
            <div style={{ fontSize: 36, lineHeight: 1 }}>📋</div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 6 }}>Resume Screener Only</div>
              <div style={{ color: 'var(--muted)', fontSize: 14, lineHeight: 1.6 }}>
                Post the job yourself. AI screens incoming resumes and conducts competency interviews automatically.
              </div>
            </div>
            <div style={{ background: 'var(--navy)', borderRadius: 8, padding: '10px 14px', fontSize: 12, color: 'var(--muted)' }}>
              <span style={{ color: 'var(--cyan)', fontWeight: 600 }}>Best for:</span> High inbound interest, junior roles, advertised positions
            </div>
            <button
              onClick={() => router.push('/jobs/new/screener')}
              style={{
                marginTop: 'auto',
                padding: '12px 20px',
                background: 'var(--cyan)',
                color: '#fff',
                border: 'none',
                borderRadius: 8,
                fontWeight: 700,
                fontSize: 14,
                cursor: 'pointer',
                textAlign: 'center',
              }}
            >
              Screener Only →
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
