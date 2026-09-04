import { Navigate, useLocation } from 'react-router';
import { useAuth } from '@/contexts/auth-context';
import { getCrossDomainDashboardRedirect } from '@/utils/domain-routing';
import type { UserRole } from '@/types';

import { appAuthUrl } from '@/features/marketing/utils/auth-url';

function AuthLoadingScreen() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#FAF7FF] dark:bg-[#0D0A1A]" role="status" aria-live="polite">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
        <span className="text-sm font-medium text-gray-600 dark:text-gray-300">Verifying your session...</span>
      </div>
    </div>
  );
}

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <AuthLoadingScreen />;
  if (!isAuthenticated) {
    const isCandidateHost = typeof window !== 'undefined' &&
      (window.location.hostname === 'candway.com' || window.location.hostname === 'www.candway.com');
    if (isCandidateHost) {
      window.location.href = appAuthUrl('/auth/login');
      return <AuthLoadingScreen />;
    }
    return <Navigate to="/auth/login" replace state={{ from: location.pathname + location.search }} />;
  }
  if (user && user.isEmailVerified === false) {
    return <Navigate to={`/auth/verify-otp?email=${encodeURIComponent(user.email)}`} replace />;
  }
  return children;
}

function hasGuestSession(): boolean {
  return document.cookie.split(';').some(c => c.trim().startsWith('logged_in=true'));
}

export function InterviewRoomRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <AuthLoadingScreen />;
  // Guests (invited candidates who entered via /auth/interview-access) carry a
  // non-HttpOnly `logged_in` marker cookie but are rejected by /auth/me
  // (get_current_user blocks guest-scoped JWTs), so the room must not rely on
  // the auth context alone.
  if (!isAuthenticated && !hasGuestSession()) {
    return <Navigate to="/auth/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return children;
}

export function RoleGuard({ roles, children }: { roles: UserRole[]; children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <AuthLoadingScreen />;
  if (!user || !roles.includes(user.role)) {
    // Route to the domain matching the user's role (candidates -> candway.com,
    // recruiters/admins/company/mentors -> app.candway.com). No-op on unknown
    // (dev) hosts.
    const crossDomainUrl = getCrossDomainDashboardRedirect(user?.role);
    if (typeof window !== 'undefined' && crossDomainUrl) {
      window.location.href = crossDomainUrl;
      return <AuthLoadingScreen />;
    }
    return <Navigate to="/dashboard" replace />;
  }
  return children;
}

export function InterviewAnalysisRoute({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <AuthLoadingScreen />;
  // Guests (invited candidates who entered via /auth/interview-access) carry a
  // non-HttpOnly `logged_in` marker cookie but are rejected by /auth/me, so the
  // analysis page must not rely on the auth context alone.
  if (!isAuthenticated && !hasGuestSession()) {
    return <Navigate to="/auth/login" replace state={{ from: location.pathname + location.search }} />;
  }
  if (user && !['candidate', 'recruiter', 'admin'].includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
}
