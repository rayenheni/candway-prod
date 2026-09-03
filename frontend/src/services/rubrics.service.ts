import apiClient from '@/lib/api-client';

export interface RubricTemplate {
  job_id: number;
  job_title: string;
  company?: string;
  rubric_id: number;
  version: number;
  seniority: string;
  category_count: number;
  skill_count: number;
}

export interface RubricManagementRow {
  job_id: number;
  job_title: string;
  is_active: boolean;
  location: string;
  type: string;
  application_count: number;
  rubric: {
    id: number;
    version: number;
    seniority: string;
    category_count: number;
    skill_count: number;
    is_current: boolean;
    created_at: string;
  } | null;
  has_draft: boolean;
}

export interface RubricManagementResponse {
  rows: RubricManagementRow[];
  drafts: any[];
  stats: {
    total_jobs: number;
    with_rubric: number;
    without_rubric: number;
    drafts: number;
    total_skills: number;
  };
}

export const rubricsService = {
  getTemplates: () =>
    apiClient.get<{ templates: RubricTemplate[] }>('/rubric/templates'),

  getManagement: () =>
    apiClient.get<RubricManagementResponse>('/rubric/management'),

  getTemplateDetail: (jobId: number) =>
    apiClient.get<any>(`/rubric/template-detail/${jobId}`),

  generateRubric: (data: { job_id?: number; jd_text?: string; role_title?: string }) =>
    apiClient.post<any>('/rubric/generate', data),

  createRubric: (jobId: number, data: any) =>
    apiClient.post<any>(`/rubric/jobs/${jobId}`, data),

  duplicateRubric: (jobId: number) =>
    apiClient.post<any>(`/rubric/duplicate/${jobId}`),
};
