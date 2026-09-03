import apiClient from '@/lib/api-client';

export const calendarService = {
  getICSDownload: (interviewId: number) =>
    apiClient.get(`/calendar/ics/interview/${interviewId}`),

  getCalendarStatus: () =>
    apiClient.get<{ connected: boolean; provider?: string }>('/calendar/status'),

  connectGoogle: (authorizationCode: string) =>
    apiClient.post('/calendar/google/connect', { authorization_code: authorizationCode }),

  connectOutlook: (accessToken: string) =>
    apiClient.post('/calendar/outlook/connect', { access_token: accessToken }),

  disconnectCalendar: (provider: string) =>
    apiClient.post(`/calendar/disconnect/${provider}`),

  syncInterviewToCalendar: (interviewId: number, calendarType: string) =>
    apiClient.post(`/calendar/google/sync/interview/${interviewId}`, { calendar_type: calendarType }),
};