'use client'
import { useState } from 'react'
import { useRouter } from '@/i18n/navigation'

interface DocSection {
  id: string
  title: string
  icon: string
  content: Array<{ heading: string; body: string }>
}

const DOCS: DocSection[] = [
  {
    id: 'overview',
    title: 'Platform Overview',
    icon: '🏠',
    content: [
      {
        heading: 'What is AI Recruiter?',
        body: 'AI Recruiter is a multi-tenant SaaS platform that automates the end-to-end recruitment process. It combines an AI Talent Scout (outbound candidate discovery) with an AI Resume Screener (inbound application processing) to help recruitment firms and hiring teams move faster with less manual effort.',
      },
      {
        heading: 'Two pipeline modes',
        body: 'Mode 1 — Talent Scout: The AI searches LinkedIn via SERP APIs, enriches profiles with BrightData, scores candidates against your job requirements, discovers their email addresses, and sends personalised outreach — all automatically.\n\nMode 2 — Screener Only: Candidates email their CVs to your jobs inbox. The AI screens resumes, invites strong candidates to a competency test (text, audio, or video), scores their answers, and notifies your hiring manager with a one-click "Invite to Interview" button.',
      },
      {
        heading: 'AI provider',
        body: 'The platform uses OpenAI GPT-4o as the primary AI provider, with Anthropic Claude as automatic fallback. You can supply your own API keys in Settings → API Keys to use your own quota, or leave them blank to use the platform keys.',
      },
    ],
  },
  {
    id: 'getting-started',
    title: 'Getting Started',
    icon: '🚀',
    content: [
      {
        heading: 'Quick Start checklist',
        body: '1. Add your API keys (Settings → API Keys)\n2. Configure your IMAP email inbox (Settings → Email & Mailbox)\n3. Upload your company knowledge base (Settings → Knowledge Base)\n4. Create your first job via the AI Recruiter Chat\n5. Activate the Talent Scout or wait for applications',
      },
      {
        heading: 'Creating a job',
        body: 'Click "+ New Job" or go to AI Recruiter Chat. The AI will ask you for the job title, location, required skills, experience level, salary range, and hiring manager details. Just describe the role naturally — the AI handles the structured data extraction.',
      },
      {
        heading: 'Choosing a mode',
        body: 'Mode 1 (Talent Scout) is best when you want to proactively find passive candidates. Mode 2 (Screener Only) is best when you already advertise the role and just need to screen inbound CVs. You can only choose the mode at job creation time.',
      },
    ],
  },
  {
    id: 'talent-scout',
    title: 'Talent Scout Pipeline',
    icon: '🔍',
    content: [
      {
        heading: 'How discovery works',
        body: 'The Scout generates multiple search queries from your job title and location, runs them through ScrapingDog (Google SERP), and creates candidate records for each LinkedIn profile found. Duplicate profiles across queries are automatically de-duplicated.',
      },
      {
        heading: 'Profile enrichment',
        body: 'BrightData fetches the full LinkedIn profile for each candidate: work history, skills, education, certifications, and contact details. This data is displayed in the candidate profile view.',
      },
      {
        heading: 'AI scoring',
        body: 'Each candidate is scored 1–10 against the job requirements. The AI considers skills match, experience level, seniority, and location fit. Only candidates at or above your minimum score threshold proceed to email discovery and outreach.',
      },
      {
        heading: 'Email discovery',
        body: 'The system tries Apollo, Hunter, and Snov in sequence (based on your Settings → API Keys configuration). If all fail, the EmailDeductionService attempts to guess the email format from the company domain and verifies it via SMTP.',
      },
      {
        heading: 'Personalised outreach',
        body: 'The AI writes a unique email for each candidate referencing their specific experience and why this opportunity is relevant to their career. Every outreach email includes an unsubscribe link. Candidates who opt out are never contacted again.',
      },
    ],
  },
  {
    id: 'resume-screener',
    title: 'Resume Screener Pipeline',
    icon: '📄',
    content: [
      {
        heading: 'How applications arrive',
        body: 'Candidates email their CV to your jobs inbox (configured in Settings → Email & Mailbox). The IMAP poller checks every 5 minutes for new emails and creates an Application record automatically. Supported file formats: PDF, DOCX, DOC.',
      },
      {
        heading: 'Resume scoring',
        body: 'The AI compares the CV text against the job requirements using both embedding similarity and direct AI evaluation. It produces a resume score (1–10), a written reasoning, and lists of strengths and gaps.',
      },
      {
        heading: 'Competency test',
        body: 'Candidates who pass the resume screen receive an invitation email with a link to the competency test. The test uses the interview type set on the job: text (typed answers), audio (recorded voice), video (recorded video), or audio + video.',
      },
      {
        heading: 'Test scoring',
        body: 'The AI evaluates each answer as Strong / Adequate / Weak and produces a test score (1–10). For audio and video, answers are transcribed via OpenAI Whisper before scoring.',
      },
      {
        heading: 'Hiring manager notification',
        body: 'Once a candidate passes the test, the hiring manager receives an email with all 3 scores (resume, test, overall) and a one-click "Invite to Interview" button. Clicking the button sends the candidate an invitation and logs the event.',
      },
    ],
  },
  {
    id: 'settings',
    title: 'Settings & Configuration',
    icon: '⚙️',
    content: [
      {
        heading: 'API Keys',
        body: 'Add your own OpenAI or Anthropic key to use your own API quota. Also configure ScrapingDog, BrightData, Apollo, Hunter, and Snov keys for the Talent Scout pipeline. All keys are encrypted at rest.',
      },
      {
        heading: 'Email & Mailbox',
        body: 'Enter your IMAP credentials to enable inbound resume screening. Requires IMAP4 SSL on port 993. The platform checks for new emails every 5 minutes. Only tenants with all 4 IMAP fields set (host, port, user, password) will have their mailbox polled.',
      },
      {
        heading: 'Knowledge Base',
        body: 'Upload PDF or Word documents, or provide a website URL to scrape. This content is chunked, embedded, and stored for use by the Chat Widget when candidates ask questions about your company.',
      },
      {
        heading: 'AI Recruiter Prompt',
        body: 'Customise the system prompt used during job creation chat. Use this to add your firm\'s tone of voice, standard job requirements, or specific questions you always want asked.',
      },
      {
        heading: 'Team Members',
        body: 'Invite colleagues with Admin, Recruiter, or Hiring Manager roles. Hiring Managers receive test result notifications for jobs where they are assigned.',
      },
      {
        heading: 'Billing',
        body: 'Click "Manage Billing" to open the Stripe Customer Portal where you can update your payment method, change your plan, view invoices, or cancel your subscription.',
      },
      {
        heading: 'Privacy & Data',
        body: 'Sign your Data Processing Agreement (DPA), configure data retention period (default 12 months), and export or delete all your data from here.',
      },
    ],
  },
  {
    id: 'billing',
    title: 'Plans & Billing',
    icon: '💳',
    content: [
      {
        heading: 'Trial',
        body: 'Free 14-day trial. Includes 3 active jobs, 10 candidates per job, and 50 resume screenings per job. No credit card required to start.',
      },
      {
        heading: 'Recruiter — $499/mo',
        body: '5 active jobs, 20 candidates per job, 50 resume screenings per job. Full access to Talent Scout and Resume Screener pipelines.',
      },
      {
        heading: 'Agency Small — $999/mo',
        body: '20 active jobs, 40 candidates per job, 75 resume screenings. Everything in Recruiter plus Chat Widget, team members (up to 5), and priority support.',
      },
      {
        heading: 'Agency Medium — $2,999/mo',
        body: '75 active jobs, 60 candidates per job, 100 resume screenings. Everything in Agency Small plus unlimited team members, advanced analytics, and a dedicated account manager.',
      },
      {
        heading: 'Enterprise',
        body: 'Unlimited everything. Custom integrations, SLA guarantees, on-premise option. Contact support@airecruiterz.com.',
      },
    ],
  },
  {
    id: 'gdpr',
    title: 'GDPR & Compliance',
    icon: '🔒',
    content: [
      {
        heading: 'Candidate data',
        body: 'All candidate PII is stored per-tenant in your Supabase database. The platform never shares candidate data between tenants.',
      },
      {
        heading: 'Unsubscribe',
        body: 'Every outreach email includes an unsubscribe link. Candidates who click it are immediately flagged as opted_out and will never be emailed again by the platform.',
      },
      {
        heading: 'GDPR erasure',
        body: 'Use the "GDPR Delete" button on any candidate profile to anonymise all their PII. This replaces personal data with [REDACTED] and deletes their resume file from storage. The audit record is kept but scrubbed of PII.',
      },
      {
        heading: 'Data retention',
        body: 'Configure your retention period in Settings → Privacy & Data. Candidates inactive beyond this period are automatically anonymised by the nightly cleanup task.',
      },
      {
        heading: 'DPA',
        body: 'Sign the Data Processing Agreement in Settings → Privacy & Data. This is required for GDPR compliance when processing EU candidate data.',
      },
    ],
  },
  {
    id: 'troubleshooting',
    title: 'Troubleshooting',
    icon: '🛠',
    content: [
      {
        heading: 'No candidates being discovered',
        body: 'Check that your ScrapingDog API key is set in Settings → API Keys. Verify the job is in "active" status. Open the job\'s Audit Trail tab to see if any errors are logged.',
      },
      {
        heading: 'Applications not arriving',
        body: 'Check IMAP credentials in Settings → Email & Mailbox. Ensure all 4 fields (host, port, user, password) are filled. The host must support IMAP4 SSL on port 993. Check your email provider hasn\'t blocked IMAP access.',
      },
      {
        heading: 'Outreach emails going to spam',
        body: 'Set up SPF/DKIM domain authentication for your sending domain in SendGrid. Go to Settings → Email & Mailbox for instructions, or contact support.',
      },
      {
        heading: 'AI responses failing',
        body: 'If OpenAI is overloaded, the system automatically falls back to Anthropic and retries indefinitely. Check the Audit Trail for error events. If both providers fail, tasks retry every 5 minutes.',
      },
      {
        heading: 'Contact support',
        body: 'Email support@airecruiterz.com or use the Support button (bottom-right of the screen) for live assistance.',
      },
    ],
  },
]

