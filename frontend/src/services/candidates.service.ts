import apiClient from '@/lib/api-client';
import type { Candidate, Application } from '@/types';

export interface CandidatesQueryParams {
  page?: number;
  per_page?: number;
  q?: string;
  search?: string;
  status?: string;
  job_id?: number;
  min_score?: number;
}

export interface CandidatesListResponse {
  items: Candidate[];
  pagination: { total: number; page: number; per_page: number; total_pages?: number };
}

export const candidatesService = {
  getCandidates: (params?: CandidatesQueryParams) =>
    apiClient.get<CandidatesListResponse>('/recruiter/candidates/list', params as Record<string, string | number | boolean | undefined>),

  getApplications: (params?: { page?: number; per_page?: number; q?: string; status?: string; job_id?: number; min_score?: number }) =>
    apiClient.get<{ items: Application[]; pagination: { total: number; page: number; per_page: number; total_pages?: number } }>('/recruiter/applications', params),

  getApplication: (id: string) =>
    apiClient.get<Application>(`/recruiter/applications/${id}`),

  getCandidateProfile: (candidateId: string | number) =>
    apiClient.get<any>(`/recruiter/candidates/${candidateId}`),

  updateApplicationStatus: (id: string, status: string) =>
    apiClient.put<Application>(`/recruiter/applications/${id}/status`, { status }),

  bulkUpdateStatus: (ids: Array<string | number>, status: string) =>
    apiClient.post<{ message: string; updated_count: number }>('/recruiter/applications/bulk-update', {
      app_ids: ids,
      new_status: status,
    }),

  // AI interview invitations
  inviteInterview: (applicationId: string | number) =>
    apiClient.post<{ success: boolean; application_id: number; access_url: string; candidate_registered: boolean }>(
      `/recruiter/applications/${applicationId}/invite-interview`,
      {},
    ),

  inviteInterviews: (applicationIds: Array<string | number>) =>
    apiClient.post<{ message: string; invited: any[]; skipped: any[] }>(
      '/recruiter/applications/invite-interviews',
      { application_ids: applicationIds },
    ),

  inviteQualified: (jobId: string | number, threshold: number = 70) =>
    apiClient.post<{ message: string; job_id: number; threshold: number; candidates_considered: number; invited: any[]; skipped: any[] }>(
      `/recruiter/jobs/${jobId}/invite-qualified`,
      { threshold },
    ),

  uploadResume: (file: File) =>
    apiClient.upload<{ resumeUrl: string; parsedData: Candidate }>('/recruiter/candidates/resume', file),

  addNote: (applicationId: string, content: string) =>
    apiClient.put(`/recruiter/applications/${applicationId}/notes`, { notes: content }),

  getNotes: (applicationId: string) =>
    apiClient.get(`/recruiter/applications/${applicationId}/notes`),

  compareCandidates: (applicationIds: string[]) =>
    apiClient.post('/recruiter/applications/compare', { application_ids: applicationIds }),

  getAIScore: (applicationId: string) =>
    apiClient.get<{ score: number; analysis: string }>(`/recruiter/applications/${applicationId}/scores`),

  getScoreComparison: (applicationId: string) =>
    apiClient.get<any>(`/recruiter/applications/${applicationId}/score-comparison`),

  getRankedCandidates: (jobId: string) =>
    apiClient.get<any>(`/recruiter/jobs/${jobId}/candidates/ranked`),

  getGhostData: (applicationId: string) =>
    apiClient.get<any>(`/recruiter/applications/${applicationId}/ghost-data`),

  getBulkGhostData: (applicationIds: string[]) =>
    apiClient.post<any[]>('/recruiter/applications/bulk-ghost-data', { application_ids: applicationIds }),

  getAllInterviews: (applicationId: string) =>
    apiClient.get<any[]>(`/recruiter/applications/${applicationId}/all-interviews`),

  getScheduledInterviews: (applicationId: string) =>
    apiClient.get<any[]>(`/recruiter/interviews/application/${applicationId}`),

  // Offers
  listOffers: (params?: { page?: number; per_page?: number; status?: string }) =>
    apiClient.get<{ items: any[]; pagination: { total: number; page: number; per_page: number } }>('/recruiter/offers/list', params),

  getOffer: (offerId: string) =>
    apiClient.get<any>(`/recruiter/offers/${offerId}`),

  sendOffer: (data: any) =>
    apiClient.post<any>('/recruiter/offers/send', data),

  withdrawOffer: (offerId: string) =>
    apiClient.put<any>(`/recruiter/offers/${offerId}/withdraw`),

  resendOffer: (offerId: string) =>
    apiClient.post<any>(`/recruiter/offers/${offerId}/resend`),

  checkEsignStatus: (offerId: string) =>
    apiClient.post<any>(`/recruiter/offers/${offerId}/esign-status`),

  getSigningUrl: (offerId: string) =>
    apiClient.get<any>(`/recruiter/offers/${offerId}/signing-url`),

  listOfferTemplates: () =>
    apiClient.get<any[]>('/recruiter/offers/templates'),

  createOfferTemplate: (data: any) =>
    apiClient.post<any>('/recruiter/offers/templates', data),

  deleteOfferTemplate: (templateId: string) =>
    apiClient.delete(`/recruiter/offers/templates/${templateId}`),

  respondToOffer: (offerId: string, accept: boolean) =>
    apiClient.post<any>(`/recruiter/offers/respond/${offerId}`, { accept }),

  // Team management
  getTeamMembers: () =>
    apiClient.get<any[]>('/recruiter/collaboration/team'),

  addTeamMember: (data: any) =>
    apiClient.post<any>('/recruiter/collaboration/team', data),

  removeTeamMember: (memberId: string) =>
    apiClient.delete(`/recruiter/collaboration/team/${memberId}`),

  updateMemberRole: (memberId: string, role: string) =>
    apiClient.patch<any>(`/recruiter/collaboration/team/${memberId}/role`, { role }),

  searchTeamUsers: (query: string) =>
    apiClient.get<any[]>('/recruiter/collaboration/team/search', { q: query }),
};