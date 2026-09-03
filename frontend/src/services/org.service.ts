import apiClient from '@/lib/api-client';

export interface OrgMember {
  user_id: number;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  joined_at: string | null;
  credit_balance: number;
  usage: { jobs: number; cvs: number; ai_interviews: number };
}

export interface OrgFunnel {
  applied: number;
  screening: number;
  interview: number;
  offer: number;
  hired: number;
}

export interface OrgRecruiterKpi {
  user_id: number;
  name: string;
  email: string;
  role: string;
  active_jobs: number;
  total_applications: number;
  total_candidates: number;
  hired: number;
  avg_score: number;
  funnel: OrgFunnel;
  interviews: { total: number; scheduled: number; completed: number };
  ai: { calls: number; cost_usd: number; credits: number };
}

export interface OrgOverview {
  company_id: number;
  recruiters: number;
  total_jobs: number;
  total_applications: number;
  total_candidates: number;
  hired: number;
  avg_score: number;
  funnel: OrgFunnel;
  interviews: { total: number; scheduled: number; completed: number };
  ai: { calls: number; cost_usd: number; credits: number };
  recruiter_kpis: OrgRecruiterKpi[];
}

export interface OrgRecruiterDetail {
  user_id: number;
  kpis: OrgRecruiterKpi;
  trends: { date: string; count: number }[];
  score_distribution: Record<string, number>;
  jobs: { id: number; title: string; is_active: boolean; applicant_count: number; hired_count: number }[];
  recent_applications: {
    id: number;
    full_name: string;
    email: string;
    score: number;
    status: string;
    created_at: string | null;
  }[];
}

export interface OrgBillingPlan {
  id: number;
  name: string;
  slug: string;
  price_monthly: number;
  price_yearly: number;
  currency: string;
  job_limit: number;
  cv_limit: number;
  ai_interview_limit: number;
  team_seat_limit: number;
  credits_monthly: number;
}

export interface OrgSeats {
  limit: number;
  used: number;
  available: number;
}

export interface OrgBillingTx {
  id: number;
  amount: number;
  amount_ht: number;
  tva_amount: number;
  stamp_duty: number;
  amount_ttc: number;
  currency: string;
  status: string;
  description: string;
  proof_url: string | null;
  created_at: string | null;
}

export interface OrgInvoice {
  id: number;
  invoice_number: string;
  amount_ht: number;
  tva_rate: number;
  tva_amount: number;
  stamp_duty: number;
  total_ttc: number;
  status: string;
  client_name: string | null;
  created_at: string | null;
  transaction_id: number | null;
}

export interface OrgBillingSummary {
  company_id: number;
  company_name: string;
  plan: {
    id: number;
    name: string;
    slug: string;
    price_monthly: number;
    price_yearly: number;
    team_seat_limit: number;
  } | null;
  subscription_status: string;
  seats: OrgSeats;
  company_credit_balance: number;
  pending_transaction: OrgBillingTx | null;
  billing_email: string | null;
  billing_address: string | null;
  tax_id: string | null;
  kyb_status: string | null;
}

export interface OrgKybDocument {
  name: string;
  url: string;
}

export interface OrgKyb {
  company_id: number;
  company_name: string;
  billing_email: string | null;
  billing_address: string | null;
  tax_id: string | null;
  kyb_status: string | null;
  kyb_documents: OrgKybDocument[];
}

export const orgService = {
  listMembers: () =>
    apiClient.get<{ company_id: number; members: OrgMember[] }>('/org/members'),

  createMember: (data: { name: string; email: string; password?: string; role?: string }) =>
    apiClient.post<OrgMember & { message: string; password?: string }>('/org/members', data),

  inviteMember: (data: { name: string; email: string }) =>
    apiClient.post<{ message: string; email: string }>('/org/members/invite', data),

  updateMemberRole: (userId: number, role: string) =>
    apiClient.patch<OrgMember & { message: string }>(`/org/members/${userId}`, { role }),

  deactivateMember: (userId: number) =>
    apiClient.post<{ message: string }>(`/org/members/${userId}/deactivate`),

  activateMember: (userId: number) =>
    apiClient.post<{ message: string }>(`/org/members/${userId}/activate`),

  resetMemberUsage: (userId: number) =>
    apiClient.post<{ message: string }>(`/org/members/${userId}/reset-usage`),

  grantMemberCredits: (userId: number, credits: number, note?: string) =>
    apiClient.post<{ message: string; user_id: number; credits: number; member_balance: number; company_balance: number; duplicate: boolean }>(`/org/members/${userId}/grant-credits`, { credits, note }),

  impersonateMember: (userId: number) =>
    apiClient.post<{ access_token: string; token_type: string; role: string; user_email: string }>(`/org/members/${userId}/impersonate`),

  getOverview: () =>
    apiClient.get<OrgOverview>('/org/analytics/overview'),

  getRecruiterDetail: (userId: number) =>
    apiClient.get<OrgRecruiterDetail>(`/org/analytics/recruiters/${userId}`),

  getCreditEconomy: () =>
    apiClient.get<{ granted: number; purchased: number; consumed: number; refunded: number; pricing?: Record<string, number> }>('/org/analytics/credits'),

  getBillingPlans: () =>
    apiClient.get<OrgBillingPlan[]>('/org/billing/plans'),

  getBillingSummary: () =>
    apiClient.get<OrgBillingSummary>('/org/billing/summary'),

  subscribeCompany: (data: { plan_id: number; billing_cycle: 'monthly' | 'yearly' }) =>
    apiClient.post<{ message: string; transaction_id: number; amount_ttc: number }>('/org/billing/subscribe', data),

  uploadReceipt: (txId: number, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return apiClient.postFormData<{ message: string; transaction_id: number }>(`/org/billing/receipt/${txId}`, form);
  },

  getTransactions: () =>
    apiClient.get<{ transactions: OrgBillingTx[] }>('/org/billing/transactions'),

  getInvoices: () =>
    apiClient.get<{ invoices: OrgInvoice[] }>('/org/billing/invoices'),

  downloadInvoice: (invoiceId: number) =>
    apiClient.getBlob(`/org/billing/invoices/${invoiceId}/download`),

  getKyb: () =>
    apiClient.get<OrgKyb>('/org/billing/kyb'),

  submitKyb: (data: { billing_email: string; billing_address?: string; tax_id?: string }) =>
    apiClient.post<{ message: string; kyb_status: string }>('/org/billing/kyb', data),

  uploadKybDocuments: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append('files', f));
    return apiClient.postFormData<{ message: string; kyb_status: string; documents: OrgKybDocument[] }>('/org/billing/kyb/documents', form);
  },

  cancelSubscription: () =>
    apiClient.post<{ message: string }>('/org/billing/cancel'),
};
