import apiClient from '@/lib/api-client';
import type { User } from '@/types';

export interface HealthResponse {
  status: string;
  timestamp?: string;
  checks: Record<string, string>;
}

export interface AdminUserRow {
  id: number;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  joined?: string;
  tier?: string;
  current_plan_id?: number | null;
}

export interface RecruiterUsageRow {
  id: number;
  name: string;
  email: string;
  tier: string;
  plan_name: string;
  cv_limit: number;
  ai_interview_limit: number;
  active_jobs: number;
  usage_jobs: number;
  usage_cvs: number;
  usage_ai_interviews: number;
}

interface OpportunityRow {
  id: number;
  title: string;
  type: string;
  description?: string;
  link?: string;
  image_url?: string;
  is_active?: boolean;
  created_at?: string;
}

export interface BlogPostRow {
  id: number;
  title: string;
  slug: string;
  content?: string;
  image_url?: string;
  tags?: string;
  is_published?: boolean;
  created_at?: string;
}

export interface Organization {
  id: number;
  name: string;
  slug: string;
  domain: string | null;
  tier: string;
  subscription_status: string;
  max_users: number;
  max_jobs: number;
  max_ai_interviews: number;
  logo_url: string | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
  recruiter_count: number;
  jobs_count: number;
  applications_count: number;
  storage: {
    bytes: number;
    documents: number;
    formatted: string;
  };
}

export interface OrganizationsResponse {
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  organizations: Organization[];
}

export interface KybDocument {
  name: string;
  url: string;
}

export interface KybCompany {
  company_id: number;
  company_name: string;
  slug: string;
  billing_email: string | null;
  billing_address: string | null;
  tax_id: string | null;
  kyb_status: string | null;
  kyb_documents: KybDocument[];
  owner_email: string | null;
  owner_name: string | null;
  created_at: string | null;
}

export interface AdminDashboardStats {
  users: { total: number; growth_rate: number };
  activity: { jobs: number; applications: number };
  revenue: { total: number; monthly_trend: { month: string; revenue: number }[]; currency: string };
  action_queue: { pending_courses: number; pending_payments: number; pending_subs: number; open_tickets: number };
  ai_intelligence: Record<string, unknown>;
}

export interface ActivityLog {
  id: number;
  action: string;
  details: string | null;
  user_id: number | null;
  created_at: string;
}

export interface Course {
  id: number;
  title: string;
  mentor_name: string;
  price: number;
  category: string;
  status: string;
  created_at: string;
}

export interface AdminJob {
  id: number;
  title: string;
  company: string;
  location: string | null;
  recruiter_name: string;
  created_at: string;
  is_active: boolean;
  applicant_count: number;
}

export interface Payment {
  id: number;
  user_id: number;
  course_id: number;
  user_name: string;
  user_email: string;
  course_title: string;
  amount: number;
  proof_url: string | null;
  date: string;
}

export interface PaymentProof {
  id: number;
  user_id: number;
  user_name: string;
  user_email: string;
  amount: number;
  currency: string;
  status: string;
  proof_url: string | null;
  proof_status: string;
  proof_verified_at: string | null;
  proof_verified_by: number | null;
  proof_file_size: number | null;
  proof_file_type: string | null;
  proof_review_notes: string | null;
  description: string | null;
  created_at: string | null;
}

export interface PaymentProofsResponse {
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  proofs: PaymentProof[];
}

export interface Payout {
  id: number;
  mentor_id: number;
  amount: number;
  currency: string;
  status: string;
  created_at: string | null;
  processed_at: string | null;
}

export interface SupportTicket {
  id: number;
  user_id: number | null;
  subject: string;
  message: string | null;
  priority: string;
  status: string;
  created_at: string | null;
  category?: string;
}

export interface UpgradeRequest {
  id: number;
  user_id: number;
  user_name: string;
  user_email: string;
  subject: string;
  description: string | null;
  status: string;
  created_at: string | null;
}

export interface SystemLog {
  logs: string[];
}

export interface BackgroundJob {
  id: number;
  recruiter_id: number | null;
  title: string;
  target_role: string | null;
  status: string;
  worker_status: string | null;
  error_message: string | null;
  created_at: string | null;
}

