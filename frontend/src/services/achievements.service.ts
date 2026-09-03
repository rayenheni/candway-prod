import apiClient from '@/lib/api-client';

export interface Achievement {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  icon_slug: string;
  category: string;
  progress_max: number;
  progress_current: number;
  unlocked: boolean;
  unlocked_at: string | null;
}

export interface AchievementListResponse {
  data: Achievement[];
}

export interface AchievementStatsResponse {
  total: number;
  unlocked: number;
}

export const achievementsService = {
  list: () =>
    apiClient.get<AchievementListResponse>('/achievements'),

  stats: () =>
    apiClient.get<AchievementStatsResponse>('/achievements/stats'),
};
