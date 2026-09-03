// ============================================================
// Register Company Page (Wizard) - Candway Platform
// Company-first signup: register the company (with billing/KYB
// details) first; recruiters join later via org invite only.
// ============================================================

import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { AnimatePresence, motion } from 'framer-motion';
import { authService } from '@/services/auth.service';
import { orgService } from '@/services/org.service';
import { useLanguage } from '@/contexts/language-context';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Progress } from '@/shared/components/ui/progress';
import { customToast } from '@/shared/components/ui/toast';
import {
  Mail, Lock, Eye, EyeOff, ArrowRight, ArrowLeft, Building2, UploadCloud, X, FileText, UserRound, CreditCard,
} from 'lucide-react';
import { cn } from '@/utils/cn';

const companySchema = z.object({
  companyName: z.string().min(2, 'Company name is required'),
  adminName: z.string().min(1, 'Admin name is required'),
  adminEmail: z.string().email('Please enter a valid email'),
  adminPassword: z.string().min(8, 'Password must be at least 8 characters'),
  billingEmail: z.string().email('Please enter a valid billing email').optional().or(z.literal('')),
  billingAddress: z.string().optional(),
  taxId: z.string().optional(),
});

type CompanyFormData = z.infer<typeof companySchema>;

const ACCEPTED = ['application/pdf', 'image/png', 'image/jpeg'];

const STEPS = [
  { key: 'company', title: 'Company details', subtitle: 'Tell us about your business', icon: Building2 },
  { key: 'admin', title: 'Admin account', subtitle: 'Who will manage the company', icon: UserRound },
  { key: 'billing', title: 'Billing & documents', subtitle: 'Verification details (optional)', icon: CreditCard },
];

const STEP_FIELDS: Array<Array<keyof CompanyFormData>> = [
  ['companyName'],
  ['adminName', 'adminEmail', 'adminPassword'],
  ['billingEmail', 'billingAddress', 'taxId'],
];

