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
  mode: 'talent_scout' | 'screener_only'
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
  opted_out: boolean
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
  // Unified pipeline status
  status: string
  // Resume
  resume_storage_path: string | null
  resume_filename: string | null
  resume_text: string | null
  resume_score: number | null
  resume_reasoning: string | null
  resume_strengths: string[] | null
  resume_gaps: string[] | null
  // Legacy screening fields
  screening_score: number | null
  screening_reasoning: string | null
  screening_status: 'pending' | 'passed' | 'failed'
  // Test
  test_status: 'not_started' | 'invited' | 'in_progress' | 'completed' | 'passed' | 'failed'
  test_score: number | null
  test_answers: Record<string, unknown> | null
  test_evaluation: {
    overall_score?: number
    overall_summary?: string
    recommended_action?: string
    strengths?: string[]
    gaps?: string[]
    questions?: Array<{
      question: string
      candidate_answer: string
      assessment: string
      rating: 'strong' | 'adequate' | 'weak'
      score: number
    }>
  } | null
  test_completed_at: string | null
  // Interview
  interview_invited: boolean
  interview_invited_at: string | null
  received_at: string | null
  created_at: string
  // Recording (from TestSession)
  recording_urls: string[] | null
  transcripts: Array<{ question_index: number; transcript: string }> | null
  interview_type: string | null
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
  plan: 'trial' | 'trial_expired' | 'recruiter' | 'agency_small' | 'agency_medium' | 'enterprise'
  credits_remaining: number
  trial_started_at: string | null
  trial_ends_at: string | null
  subscription_started_at: string | null
  subscription_ends_at: string | null
  ai_provider: 'anthropic' | 'openai'
  search_provider: 'scrapingdog' | 'brightdata' | 'both'
  gdpr_dpa_signed_at: string | null
  data_retention_months: number
  recruiter_system_prompt: string | null
  widget_primary_color: string | null
  widget_bot_name: string | null
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

export interface SuperAdminStats {
  total_tenants: number
  active_subscriptions: number
  mrr_aud: number
  failed_tasks_24h: number
}

export interface SystemHealth {
  celery_queue_depth: number | null
  failed_tasks_count: number | null
  worker_count: number | null
  redis_status: string | null
  status: string
  checked_at: string
}

export interface PromoCode {
  id: string
  tenant_id: string | null
  code: string
  type: 'credits' | 'discount_pct' | 'full_access'
  value: string
  expires_at: string | null
  max_uses: number | null
  uses_count: number
  is_active: boolean
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

// Marketing Module

export interface MarketingAccount {
  id: string
  tenant_id: string | null
  platform: 'linkedin' | 'twitter' | 'facebook'
  account_name: string
  account_type: 'personal' | 'company'
  linkedin_urn: string | null
  token_expires_at: string | null
  is_active: boolean
  created_at: string
  is_token_expiring_soon: boolean
  author_urn: string
  account_type_label: string
}

export interface MarketingSettings {
  id: string
  tenant_id: string | null
  post_frequency: 'daily' | 'twice_weekly' | 'weekly'
  post_time_utc: string          // HH:MM:SS
  post_types_enabled: string[]
  platforms_enabled: string[]
  target_audience: string | null
  tone: 'professional' | 'conversational' | 'bold' | 'educational'
  topics: string[]
  auto_engage: boolean
  engagement_per_day: number
  requires_approval: boolean
  include_images: boolean
  is_active: boolean
  created_at: string
}

export interface MarketingPost {
  id: string
  tenant_id: string | null
  account_id: string
  platform: 'linkedin' | 'twitter' | 'facebook'
  post_type: 'thought_leadership' | 'industry_stat' | 'success_story' | 'tip' | 'poll' | 'carousel'
  content: string
  hashtags: string[]
  topic: string | null
  include_image: boolean
  image_search_query: string | null
  image_url: string | null
  image_attribution: { photographer_name: string; photographer_url: string; unsplash_url: string } | null
  scheduled_at: string
  posted_at: string | null
  status: 'draft' | 'scheduled' | 'posted' | 'failed'
  retry_count: number
  platform_post_id: string | null
  likes: number
  comments: number
  impressions: number
  clicks: number
  created_at: string
}

export interface MarketingEngagement {
  id: string
  account_id: string
  action_type: 'like' | 'comment' | 'follow' | 'group_post'
  target_post_id: string
  target_author: string
  content: string | null
  performed_at: string
  created_at: string
}

export interface MarketingAnalyticsSummary {
  total_posts: number
  total_impressions: number
  avg_engagement_rate: number
  top_post: MarketingPost | null
}

export interface DailyAnalytics {
  date: string
  impressions: number
  likes: number
  comments: number
  posts_count: number
}
