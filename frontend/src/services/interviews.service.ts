import apiClient from '@/lib/api-client';
import type { Interview, InterviewFeedback } from '@/types';

export const interviewsService = {
  getInterviews: (params?: { limit?: number; offset?: number }) =>
    apiClient.get<Interview[]>('/recruiter/interviews/upcoming', params),

  getInterview: (id: string) =>
    apiClient.get<Interview>(`/recruiter/interviews/${id}`),

  scheduleInterview: (data: Partial<Interview>) =>
    apiClient.post<Interview>('/recruiter/interviews/schedule', {
      application_id: data.applicationId,
      scheduled_time: data.scheduledAt,
      duration_minutes: data.duration,
      type: data.type,
      meeting_link: data.meetingUrl,
      location: data.location,
      agenda: data.notes,
    }),

  updateInterview: (id: string, data: Partial<Interview>) =>
    apiClient.put<Interview>(`/recruiter/interviews/${id}`, data),

  cancelInterview: (id: string, reason?: string) =>
    apiClient.delete(`/recruiter/interviews/${id}`, { reason } as any),

  submitFeedback: (interviewId: string, feedback: Partial<InterviewFeedback>) =>
    apiClient.post<InterviewFeedback>(`/recruiter/interviews/${interviewId}/feedback`, feedback),

  getFeedback: (interviewId: string) =>
    apiClient.get<InterviewFeedback>(`/recruiter/interviews/${interviewId}/feedback`),

  reschedule: (id: string, newDate: string) =>
    apiClient.put(`/recruiter/interviews/${id}`, { scheduled_at: newDate }),
};