'use client'
import { useEffect } from 'react'
import { useRouter } from '@/i18n/navigation'

interface HelpTip {
  heading: string
  body: string
}

interface HelpContent {
  title: string
  intro: string
  tips: HelpTip[]
}

const HELP: Record<string, HelpContent> = {
  '/': {
    title: 'Dashboard',
    intro: 'Your real-time recruitment command centre.',
    tips: [
      { heading: 'Pipeline counts', body: 'Each number shows candidates at that stage across all active jobs — Discovered → Profiled → Scored → Passed → Emailed → Applied → Tested → Invited.' },
      { heading: 'Recent activity', body: 'Live feed of audit events from all pipelines. Green = success, amber = warning, red = error.' },
      { heading: 'Setup banner', body: 'If the blue setup banner appears, click "Continue Setup" to finish configuring your account via the Quick Start page.' },
      { heading: 'New Job button', body: 'Use the "+ New Job" button in the top bar to start the AI Recruiter chat and create a job.' },
    ],
  },
  '/chat': {
    title: 'AI Recruiter Chat',
    intro: 'The AI collects job details through a conversation, then posts the job and starts the pipeline.',
    tips: [
      { heading: 'Mode 1 — Talent Scout', body: 'The AI will actively search LinkedIn for candidates, score them, find their emails, and send personalised outreach automatically.' },
      { heading: 'Mode 2 — Screener Only', body: 'Candidates apply by emailing your jobs inbox. The AI screens their CVs, invites top candidates to a competency test, and notifies your hiring manager.' },
      { heading: 'What to say', body: 'Just describe the role naturally — job title, location, required skills, salary range. The AI will ask follow-up questions for anything missing.' },
      { heading: 'Interview types', body: 'For Screener Only jobs you can choose: text-based test, audio recording, video recording, or audio + video combined.' },
    ],
  },
  '/chat/history': {
    title: 'Chat History',
    intro: 'All previous AI Recruiter conversations.',
    tips: [
      { heading: 'Resuming a chat', body: 'Click any conversation to continue it. Useful if a job creation was interrupted mid-way.' },
      { heading: 'Completed chats', body: 'Once a job is created the chat phase moves to "recruitment". These chats are kept for reference.' },
    ],
  },
  '/jobs': {
    title: 'Jobs',
    intro: 'All jobs posted through your account.',
    tips: [
      { heading: 'AI Scout badge', body: 'Jobs with the "AI Scout" badge use Mode 1 — the Talent Scout pipeline runs automatically.' },
      { heading: 'Screener Only badge', body: 'Jobs with "Screener Only" only process inbound CVs via your email inbox.' },
      { heading: 'Triggering the Scout', body: 'Open a job and click "Trigger Scout" to manually start a new discovery run, e.g. after pausing.' },
      { heading: 'Job statuses', body: 'Active = pipeline running. Paused = pipeline stopped but data kept. Closed = no further processing.' },
    ],
  },
  '/jobs/': {
    title: 'Job Detail',
    intro: 'Full detail view for a single job with tabs for evaluation, audit trail, and job spec.',
    tips: [
      { heading: 'Evaluation tab', body: 'Shows all candidates and applications with scores. Click any row to open the full profile.' },
      { heading: 'Audit tab', body: 'Live stream of every pipeline step for this job. Use the filters to isolate errors or specific event types.' },
      { heading: 'Spec tab', body: 'The original job specification as captured by the AI during the chat.' },
      { heading: 'Minimum score', body: 'Only candidates scoring at or above the minimum score proceed to outreach. Adjust this in the job settings.' },
    ],
  },
  '/candidates': {
    title: 'Candidates',
    intro: 'All candidates discovered by the Talent Scout across all jobs.',
    tips: [
      { heading: 'Suitability score', body: 'Scored 1–10 by the AI against the job requirements. 8+ = strong match, 6–7 = good, below 6 = weak.' },
      { heading: 'Opted Out badge', body: 'Candidates who clicked the unsubscribe link in their outreach email. They will never be emailed again.' },
      { heading: 'Status pipeline', body: 'Discovered → Profiled → Scored → Passed/Failed → Emailed → Applied.' },
      { heading: 'Manual outreach', body: 'Open a candidate profile and click "Send Outreach" to trigger a manual personalised email.' },
    ],
  },
  '/candidates/': {
    title: 'Candidate Profile',
    intro: 'Full profile for a single candidate including AI scoring and LinkedIn data.',
    tips: [
      { heading: 'AI Score Reasoning', body: 'The AI\'s explanation of why it gave this score, with specific strengths and gaps.' },
      { heading: 'LinkedIn Profile', body: 'Enriched BrightData profile showing work history, skills, education, and certifications.' },
      { heading: 'Outreach Email', body: 'The personalised email sent to this candidate, shown at the bottom of the profile.' },
      { heading: 'GDPR Delete', body: 'Anonymises all PII for this candidate and redacts their data from the audit trail. Cannot be undone.' },
    ],
  },
  '/applications': {
    title: 'Applications',
    intro: 'Inbound applications received via your email inbox.',
    tips: [
      { heading: 'How applications arrive', body: 'Candidates email their CV to your jobs inbox. The IMAP poller checks every 5 minutes and creates an application automatically.' },
      { heading: 'Resume score', body: 'AI screening score (1–10) comparing the CV to the job requirements using semantic similarity.' },
      { heading: 'Test score', body: 'Score awarded after the candidate completes the competency test (text, audio, or video).' },
      { heading: 'HM Notification', body: 'Once a candidate passes the test, your hiring manager receives an email with all 3 scores and a one-click "Invite to Interview" button.' },
    ],
  },
  '/applications/': {
    title: 'Application Detail',
    intro: 'Full evaluation report for a single application.',
    tips: [
      { heading: '3 scores', body: 'Resume Score (CV vs job), Test Score (competency answers), and Overall Score from the AI evaluation.' },
      { heading: 'Per-question evaluation', body: 'The AI rates each test answer as Strong / Adequate / Weak with a written assessment.' },
      { heading: 'Recording playback', body: 'For audio/video interviews, recordings are stored in Supabase Storage and playable directly in this view.' },
      { heading: 'Interview invited', body: 'Shows a green tick once the hiring manager has clicked the Invite to Interview button.' },
    ],
  },
  '/settings': {
    title: 'Settings',
    intro: 'Configure your AI Recruiter account, integrations, and pipeline behaviour.',
    tips: [
      { heading: 'API Keys', body: 'Add your own OpenAI or Anthropic key to use your own quota. Leave blank to use the platform key.' },
      { heading: 'Email & Mailbox', body: 'Set up IMAP credentials so the Resume Screener can receive inbound applications. Requires IMAP4 SSL access on port 993.' },
      { heading: 'Knowledge Base', body: 'Upload PDFs or scrape your website so the AI knows about your company when candidates chat with the widget.' },
      { heading: 'AI Recruiter Prompt', body: 'Customise the system prompt the AI uses during job creation chat to match your tone and process.' },
      { heading: 'Billing', body: 'Use "Manage Billing" to access the Stripe portal to update payment, change plan, or cancel subscription.' },
    ],
  },
  '/quickstart': {
    title: 'Quick Start',
    intro: 'Step-by-step setup guide to get your AI Recruiter fully configured.',
    tips: [
      { heading: 'Step order', body: 'Complete the steps in order — each one unlocks more pipeline functionality.' },
      { heading: 'Auto-detection', body: 'Steps are automatically marked complete when the system detects the configuration is in place. Click "Refresh status" after saving settings.' },
      { heading: 'Always accessible', body: 'This page is always available from the sidebar even after all steps are complete, as a reference.' },
    ],
  },
  '/super-admin': {
    title: 'Super Admin',
    intro: 'Platform-wide management for the AIWorkerz team only.',
    tips: [
      { heading: 'MRR', body: 'Monthly Recurring Revenue calculated live from active paying subscriptions.' },
      { heading: 'Failed Tasks (24h)', body: 'Count of error-severity audit events in the last 24 hours across all tenants.' },
      { heading: 'Impersonate', body: 'Generates a 1-hour token to log in as any tenant. All impersonation events are audit-logged.' },
      { heading: 'Promo Codes', body: 'Platform-wide codes (tenant_id = NULL) are available to all tenants at checkout.' },
    ],
  },
}

