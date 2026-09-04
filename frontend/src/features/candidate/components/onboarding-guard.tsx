import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router';
import { useAuth } from '@/contexts/auth-context';
import { Button } from '@/shared/components/ui/button';
import { Loader2, Rocket, LogIn } from 'lucide-react';
import { candidateService } from '@/services/candidate.service';

let cachedBlocked: boolean | null = null;
let cachedUserId: string | number | null = null;

export function resetOnboardingGuardCache() {
  cachedBlocked = null;
  cachedUserId = null;
}

export function OnboardingGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [checking, setChecking] = useState(true);
  const [blocked, setBlocked] = useState(false);

  useEffect(() => {
    if (!user) return;
    if (user.role !== 'candidate') {
      setChecking(false);
      return;
    }
    if (location.pathname === '/onboarding' || location.pathname.startsWith('/onboarding')) {
      cachedBlocked = null;
      setBlocked(false);
      setChecking(false);
      return;
    }
    if (cachedBlocked !== null && cachedUserId === (user.id ?? null)) {
      setBlocked(cachedBlocked);
      setChecking(false);
      return;
    }
    candidateService.getDashboardSummary()
      .then(data => {
        const onboarded = (data as any).onboarding_completed;
        if (typeof onboarded === 'boolean') {
          cachedBlocked = !onboarded;
          cachedUserId = user.id ?? null;
          setBlocked(cachedBlocked);
          return;
        }
        const count = (data as any).applications_count ?? (data as any).total_applications ?? 0;
        const checklist = (data as any).checklist ?? [];
        const skillsDone = Array.isArray(checklist) && checklist.some(
          (c: any) => c && c.id === 'skills' && c.completed
        );
        cachedBlocked = count === 0 && !skillsDone;
        cachedUserId = user.id ?? null;
        setBlocked(cachedBlocked);
      })
      .catch(() => {
        cachedBlocked = false;
        cachedUserId = user.id ?? null;
        setBlocked(false);
      })
      .finally(() => setChecking(false));
  }, [user, location.pathname]);

  if (checking) {
    return <div className="flex items-center justify-center h-[60vh]"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>;
  }

  if (!blocked) return children;

  return (
    <div className="relative">
      {/* Blurred content */}
      <div className="pointer-events-none select-none blur-sm opacity-30">
        {children}
      </div>
      {/* Overlay */}
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
        <div className="bg-white dark:bg-[#12102a] rounded-2xl shadow-2xl border border-purple-200 dark:border-purple-500/20 p-8 max-w-md w-full mx-4 text-center space-y-5">
          <div className="mx-auto h-16 w-16 rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center">
            <Rocket className="h-8 w-8 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">Welcome to Candway!</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              Please complete your onboarding to unlock all features — profile setup, AI interview, dashboard, and more.
            </p>
          </div>
          {import.meta.env.DEV && (
          <div className="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 rounded-xl p-4 text-left text-xs text-amber-800 dark:text-amber-300 space-y-1">
            <p className="font-semibold">Test Account</p>
            <p>Email: <span className="font-mono">test@candway.tn</span></p>
            <p>Password: <span className="font-mono">Test123456!</span></p>
            <p className="text-amber-600 dark:text-amber-400">Register, login, then you'll see this popup. Click below to complete onboarding.</p>
          </div>
          )}
          <Button
            variant="primary"
            size="lg"
            className="w-full"
            onClick={() => navigate('/onboarding')}
            leftIcon={<LogIn className="h-4 w-4" />}
          >
            Complete Onboarding
          </Button>
          <p className="text-[11px] text-gray-400 dark:text-gray-500">
            This will only take a few minutes. You'll be able to build your CV, take an AI interview, and explore opportunities.
          </p>
        </div>
      </div>
    </div>
  );
}
