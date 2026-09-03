import apiClient from '@/lib/api-client';

export const backgroundChecksService = {
  list: (params?: { page?: number; per_page?: number; status?: string }) =>
    apiClient.get<{ items: any[]; pagination: { total: number; page: number; per_page: number } }>('/recruiter/background-checks', params),

  getByApplication: (appId: string) =>
    apiClient.get<any>(`/recruiter/background-checks/${appId}`),

  initiate: (appId: string) =>
    apiClient.post<any>(`/recruiter/background-checks/initiate/${appId}`),

  initiateAdverseAction: (id: string) =>
    apiClient.post<any>(`/recruiter/background-checks/${id}/adverse-action`),

  getStats: () =>
    apiClient.get<any>('/recruiter/background-checks/stats/summary'),
};
