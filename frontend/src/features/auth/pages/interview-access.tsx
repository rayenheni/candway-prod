import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { motion } from 'framer-motion';
import { authService } from '@/services/auth.service';
import apiClient from '@/lib/api-client';
import { Button } from '@/shared/components/ui/button';
import { Loader2, CheckCircle2, XCircle, ArrowRight } from 'lucide-react';

type Phase = 'validating' | 'success' | 'error';

export default function InterviewAccessPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const appId = searchParams.get('app_id');
  const token = searchParams.get('token');
  const [phase, setPhase] = useState<Phase>('validating');
  const [error, setError] = useState('');
  const handled = useRef(false);

  useEffect(() => {
    document.title = 'Interview Access | Candway';
  }, []);

  useEffect(() => {
    if (handled.current) return;
    if (!appId || !token) {
      setPhase('error');
      setError('This interview link is incomplete or has expired. Please ask your recruiter to resend the invitation.');
      return;
    }
    // If we already authenticated this guest for THIS exact app (logged_in marker cookie +
    // active app stored) AND no fresh token was supplied in URL parameters, skip guestLogin.
    const existingApp = localStorage.getItem('active_app_id');
    const hasSessionCookie = document.cookie
      .split(';')
      .some(c => c.trim().startsWith('logged_in=true'));
    if (existingApp && existingApp === String(appId) && hasSessionCookie && !token) {
      handled.current = true;
      setPhase('success');
      setTimeout(() => {
        navigate(`/interviews/room/${existingApp}`, { replace: true });
      }, 600);
      return;
    }
    handled.current = true;
    authService
      .guestLogin(Number(appId), token)
      .then(async (res) => {
        setPhase('success');
        const target = Number(res.application_id ?? appId);
        localStorage.setItem('active_app_id', String(target));
        // guest-login's own csrf cookie is a plain random token; the CSRF
        // middleware only issues a valid HMAC token on GET responses, so fetch
        // a public GET so the next (resume/chat) POST carries a valid token.
        try {
          await apiClient.get('/monitoring/health');
        } catch {
          // Middleware still attaches the token even on error responses.
        }
        setTimeout(() => {
          if (res.redirect) {
            navigate(res.redirect, { replace: true });
          } else {
            navigate(`/interviews/room/${target}`, { replace: true });
          }
        }, 1200);
      })
      .catch((err: any) => {
        setPhase('error');
        setError(
          err?.message ||
            'We could not validate your interview link. It may have expired or already been used.',
        );
      });
  }, [appId, token, navigate]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Interview Access</h1>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          {phase === 'validating' && 'Validating your invitation link...'}
          {phase === 'success' && 'Access granted. Redirecting you to your interview...'}
          {phase === 'error' && 'Your invitation link could not be used.'}
        </p>
      </div>

      {phase === 'validating' && (
        <div className="flex items-center justify-center h-24 rounded-2xl bg-violet-50 dark:bg-violet-500/10 border border-violet-200 dark:border-violet-500/20">
          <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
        </div>
      )}

      {phase === 'success' && (
        <div className="space-y-6">
          <div className="flex items-center justify-center h-24 rounded-2xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20">
            <CheckCircle2 className="h-12 w-12 text-emerald-500" />
          </div>
          <p className="text-center text-sm text-gray-500 dark:text-gray-400">
            Preparing your AI interview room...
          </p>
        </div>
      )}

      {phase === 'error' && (
        <div className="space-y-6">
          <div className="flex items-center justify-center h-24 rounded-2xl bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20">
            <XCircle className="h-12 w-12 text-red-500" />
          </div>
          <p className="text-center text-sm text-gray-500 dark:text-gray-400">{error}</p>
          <Button
            variant="primary"
            className="w-full"
            size="lg"
            rightIcon={<ArrowRight className="h-4 w-4" />}
            onClick={() => navigate('/auth/login')}
          >
            Go to Sign In
          </Button>
          <p className="text-center text-sm text-gray-500 dark:text-gray-400">
            <Link
              to="/auth/register"
              className="text-purple-600 hover:text-purple-700 dark:text-purple-400 font-medium"
            >
              Create an account instead
            </Link>
          </p>
        </div>
      )}
    </motion.div>
  );
}
