import apiClient from '@/lib/api-client';

export interface NotificationItem {
  id: number;
  type: string;
  title: string;
  message: string;
  level: string;
  is_read: boolean;
  created_at: string;
  payload?: Record<string, unknown>;
}

export const notificationsService = {
  getNotifications: (params?: { limit?: number; offset?: number; unread_only?: boolean }) =>
    apiClient.get<NotificationItem[]>('/notifications/latest', params as Record<string, string | number | boolean | undefined>),

  getUnreadCount: () =>
    apiClient.get<{ count: number }>('/notifications/unread-count'),

  markAsRead: (id: number) =>
    apiClient.post(`/notifications/${id}/mark-read`),

  markAllAsRead: () =>
    apiClient.post('/notifications/mark-all-read'),
};