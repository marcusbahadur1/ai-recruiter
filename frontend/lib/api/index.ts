import { apiClient, supabase } from './client'
import type {
  PaginatedResponse, Job, Candidate, Application,
  ChatSession, AuditEvent, Tenant, DashboardStats,
  RagDocument, TeamMember, SuperAdminStats, SystemHealth, PromoCode,
} from './types'

export * from './types'
export { supabase }

// Auth
export const authApi = {
  async login(email: string, password: string) {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw new Error(error.message)
    return data
  },
  async signup(email: string, password: string, firmName: string) {
    // Generate a URL-safe slug from the firm name with a short random suffix
    // to avoid uniqueness collisions.
    const base = firmName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50)
    const slug = `${base}-${Math.random().toString(36).slice(2, 8)}`

    // Call the backend which creates both the Supabase Auth user AND the
    // Tenant record in one transaction, then tags the user's app_metadata.
    const res = await apiClient.post<{
      access_token: string
      refresh_token: string
      user_id: string
      tenant_id: string
      message: string
    }>('/auth/signup', { email, password, firm_name: firmName, slug })

    // Persist the session in the Supabase JS client (localStorage) so that
    // subsequent apiClient requests can read it via supabase.auth.getSession().
    if (res.data.access_token && res.data.refresh_token) {
      await supabase.auth.setSession({
        access_token: res.data.access_token,
        refresh_token: res.data.refresh_token,
      })
    }

    return res.data
  },
  async logout() {
    await supabase.auth.signOut()
  },
}

// Quickstart
export interface QuickStartStep {
  key: string
  title: string
  description: string
  completed: boolean
  href: string
}
export interface QuickStartStatus {
  steps: QuickStartStep[]
  completed_count: number
  total_count: number
  all_done: boolean
}
export const tenantApi = {
  async getQuickStartStatus(): Promise<QuickStartStatus> {
    const res = await apiClient.get<QuickStartStatus>('/tenants/me/quickstart-status')
    return res.data
  },
}

// Dashboard
export const dashboardApi = {
  async getStats(): Promise<DashboardStats> {
    const res = await apiClient.get<DashboardStats>('/dashboard/stats')
    return res.data
  },
}

export interface ChatSessionListItem {
  id: string
  phase: string
  job_id: string | null
  job_title: string | null
  preview: string
  message_count: number
  created_at: string
  updated_at: string
}

// Chat Sessions
export const chatApi = {
  async getCurrentSession(): Promise<ChatSession> {
    const res = await apiClient.get<ChatSession>('/chat-sessions/current')
    return res.data
  },
  async sendMessage(sessionId: string, content: string) {
    // Backend expects { message: "..." } and returns { session_id, message, phase, ... }
    const res = await apiClient.post<{
      session_id: string
      message: string
      phase: string
      payment_confirmed?: boolean
    }>(`/chat-sessions/${sessionId}/message`, { message: content })

    // Defensive: if the backend ever returns a JSON string instead of plain text
    // (e.g. due to an AI parsing failure), extract the message field rather than
    // displaying raw JSON to the user.
    let text = res.data.message ?? ''
    if (text.trimStart().startsWith('{')) {
      try {
        const inner = JSON.parse(text)
        if (typeof inner?.message === 'string') text = inner.message
      } catch {
        // leave text as-is; backend fixes should prevent this
      }
    }

    return {
      role: 'assistant' as const,
      content: text,
      timestamp: new Date().toISOString(),
    }
  },
  async newSession(): Promise<ChatSession> {
    const res = await apiClient.post<ChatSession>('/chat-sessions/new')
    return res.data
  },
  async listSessions(params?: { limit?: number; offset?: number }): Promise<PaginatedResponse<ChatSessionListItem>> {
    const res = await apiClient.get<PaginatedResponse<ChatSessionListItem>>('/chat-sessions', { params })
    return res.data
  },
  async getSession(id: string): Promise<ChatSession> {
    const res = await apiClient.get<ChatSession>(`/chat-sessions/${id}`)
    return res.data
  },
}

