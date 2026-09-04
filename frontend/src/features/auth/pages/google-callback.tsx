import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { motion } from 'framer-motion';
import { authService } from '@/services/auth.service';
import { useLanguage } from '@/contexts/language-context';
import { Loader2, XCircle } from 'lucide-react';

import { getCrossDomainDashboardRedirect } from '@/utils/domain-routing';

const ROLE_HOME: Record<string, string> = {
  candidate: '/dashboard',
  recruiter: '/dashboard',
  mentor: '/dashboard',
  admin: '/dashboard',
  company: '/org/dashboard',
};

export default function GoogleCallbackPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const oauthError = searchParams.get('error');

    const finish = (msg: string) => {
      if (!active) return;
      setError(msg);
    };

    if (oauthError) {
      finish(t('auth.google.authFailed') + oauthError);
      return;
    }
    if (!code) {
      finish(t('auth.google.noCode'));
      return;
    }

    authService
      .googleCallback(code, state ?? undefined)
      .then((data) => {
        if (!active) return;
        const role = ((data as Record<string, unknown>)?.user as Record<string, unknown> | undefined)?.role as string | undefined;
        const crossDomainUrl = getCrossDomainDashboardRedirect(role);
        if (crossDomainUrl) {
          window.location.href = crossDomainUrl;
        } else {
          const home = (role && ROLE_HOME[role]) || '/dashboard';
          navigate(home, { replace: true });
        }
      })
      .catch((err: any) => {
        finish(err?.message || t('auth.google.signInFailed'));
      });

    return () => {
      active = false;
    };
  }, [searchParams, navigate, t]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="text-center"
    >
      {error ? (
        <div className="flex flex-col items-center gap-4 py-8">
          <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20">
            <XCircle className="h-10 w-10 text-red-500" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('auth.google.signInFailedTitle')}</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-sm">{error}</p>
          <a
            href="/auth/login"
            className="rounded-lg border border-purple-200 bg-white px-4 py-2.5 text-sm font-medium text-purple-700 hover:bg-purple-50 dark:border-white/10 dark:bg-white/5 dark:text-purple-300"
          >
            {t('auth.backToLogin')}
          </a>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4 py-8">
          <Loader2 className="h-12 w-12 animate-spin text-purple-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('auth.google.signingIn')}</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">{t('auth.google.pleaseWait')}</p>
        </div>
      )}
    </motion.div>
  );
}
