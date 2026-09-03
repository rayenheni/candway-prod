import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { authService } from '@/services/auth.service';
import { useLanguage } from '@/contexts/language-context';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { customToast } from '@/shared/components/ui/toast';
import { Mail, ArrowRight, CheckCircle2, KeyRound } from 'lucide-react';

export default function VerifyOtpPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState(searchParams.get('email') || '');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    document.title = `${t('auth.verifyOtp.documentTitle')} | Candway`;
  }, [t]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !code) return;
    setLoading(true);
    try {
      await authService.verifyOtp(email, code);
      await queryClient.invalidateQueries({ queryKey: ['auth', 'profile'] });
      setDone(true);
      customToast({ type: 'success', title: t('auth.verifyOtp.emailVerifiedTitle'), message: t('auth.verifyOtp.emailVerifiedMsg') });
      setTimeout(() => navigate('/dashboard'), 2000);
    } catch (err: any) {
      customToast({ type: 'error', title: t('auth.verifyOtp.verificationFailedTitle'), message: err?.message || t('auth.verifyOtp.invalidCodeMsg') });
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (!email) {
      customToast({ type: 'error', title: t('auth.verifyOtp.emailRequiredTitle'), message: t('auth.verifyOtp.emailRequiredMsg') });
      return;
    }
    setResending(true);
    try {
      await authService.resendOtp(email);
      customToast({ type: 'success', title: t('auth.verifyOtp.codeSentTitle'), message: t('auth.verifyOtp.codeSentMsg') });
    } catch (err: any) {
      customToast({ type: 'error', title: t('auth.errorTitle'), message: err?.message || t('auth.verifyOtp.resendFailedMsg') });
    } finally {
      setResending(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('auth.verifyOtp.title')}</h1>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          {done ? t('auth.verifyOtp.accountVerified') : t('auth.verifyOtp.enterCode')}
        </p>
      </div>

      {done ? (
        <div className="space-y-6">
          <div className="flex items-center justify-center h-24 rounded-2xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20">
            <CheckCircle2 className="h-12 w-12 text-emerald-500" />
          </div>
          <p className="text-center text-sm text-gray-500 dark:text-gray-400">{t('auth.redirectingToLogin')}</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          <Input
            label={t('auth.emailAddress')}
            type="email"
            placeholder="you@company.com"
            leftIcon={<Mail className="h-4 w-4" />}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={Boolean(searchParams.get('email'))}
          />
          <Input
            label={t('auth.verifyOtp.codeLabel')}
            placeholder={t('auth.verifyOtp.codePlaceholder')}
            inputMode="numeric"
            maxLength={6}
            leftIcon={<KeyRound className="h-4 w-4" />}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            helperText={t('auth.verifyOtp.codeHelper')}
          />
          <Button type="submit" variant="primary" className="w-full" size="lg" loading={loading} rightIcon={<ArrowRight className="h-4 w-4" />}>
            {t('auth.verifyOtp.verifyBtn')}
          </Button>
          <div className="text-center">
            <button
              type="button"
              onClick={handleResend}
              disabled={resending}
              className="text-sm font-medium text-purple-600 hover:text-purple-700 dark:text-purple-400 disabled:opacity-50"
            >
              {resending ? t('auth.verifyOtp.sending') : t('auth.verifyOtp.resendIt')}
            </button>
          </div>
          <p className="text-center text-sm text-gray-500 dark:text-gray-400">
            <Link to="/auth/login" className="text-purple-600 hover:text-purple-700 dark:text-purple-400 font-medium">{t('auth.backToSignIn')}</Link>
          </p>
        </form>
      )}
    </motion.div>
  );
}