function getContent(pathname: string): HelpContent {
  if (HELP[pathname]) return HELP[pathname]
  // Match by prefix for detail pages
  for (const key of Object.keys(HELP).sort((a, b) => b.length - a.length)) {
    if (key.endsWith('/') && pathname.startsWith(key)) return HELP[key]
  }
  return {
    title: 'Help',
    intro: 'AI Recruiter automates candidate discovery, screening, and outreach.',
    tips: [
      { heading: 'Getting started', body: 'Use the AI Recruiter Chat to create your first job. The AI will guide you through the process.' },
      { heading: 'Full documentation', body: 'Visit the Help page for complete guides on every feature.' },
    ],
  }
}

interface HelpPanelProps {
  pathname: string
  open: boolean
  onClose: () => void
}

export default function HelpPanel({ pathname, open, onClose }: HelpPanelProps) {
  const router = useRouter()
  const content = getContent(pathname)

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          onClick={onClose}
          style={{
            position: 'fixed', inset: 0, zIndex: 40,
            background: 'rgba(0,0,0,0.4)',
          }}
        />
      )}

      {/* Drawer */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 50,
        width: 360, maxWidth: '90vw',
        background: 'var(--navy-mid)',
        borderLeft: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column',
        transform: open ? 'translateX(0)' : 'translateX(100%)',
        transition: 'transform 0.25s cubic-bezier(0.4,0,0.2,1)',
        boxShadow: open ? '-8px 0 32px rgba(0,0,0,0.4)' : 'none',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px', borderBottom: '1px solid var(--border)', flexShrink: 0,
        }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--white)' }}>
              ? Help — {content.title}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--muted)', fontSize: 20, lineHeight: 1, padding: 4,
          }}>✕</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
          <p style={{ fontSize: 13, color: 'var(--cyan)', marginBottom: 20, lineHeight: 1.6 }}>
            {content.intro}
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {content.tips.map((tip, i) => (
              <div key={i} style={{
                background: 'var(--card)', border: '1px solid var(--border)',
                borderRadius: 8, padding: '12px 14px',
              }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--white)', marginBottom: 4 }}>
                  {tip.heading}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.6 }}>
                  {tip.body}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div style={{
          padding: '16px 20px', borderTop: '1px solid var(--border)', flexShrink: 0,
          display: 'flex', gap: 8,
        }}>
          <button
            className="btn btn-ghost btn-sm"
            style={{ flex: 1, justifyContent: 'center' }}
            onClick={() => { onClose(); router.push('/help') }}
          >
            Full Documentation →
          </button>
        </div>
      </div>
    </>
  )
}