export default function RegisterCompanyPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    register,
    handleSubmit,
    trigger,
    formState: { errors },
  } = useForm<CompanyFormData>({
    resolver: zodResolver(companySchema),
    mode: 'onTouched',
  });

  const addFiles = (list: FileList | null) => {
    setUploadError(null);
    if (!list) return;
    const next = [...files];
    for (const file of Array.from(list)) {
      if (next.length >= 6) {
        setUploadError(t('auth.registerCompany.maxDocs'));
        break;
      }
      if (!ACCEPTED.includes(file.type)) {
        setUploadError(`${t('auth.registerCompany.unsupportedFileType')}${file.name}${t('auth.registerCompany.acceptedFormats')}`);
        continue;
      }
      if (file.size > 5 * 1024 * 1024) {
        setUploadError(`${t('auth.registerCompany.fileTooLarge')}${file.name}`);
        continue;
      }
      next.push(file);
    }
    setFiles(next);
  };

  const nextStep = async () => {
    const valid = await trigger(STEP_FIELDS[step]);
    if (valid) setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const onSubmit = async (data: CompanyFormData) => {
    setIsLoading(true);
    setUploadError(null);
    try {
      const res = await authService.registerOrg({
        companyName: data.companyName,
        adminName: data.adminName,
        adminEmail: data.adminEmail,
        adminPassword: data.adminPassword,
        billingEmail: data.billingEmail || undefined,
        billingAddress: data.billingAddress || undefined,
        taxId: data.taxId || undefined,
      });

      if (files.length > 0) {
        try {
          await orgService.uploadKybDocuments(files);
        } catch {
          customToast({
            type: 'warning',
            title: t('auth.registerCompany.kybPendingTitle'),
            message: t('auth.registerCompany.kybPendingMsg'),
          });
        }
      }

      customToast({
        type: 'success',
        title: t('auth.registerCompany.createdTitle'),
        message: t('auth.registerCompany.createdMsg').replace('{name}', data.companyName),
      });

      if (res.email_verification_required) {
        navigate('/auth/verify-otp?email=' + encodeURIComponent(data.adminEmail));
      } else {
        navigate('/org/dashboard');
      }
    } catch (err: any) {
      const msg = err?.message || t('auth.registerCompany.regFailedMsg');
      setUploadError(msg);
      customToast({ type: 'error', title: t('auth.registerCompany.regFailedTitle'), message: msg });
    } finally {
      setIsLoading(false);
    }
  };

  const isLastStep = step === STEPS.length - 1;
  const CurrentIcon = STEPS[step].icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('auth.registerCompany.title')}</h1>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          {t('auth.registerCompany.subtitle')}
        </p>
      </div>

      {/* Step header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-purple-100 dark:bg-purple-500/15 text-purple-600 dark:text-purple-400">
              <CurrentIcon className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-semibold text-gray-900 dark:text-white">
                {STEPS[step].title}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                {STEPS[step].subtitle}
              </div>
            </div>
          </div>
          <span className="text-xs font-medium text-gray-400">
            {t('auth.registerCompany.step')} {step + 1} {t('common.of')} {STEPS.length}
          </span>
        </div>
        <Progress value={step + 1} max={STEPS.length} size="sm" />
        <div className="mt-3 flex items-center gap-2">
          {STEPS.map((s, i) => (
            <button
              key={s.key}
              type="button"
              onClick={() => i < step && setStep(i)}
              className={cn(
                'flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors',
                i === step
                  ? 'bg-purple-600 text-white'
                  : i < step
                    ? 'bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-300 hover:bg-purple-200'
                    : 'bg-gray-100 text-gray-400 dark:bg-white/5 dark:text-gray-500'
              )}
            >
              <span>{i + 1}</span>
              <span className="hidden sm:inline">{s.title}</span>
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        {uploadError && (
          <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
            {uploadError}
          </div>
        )}

        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -24 }}
            transition={{ duration: 0.2 }}
            className="space-y-5"
          >
            {step === 0 && (
              <div className="rounded-xl border border-purple-200/60 dark:border-white/10 p-4 space-y-4">
                <Input
                  label={t('auth.registerCompany.companyName')}
                  placeholder="Acme Corp"
                  leftIcon={<Building2 className="h-4 w-4" />}
                  error={errors.companyName?.message}
                  {...register('companyName')}
                />
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t('auth.registerCompany.companyHint')}
                </p>
              </div>
            )}

            {step === 1 && (
              <div className="rounded-xl border border-purple-200/60 dark:border-white/10 p-4 space-y-4">
                <Input
                  label={t('auth.registerCompany.adminName')}
                  placeholder="Jane Doe"
                  leftIcon={<UserRound className="h-4 w-4" />}
                  error={errors.adminName?.message}
                  {...register('adminName')}
                />
                <Input
                  label={t('auth.registerCompany.adminEmail')}
                  type="email"
                  placeholder="admin@company.com"
                  leftIcon={<Mail className="h-4 w-4" />}
                  error={errors.adminEmail?.message}
                  {...register('adminEmail')}
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
                  error={errors.adminPassword?.message}
                  {...register('adminPassword')}
                />
              </div>
            )}

            {step === 2 && (
              <div className="rounded-xl border border-purple-200/60 dark:border-white/10 p-4 space-y-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-purple-700 dark:text-purple-400">
                  <CreditCard className="h-4 w-4" /> {t('auth.registerCompany.billingDetails')}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Input
                    label={t('auth.registerCompany.billingEmail')}
                    type="email"
                    placeholder="billing@company.com"
                    error={errors.billingEmail?.message}
                    {...register('billingEmail')}
                  />
                  <Input
                    label={t('auth.registerCompany.taxId')}
                    placeholder={t('auth.registerCompany.taxIdPlaceholder')}
                    error={errors.taxId?.message}
                    {...register('taxId')}
                  />
                </div>
                <Input
                  label={t('auth.registerCompany.billingAddress')}
                  placeholder={t('auth.registerCompany.billingAddressPlaceholder')}
                  error={errors.billingAddress?.message}
                  {...register('billingAddress')}
                />

                <div>
                  <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    {t('auth.registerCompany.documentsLabel')}
                  </span>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="w-full rounded-xl border-2 border-dashed border-purple-300/60 dark:border-white/15 p-6 flex flex-col items-center gap-2 text-sm text-gray-500 dark:text-gray-400 hover:border-purple-500/70 transition-colors"
                  >
                    <UploadCloud className="h-6 w-6 text-purple-500" />
                    <span>{t('auth.registerCompany.uploadHint')}</span>
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.png,.jpg,.jpeg"
                    className="hidden"
                    onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }}
                  />
                  {files.length > 0 && (
                    <ul className="mt-3 space-y-2">
                      {files.map((file, idx) => (
                        <li
                          key={`${file.name}-${idx}`}
                          className="flex items-center justify-between rounded-lg border border-gray-200 dark:border-white/10 px-3 py-2 text-sm"
                        >
                          <span className="flex items-center gap-2 text-gray-700 dark:text-gray-300">
                            <FileText className="h-4 w-4 text-purple-500" />
                            {file.name}
                            <span className="text-xs text-gray-400">({Math.round(file.size / 1024)} KB)</span>
                          </span>
                          <button
                            type="button"
                            onClick={() => setFiles(files.filter((_, i) => i !== idx))}
                            className="text-gray-400 hover:text-red-500"
                            aria-label={`${t('auth.registerCompany.removeFile')} ${file.name}`}
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        {/* Wizard navigation */}
        <div className="flex items-center gap-3 pt-2">
          {step > 0 && (
            <Button
              type="button"
              variant="outline"
              onClick={() => setStep((s) => Math.max(s - 1, 0))}
              leftIcon={<ArrowLeft className="h-4 w-4" />}
              disabled={isLoading}
            >
              {t('common.back')}
            </Button>
          )}
          <Button
            type={isLastStep ? 'submit' : 'button'}
            variant="primary"
            className="flex-1"
            size="lg"
            loading={isLoading}
            rightIcon={isLastStep ? <Building2 className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />}
            onClick={isLastStep ? undefined : nextStep}
          >
            {isLastStep ? t('auth.registerCompany.createCompany') : t('common.continue')}
          </Button>
        </div>

        <p className="text-xs text-center text-gray-500 dark:text-gray-400">
          {t('auth.registerCompany.individualPrompt')}{' '}
          <Link
            to="/auth/register"
            className="font-medium text-purple-600 hover:text-purple-700 dark:text-purple-400"
          >
            {t('auth.registerCompany.personalAccount')}
          </Link>
        </p>
      </form>

      <p className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
        {t('auth.registerCompany.haveCompanyAccount')}{' '}
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
