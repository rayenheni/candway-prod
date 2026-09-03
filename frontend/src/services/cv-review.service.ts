import apiClient from '@/lib/api-client';

export interface RubricDimensionScore {
  category: string;
  weight: number;
  score: number;
  level: string;
  evidence: string;
}

export interface SkillTreeCoverage {
  tree_name: string;
  covered: string[];
  missing: string[];
}

export interface GapAnalysisItem {
  skill: string;
  priority: string;
  recommendation: string;
}

export interface CVReviewResult {
  overall_grade: string;
  grade_explanation: string;
  summary: string;
  spelling_errors?: Array<{ original: string; corrected: string; context: string }>;
  grammar_issues?: Array<{ sentence: string; correction: string; rule: string }>;
  improvement_suggestions?: Array<{
    category: string;
    title: string;
    description: string;
    priority: string;
    example_before?: string;
    example_after?: string;
  }>;
  keyword_suggestions?: Array<{ keyword: string; reason: string }>;
  strengths?: string[];
  declared_role?: string;
  cv_length?: number;
  rubric_dimension_scores?: RubricDimensionScore[];
  skill_tree_coverage?: SkillTreeCoverage;
  gap_analysis?: GapAnalysisItem[];
}

export interface CandidateUsage {
  cv_uploads_used: number;
  cv_uploads_limit: number;
  ai_interviews_used: number;
  ai_interviews_limit: number;
  tier: string;
  subscription_status?: string;
}

export const cvReviewService = {
  getCvReview: (force = false) =>
    apiClient.get<CVReviewResult>(`/candidate/cv-review${force ? '?force=true' : ''}`),

  getCvReviewEnriched: (force = false) =>
    apiClient.get<CVReviewResult>(`/candidate/cv-review/enriched${force ? '?force=true' : ''}`),

  uploadCv: (file: File, declaredRole = 'General Software Engineer') => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('declared_role', declaredRole);
    return apiClient.postFormData<{ success: boolean; message: string; analysis?: CVReviewResult }>('/candidate/upload-cv', fd);
  },

  getCandidateUsage: () =>
    apiClient.get<CandidateUsage>('/candidate/subscription/usage'),

  getCandidatePlans: () =>
    apiClient.get<any[]>('/candidate/plans'),

  requestUpgrade: (planId: number, message?: string) =>
    apiClient.post<{ message: string; status: string }>('/candidate/upgrade', { plan_id: planId, message }),
};
