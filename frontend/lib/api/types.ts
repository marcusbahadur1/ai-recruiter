export interface PaginatedResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface Job {
  id: string
  tenant_id: string
  job_ref: string
  title: string
  job_type: string
  description: string
  required_skills: string[]
  experience_years: number
  salary_min: number | null
  salary_max: number | null
  location: string
  work_type: 'onsite' | 'hybrid' | 'remote' | 'remote_global'
  tech_stack: string[]
  minimum_score: number
  hiring_manager_email: string
  hiring_manager_name: string
  evaluation_prompt: string
  status: 'draft' | 'active' | 'paused' | 'closed'
  candidate_count?: number
  candidates?: Candidate[]
  created_at: string
  updated_at: string
}

export interface Candidate {
  id: string
  tenant_id: string
  job_id: string
  name: string
  title: string
  snippet: string
  linkedin_url: string
  email: string | null
  email_source: string
  company: string
  location: string
  brightdata_profile: Record<string, unknown>
  suitability_score: number | null
  score_reasoning: string
  strengths: string[] | null
  gaps: string[] | null
  status: string
  outreach_email_sent_at: string | null
  outreach_email_content: string
  job_title?: string
  created_at: string
}

export interface Application {
  id: string
  tenant_id: string
  job_id: string
  candidate_id: string | null
  applicant_name: string
  applicant_email: string
  resume_storage_path: string
  resume_text: string
  screening_score: number | null
  screening_reasoning: string
  screening_status: 'pending' | 'passed' | 'failed'
  test_status: 'not_started' | 'invited' | 'in_progress' | 'completed' | 'passed' | 'failed'
  test_score: number | null
  test_answers: Record<string, unknown> | null
  interview_invited: boolean
  interview_invited_at: string | null
  received_at: string
  created_at: string
}

export interface ChatSession {
  id: string
  tenant_id: string
  user_id: string
  job_id: string | null
  messages: Array<{ role: 'user' | 'assistant'; content: string; timestamp: string }>
  phase: 'job_collection' | 'payment' | 'recruitment' | 'post_recruitment'
  created_at: string
  updated_at: string
}

export interface AuditEvent {
  id: string
  tenant_id: string
  job_id: string
  candidate_id: string | null
  event_type: string
  event_category: 'talent_scout' | 'resume_screener' | 'payment' | 'system'
  severity: 'info' | 'success' | 'warning' | 'error'
  actor: string
  summary: string
  detail: Record<string, unknown> | null
  duration_ms: number | null
  created_at: string
}

export interface Tenant {
  id: string
  name: string
  slug: string
  phone: string
  address: string
  main_contact_name: string
  main_contact_email: string
  email_inbox: string
  jobs_email: string | null
  email_inbox_host: string | null
  email_inbox_port: number | null
  email_inbox_user: string | null
  website_url: string | null
  stripe_customer_id: string | null
  stripe_subscription_id: string | null
  plan: 'free' | 'casual' | 'individual' | 'small_firm' | 'mid_firm' | 'enterprise'
  credits_remaining: number
  ai_provider: 'anthropic' | 'openai'
  search_provider: 'scrapingdog' | 'brightdata' | 'both'
  gdpr_dpa_signed_at: string | null
  data_retention_months: number
  is_active: boolean
  created_at: string
}

export interface RagDocument {
  id: string
  tenant_id: string
  source_type: 'website_scrape' | 'manual_upload'
  source_url: string | null
  filename: string | null
  content_text: string
  created_at: string
}

export interface TeamMember {
  id: string
  tenant_id: string
  email: string
  name: string | null
  role: 'admin' | 'recruiter' | 'hiring_manager'
  status: 'invited' | 'active' | 'removed'
  invited_at: string
  joined_at: string | null
}

export interface DashboardPipeline {
  discovered: number
  profiled: number
  scored: number
  passed: number
  emailed: number
  applied: number
  tested: number
  invited: number
}

export interface DashboardJobItem {
  id: string
  title: string
  status: string
  job_ref: string
  candidate_count: number
}

export interface DashboardStats {
  active_jobs: number
  candidates_today: number
  applications: number
  credits_remaining: number
  pipeline: DashboardPipeline
  recent_activity: AuditEvent[]
  active_jobs_list: DashboardJobItem[]
}