// Jobs
export const jobsApi = {
  async list(params?: { limit?: number; offset?: number }): Promise<PaginatedResponse<Job>> {
    const res = await apiClient.get<PaginatedResponse<Job>>('/jobs', { params })
    return res.data
  },
  async get(id: string): Promise<Job> {
    const res = await apiClient.get<Job>(`/jobs/${id}`)
    return res.data
  },
  async triggerScout(id: string) {
    const res = await apiClient.post(`/jobs/${id}/trigger-scout`)
    return res.data
  },
}

// Candidates
export const candidatesApi = {
  async list(params?: { search?: string; status?: string; job_id?: string; min_score?: number; max_score?: number; limit?: number; offset?: number }): Promise<PaginatedResponse<Candidate>> {
    const res = await apiClient.get<PaginatedResponse<Candidate>>('/candidates', { params })
    return res.data
  },
  async get(id: string): Promise<Candidate> {
    const res = await apiClient.get<Candidate>(`/candidates/${id}`)
    return res.data
  },
  async gdprDelete(id: string) {
    const res = await apiClient.delete(`/candidates/${id}`)
    return res.data
  },
  async sendOutreach(id: string) {
    const res = await apiClient.post(`/candidates/${id}/send-outreach`)
    return res.data
  },
}

// Applications
export const applicationsApi = {
  async list(params?: { job_id?: string }): Promise<PaginatedResponse<Application>> {
    const res = await apiClient.get<PaginatedResponse<Application>>('/applications', { params })
    return res.data
  },
  async get(id: string): Promise<Application> {
    const res = await apiClient.get<Application>(`/applications/${id}`)
    return res.data
  },
  async triggerTest(id: string) {
    const res = await apiClient.post(`/applications/${id}/trigger-test`)
    return res.data
  },
}

// Audit Trail
export const auditApi = {
  async getEvents(jobId: string, params?: { limit?: number; offset?: number }): Promise<PaginatedResponse<AuditEvent>> {
    const res = await apiClient.get<PaginatedResponse<AuditEvent>>(`/jobs/${jobId}/audit-events`, { params })
    return res.data
  },
}

// Settings
export const settingsApi = {
  async getTenant(): Promise<Tenant> {
    const res = await apiClient.get<Tenant>('/tenants/me')
    return res.data
  },
  async updateTenant(data: Partial<Tenant>) {
    const res = await apiClient.patch<Tenant>('/tenants/me', data)
    return res.data
  },
}

