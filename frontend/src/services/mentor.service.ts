import apiClient from '@/lib/api-client';

export interface MentorStats {
  total_courses: number;
  total_students: number;
  revenue: number;
  average_rating: number;
}

export interface MentorEarningsChart {
  labels: string[];
  data: number[];
}

export interface MentorStudent {
  student_id: number;
  name: string;
  email: string;
  course_id: number;
  course_title: string;
  progress: number;
  status: string;
  enrolled_at: string | null;
}

export const mentorService = {
  getStats: () =>
    apiClient.get<MentorStats>('/mentor/stats'),

  getEarningsChart: () =>
    apiClient.get<MentorEarningsChart>('/mentor/earnings-chart'),

  getStudents: () =>
    apiClient.get<{ students: MentorStudent[]; total: number }>('/mentor/students'),
};
