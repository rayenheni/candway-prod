import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { motion } from 'framer-motion';
import { authService } from '@/services/auth.service';
import { useLanguage } from '@/contexts/language-context';
import { Button } from '@/shared/components/ui/button';
import { CheckCircle2, XCircle, Loader2, Mail } from 'lucide-react';

type VerifyState = 'loading' | 'success' | 'error';

export default function VerifyEmailPage() {
  const { t } = useLanguage();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || undefined;
  const [state, setState] = useState<VerifyState>('loading');
  const [message, setMessage] = useState('');
  const [email, setEmail] = useState('');
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

  useEffect(() => {
    let active = true;
    if (!token) {
      setState('error');
      setMessage(t('auth.verifyEmail.missingToken'));
      return;
    }
    authService
      .verifyEmail(token)
      .then((res) => {
        if (!active) return;
        setMessage(res?.message || t('auth.verifyEmail.successMsg'));
        setState('success');
      })
      .catch((err: any) => {
        if (!active) return;
        setMessage(err?.message || t('auth.verifyEmail.invalidLink'));
        setState('error');
      });
    return () => {
      active = false;
    };
  }, [token, t]);

  const resend = async () => {
    if (!email.trim()) return;
    setResending(true);
    setResent(false);
    try {
      const res = await authService.resendVerification(email.trim());
      setResent(true);
      setMessage(res?.message || t('auth.verifyEmail.linkSentMsg'));
    } catch (e: any) {
      setMessage(e?.message || t('auth.verifyEmail.resendFailedMsg'));
    } finally {
      setResending(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="text-center"
    >
      {state === 'loading' && (
        <div className="flex flex-col items-center gap-4 py-8">
          <Loader2 className="h-12 w-12 animate-spin text-purple-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('auth.verifyEmail.verifying')}</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">{t('auth.verifyEmail.pleaseWait')}</p>
        </div>
      )}

      {state === 'success' && (
        <div className="flex flex-col items-center gap-4">
          <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20">
            <CheckCircle2 className="h-10 w-10 text-emerald-500" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('auth.verifyEmail.successTitle')}</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-sm">{message}</p>
          <Link to="/auth/login" className="w-full">
            <Button variant="primary" className="w-full" size="lg">{t('auth.verifyEmail.goToLogin')}</Button>
          </Link>
        </div>
      )}

      {state === 'error' && (
        <div className="flex flex-col items-center gap-4">
          <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20">
            <XCircle className="h-10 w-10 text-red-500" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('auth.verifyEmail.failedTitle')}</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-sm">{message}</p>

          <div className="w-full max-w-sm rounded-2xl border border-gray-200 dark:border-gray-700 p-4 text-left">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
              <Mail className="h-4 w-4 text-purple-600" /> {t('auth.verifyEmail.noValidLink')}
            </h2>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {t('auth.verifyEmail.enterEmailDesc')}
            </p>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              className="mt-3 w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
            <Button
              variant="primary"
              className="mt-3 w-full"
              size="lg"
              disabled={resending || !email.trim()}
              onClick={resend}
            >
              {resending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Mail className="h-4 w-4 mr-2" />}
              {resent ? t('auth.verifyEmail.linkSent') : t('auth.verifyEmail.resendLink')}
            </Button>
          </div>

          <Link to="/auth/login" className="w-full">
            <Button variant="outline" className="w-full" size="lg">{t('auth.backToLogin')}</Button>
          </Link>
        </div>
      )}
    </motion.div>
  );
}
