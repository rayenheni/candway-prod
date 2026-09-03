import { createContext, useCallback, useContext, useEffect, useReducer, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiClientError } from '@/lib/api-client';
import { authService } from '@/services/auth.service';
import type { LoginCredentials, RegisterData, User, UserRole } from '@/types';

interface AuthState { user: User | null; isAuthenticated: boolean; error: string | null }
type AuthAction = { type: 'SET_USER'; payload: User } | { type: 'CLEAR_USER' } | { type: 'SET_ERROR'; payload: string | null };

const initialState: AuthState = { user: null, isAuthenticated: false, error: null };

function reducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'SET_USER': return { user: action.payload, isAuthenticated: true, error: null };
    case 'CLEAR_USER': return { user: null, isAuthenticated: false, error: null };
    case 'SET_ERROR': return { ...state, error: action.payload };
  }
}

interface AuthContextValue extends AuthState {
  isLoading: boolean;
  isDemoMode: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (data: Partial<User>) => Promise<void>;
  switchRole: (role: UserRole) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function errorMessage(error: unknown): string {
  if (error instanceof ApiClientError || error instanceof Error) return error.message;
  return 'Authentication request failed.';
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const queryClient = useQueryClient();
  const profileQuery = useQuery({
    queryKey: ['auth', 'profile'],
    queryFn: authService.getProfile,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (profileQuery.data) dispatch({ type: 'SET_USER', payload: profileQuery.data });
    if (profileQuery.isError) dispatch({ type: 'CLEAR_USER' });
  }, [profileQuery.data, profileQuery.isError]);

  const loginMutation = useMutation({ mutationFn: authService.login });
  const registerMutation = useMutation({ mutationFn: authService.register });
  const logoutMutation = useMutation({ mutationFn: authService.logout });
  const updateMutation = useMutation({ mutationFn: authService.updateProfile });

  const login = useCallback(async (credentials: LoginCredentials) => {
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const user = await loginMutation.mutateAsync(credentials);
      dispatch({ type: 'SET_USER', payload: user });
      queryClient.setQueryData(['auth', 'profile'], user);
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: errorMessage(error) });
      throw error;
    }
  }, [loginMutation, queryClient]);

  const register = useCallback(async (data: RegisterData) => {
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const user = await registerMutation.mutateAsync(data);
      if (!user.isEmailVerified) {
        // Do not auto-authenticate until email is verified.
        throw new ApiClientError('Verification required — check your email for the OTP code.', 0);
      }
      dispatch({ type: 'SET_USER', payload: user });
      queryClient.setQueryData(['auth', 'profile'], user);
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: errorMessage(error) });
      throw error;
    }
  }, [queryClient, registerMutation]);

  const logout = useCallback(async () => {
    try {
      await logoutMutation.mutateAsync();
    } catch {
      // Silently handle - backend may return errors if already logged out
    } finally {
      dispatch({ type: 'CLEAR_USER' });
      queryClient.clear();
    }
  }, [logoutMutation, queryClient]);

  const updateProfile = useCallback(async (data: Partial<User>) => {
    const updated = state.user ? { ...state.user, ...data } : {} as User;
    try {
      await updateMutation.mutateAsync(data);
    } catch {
      // Continue optimistically
    }
    dispatch({ type: 'SET_USER', payload: updated });
    queryClient.setQueryData(['auth', 'profile'], updated);
  }, [queryClient, state.user, updateMutation]);

  const switchRole = useCallback((_role: UserRole) => false, []);

  const isAuthenticated = profileQuery.isLoading
    ? state.isAuthenticated
    : !!profileQuery.data;

  const user = profileQuery.data || state.user;

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, error: state.error, isLoading: profileQuery.isLoading, isDemoMode: Boolean(user?.is_demo), login, register, logout, updateProfile, switchRole }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}