export interface SystemEvent {
  id: number;
  user_id: number | null;
  action: string;
  target_id: string | null;
  details: string | null;
  ip_address: string | null;
  timestamp: string | null;
}

export interface BackgroundJobsResponse {
  active_batch_jobs: BackgroundJob[];
  recent_system_events: SystemEvent[];
}

export interface AnalyticsOverview {
  users: { total: number; new_30d: number; growth_rate: number; by_role: { recruiters: number; candidates: number } };
  activity: { jobs: number; applications: number; interviews: number; funnel_conversion: number };
  sales_autopilot: { leads_found: number; active_missions: number };
}

export interface GrowthPoint {
  date: string;
  new_users: number;
  new_jobs: number;
}

export interface RevenueTrend {
  month: string;
  revenue: number;
}

export interface RevenueAnalytics {
  total_revenue: number;
  monthly_trend: RevenueTrend[];
  status_breakdown: Record<string, number>;
}

export interface PlatformEfficiency {
  ai_cost_usd: number;
  revenue_tnd: number;
  roi_multiplier: number;
  token_usage: number;
  avg_cost_per_execution: number;
}

export interface AISalesLead {
  id: number;
  email: string;
  name: string;
  company: string;
  role?: string;
  source?: string;
  status?: string;
  score?: number;
  ai_notes?: string;
  created_at?: string;
  last_contacted_at?: string;
}

export interface AIAnalytics {
  total_executions: number;
  total_tokens: number;
  estimated_cost_usd: number;
  model_usage: Record<string, number>;
  latest_events: { action: string; target: string; time: string; status?: string }[];
}

export interface PromptVariant {
  id: number;
  prompt_type: string;
  version: number;
  variant_name: string;
  is_active: boolean;
  traffic_percentage: number;
}

export interface PromptTest {
  id: number;
  prompt_type: string;
  version: number;
  variant: string;
  status: string;
  success_rate: number;
  avg_latency: number;
  total_calls: number;
}

export interface ABTestStats {
  period_days: number;
  total_prompt_calls: number;
  stats: {
    prompt_type: string;
    version: number;
    variant: string;
    total_calls: number;
    successful_calls: number;
    success_rate: number;
    avg_latency: number;
  }[];
}

export interface Rubric {
  id: number;
  name: string;
  job_id: number | null;
  title: string;
  version: number;
  status: string;
  skills_count: number;
  applications: number;
  updated_at: string;
}

export interface AdminRubricList {
  rubrics: Rubric[];
  stats: { total: number; active: number; draft: number };
}

