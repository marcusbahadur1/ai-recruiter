import { apiClient, supabase } from './client'
import type {
  PaginatedResponse, Job, Candidate, Application,
  ChatSession, AuditEvent, Tenant, DashboardStats,
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

// Dashboard
export const dashboardApi = {
  async getStats(): Promise<DashboardStats> {
    const empty = { data: { items: [], total: 0 } }
    const [jobsRes, auditRes, candidatesRes, appsRes, tenantRes, todayRes] = await Promise.all([
      apiClient.get<PaginatedResponse<Job>>('/jobs?status=active&limit=5'),
      apiClient.get<PaginatedResponse<AuditEvent>>('/jobs/audit-events?limit=10').catch(() => empty),
      apiClient.get<PaginatedResponse<Candidate>>('/candidates?limit=500').catch(() => empty),
      apiClient.get<PaginatedResponse<Application>>('/applications?limit=1').catch(() => empty),
      apiClient.get<Tenant>('/tenants/me').catch(() => ({ data: { credits_remaining: 0 } as Tenant })),
      apiClient.get<PaginatedResponse<Candidate>>('/candidates?created_today=true&limit=1').catch(() => empty),
    ])

    // Build pipeline counts from candidate statuses
    const pipeline: Record<string, number> = {}
    for (const c of (candidatesRes.data.items ?? [])) {
      pipeline[c.status] = (pipeline[c.status] ?? 0) + 1
    }

    return {
      active_jobs: jobsRes.data.total ?? 0,
      candidates_today: todayRes.data.total ?? 0,
      applications: appsRes.data.total ?? 0,
      credits_remaining: tenantRes.data.credits_remaining ?? 0,
      pipeline,
      recent_activity: auditRes.data.items ?? [],
      active_jobs_list: jobsRes.data.items ?? [],
    }
  },
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
      job_fields?: Record<string, unknown>
      payment_confirmed?: boolean
    }>(`/chat-sessions/${sessionId}/message`, { message: content })
    // Normalise to the Message shape the chat UI expects
    return {
      role: 'assistant' as const,
      content: res.data.message,
      timestamp: new Date().toISOString(),
    }
  },
  async newSession(): Promise<ChatSession> {
    const res = await apiClient.post<ChatSession>('/chat-sessions/new')
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
  async list(params?: { search?: string; status?: string; job_id?: string; limit?: number; offset?: number }): Promise<PaginatedResponse<Candidate>> {
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

// Super Admin
export const superAdminApi = {
  async getTenants(): Promise<PaginatedResponse<Tenant>> {
    const res = await apiClient.get<PaginatedResponse<Tenant>>('/super-admin/tenants')
    return res.data
  },
  async impersonate(tenantId: string) {
    const res = await apiClient.post(`/super-admin/impersonate/${tenantId}`)
    return res.data
  },
  async getSystemHealth(): Promise<Record<string, unknown>> {
    const res = await apiClient.get<Record<string, unknown>>('/super-admin/health').catch(() => ({ data: {} as Record<string, unknown> }))
    return res.data
  },
}
