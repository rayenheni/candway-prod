import apiClient from '@/lib/api-client';

export interface StandaloneSkillTreeCreate {
  name: string;
  category_id?: number;
  industry?: string;
  seniority?: string;
  description?: string;
  categories: Record<string, unknown>[];
  skill_count?: number;
}

export interface SkillTreeCreate {
  job_id: number;
  title?: string;
  description?: string;
  categories?: number[];
  rubric?: Record<string, unknown>;
  seniority?: string;
}

export interface SkillTreeUpdate {
  rubric: Record<string, unknown>;
  seniority?: string;
}

export interface SkillTreePatch {
  title?: string;
  name?: string;
  seniority?: string;
  description?: string;
  is_active?: boolean;
}

export interface SkillTreeDuplicate {
  new_name?: string;
  job_id?: number;
}

export interface RubricDetail extends Record<string, unknown> {
  id: number;
  title?: string;
  job_name?: string;
  version?: number;
  seniority?: string;
  description?: string | null;
  skill_count?: number;
  category_count?: number;
  rubric_json?: { categories: Record<string, unknown>[] };
  linked_jobs?: {
    id: number;
    title: string;
    location?: string;
    type?: string;
    status?: string;
    link_type?: string;
  }[];
  evaluated_candidates?: {
    application_id: number;
    candidate_id?: number | null;
    candidate_name: string;
    email?: string;
    job_title?: string;
    final_score?: number;
    rubric_score?: number;
    rubric_version?: number;
    cv_score?: number;
    status?: string;
    evaluated_at?: string;
  }[];
}

export const skillTreesService = {
  list: () =>
    apiClient.get<{ skill_trees: Record<string, unknown>[] }>('/recruiter/skill-trees'),

  create: (data: SkillTreeCreate) =>
    apiClient.post<{ success: boolean; id: number; job_id?: number; version: number; skill_tree: Record<string, unknown> }>('/recruiter/skill-trees', data),

  createStandalone: (data: StandaloneSkillTreeCreate) =>
    apiClient.post<{ success: boolean; id: number; version: number; skill_tree: Record<string, unknown> }>('/recruiter/skill-trees/standalone', data),

  generate: (data: { title: string; description?: string }) =>
    apiClient.post<{ success: boolean; source: 'ai' | 'fallback'; categories: Record<string, unknown>[] }>('/recruiter/skill-trees/ai/generate', data),

  get: (treeId: number) =>
    apiClient.get<Record<string, unknown>>(`/recruiter/skill-trees/${treeId}`),

  getDetail: (treeId: number) =>
    apiClient.get<RubricDetail>(`/recruiter/skill-trees/${treeId}/detail`),

  update: (treeId: number, data: SkillTreeUpdate) =>
    apiClient.put<{ success: boolean; id: number; version: number; skill_tree: Record<string, unknown> }>(`/recruiter/skill-trees/${treeId}`, data),

  patch: (treeId: number, data: SkillTreePatch) =>
    apiClient.patch<{ success: boolean; id: number; skill_tree: Record<string, unknown> }>(`/recruiter/skill-trees/${treeId}`, data),

  delete: (treeId: number) =>
    apiClient.delete<{ success: boolean; id: number }>(`/recruiter/skill-trees/${treeId}`),

  duplicate: (treeId: number, data?: SkillTreeDuplicate) =>
    apiClient.post<{ success: boolean; id: number; version: number; skill_tree: Record<string, unknown> }>(`/recruiter/skill-trees/${treeId}/duplicate`, data),
};