export default function HelpPage() {
  const router = useRouter()
  const [activeSection, setActiveSection] = useState('overview')
  const [search, setSearch] = useState('')

  const section = DOCS.find(d => d.id === activeSection) ?? DOCS[0]

  const filteredDocs = search.trim()
    ? DOCS.map(doc => ({
        ...doc,
        content: doc.content.filter(c =>
          c.heading.toLowerCase().includes(search.toLowerCase()) ||
          c.body.toLowerCase().includes(search.toLowerCase())
        ),
      })).filter(doc => doc.content.length > 0)
    : null

  return (
    <div style={{ height: '100%', display: 'flex', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside style={{
        width: 220, flexShrink: 0,
        borderRight: '1px solid var(--border)',
        overflowY: 'auto', padding: '20px 12px',
        background: 'var(--navy-mid)',
      }}>
        <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.8px', fontWeight: 600, padding: '0 8px', marginBottom: 12 }}>
          Documentation
        </div>
        {DOCS.map(doc => (
          <button key={doc.id} onClick={() => { setActiveSection(doc.id); setSearch('') }}
            style={{
              display: 'flex', alignItems: 'center', gap: 8, width: '100%',
              padding: '8px 10px', borderRadius: 6, border: 'none', cursor: 'pointer',
              background: activeSection === doc.id ? 'var(--cyan-dim)' : 'transparent',
              color: activeSection === doc.id ? 'var(--cyan)' : 'var(--muted)',
              fontSize: 13, fontWeight: 500, marginBottom: 2, textAlign: 'left',
            }}>
            <span>{doc.icon}</span>
            <span>{doc.title}</span>
          </button>
        ))}
      </aside>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '28px 32px' }}>
        {/* Search */}
        <div style={{ marginBottom: 24, maxWidth: 480 }}>
          <input
            className="form-input"
            placeholder="Search documentation…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        {/* Search results */}
        {filteredDocs ? (
          filteredDocs.length === 0 ? (
            <div style={{ color: 'var(--muted)', fontSize: 14 }}>No results for "{search}"</div>
          ) : (
            filteredDocs.map(doc => (
              <div key={doc.id} style={{ marginBottom: 32 }}>
                <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--white)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span>{doc.icon}</span> {doc.title}
                </div>
                {doc.content.map((item, i) => (
                  <div key={i} style={{ marginBottom: 16, padding: '14px 16px', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--white)', marginBottom: 6 }}>{item.heading}</div>
                    <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.7, whiteSpace: 'pre-line' }}>{item.body}</div>
                  </div>
                ))}
              </div>
            ))
          )
        ) : (
          <>
            <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--white)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 10 }}>
              <span>{section.icon}</span> {section.title}
            </div>
            <div style={{ height: 2, background: 'var(--border)', marginBottom: 24, borderRadius: 1 }} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {section.content.map((item, i) => (
                <div key={i} style={{ padding: '16px 18px', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--white)', marginBottom: 8 }}>{item.heading}</div>
                  <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.75, whiteSpace: 'pre-line' }}>{item.body}</div>
                </div>
              ))}
            </div>
          </>
        )}

        <div style={{ marginTop: 40, paddingTop: 20, borderTop: '1px solid var(--border)', fontSize: 13, color: 'var(--muted)' }}>
          Still stuck? Email <a href="mailto:support@airecruiterz.com" style={{ color: 'var(--cyan)' }}>support@airecruiterz.com</a>
        </div>
      </div>
    </div>
  )
}
