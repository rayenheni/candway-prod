import apiClient from '@/lib/api-client';

export const reportsService = {
  list: (params?: { page?: number; per_page?: number }) =>
    apiClient.get<{ total: number; page: number; per_page: number; reports: any[] }>('/recruiter/reports', params),

  get: (id: string) =>
    apiClient.get<any>(`/recruiter/reports/${id}`),

  build: (config: any) =>
    apiClient.post<any>('/recruiter/reports/build', config),

  save: (data: { name: string; description?: string; config: any }) =>
    apiClient.post<any>('/recruiter/reports/save', data),

  getData: (id: string) =>
    apiClient.get<any>(`/recruiter/reports/${id}/snapshots`),

  schedule: (id: string, data: { frequency: string; enabled: boolean }) =>
    apiClient.post<any>(`/recruiter/reports/${id}/schedule`, data),

  export: (id: string, format: string = 'csv') =>
    apiClient.postBlob(`/recruiter/reports/${id}/export/${format}`),

  metrics: () =>
    apiClient.get<any[]>('/recruiter/reports/metrics'),
};
