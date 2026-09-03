import { useState } from 'react';
import { Link } from 'react-router';
import { motion } from 'framer-motion';
import { authService } from '@/services/auth.service';
import { useLanguage } from '@/contexts/language-context';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { customToast } from '@/shared/components/ui/toast';
import { Mail, ArrowLeft, CheckCircle2 } from 'lucide-react';

export default function ForgotPasswordPage() {
  const { t } = useLanguage();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setLoading(true);
    try {
      await authService.forgotPassword(email);
      setSent(true);
      customToast({ type: 'success', title: t('auth.forgot.resetLinkSent'), message: t('auth.checkInbox') });
    } catch (err: any) {
      customToast({ type: 'error', title: t('auth.errorTitle'), message: err?.message || t('auth.forgot.sendFailed') });
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('auth.forgot.title')}</h1>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          {sent ? t('auth.checkInbox') : t('auth.enterEmailForReset')}
        </p>
      </div>

      {sent ? (
        <div className="space-y-6">
          <div className="flex items-center justify-center h-24 rounded-2xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20">
            <CheckCircle2 className="h-12 w-12 text-emerald-500" />
          </div>
          <Link to="/auth/login"><Button variant="primary" className="w-full" size="lg" leftIcon={<ArrowLeft className="h-4 w-4" />}>{t('auth.backToLogin')}</Button></Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          <Input label={t('auth.emailAddress')} type="email" placeholder="you@company.com" leftIcon={<Mail className="h-4 w-4" />} value={email} onChange={(e) => setEmail(e.target.value)} />
          <Button type="submit" variant="primary" className="w-full" size="lg" loading={loading}>{t('auth.sendResetLink')}</Button>
          <p className="text-center text-sm text-gray-500">
            <Link to="/auth/login" className="text-purple-600 hover:text-purple-700 dark:text-purple-400 font-medium">{t('auth.backToSignIn')}</Link>
          </p>
        </form>
      )}
    </motion.div>
  );
}