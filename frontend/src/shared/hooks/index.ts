import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { candidatesService } from '@/services/candidates.service';
import { jobsService } from '@/services/jobs.service';
import { analyticsService } from '@/services/analytics.service';
import { interviewsService } from '@/services/interviews.service';
import { adminService } from '@/services/admin.service';
import { authService } from '@/services/auth.service';
import { notificationsService } from '@/services/notifications.service';

// ─── Auth ───
export function useProfile() {
  return useQuery({ queryKey: ['auth', 'profile'], queryFn: authService.getProfile, retry: false, staleTime: 5 * 60 * 1000 });
}

// ─── Dashboard ───
export function useRecruiterStats() {
  return useQuery({ queryKey: ['dashboard', 'stats'], queryFn: () => analyticsService.getDashboardStats() });
}

export function useAnalyticsDashboard() {
  return useQuery({ queryKey: ['dashboard', 'analytics'], queryFn: () => analyticsService.getAnalyticsDashboard() });
}

// ─── Candidates ───
export function useCandidates(params?: Parameters<typeof candidatesService.getCandidates>[0]) {
  return useQuery({ queryKey: ['candidates', params], queryFn: () => candidatesService.getCandidates(params) });
}

export function useApplications(params?: Parameters<typeof candidatesService.getApplications>[0]) {
  return useQuery({ queryKey: ['applications', params], queryFn: () => candidatesService.getApplications(params) });
}

export function useApplication(id: string) {
  return useQuery({ queryKey: ['application', id], queryFn: () => candidatesService.getApplication(id), enabled: !!id });
}

export function useUpdateApplicationStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => candidatesService.updateApplicationStatus(id, status),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['applications'] }); qc.invalidateQueries({ queryKey: ['candidates'] }); },
  });
}

// ─── Jobs ───
export function useJobs(params?: Parameters<typeof jobsService.getJobs>[0]) {
  return useQuery({ queryKey: ['jobs', params], queryFn: () => jobsService.getJobs(params) });
}

export function useJob(id: string) {
  return useQuery({ queryKey: ['job', id], queryFn: () => jobsService.getJob(id), enabled: !!id });
}

export function useCreateJob() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: jobsService.createJob, onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }) });
}

export function useUpdateJob() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: Partial<any> }) => jobsService.updateJob(id, data), onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }) });
}

export function useDeleteJob() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: jobsService.deleteJob, onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }) });
}

// ─── Interviews ───
export function useInterviews(params?: Parameters<typeof interviewsService.getInterviews>[0]) {
  return useQuery({ queryKey: ['interviews', params], queryFn: () => interviewsService.getInterviews(params) });
}

export function useInterview(id: string) {
  return useQuery({ queryKey: ['interview', id], queryFn: () => interviewsService.getInterview(id), enabled: !!id });
}

export function useScheduleInterview() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: interviewsService.scheduleInterview, onSuccess: () => qc.invalidateQueries({ queryKey: ['interviews'] }) });
}

// ─── Admin ───
export function useAdminUsers(params?: Parameters<typeof adminService.getUsers>[0]) {
  return useQuery({ queryKey: ['admin', 'users', params], queryFn: () => adminService.getUsers(params) });
}

// ─── Notifications ───
export function useNotifications(params?: { limit?: number; unread_only?: boolean }) {
  return useQuery({ queryKey: ['notifications', params], queryFn: () => notificationsService.getNotifications(params) });
}

export function useUnreadCount() {
  return useQuery({ queryKey: ['notifications', 'unread-count'], queryFn: () => notificationsService.getUnreadCount() });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: notificationsService.markAsRead, onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }) });
}

export function useMarkAllNotificationsRead() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: notificationsService.markAllAsRead, onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }) });
}