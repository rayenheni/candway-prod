import apiClient from '@/lib/api-client';
import type { Course } from '@/types';

export const coursesService = {
  getCourse: (id: string) =>
    apiClient.get<Course>(`/courses/${id}`),

  getCourseDetails: (id: string) =>
    apiClient.get<Course>(`/courses/${id}/details`),

  getCurriculum: (id: string) =>
    apiClient.get(`/courses/${id}/curriculum`),

  getMyEnrollments: () =>
    apiClient.get<{ id: number; course_id: number; course_title: string; progress: number; status: string }[]>('/courses/my-enrollments'),

  getMyProgress: () =>
    apiClient.get('/courses/my-progress'),

  enroll: (courseId: string) =>
    apiClient.post(`/courses/${courseId}/enroll`),

  updateLessonProgress: (courseId: string, lessonId: string, completed: boolean, watchTime?: number) =>
    apiClient.post(`/courses/${courseId}/lessons/${lessonId}/progress`, { completed, watch_time: watchTime }),

  getReviews: (courseId: string) =>
    apiClient.get(`/courses/${courseId}/reviews`),
};