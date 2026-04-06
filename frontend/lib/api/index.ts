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
    const { data, error } = await supabase.auth.signUp({
      email, password,
      options: { data: { firm_name: firmName } },
    })
    if (error) throw new Error(error.message)
    return data
  },
  async logout() {
    await supabase.auth.signOut()
  },
}

// Dashboard
export const dashboardApi = {
  async getStats(): Promise<DashboardStats> {
    const [jobsRes, auditRes] = await Promise.all([
      apiClient.get<{ items: Job[] }>('/jobs?limit=100'),
      apiClient.get<{ items: AuditEvent[] }>('/jobs/audit-events?limit=10').catch(() => ({ data: { items: [] } })),
    ])
    const jobs = jobsRes.data.items ?? []
    const active_jobs = jobs.filter((j) => j.status === 'active').length
    return {
      active_jobs,
      candidates_today: 0,
      applications: 0,
      credits_remaining: 0,
      pipeline: {},
      recent_activity: auditRes.data.items ?? [],
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
    const res = await apiClient.post<{ role: string; content: string; timestamp: string }>(
      `/chat-sessions/${sessionId}/message`,
      { content }
    )
    return res.data
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
