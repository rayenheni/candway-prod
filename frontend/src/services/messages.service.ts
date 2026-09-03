import apiClient from '@/lib/api-client';
import type { Message, Conversation } from '@/types';

export const messagesService = {
  getConversations: () =>
    apiClient.get<Conversation[]>('/messages/conversations'),

  getConversation: (id: string) =>
    apiClient.get<Conversation>(`/messages/conversations/${id}`),

  getMessages: async (conversationId: string, params?: { page?: number; before?: string }) => {
    const data: any = await apiClient.get(`/messages/conversations/${conversationId}`, params);
    return Array.isArray(data) ? data : data?.messages ?? [];
  },

  sendMessage: (conversationId: string, content: string) =>
    apiClient.post<Message>(`/messages/conversations/${conversationId}/messages`, { content }),

  markAsRead: (conversationId: string) =>
    apiClient.post(`/messages/conversations/${conversationId}/read`),

  createConversation: (participantIds: number[], initialMessage?: string) =>
    apiClient.post<Conversation>('/messages/conversations', { participant_ids: participantIds, initial_message: initialMessage }),

  getUnreadCount: () =>
    apiClient.get<{ count: number }>('/messages/unread-count'),

  searchUsers: (query: string) =>
    apiClient.get('/messages/users/search', { q: query }),
};