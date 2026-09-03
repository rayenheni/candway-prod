import apiClient from '@/lib/api-client';
import type { ChartDataPoint, DashboardStats } from '@/types';

export const analyticsService = {
  getDashboardStats: () =>
    apiClient.get<DashboardStats>('/recruiter/stats'),

  getAnalyticsDashboard: () =>
    apiClient.get<Record<string, unknown>>('/recruiter/analytics-dashboard'),

  getApplicationTrends: (params?: { period?: string; startDate?: string; endDate?: string }) =>
    apiClient.get<ChartDataPoint[]>('/analytics/dashboard', params),

  getHiringFunnel: () =>
    apiClient.get<{ stage: string; count: number; conversionRate: number }[]>('/analytics/pipeline'),

  getInterviewAnalytics: () =>
    apiClient.get('/analytics/interviews'),

  getOfferAnalytics: () =>
    apiClient.get('/analytics/offers'),

  getTeamPerformance: () =>
    apiClient.get('/analytics/team'),

  exportReport: (params?: { format?: string; days?: number }) => {
    const format = params?.format ?? 'csv';
    const days = params?.days ?? 30;
    return apiClient.getBlob(`/analytics/export?format=${format}&days=${days}`);
  },

  listReports: (params?: { page?: number; per_page?: number }) =>
    apiClient.get<{ total: number; page: number; per_page: number; reports: Record<string, unknown>[] }>('/recruiter/reports', params),

  getReport: (reportId: number) =>
    apiClient.get<Record<string, unknown>>(`/recruiter/reports/${reportId}`),

  generateReport: (reportId: number) =>
    apiClient.post<{ snapshot_id: number; generated_at: string; report_data: Record<string, unknown> }>(`/recruiter/reports/${reportId}/generate`),
};