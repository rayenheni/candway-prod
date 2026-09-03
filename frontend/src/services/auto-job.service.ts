import apiClient from '@/lib/api-client';

export const autoJobService = {
  create: (data: { title: string; skills?: string[]; seniority?: string; company?: string; location?: string; type?: string; description_override?: string }) =>
    apiClient.post<{ job_id: number; job_title: string; rubric_id: number | null; questions_count: number; email_template_id: number | null }>('/recruiter/jobs/auto-create', data),
};
