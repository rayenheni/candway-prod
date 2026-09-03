import apiClient from '@/lib/api-client';
import type { Job } from '@/types';

export interface JobsQueryParams {
  [key: string]: string | number | boolean | undefined;
  page?: number;
  per_page?: number;
  search?: string;
  status?: string;
  type?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export const jobsService = {
  getJobs: (params?: JobsQueryParams) =>
    apiClient.get<{ items: Job[]; pagination: { total: number; page: number; per_page: number } }>('/recruiter/jobs/my', params),

  getJob: (id: string) =>
    apiClient.get<Job>(`/recruiter/jobs/${id}`),

  createJob: (data: Partial<Job>) =>
    apiClient.post<Job>('/recruiter/jobs', data),

  updateJob: (id: string, data: Partial<Job>) =>
    apiClient.patch<Job>(`/recruiter/jobs/${id}`, data),

  deleteJob: (id: string) =>
    apiClient.delete(`/recruiter/jobs/${id}`),

  publishJob: (id: string) =>
    apiClient.post<Job>(`/recruiter/jobs/${id}/publish`),

  closeJob: (id: string) =>
    apiClient.post<Job>(`/recruiter/jobs/${id}/close`),

  duplicateJob: (id: string) =>
    apiClient.post<Job>(`/recruiter/jobs/${id}/clone`),

  getJobPipelineStages: (id: string) =>
    apiClient.get<any[]>(`/recruiter/jobs/${id}/pipeline-stages`),

  getJobAnalytics: (id: string) =>
    apiClient.get(`/recruiter/jobs/${id}/analytics`),

  getJobReport: (id: string) =>
    apiClient.get<any>(`/recruiter/jobs/${id}/report`),

  exportJobReport: (id: string, format: 'csv' | 'pdf' = 'csv') =>
    apiClient.getBlob(`/recruiter/jobs/${id}/report/export?format=${format}`),

  // Job Wizard
  getWizardCategories: () =>
    apiClient.get<any[]>('/recruiter/jobs/wizard/categories'),

  getWizardRecruiters: () =>
    apiClient.get<any[]>('/recruiter/jobs/wizard/recruiters'),

  startWizard: (data: any) =>
    apiClient.post<any>('/recruiter/jobs/wizard/start', data),

  getWizard: (jobId: string) =>
    apiClient.get<any>(`/recruiter/jobs/wizard/${jobId}`),

  updateWizardStep1: (jobId: string, data: any) =>
    apiClient.patch<any>(`/recruiter/jobs/wizard/${jobId}/step1`, data),

  updateWizardStep2: (jobId: string, data: any) =>
    apiClient.patch<any>(`/recruiter/jobs/wizard/${jobId}/step2`, data),

  updateWizardStep3: (jobId: string, data: any) =>
    apiClient.patch<any>(`/recruiter/jobs/wizard/${jobId}/step3`, data),

  updateWizardStep4: (jobId: string, data: any) =>
    apiClient.patch<any>(`/recruiter/jobs/wizard/${jobId}/step4`, data),

  updateWizardStep5: (jobId: string, data: any) =>
    apiClient.patch<any>(`/recruiter/jobs/wizard/${jobId}/step5`, data),

  publishWizardJob: (jobId: string) =>
    apiClient.post<any>(`/recruiter/jobs/wizard/${jobId}/publish`),

  deleteWizard: (jobId: string) =>
    apiClient.delete(`/recruiter/jobs/wizard/${jobId}`),

  // AI Suggestion endpoints
  suggestSkills: (title: string) =>
    apiClient.post<any>('/recruiter/jobs/wizard/ai/suggest-skills', { title }),

  suggestWeights: (skills: string[]) =>
    apiClient.post<any>('/recruiter/jobs/wizard/ai/suggest-weights', { skills }),

  generateSummary: (items: { question_key: string; question: string; answer?: string }[]) =>
    apiClient.post<any>('/recruiter/jobs/wizard/ai/generate-summary', { items }),

  suggestCategories: (skills: string[]) =>
    apiClient.post<any>('/recruiter/jobs/wizard/ai/suggest-categories', { skills }),

  suggestPipeline: (employment_type: string) =>
    apiClient.post<any>('/recruiter/jobs/wizard/ai/suggest-pipeline', { employment_type }),

  suggestQuestions: (skills: string[]) =>
    apiClient.post<any>('/recruiter/jobs/wizard/ai/suggest-questions', { skills }),

  suggestSalary: (title: string, location: string) =>
    apiClient.post<any>('/recruiter/jobs/wizard/ai/suggest-salary', { title, location }),

  detectGaps: (current_state: Record<string, any>) =>
    apiClient.post<any>('/recruiter/jobs/wizard/ai/detect-gaps', { current_state }),
};