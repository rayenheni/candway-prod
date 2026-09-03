import apiClient from '@/lib/api-client';

export const eeoService = {
  getDashboard: () =>
    apiClient.get<any>('/recruiter/eeo/dashboard'),

  getPipelineDiversity: () =>
    apiClient.get<any>('/recruiter/eeo/pipeline-diversity'),

  getSelectionRates: () =>
    apiClient.get<any>('/recruiter/eeo/selection-rates'),

  getTrends: () =>
    apiClient.get<any>('/recruiter/eeo/trends'),

  getEEO1Report: () =>
    apiClient.get<any>('/recruiter/eeo/eeo1-report'),

  getComplianceSummary: () =>
    apiClient.get<any>('/recruiter/eeo/compliance-summary'),

  getCoverageRate: () =>
    apiClient.get<any>('/recruiter/eeo/coverage-rate'),

  getCoverageDetail: () =>
    apiClient.get<any>('/recruiter/eeo/coverage-detail'),

  exportReport: (format: string) =>
    apiClient.post<any>(`/recruiter/eeo/export/${format}`),

  getCandidateEeoStatus: (applicationId: string) =>
    apiClient.get<any>(`/candidate/eeo/status/${applicationId}`),

  submitCandidateEeo: (data: any) =>
    apiClient.post<any>('/candidate/eeo/submit', data),

  getMyEeoData: () =>
    apiClient.get<any>('/candidate/eeo/my-data'),
};
