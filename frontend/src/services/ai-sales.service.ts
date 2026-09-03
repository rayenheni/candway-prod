import apiClient from '@/lib/api-client';

export interface SalesLead {
  id: number;
  name: string;
  email: string;
  company: string;
  source: string;
  score: number;
  status: string;
  ai_notes: string;
  created_at?: string;
}

export interface SalesCampaign {
  id: number;
  name: string;
  status: string;
  created_at: string;
}

export interface StatusUpdateRequest {
  status: string;
}

export interface AutopilotMissionRequest {
  niche: string;
  run_outreach?: boolean;
}

export interface SalesLeadRequest {
  source?: string;
  criteria?: string;
}

export interface OutreachRequest {
  lead_id: number;
  channel?: string;
  context?: string;
}

export const aiSalesService = {
  getLeads: (status?: string) =>
    apiClient.get<SalesLead[]>('/admin/ai/sales/leads', status ? { status } as any : undefined),

  updateLeadStatus: (leadId: number, data: StatusUpdateRequest) =>
    apiClient.post<{ message: string }>(`/admin/ai/sales/leads/${leadId}/status`, data),

  launchAutopilot: (data: AutopilotMissionRequest) =>
    apiClient.post<{ message: string }>('/admin/ai/sales/autopilot/launch', data),

  getCampaigns: () =>
    apiClient.get<SalesCampaign[]>('/admin/ai/sales/campaigns'),

  generateInternalLeads: (data?: SalesLeadRequest) =>
    apiClient.post<{ message: string }>('/admin/ai/sales/leads/scan-internal', data || { source: 'internal', criteria: 'High Engagement' }),

  generateOutreach: (data: OutreachRequest) =>
    apiClient.post<{ channel: string; content: string }>('/admin/ai/sales/outreach', data),
};
