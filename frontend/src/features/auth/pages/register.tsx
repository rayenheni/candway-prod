// ============================================================
// Register Page - Candway Platform
// ============================================================

import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { motion } from 'framer-motion';
import { useAuth } from '@/contexts/auth-context';
import { useLanguage } from '@/contexts/language-context';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { cn } from '@/utils/cn';
import { Mail, Lock, Eye, EyeOff, User, ArrowRight, Briefcase, GraduationCap, Building2 } from 'lucide-react';
import type { UserRole } from '@/types';

const registerSchema = z.object({
  firstName: z.string().min(1, 'First name is required'),
  lastName: z.string().min(1, 'Last name is required'),
  email: z.string().email('Please enter a valid email'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  role: z.enum(['candidate', 'recruiter']),
});

type RegisterFormData = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const { t } = useLanguage();
  const { register: registerUser, error: authError } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const paramRole = searchParams.get('role') === 'recruiter' ? 'recruiter' : 'candidate';
  const paramEmail = searchParams.get('email') ?? '';
  const redirect = searchParams.get('redirect') || '';
  const safeRedirect =
    redirect.startsWith('/') &&
    !redirect.startsWith('//') &&
    !redirect.includes('\\') &&
    !/^\/\w+:/.test(redirect)
      ? redirect
      : null;

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: { role: paramRole, email: paramEmail },
  });

  const selectedRole = watch('role');

  const onSubmit = async (data: RegisterFormData) => {
    setIsLoading(true);
    try {
      await registerUser({
        ...data,
        role: data.role as UserRole,
      });
      navigate(safeRedirect || '/dashboard');
    } catch (err: any) {
      if (err?.message?.includes('Verification required')) {
        navigate('/auth/verify-otp?email=' + encodeURIComponent(data.email));
        return;
      }
      if (err?.message?.includes('verify') || err?.message?.includes('OTP')) {
        navigate('/auth/verify-otp?email=' + encodeURIComponent(data.email));
        return;
      }
      // Error handled by auth context
    } finally {
      setIsLoading(false);
    }
  };

  const roles = [
    {
      value: 'candidate',
      label: t('auth.lookingForJob'),
      icon: GraduationCap,
      description: t('auth.lookingForJobDesc'),
    },
    {
      value: 'recruiter',
      label: t('auth.hiringTalent'),
      icon: Briefcase,
      description: t('auth.hiringTalentDesc'),
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('auth.createAccount')}</h1>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          {t('auth.startJourney')}
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        {authError && (
          <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
            {authError}
          </div>
        )}
        {/* Role Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            {t('auth.iAmA')}
          </label>
          <div className="grid grid-cols-2 gap-3">
            {roles.map((role) => (
              <button
                key={role.value}
                type="button"
                onClick={() => setValue('role', role.value as 'candidate' | 'recruiter')}
                className={cn(
                  'flex flex-col items-start gap-2 p-4 rounded-xl border-2 transition-all text-left backdrop-blur-sm',
                  selectedRole === role.value
                    ? 'border-purple-600 bg-purple-50/60 dark:bg-purple-500/10 dark:border-purple-400'
                    : 'border-purple-200/50 hover:border-purple-300/70 dark:border-white/10 dark:hover:border-purple-500/30'
                )}
              >
                <role.icon className={cn(
                  'h-5 w-5',
                  selectedRole === role.value ? 'text-purple-600 dark:text-purple-400' : 'text-gray-400'
                )} />
                <div>
                  <div className={cn(
                    'text-sm font-medium',
                    selectedRole === role.value ? 'text-purple-700 dark:text-purple-400' : 'text-gray-700 dark:text-gray-300'
                  )}>
                    {role.label}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    {role.description}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        <button
          type="button"
          onClick={() => navigate('/auth/register-company')}
          className="w-full flex flex-col items-start gap-2 p-4 rounded-xl border-2 border-dashed border-purple-300/60 dark:border-white/15 text-left transition-all hover:border-purple-500/70"
        >
          <div className="flex items-center gap-2 text-sm font-medium text-purple-700 dark:text-purple-400">
            <Building2 className="h-5 w-5" />
            {t('auth.register.myCompany')}
            <ArrowRight className="h-4 w-4 ml-auto" />
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {t('auth.register.myCompanyDesc')}
          </div>
        </button>

        <div className="grid grid-cols-2 gap-3">
          <Input
            label={t('auth.firstName')}
            placeholder="John"
            leftIcon={<User className="h-4 w-4" />}
            error={errors.firstName?.message}
            {...register('firstName')}
          />
          <Input
            label={t('auth.lastName')}
            placeholder="Doe"
            error={errors.lastName?.message}
            {...register('lastName')}
          />
        </div>

        <Input
          label={t('auth.emailAddress')}
          type="email"
          placeholder="you@company.com"
          leftIcon={<Mail className="h-4 w-4" />}
          error={errors.email?.message}
          {...register('email')}
        />

        <Input
          label={t('common.password')}
          type={showPassword ? 'text' : 'password'}
          placeholder={t('auth.createStrongPassword')}
          leftIcon={<Lock className="h-4 w-4" />}
          rightIcon={
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          }
          helperText={t('auth.min8chars')}
          error={errors.password?.message}
          {...register('password')}
        />

        <Button
          type="submit"
          variant="primary"
          className="w-full"
          size="lg"
          loading={isLoading}
          rightIcon={<ArrowRight className="h-4 w-4" />}
        >
          {t('auth.register.submit')}
        </Button>

        <p className="text-xs text-center text-gray-500 dark:text-gray-400">
          {t('auth.byRegister')}{' '}
          <Link to="/terms" className="text-blue-600 hover:underline dark:text-blue-400">{t('auth.terms')}</Link>
          {' '}{t('auth.and')}{' '}
          <Link to="/privacy" className="text-blue-600 hover:underline dark:text-blue-400">{t('auth.privacy')}</Link>
        </p>
      </form>

      <p className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
        {t('auth.haveAccount')}{' '}
        <Link
          to="/auth/login"
          className="font-medium text-purple-600 hover:text-purple-700 dark:text-purple-400"
        >
          {t('auth.signIn')}
        </Link>
      </p>
    </motion.div>
  );
}
