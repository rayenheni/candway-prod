import apiClient from '@/lib/api-client';

export interface SkillItem {
  name: string;
  level: number;
  trend: string;
  verified: boolean;
}

export interface SkillCategory {
  name: string;
  skills: SkillItem[];
}

export interface SkillProgressStats {
  total_skills: number;
  avg_level: number;
  verified_count: number;
  improving_count: number;
}

export interface SkillProgressResponse {
  categories: SkillCategory[];
  stats: SkillProgressStats;
}

export const skillProgressService = {
  get: () =>
    apiClient.get<SkillProgressResponse>('/skill-progress'),
};