// Knowledge Base (RAG)
export const ragApi = {
  async getDocuments(params?: { limit?: number; offset?: number }): Promise<PaginatedResponse<RagDocument>> {
    const res = await apiClient.get<PaginatedResponse<RagDocument>>('/rag/documents', { params })
    return res.data
  },
  async uploadDocument(file: File): Promise<RagDocument[]> {
    const formData = new FormData()
    formData.append('file', file)
    const res = await apiClient.post<RagDocument[]>('/rag/documents', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },
  async deleteDocument(id: string): Promise<void> {
    await apiClient.delete(`/rag/documents/${id}`)
  },
  async scrapeWebsite(url: string): Promise<{ chunks_stored: number; url: string }> {
    const res = await apiClient.post<{ chunks_stored: number; url: string }>('/rag/scrape', { url })
    return res.data
  },
}

// Team Members
export const teamApi = {
  async getMembers(): Promise<PaginatedResponse<TeamMember>> {
    const res = await apiClient.get<PaginatedResponse<TeamMember>>('/team')
    return res.data
  },
  async invite(data: { email: string; name?: string; role: string }): Promise<TeamMember> {
    const res = await apiClient.post<TeamMember>('/team/invite', data)
    return res.data
  },
  async remove(memberId: string): Promise<void> {
    await apiClient.delete(`/team/${memberId}`)
  },
}

// Screener
export const screenerApi = {
  async extractFromText(text: string): Promise<Record<string, unknown>> {
    const res = await apiClient.post<Record<string, unknown>>('/screener/jobs/extract-from-text', { text })
    return res.data
  },
  async extractFromUrl(url: string): Promise<Record<string, unknown>> {
    const res = await apiClient.post<Record<string, unknown>>('/screener/jobs/extract-from-url', { url })
    return res.data
  },
  async createJob(data: Record<string, unknown>): Promise<{ job: import('./types').Job; jobs_email: string; application_instructions: string }> {
    const res = await apiClient.post('/screener/jobs', data)
    return res.data
  },
  async getTestSession(applicationId: string, token: string) {
    const res = await apiClient.get(`/screener/test/${applicationId}/${token}`)
    return res.data
  },
  async submitAnswer(applicationId: string, token: string, answer: string, questionIndex: number) {
    const res = await apiClient.post(`/screener/test/${applicationId}/${token}/answer`, { answer, question_index: questionIndex })
    return res.data
  },
  async completeTest(applicationId: string, token: string) {
    const res = await apiClient.post(`/screener/test/${applicationId}/${token}/complete`)
    return res.data
  },
}

// Billing
export const billingApi = {
  async getPortal(): Promise<{ url: string }> {
    const res = await apiClient.get<{ url: string }>('/billing/portal')
    return res.data
  },
  async createCheckoutSession(plan: 'recruiter' | 'agency_small' | 'agency_medium'): Promise<{ checkout_url: string }> {
    const res = await apiClient.post<{ checkout_url: string }>('/billing/create-checkout-session', { plan })
    return res.data
  },
}

// GDPR
export const gdprApi = {
  async exportData(): Promise<Record<string, unknown>> {
    const res = await apiClient.post<Record<string, unknown>>('/gdpr/export')
    return res.data
  },
  async deleteAll(): Promise<void> {
    await apiClient.post('/gdpr/delete-all', { confirm: true })
  },
}

// Global search
export interface SearchResults {
  candidates: { id: string; name: string; title: string | null; company: string | null; status: string; type: 'candidate' }[]
  jobs: { id: string; title: string; job_ref: string; status: string; type: 'job' }[]
  query: string
}

export const searchApi = {
  async search(q: string): Promise<SearchResults> {
    const res = await apiClient.get<SearchResults>('/search', { params: { q } })
    return res.data
  },
}

// Super Admin
export const superAdminApi = {
  async getStats(): Promise<SuperAdminStats> {
    const res = await apiClient.get<SuperAdminStats>('/super-admin/stats')
    return res.data
  },
  async getTenants(params?: { limit?: number; offset?: number; plan?: string; search?: string }): Promise<PaginatedResponse<Tenant>> {
    const res = await apiClient.get<PaginatedResponse<Tenant>>('/super-admin/tenants', { params })
    return res.data
  },
  async impersonate(tenantId: string) {
    const res = await apiClient.post(`/super-admin/impersonate/${tenantId}`)
    return res.data
  },
  async getSystemHealth(): Promise<SystemHealth> {
    const res = await apiClient.get<SystemHealth>('/super-admin/health')
    return res.data
  },
  async getPromoCodes(): Promise<PaginatedResponse<PromoCode>> {
    const res = await apiClient.get<PaginatedResponse<PromoCode>>('/super-admin/promo-codes')
    return res.data
  },
  async createPromoCode(body: { code: string; type: string; value: number; expires_at?: string | null; max_uses?: number | null; is_active?: boolean }): Promise<PromoCode> {
    const res = await apiClient.post<PromoCode>('/super-admin/promo-codes', body)
    return res.data
  },
  async getAuditLog(params?: { limit?: number; offset?: number; event_category?: string }): Promise<PaginatedResponse<AuditEvent>> {
    const res = await apiClient.get<PaginatedResponse<AuditEvent>>('/super-admin/audit', { params })
    return res.data
  },
}
