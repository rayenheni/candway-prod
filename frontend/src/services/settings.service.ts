import apiClient from '@/lib/api-client';

export interface RecruiterSettings {
  company_name: string;
  company_description: string;
  company_logo_url: string;
  smtp_host: string;
  smtp_port: number | null;
  smtp_user: string;
  smtp_password_set: boolean;
}

export interface SubscriptionStatus {
  tier: string;
  status: string;
  plan_name: string;
  plan_slug: string;
  expiry: string | null;
  managed_by_company?: boolean;
  rejection_reason?: string | null;
  rejected_at?: string | null;
  credit_balance?: number;
  usage: { jobs: number; cvs: number; ai_interviews: number };
  limits: { job_limit: number; cv_limit: number; ai_interview_limit: number; team_seat_limit: number };
}

export interface SubscriptionPlan {
  name: string;
  slug: string;
  price_monthly: number;
  price_yearly: number;
  currency: string;
  is_active: boolean;
  is_featured: boolean;
  job_limit: number;
  cv_limit: number;
  ai_interview_limit: number;
  team_seat_limit: number;
  features: string;
}

export const settingsService = {
  getRecruiterSettings: () =>
    apiClient.get<RecruiterSettings>('/recruiter/settings'),

  updateRecruiterSettings: (data: Partial<RecruiterSettings>) =>
    apiClient.post<{ message: string }>('/recruiter/settings', data),

  uploadCompanyLogo: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return apiClient.postFormData<{ message: string; company_logo_url: string }>('/recruiter/company-logo', fd);
  },

  getSubscriptionStatus: () =>
    apiClient.get<SubscriptionStatus>('/recruiter/subscription/status'),

  getSubscriptionPlans: () =>
    apiClient.get<SubscriptionPlan[]>('/recruiter/subscription/plans'),

  changePassword: (data: { current_password: string; new_password: string }) =>
    apiClient.post<{ message: string }>('/auth/change-password', data),

  getEmailSettings: () =>
    apiClient.get<{ auto_email_enabled: boolean; templates: Record<string, unknown> }>('/recruiter/email-settings'),

  updateEmailSettings: (data: { auto_email_enabled?: boolean }) =>
    apiClient.put<{ message: string }>('/recruiter/email-settings', data),

  testEmail: (email?: string) =>
    apiClient.post<{ message: string }>('/recruiter/email/test', { email }),
};
