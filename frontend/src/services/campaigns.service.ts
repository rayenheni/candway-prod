import apiClient from '@/lib/api-client';

export const campaignsService = {
  list: (params?: { page?: number; per_page?: number }) =>
    apiClient.get<{ items: any[]; pagination: { total: number; page: number; per_page: number } } | any[]>('/recruiter/campaigns', params),

  get: (id: string) =>
    apiClient.get<any>(`/recruiter/campaigns/${id}`),

  create: (data: any) =>
    apiClient.post<any>('/recruiter/campaigns', data),

  update: (id: string, data: any) =>
    apiClient.patch<any>(`/recruiter/campaigns/${id}`, data),

  delete: (id: string) =>
    apiClient.delete(`/recruiter/campaigns/${id}`),

  getCandidates: (id: string, params?: { page?: number; page_size?: number; status?: string; sort_by?: string; sort_dir?: string; search?: string }) =>
    apiClient.get<{ items: any[]; total: number; page: number; page_size: number; total_pages: number } | any[]>(`/recruiter/campaigns/${id}/candidates`, params),

  inviteCandidate: (id: string, appId: number) =>
    apiClient.post<{ success: boolean; message?: string; candidate_registered?: boolean }>(`/recruiter/campaigns/${id}/candidates/${appId}/invite`),

  inviteAll: (id: string, appIds: number[]) =>
    apiClient.post<{ success: boolean; sent?: number; remaining_quota?: number }>(`/recruiter/campaigns/${id}/invite-all`, { app_ids: appIds }),

  shortlistCandidate: (id: string, appId: number) =>
    apiClient.patch<{ success: boolean; status: string }>(`/recruiter/campaigns/${id}/candidates/${appId}/shortlist`),

  exportCSV: (id: string, scope: 'all' | 'shortlisted' = 'all') =>
    `/api/v1/recruiter/campaigns/${id}/export/csv?scope=${scope}`,

  exportPDF: (id: string, scope: 'all' | 'shortlisted' = 'shortlisted', tier: boolean = false) =>
    `/api/v1/recruiter/campaigns/${id}/export/pdf?scope=${scope}${tier ? '&tier=true' : ''}`,

  compare: (ids: (number | string)[], threshold: number = 70) =>
    apiClient.get<any[]>(`/recruiter/campaigns/compare?ids=${ids.join(',')}&threshold=${threshold}`),

  getStaleInvites: (id: string, days: number = 3) =>
    apiClient.get<any[]>(`/recruiter/campaigns/${id}/stale-invites?days=${days}`),

  nudgeStaleCandidates: (id: string, applicationIds?: number[]) =>
    apiClient.post<any>(`/recruiter/campaigns/${id}/nudge`, { application_ids: applicationIds }),

  getDuplicateSummary: (id: string) =>
    apiClient.get<any>(`/recruiter/campaigns/${id}/duplicate-summary`),

  getCandidateDuplicates: (id: string, appId: number) =>
    apiClient.get<any>(`/recruiter/campaigns/${id}/candidates/${appId}/duplicates`),

  getTeam: (id: string) =>
    apiClient.get<any>(`/recruiter/campaigns/${id}/team`),

  addTeamMember: (id: string, email: string, role: string = 'member') =>
    apiClient.post<any>(`/recruiter/campaigns/${id}/team`, { email, role }),

  updateCandidateEmail: (id: string, appId: number, email: string) =>
    apiClient.patch<{ success: boolean; email?: string }>(`/recruiter/campaigns/${id}/candidates/${appId}/email`, { email }),

  uploadCVs: (file: File, campaignId?: string) => {
    const formData = new FormData();
    formData.append('file', file);

    if (campaignId) {
      formData.append('campaign_id', campaignId);
    }

    return apiClient.postFormData<any>(
      '/recruiter/campaigns/upload-cvs',
      formData,
    );
  },
  getTemplates: () =>
    apiClient.get<any[]>('/recruiter/campaigns/templates'),

  createTemplate: (data: any) =>
    apiClient.post<any>('/recruiter/campaigns/templates', data),

  updateTemplate: (id: number, data: any) =>
    apiClient.put<any>(`/recruiter/campaigns/templates/${id}`, data),

  deleteTemplate: (id: number) =>
    apiClient.delete<any>(`/recruiter/campaigns/templates/${id}`),

  seedDefaults: () =>
    apiClient.post<any>('/recruiter/campaigns/templates/seed-defaults'),

  getTracking: (id: string) =>
    apiClient.get<any>(`/recruiter/campaigns/${id}/analytics`),

  getStats: (id: string) =>
    apiClient.get<any>(`/recruiter/campaigns/${id}/stats`),

  getAnalytics: (id: string) =>
    apiClient.get<any>(`/recruiter/campaigns/${id}/analytics`),

  createFull: (data: any) =>
    apiClient.post<any>('/recruiter/campaigns/full', data),

  getRubrics: () =>
    apiClient.get<{ rubrics: any[] }>('/recruiter/campaigns/rubrics'),

  uploadCvsToCampaign: (formData: FormData) =>
    apiClient.postFormData<any>('/recruiter/campaigns/upload/cv', formData),

  previewMatch: (formData: FormData) =>
    apiClient.post<any>('/recruiter/campaigns/preview-match', formData),

  getJobs: (params?: { per_page?: number }) =>
    apiClient.get<any[]>('/recruiter/jobs/my', params),
};
