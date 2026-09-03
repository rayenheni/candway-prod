import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { motion } from 'framer-motion';
import { authService } from '@/services/auth.service';
import { useLanguage } from '@/contexts/language-context';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { customToast } from '@/shared/components/ui/toast';
import { Lock, Eye, EyeOff, CheckCircle2 } from 'lucide-react';

export default function ResetPasswordPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [showPwd, setShowPwd] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      customToast({ type: 'error', title: t('auth.reset.mismatchTitle'), message: t('auth.reset.mismatchMsg') });
      return;
    }
    if (!token) {
      customToast({ type: 'error', title: t('auth.reset.invalidTokenTitle'), message: t('auth.reset.missingTokenMsg') });
      return;
    }
    setLoading(true);
    try {
      await authService.resetPassword({ token, password });
      setDone(true);
      customToast({ type: 'success', title: t('auth.reset.successTitle'), message: t('auth.reset.successMsg') });
      setTimeout(() => navigate('/auth/login'), 2000);
    } catch (err: any) {
      customToast({ type: 'error', title: t('auth.errorTitle'), message: err?.message || t('auth.reset.failedMsg') });
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('auth.resetPassword')}</h1>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">{t('auth.reset.enterNewPassword')}</p>
      </div>

      {done ? (
        <div className="space-y-6">
          <div className="flex items-center justify-center h-24 rounded-2xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20">
            <CheckCircle2 className="h-12 w-12 text-emerald-500" />
          </div>
          <p className="text-center text-sm text-gray-500">{t('auth.redirectingToLogin')}</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          <Input label={t('auth.newPassword')} type={showPwd ? 'text' : 'password'} leftIcon={<Lock className="h-4 w-4" />}
            rightIcon={<button type="button" onClick={() => setShowPwd(!showPwd)}>{showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button>}
            value={password} onChange={(e) => setPassword(e.target.value)} helperText={t('auth.min8chars')} />
          <Input label={t('auth.confirmPassword')} type={showConfirm ? 'text' : 'password'} leftIcon={<Lock className="h-4 w-4" />}
            rightIcon={<button type="button" onClick={() => setShowConfirm(!showConfirm)}>{showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button>}
            value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          <Button type="submit" variant="primary" className="w-full" size="lg" loading={loading}>{t('auth.resetPassword')}</Button>
          <p className="text-center text-sm text-gray-500">
            <Link to="/auth/login" className="text-purple-600 hover:text-purple-700 dark:text-purple-400 font-medium">{t('auth.backToSignIn')}</Link>
          </p>
        </form>
      )}
    </motion.div>
  );
}