export const adminService = {
  getUsers: (params?: { page?: number; role?: string; search?: string; per_page?: number }) =>
    apiClient.get<{ users: AdminUserRow[]; total: number; page: number; per_page: number }>('/admin/users', params),

  getRecruiterUsage: (params?: { page?: number; per_page?: number }) =>
    apiClient.get<{ users: RecruiterUsageRow[]; total: number; page: number; per_page: number; total_pages: number }>('/admin/users/usage', params),

  getUser: (id: string) =>
    apiClient.get<User>(`/admin/users/${id}`),

  updateUser: (id: string, data: Partial<User>) =>
    apiClient.patch<User>(`/admin/users/${id}`, data),

  suspendUser: (id: string, reason: string) =>
    apiClient.post(`/admin/users/${id}/suspend`, { reason }),

  activateUser: (id: string) =>
    apiClient.post(`/admin/users/${id}/activate`),

  getUserUsage: (id: string) =>
    apiClient.post(`/admin/users/${id}/usage`),

  assignPlan: (userId: string, planId: number) =>
    apiClient.post(`/admin/users/${userId}/assign-plan/${planId}`),

  impersonateUser: (userId: string) =>
    apiClient.post(`/admin/users/${userId}/impersonate`),

  getUserPermissions: (id: string) =>
    apiClient.get<{ permissions: string[]; is_super_admin: boolean }>(`/admin/users/${id}/permissions`),

  updateUserPermissions: (id: string, permissions: string[], isSuperAdmin: boolean) =>
    apiClient.put(`/admin/users/${id}/permissions`, { permissions, is_super_admin: isSuperAdmin }),

  getPlatformHealth: () =>
    apiClient.get<HealthResponse>('/monitoring/health'),

  adminHealth: () =>
    apiClient.get('/admin/health'),

  getAIMonitoring: () =>
    apiClient.get('/admin/ai/monitoring'),

  getModerationQueue: (params?: { page?: number; status?: string }) =>
    apiClient.get('/admin/verifications', params),

  moderateContent: (id: string, action: 'approve' | 'reject', reason?: string) =>
    action === 'approve'
      ? apiClient.post(`/admin/verifications/${id}/approve`)
      : apiClient.post(`/admin/verifications/${id}/reject`, { reason: reason || 'Insufficient documentation' }),

  getSubscriptions: <T = Record<string, unknown>>(params?: { page?: number; per_page?: number }) =>
    apiClient.get<T>('/admin/subscriptions', params),

  getActiveSubscriptions: <T = Record<string, unknown>>(params?: { page?: number; per_page?: number }) =>
    apiClient.get<T>('/admin/subscriptions/active', params),

  getPlans: <T = Record<string, unknown>>(params?: { page?: number; per_page?: number }) =>
    apiClient.get<T>('/admin/plans', params),

  getPlan: <T = Record<string, unknown>>(planId: number) =>
    apiClient.get<T>(`/admin/plans/${planId}`),

  createPlan: <T = Record<string, unknown>>(data: Record<string, any>) =>
    apiClient.post<T>('/admin/plans', data),

  updatePlan: <T = Record<string, unknown>>(planId: number, data: Record<string, any>) =>
    apiClient.put<T>(`/admin/plans/${planId}`, data),

  deletePlan: (planId: number) =>
    apiClient.delete<{ message: string }>(`/admin/plans/${planId}`),

  activatePlan: (planId: number) =>
    apiClient.post<{ message: string }>(`/admin/plans/${planId}/activate`),

  archivePlan: (planId: number) =>
    apiClient.post<{ message: string }>(`/admin/plans/${planId}/archive`),

  duplicatePlan: (planId: number, overrides?: Record<string, any>) =>
    apiClient.post<Record<string, any>>(`/admin/plans/${planId}/duplicate`, overrides || {}),

  getPlanVersions: <T = Record<string, unknown>>(planId: number) =>
    apiClient.get<T>(`/admin/plans/${planId}/versions`),

  getSubscriptionHistory: <T = Record<string, unknown>>(userId: number) =>
    apiClient.get<T>(`/admin/subscriptions/${userId}/history`),

  adjustUserUsage: (userId: number, action: 'reset' | 'give_bonus', field: 'all' | 'usage_cvs' | 'usage_interviews' | 'usage_jobs', amount = 0) =>
    apiClient.post<{ message: string }>(`/admin/users/${userId}/usage`, { action, amount, field }),

  getJobs: (params?: { status?: string; search?: string; page?: number; per_page?: number }) =>
    apiClient.get<{ jobs: AdminJob[]; total: number; page: number; per_page: number }>('/admin/jobs', params),

  getOrganizations: (params?: { status?: string; tier?: string; search?: string; page?: number; per_page?: number }) =>
    apiClient.get<OrganizationsResponse>('/admin/organizations', params),

  getOrganization: (id: number) =>
    apiClient.get<Organization>(`/admin/organizations/${id}`),

  createOrganization: (data: Partial<Organization>) =>
    apiClient.post<{ message: string; id: number }>('/admin/organizations', data),

  updateOrganization: (id: number, data: Partial<Organization>) =>
    apiClient.put<{ message: string }>(`/admin/organizations/${id}`, data),

  deleteOrganization: (id: number) =>
    apiClient.delete<{ message: string }>(`/admin/organizations/${id}`),

  toggleOrganization: (id: number) =>
    apiClient.post<{ message: string; is_active: boolean }>(`/admin/organizations/${id}/toggle`),

  getOrganizationAudit: (id: number, page = 1, perPage = 30) =>
    apiClient.get<{ total: number; page: number; per_page: number; total_pages: number; logs: unknown[] }>(
      `/admin/organizations/${id}/audit`, { page, per_page: perPage }
    ),

  approveSubscription: (txId: number) =>
    apiClient.post<{ message: string }>(`/admin/subscriptions/${txId}/approve`),

  rejectSubscription: (txId: number, reason?: string) =>
    apiClient.post<{ message: string }>(`/admin/subscriptions/${txId}/reject`, { reason }),

  cancelSubscription: (userId: number) =>
    apiClient.post<{ message: string }>(`/admin/subscriptions/${userId}/cancel`),

  extendSubscription: (userId: number, days = 30) =>
    apiClient.post<{ message: string }>(`/admin/subscriptions/${userId}/extend?days=${days}`),

  changePlan: (userId: number, planId: number) =>
    apiClient.post<{ message: string }>(`/admin/subscriptions/${userId}/change-plan?plan_id=${planId}`),

  expireSubscription: (userId: number) =>
    apiClient.post<{ message: string }>(`/admin/subscriptions/${userId}/expire`),

  reinstateSubscription: (userId: number) =>
    apiClient.post<{ message: string }>(`/admin/subscriptions/${userId}/reinstate`),

  startTrial: (userId: number, planId: number, days = 14) =>
    apiClient.post<{ message: string }>(`/admin/subscriptions/${userId}/start-trial?plan_id=${planId}&days=${days}`),

  getCourses: (params?: { status?: string; page?: number; per_page?: number }) =>
    apiClient.get<{ courses: Course[]; total: number; page: number; per_page: number }>('/admin/courses', params),

  approveCourse: (courseId: number) =>
    apiClient.post(`/admin/courses/${courseId}/approve`),

  rejectCourse: (courseId: number) =>
    apiClient.post(`/admin/courses/${courseId}/reject`),

  createExternalCourse: (course: { title: string; description: string; category: string; difficulty: string; duration: number; thumbnail_url: string; price: number; url: string }) =>
    apiClient.post<{ message: string; course_id: number }>('/admin/courses/external', course),

  getFinanceOverview: <T = Record<string, unknown>>() =>
    apiClient.get<T>('/admin/finance/overview'),

  getFinanceRevenue: <T = Record<string, unknown>>(months = 6) =>
    apiClient.get<T>('/admin/finance/revenue', { months }),

  getFinanceCustomers: <T = Record<string, unknown>>() =>
    apiClient.get<T>('/admin/finance/customers'),

  getFinanceCredits: <T = Record<string, unknown>>() =>
    apiClient.get<T>('/admin/finance/credits'),

  getFinanceForecast: <T = Record<string, unknown>>(months = 3) =>
    apiClient.get<T>('/admin/finance/forecast', { months }),

  exportFinance: async (section = 'overview', format: 'csv' | 'pdf' = 'csv') => {
    const blob = await apiClient.getBlob(`/admin/finance/export?section=${section}&format=${format}`);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `candway-finance-${section}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  },

  getAdminDashboardStats: () =>
    apiClient.get<AdminDashboardStats>('/admin/stats'),

  getRecentActivity: () =>
    apiClient.get<ActivityLog[]>('/admin/activity'),

  getAIReport: () =>
    apiClient.get('/admin/analytics/daily-report'),

  refreshAIReport: () =>
    apiClient.post('/admin/analytics/daily-report/refresh'),

  backupDatabase: () =>
    apiClient.getBlob('/admin/backup/db'),

  getSystemLogs: (lines = 200) =>
    apiClient.get<SystemLog>('/admin/logs', { lines }),

  getBackgroundJobs: () =>
    apiClient.get<BackgroundJobsResponse>('/admin/background-jobs'),

  getAnalyticsOverview: () =>
    apiClient.get<AnalyticsOverview>('/admin/analytics/overview'),

  getGrowthData: (days = 30) =>
    apiClient.get<GrowthPoint[]>('/admin/analytics/growth', { days }),

  getRevenueAnalytics: (months = 6) =>
    apiClient.get<RevenueAnalytics>('/admin/analytics/revenue', { months }),

  getAIAnalytics: () =>
    apiClient.get<AIAnalytics>('/admin/analytics/ai'),

  getPlatformEfficiency: () =>
    apiClient.get<PlatformEfficiency>('/admin/analytics/efficiency'),

  getAuditTrail: (params?: { application_id?: number; limit?: number }) =>
    apiClient.get<{ records: unknown[]; total: number }>('/admin/audit-trail', params),

  getDriftSummary: () =>
    apiClient.get('/admin/drift-summary'),

  getDriftHistory: (metric = 'overall_score') =>
    apiClient.get<{ records: unknown[]; metric_name: string }>('/admin/drift-history', { metric_name: metric }),

  getExperiments: () =>
    apiClient.get<{ experiments: unknown[] }>('/admin/experiments'),

  getSystemPrompts: (params?: { page?: number; per_page?: number }) =>
    apiClient.get<{ prompts: unknown[]; total: number; page: number; per_page: number }>('/admin/prompts', params),

  updateSystemPrompt: (key: string, content: string, description?: string) =>
    apiClient.post('/admin/prompts', { key, content, description }),

  getPromptVariants: () =>
    apiClient.get<{ variants: PromptVariant[] }>('/admin/prompts/variants'),

  createPromptVariant: (data: { prompt_type: string; variant_name: string; content: string; traffic_percentage: number }) =>
    apiClient.post('/admin/prompts/variants', data),

  updatePromptVariant: (id: number, data: Partial<PromptVariant>) =>
    apiClient.patch(`/admin/prompts/variants/${id}`, data),

  getPromptTests: () =>
    apiClient.get<{ tests: PromptTest[] }>('/admin/prompts/tests'),

  runPromptTest: (data: { prompt_type: string; variant_a: string; variant_b: string; test_cases: unknown[] }) =>
    apiClient.post('/admin/prompts/test', data),

  getPromptPerformance: () =>
    apiClient.get('/admin/prompts/performance'),

  getPromptMonitoringAlerts: () =>
    apiClient.get('/admin/prompts/monitoring/alerts'),

  getPromptMonitoringLive: <T = Record<string, unknown>>() =>
    apiClient.get<T>('/admin/prompts/monitoring/live'),

  getPromptCatalog: () =>
    apiClient.get('/admin/prompts/catalog'),

  getPromptRecommendations: () =>
    apiClient.post('/admin/prompts/recommendations'),

  exportPrompts: () =>
    apiClient.get('/admin/prompts/export'),

  getABTestConfig: () =>
    apiClient.get<{ ab_test_enabled: boolean; ab_test_bucket_size: number; prompt_versions: Record<string, unknown> }>('/admin/ab-testing/config'),

  updateABTestConfig: (config: { ab_test_enabled: boolean; ab_test_bucket_size: number }) =>
    apiClient.post('/admin/ab-testing/config', config),

  getABTestStats: (days = 7) =>
    apiClient.get<ABTestStats>('/admin/ab-testing/stats', { days }),

  resetABTestStats: () =>
    apiClient.post('/admin/ab-testing/reset-stats'),

  getMarketingLeads: (params?: { page?: number; per_page?: number }) =>
    apiClient.get<{ leads: { id: number; email: string; name: string; company: string; status: string; created_at: string }[]; total: number; page: number; per_page: number }>('/admin/marketing/leads', params),

  sendMarketingCampaign: (campaign: { subject: string; content: string }) =>
    apiClient.post('/admin/marketing/send', campaign),

  getCoupons: (params?: { page?: number; per_page?: number }) =>
    apiClient.get<{ coupons: { id: number; code: string; discount_percent: number; expires_in_days: number; is_active: boolean; created_at: string }[]; total: number; page: number; per_page: number }>('/admin/coupons', params),

  createCoupon: (coupon: { code: string; discount_percent: number; max_uses?: number; expires_in_days?: number }) =>
    apiClient.post('/admin/coupons', coupon),

  deleteCoupon: (id: number) =>
    apiClient.delete(`/admin/coupons/${id}`),

  getAIJobs: () =>
    apiClient.get<AISalesLead[]>('/admin/ai/sales/leads'),

  getCampaigns: () =>
    apiClient.get('/admin/ai/sales/campaigns'),

  launchAIPipeline: (niche = 'Tunisian Startups') =>
    apiClient.post('/admin/ai/sales/autopilot/launch', { niche, run_outreach: false }),

  updateLeadStatus: (leadId: string, status: string) =>
    apiClient.post(`/admin/ai/sales/leads/${leadId}/status`, { status }),

  getCategories: (params?: { page?: number; per_page?: number }) =>
    apiClient.get<{ categories: unknown[]; total: number; page: number; per_page: number }>('/admin/categories', params),

  createCategory: (data: { name: string; type: string; parent_id?: number }) =>
    apiClient.post('/admin/categories', data),

  updateCategory: (id: number, data: { name: string; type: string; parent_id?: number }) =>
    apiClient.put(`/admin/categories/${id}`, data),

  deleteCategory: (id: number) =>
    apiClient.delete(`/admin/categories/${id}`),

  getRubrics: () =>
    apiClient.get<AdminRubricList>('/admin/rubrics'),

  getRubric: (id: number) =>
    apiClient.get<{ id: number; name: string; title: string; description?: string; job_id: number | null; version: number; status: string; skills_count: number; criteria_json?: string; updated_at?: string | null; created_at?: string | null }>(`/admin/rubrics/${id}`),

  createRubric: (data: { title: string; description?: string; criteria_json: string; is_active?: boolean }) =>
    apiClient.post<{ id: number }>('/admin/rubrics', data),

  updateRubric: (id: number, data: { title: string; description?: string; criteria_json: string; is_active?: boolean }) =>
    apiClient.put(`/admin/rubrics/${id}`, data),

  deleteRubric: (id: number) =>
    apiClient.delete(`/admin/rubrics/${id}`),

  getAnnouncements: (params?: { page?: number; per_page?: number }) =>
    apiClient.get<{ announcements: any[]; total: number; page: number; per_page: number }>('/admin/announcements', params),

  createAnnouncement: (data: { title: string; message: string; type: string; target_role: string; expires_at?: string }) =>
    apiClient.post('/admin/announcements', data),

  updateAnnouncement: (id: number, data: { title: string; message: string; type: string; target_role: string; expires_at?: string }) =>
    apiClient.put(`/admin/announcements/${id}`, data),

  archiveAnnouncement: (id: number) =>
    apiClient.post<{ is_active: boolean }>(`/admin/announcements/${id}/archive`),

  createOpportunity: (data: { title: string; type: string; description: string; link: string; image_url?: string }) =>
    apiClient.post('/admin/opportunities', data),

  deleteOpportunity: (id: number) =>
    apiClient.delete(`/admin/opportunities/${id}`),

  updateOpportunity: (id: number, data: { title: string; type: string; description: string; link: string; image_url?: string }) =>
    apiClient.put(`/admin/opportunities/${id}`, data),

  getOpportunities: (params?: { page?: number; per_page?: number }) =>
    apiClient.get<{ opportunities: OpportunityRow[]; total: number; page: number; per_page: number }>('/admin/opportunities', params),

  getPages: (slug: string, params?: { page?: number; per_page?: number }) =>
    apiClient.get(`/admin/pages/${slug}`, params),

  updatePageSection: (pageSlug: string, sectionSlug: string, contentJson: unknown) =>
    apiClient.post(`/admin/pages/${pageSlug}/${sectionSlug}`, { content_json: contentJson }),

  getBlogPosts: (params?: { page?: number; per_page?: number }) =>
    apiClient.get<{ blogs: BlogPostRow[]; total: number; page: number; per_page: number }>('/admin/blogs', params),

  createBlogPost: (post: { title: string; slug: string; content: string; image_url?: string; tags?: string }) =>
    apiClient.post('/admin/blogs', post),

  updateBlogPost: (id: number, post: { title: string; slug: string; content: string; image_url?: string; tags?: string }) =>
    apiClient.put(`/admin/blogs/${id}`, post),

  deleteBlogPost: (id: number) =>
    apiClient.delete(`/admin/blogs/${id}`),

  uploadBlogImage: (file: File) =>
    apiClient.upload<{ url: string }>('/admin/blogs/upload-image', file),

  getInvoices: (params?: { page?: number; per_page?: number }) =>
    apiClient.get<{ invoices: unknown[]; total: number; page: number; per_page: number }>('/admin/invoices', params),

  generateInvoice: (data: { user_id: number; amount_ht: number; transaction_id?: number }) =>
    apiClient.post('/admin/invoices/generate', data),

  downloadInvoicePDF: (invoiceId: number) =>
    apiClient.getBlob(`/admin/invoices/${invoiceId}/download`),

  downloadInvoiceXML: (invoiceId: number) =>
    apiClient.getBlob(`/admin/invoices/${invoiceId}/xml`),

  getPendingPayments: (params?: { page?: number; per_page?: number; status?: string }) =>
    apiClient.get<{ payments: Payment[]; total: number; page: number; per_page: number }>('/admin/payments', params),

  approvePayment: (id: number) =>
    apiClient.post(`/admin/payments/${id}/approve`),

  rejectPayment: (id: number) =>
    apiClient.post(`/admin/payments/${id}/reject`),

  getPayouts: (params?: { status?: string; page?: number; per_page?: number }) =>
    apiClient.get<{ payouts: Payout[]; total: number; page: number; per_page: number }>('/admin/payouts', params),

  markPayoutPaid: (id: number) =>
    apiClient.post(`/admin/payouts/${id}/pay`),

  getTickets: (params?: { status?: string; page?: number; per_page?: number }) =>
    apiClient.get<{ tickets: SupportTicket[]; total: number; page: number; per_page: number }>('/admin/tickets', params),

  replyTicket: (id: number, message: string, closeTicket?: boolean) =>
    apiClient.post(`/admin/tickets/${id}/reply`, { message, close_ticket: closeTicket }),

  getUpgradeRequests: (params?: { status?: string; page?: number; per_page?: number }) =>
    apiClient.get<{ upgrade_requests: UpgradeRequest[]; total: number; page: number; per_page: number }>('/admin/upgrade-requests', params),

  approveUpgradeRequest: (id: number) =>
    apiClient.post(`/admin/upgrade-requests/${id}/approve`),

  rejectUpgradeRequest: (id: number, reason?: string) =>
    apiClient.post(`/admin/upgrade-requests/${id}/reject`, reason || 'Your upgrade request has been declined.'),

  getSystemSettings: () =>
    apiClient.get('/admin/settings'),

  updateSystemSettings: (settings: Record<string, unknown>) =>
    apiClient.post('/admin/settings', settings),

  testSMTP: (email: string) =>
    apiClient.post('/admin/email/test', { email }),

  getKyb: (status = 'pending', page = 1, perPage = 30) =>
    apiClient.get<{ total: number; page: number; per_page: number; total_pages: number; companies: KybCompany[] }>(
      '/admin/kyb', { status, page, per_page: perPage }
    ),

  approveKyb: (companyId: number) =>
    apiClient.post<{ message: string; company_id: number; kyb_status: string }>(`/admin/kyb/${companyId}/approve`),

  rejectKyb: (companyId: number, reason: string) =>
    apiClient.post<{ message: string; company_id: number; kyb_status: string }>(`/admin/kyb/${companyId}/reject`, { reason }),

  getPaymentProofs: (params?: { page?: number; per_page?: number; proof_status?: string }) =>
    apiClient.get<PaymentProofsResponse>('/admin/payment-proofs', params),

  getPaymentProof: (txId: number) =>
    apiClient.get<PaymentProof>(`/admin/payment-proofs/${txId}`),

  verifyPaymentProof: (txId: number, notes?: string) =>
    apiClient.post<{ message: string }>(`/admin/payment-proofs/${txId}/verify`, { notes }),

  rejectPaymentProof: (txId: number, notes: string) =>
    apiClient.post<{ message: string }>(`/admin/payment-proofs/${txId}/reject`, { notes }),

  downloadPaymentProof: (txId: number) =>
    apiClient.getBlob(`/admin/payment-proofs/${txId}/file`),
};
