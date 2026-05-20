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
  require_local_candidates: boolean
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
  anthropic_model: string
  openai_model: string
  search_provider: 'scrapingdog' | 'brightdata' | 'both'
  gdpr_dpa_signed_at: string | null
  data_retention_months: number
  recruiter_system_prompt: string | null
  widget_primary_color: string | null
  widget_bot_name: string | null
  outreach_from_name: string | null
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

export interface IcpConfig {
  target_titles: string[]
  company_types: string[]
  size_min: number
  size_max: number
  locations: string[]
  min_score: number
}

export interface SmtpConfig {
  host: string
  port: number
  username: string
  password: string
}

export interface ChannelConfig {
  brightdata_api_key?: string
  hunter_api_key?: string
  smtp?: SmtpConfig
}

export interface SignalConfig {
  hiring_spike_threshold: number
  scrape_frequency_hours: number
  monitor_pain_posts: boolean
  monitor_growth_signals: boolean
  auto_enroll: boolean
  require_approval: boolean
}

export interface OutreachLimits {
  linkedin_connects_per_day: number
  linkedin_dms_per_day: number
  emails_per_day: number
  window_start_utc: string
  window_end_utc: string
  skip_weekends: boolean
}

export interface TenantModeConfig {
  min_plan: string
  max_prospects_per_month: number
  max_sequences: number
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
  // Client Pipeline config (migration 0024)
  icp_config: IcpConfig | null
  channel_config: ChannelConfig | null
  signal_config: SignalConfig | null
  outreach_limits: OutreachLimits | null
  tenant_mode_enabled: boolean
  tenant_mode_config: TenantModeConfig | null
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

// ── Client Pipeline: Content tab ──────────────────────────────────────────────

export type ContentPostType = 'roi_post' | 'pain_post' | 'proof_post' | 'tip_post'
export type ContentPostStatus = 'draft' | 'scheduled' | 'posted' | 'partial' | 'failed' | 'discarded'

export interface PagePublishResult {
  status: 'posted' | 'failed' | 'pending'
  post_id?: string
  posted_at?: string
  error?: string
}

export interface LinkedInPage {
  id: string
  tenant_id: string
  linkedin_account_id: string
  page_type: 'personal' | 'company' | 'showcase'
  page_name: string
  page_urn: string
  page_id: string
  vanity_name: string | null
  logo_url: string | null
  follower_count: number | null
  is_active: boolean
  last_synced_at: string | null
  created_at: string
}

export interface SyncPagesResponse {
  pages_synced: number
  pages: LinkedInPage[]
}

export interface ContentPost {
  id: string
  post_type: ContentPostType
  content: string
  hashtags: string[]
  status: ContentPostStatus
  scheduled_at: string | null
  posted_at: string | null
  impressions: number
  likes: number
  comments: number
  connections_attributed: number
  demos_attributed: number
  platform_post_id: string | null
  target_pages: string[] | null       // array of page URNs
  publish_results: Record<string, PagePublishResult> | null  // {urn: result}
  created_at: string
}

export interface ContentStatsResponse {
  avg_views: number
  avg_connections: number
  post_demo_rate: number
  best_post_type: ContentPostType | null
  mix: Record<ContentPostType, number>
  upcoming: ContentPost[]
}

// ── Client Pipeline: Prospects ─────────────────────────────────────────────────

export type ProspectStage = 'identified' | 'connected' | 'messaged' | 'replied' | 'demo_booked' | 'trial' | 'paid'
export type ProspectSource = 'brightdata' | 'hunter' | 'manual'

export interface OutreachLog {
  id: string
  prospect_id: string
  step_id: string | null
  channel: 'linkedin' | 'email'
  sent_at: string | null
  opened_at: string | null
  replied_at: string | null
}

export interface Prospect {
  id: string
  tenant_id: string
  name: string | null
  company: string | null
  title: string | null
  location: string | null
  company_size: number | null
  company_type: string | null
  linkedin_url: string | null
  email: string | null
  icp_score: number | null
  score_breakdown: Record<string, number> | null
  source: ProspectSource
  stage: ProspectStage
  notes: string | null
  last_linkedin_post_at: string | null
  created_at: string
  last_activity_at: string | null
  outreach_log: OutreachLog[]
}

export interface ProspectListResponse {
  items: Prospect[]
  total: number
  page: number
  page_size: number
}

export interface ScrapeRequest {
  titles: string[]
  locations: string[]
  company_types: string[]
  company_size_min?: number
  company_size_max?: number
  max_prospects: 50 | 100 | 250 | 500
}

export interface ScrapeResponse {
  inserted: number
  message: string
}

// ── Client Pipeline: Signals & Sequences ──────────────────────────────────────

export type SignalType = 'hiring_spike' | 'pain_post' | 'growth_signal'
export type SignalUrgency = 'high' | 'medium'

export interface Signal {
  id: string
  tenant_id: string
  type: SignalType
  company: string | null
  person_name: string | null
  linkedin_url: string | null
  summary: string | null
  urgency: SignalUrgency
  detected_at: string
  actioned: boolean
  dismissed: boolean
  location: string | null
  company_type: string | null
  job_count: number | null
}

export interface SignalRun {
  id: string
  tenant_id: string
  started_at: string
  completed_at: string | null
  signals_found: number
}

export interface SignalListResponse {
  items: Signal[]
  total: number
  last_run: SignalRun | null
  scrape_frequency_hours: number
}

export interface SequenceSummary {
  id: string
  name: string
  status: 'live' | 'paused'
  enrolled_count: number
  reply_rate: number  // 0.0–1.0
}

// ── Full Sequence objects (for SequencesTab) ──────────────────────────────────

export type SequenceStatus = 'live' | 'paused' | 'draft'
export type SequenceStepType = 'linkedin_connect' | 'linkedin_dm' | 'email' | 'wait'
export type SequenceAngle = 'pain-led' | 'ROI-led' | 'curiosity/question' | 'social proof'

export interface SequenceStep {
  id: string
  sequence_id: string
  step_type: SequenceStepType
  step_name: string | null
  day_offset: number
  message_template: string | null
  condition: string | null
  sort_order: number
  // Stats (from backend)
  sent_count: number
  accept_open_rate: number
  reply_rate: number
  has_been_sent: boolean
}

export interface Sequence {
  id: string
  tenant_id: string
  name: string
  status: SequenceStatus
  persona_target: string | null
  angle: SequenceAngle | null
  enrolled_count: number
  steps: SequenceStep[]
  channel_tags: string[]  // e.g. ['LI', 'Email', 'Wait']
}

export interface SequenceStats {
  sent: number
  accept_open_rate: number
  reply_rate: number
  demos_booked: number
}

export interface GeneratedStep {
  step_type: SequenceStepType
  day_offset: number
  message_template: string | null
  condition: string | null
}

export interface GenerateSequenceResponse {
  steps: GeneratedStep[]
}

export interface EnrollProspectsResponse {
  enrolled: number
  already_enrolled: number
}

export interface FunnelRow {
  stage: string
  label: string
  count: number
  percentage: number
}

export interface MetricCard {
  value: number
  delta: number
  pct_label: string | null
}

export interface PipelineSummary {
  prospects_found: MetricCard
  connected: MetricCard
  replied: MetricCard
  demos_booked: MetricCard
  trials_started: MetricCard
  funnel: FunnelRow[]
  signals: Signal[]
  recent_prospects: Prospect[]
  sequences: SequenceSummary[]
}

// ── Tenant Mode ──────────────────────────────────────────────────────────────

export interface TenantStatus {
  is_super_admin: boolean
  has_pipeline_access: boolean
  access_denied_reason: 'tenant_mode_disabled' | 'plan_too_low' | null
  min_plan: string | null
  has_linkedin: boolean
  has_hunter: boolean
  this_month_prospects: number
  prospect_month_limit: number | null
  sequences_used: number
  sequence_limit: number | null
  is_new_user: boolean
}

export interface TenantUsageRow {
  tenant_id: string
  tenant_name: string
  plan: string
  prospects_this_month: number
  sequences_count: number
  has_linkedin: boolean
  last_active: string | null
}

export interface AdminTenantUsage {
  rows: TenantUsageRow[]
}
