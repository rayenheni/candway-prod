import apiClient from '@/lib/api-client';
import type {
  User, LoginCredentials, RegisterData, OrgRegisterData, OrgRegisterResponse,
  AuthTokenResponse, GuestLoginResponse,
  UserLoginRequest, UserSignupRequest, UserUpdateRequest,
} from '@/types';

function mapBackendUser(data: Record<string, unknown>): User {
  const name = (data.name as string) || '';
  const parts = name.split(' ');
  return {
    id: String(data.id ?? ''),
    email: (data.email as string) || '',
    firstName: parts[0] || '',
    lastName: parts.slice(1).join(' ') || '',
    avatar: (data.avatar as string) || (data.avatar_url as string) || undefined,
    role: (data.role as User['role']) || 'candidate',
    organizationId: data.company_id ? String(data.company_id) : undefined,
    isEmailVerified: data.email_verified !== false,
    createdAt: '',
    updatedAt: '',
  };
}

export const authService = {
  login: async (credentials: LoginCredentials) => {
    const body: UserLoginRequest = {
      email: credentials.email,
      password: credentials.password,
    };
    const res = await apiClient.post<AuthTokenResponse & { id?: number; name?: string; avatar?: string }>('/auth/login', body);
    return mapBackendUser(res as unknown as Record<string, unknown>);
  },

  guestLogin: (appId: number, token: string) =>
    apiClient.post<GuestLoginResponse>('/auth/guest-login', { app_id: appId, token }),

  register: async (data: RegisterData) => {
    const body: UserSignupRequest = {
      email: data.email,
      password: data.password,
      role: data.role as 'candidate' | 'recruiter',
      name: `${data.firstName} ${data.lastName}`.trim(),
    };
    const res = await apiClient.post<AuthTokenResponse & { id?: number; name?: string; email_verification_required?: boolean }>('/auth/signup', body);
    const user = mapBackendUser(res as unknown as Record<string, unknown>);
    user.isEmailVerified = !res.email_verification_required;
    return user;
  },

  registerOrg: async (data: OrgRegisterData) => {
    const body = {
      company_name: data.companyName,
      admin_name: data.adminName,
      admin_email: data.adminEmail,
      admin_password: data.adminPassword,
      domain: data.domain || undefined,
      slug: data.slug || undefined,
      billing_email: data.billingEmail || undefined,
      billing_address: data.billingAddress || undefined,
      tax_id: data.taxId || undefined,
    };
    const res = await apiClient.post<OrgRegisterResponse>('/auth/signup/org', body);
    const user = mapBackendUser(res as unknown as Record<string, unknown>);
    user.isEmailVerified = !res.email_verification_required;
    return { ...res, user };
  },

  logout: () => apiClient.post<{ message: string }>('/auth/logout'),

  getProfile: async () => {
    const res = await apiClient.get<Record<string, unknown>>('/auth/me');
    return mapBackendUser(res);
  },

  updateProfile: async (data: Partial<User>) => {
    const body: UserUpdateRequest = {};
    if (data.firstName || data.lastName) {
      body.name = `${data.firstName || ''} ${data.lastName || ''}`.trim();
    }
    if (data.avatar) body.avatar_url = data.avatar;
    const res = await apiClient.put<{ message: string }>('/auth/me', body);
    return res;
  },

  forgotPassword: (email: string) =>
    apiClient.post<{ message: string }>('/auth/forgot-password', { email }),

  resetPassword: (data: { token: string; password: string }) =>
    apiClient.post<{ message: string }>('/auth/reset-password', { token: data.token, new_password: data.password }),

  verifyEmail: (token: string) =>
    apiClient.get<{ message: string }>(`/auth/verify-email/${encodeURIComponent(token)}`),

  verifyOtp: (email: string, code: string) =>
    apiClient.post<{ message: string }>('/auth/verify-otp', { email, code }),

  resendOtp: (email: string) =>
    apiClient.post<{ message: string }>('/auth/resend-otp', { email }),

  resendVerification: (email: string) =>
    apiClient.post<{ message: string }>('/auth/resend-verification', { email }),

  googleLogin: () =>
    apiClient.get<{ auth_url: string }>('/auth/google/login'),

  googleCallback: (code: string, state?: string) =>
    apiClient.get<Record<string, unknown>>(
      `/auth/google/callback?code=${encodeURIComponent(code)}${state ? `&state=${encodeURIComponent(state)}` : ''}`,
    ),

  refreshToken: () =>
    apiClient.post<{ access_token: string; token_type: string }>('/auth/refresh'),
};