import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { customToast } from '@/shared/components/ui/toast';
import { subscriptionService } from '@/services/subscription.service';
import CreditPricing, { type CreditPricingMap } from '@/shared/components/credit-pricing';
import { useLanguage } from '@/contexts/language-context';
import {
  CheckCircle2, Crown, Sparkles, Loader2, X, Building2, AlertCircle, Clock, TrendingUp, Coins,
} from 'lucide-react';
import { cn } from '@/utils/cn';

// ─── Types ────────────────────────────────────────────────────────────────────

interface SubscriptionStatus {
  tier: string;
  status: string;
  plan_name: string;
  plan_slug: string;
  expiry: string | null;
  managed_by_company?: boolean;
  rejection_reason?: string | null;
  rejected_at?: string | null;
  credit_balance: number;
  company_credit_balance?: number | null;
  company_name?: string | null;
  credit_pricing?: CreditPricingMap;
  usage: { jobs: number; cvs: number; ai_interviews: number };
  limits: { job_limit: number; cv_limit: number; ai_interview_limit: number; team_seat_limit: number };
}

// ─── Usage bar ────────────────────────────────────────────────────────────────
function UsageBar({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const color = pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-amber-500' : 'bg-violet-500';
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>{label}</span>
        <span className="font-semibold">{used} / {limit === -1 ? '∞' : limit}</span>
      </div>
      <div className="h-1.5 bg-gray-100 dark:bg-white/10 rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full transition-all duration-500', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function BillingPage() {
  const { t } = useLanguage();
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    subscriptionService.getStatus()
      .then(s => setStatus(s as SubscriptionStatus))
      .catch((err: any) => {
        customToast({ type: 'error', title: t('common.status'), message: err?.message || 'Failed to load quota.' });
      })
      .finally(() => setLoading(false));
  }, [t]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  const currentPlanName = status?.plan_name ?? t('recruiter.billing.freeTier');
  const isPending = status?.status === 'pending_approval';
  const isRejected = status?.status === 'rejected';
  const isCompanyManaged = status?.managed_by_company === true;

  const personalQuota = status?.credit_balance ?? 0;
  const companyQuota = status?.company_credit_balance ?? null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('nav.billing')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {t('recruiter.billing.managedByCompanyDesc')}
          </p>
        </div>
        {isPending && (
          <Badge variant="warning" size="lg" dot className="font-semibold">
            <Clock className="h-3.5 w-3.5 mr-1" />
            {t('recruiter.billing.pendingUpgrade')}
          </Badge>
        )}
        {isRejected && (
          <Badge variant="danger" size="lg" dot className="font-semibold">
            <X className="h-3.5 w-3.5 mr-1" />
            {t('recruiter.billing.rejectedUpgrade')}
          </Badge>
        )}
      </div>

      {isRejected && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 dark:bg-red-500/10 dark:border-red-500/20 px-4 py-3">
          <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
          <div className="text-sm text-red-900 dark:text-red-200">
            <p className="font-semibold">{t('recruiter.billing.rejectedMsg')}</p>
            {status?.rejection_reason ? (
              <p className="mt-0.5 text-red-700/80 dark:text-red-300/70">
                {t('recruiter.billing.rejectedReason')} <strong>{status.rejection_reason}</strong>
              </p>
            ) : (
              <p className="mt-0.5 text-red-700/80 dark:text-red-300/70">
                {t('recruiter.billing.rejectedContact')} <a className="underline" href="mailto:hello@candway.com">hello@candway.com</a>{t('recruiter.billing.rejectedContactDetails')}
              </p>
            )}
          </div>
        </div>
      )}

      {isCompanyManaged && (
        <div className="flex items-start gap-3 rounded-xl border border-purple-200 bg-purple-50 dark:bg-purple-500/10 dark:border-purple-500/20 px-4 py-3">
          <Building2 className="h-5 w-5 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5" />
          <div className="text-sm text-purple-900 dark:text-purple-200">
            <p className="font-semibold">{t('recruiter.billing.managedByCompany')}</p>
            <p className="mt-0.5 text-purple-700/80 dark:text-purple-300/70">
              {t('recruiter.billing.managedByCompanyDesc')}
            </p>
          </div>
        </div>
      )}

      {/* Current Plan Card */}
      <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <CardTitle>{t('recruiter.billing.currentPlan')}</CardTitle>
              <CardDescription>{t('recruiter.billing.currentPlanDesc')}</CardDescription>
            </div>
            <Badge
              variant={status?.status === 'active' ? 'success' : status?.status === 'pending_approval' ? 'warning' : status?.status === 'rejected' ? 'danger' : 'default'}
              size="lg"
              dot
              className="font-bold uppercase text-[10px]"
            >
              {status?.status === 'pending_approval' ? t('recruiter.billing.pendingApproval') : status?.status === 'active' ? t('recruiter.billing.active') : status?.status ?? t('recruiter.billing.active')}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-purple-600 to-violet-600 text-white shadow-lg shadow-purple-500/25">
                <Crown className="h-7 w-7" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-black text-gray-900 dark:text-white">{currentPlanName}</h2>
                  <Badge variant="primary" size="sm"><Sparkles className="h-3 w-3 mr-0.5" />{t('recruiter.billing.aiEnabled')}</Badge>
                </div>
                {status?.expiry && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    {t('recruiter.billing.validUntil')} <span className="font-semibold text-gray-600 dark:text-gray-300">{status.expiry}</span>
                  </p>
                )}
              </div>
            </div>
            {/* Usage summary */}
            {status?.usage && status?.limits && (
              <div className="flex-1 max-w-xs space-y-2">
                <p className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider flex items-center gap-1">
                  <TrendingUp className="h-3.5 w-3.5" /> {t('recruiter.billing.thisMonthUsage')}
                </p>
                <UsageBar label={t('recruiter.billing.jobsPosted')} used={status.usage.jobs} limit={status.limits.job_limit} />
                <UsageBar label={t('recruiter.billing.cvAnalyses')} used={status.usage.cvs} limit={status.limits.cv_limit} />
                <UsageBar label={t('recruiter.billing.aiInterviews')} used={status.usage.ai_interviews} limit={status.limits.ai_interview_limit} />
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* AI Credits — My Quota */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider flex items-center gap-1">
                  <Coins className="h-3.5 w-3.5" /> {t('topbar.credits')}
                </p>
                <p className="mt-2 text-4xl font-black text-gray-900 dark:text-white">{personalQuota}</p>
                <p className="text-xs text-gray-400 mt-1">{t('recruiter.billing.currentPlanDesc')}</p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-500">
                <CheckCircle2 className="h-5 w-5" />
              </div>
            </div>
          </CardContent>
        </Card>

        {isCompanyManaged && companyQuota !== null ? (
          <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
            <CardContent className="pt-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider flex items-center gap-1">
                    <Building2 className="h-3.5 w-3.5" /> {t('role.company')} {t('topbar.credits')}
                  </p>
                  <p className="mt-2 text-4xl font-black text-gray-900 dark:text-white">{companyQuota}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    {status?.company_name || t('role.company')}
                  </p>
                </div>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 text-purple-500">
                  <Building2 className="h-5 w-5" />
                </div>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card className="glass-panel border-gray-200/50 dark:border-white/10">
            <CardContent className="pt-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider flex items-center gap-1">
                    <Building2 className="h-3.5 w-3.5" /> {t('role.company')} {t('topbar.credits')}
                  </p>
                  <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                    {t('recruiter.billing.managedByCompany')}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">{t('recruiter.billing.managedByCompanyDesc')}</p>
                </div>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-500/10 text-gray-500">
                  <Building2 className="h-5 w-5" />
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Credit pricing — admin-controlled */}
      <CreditPricing
        pricing={status?.credit_pricing}
        title={t('topbar.credits')}
        description={t('recruiter.billing.currentPlanDesc')}
      />

      {/* Billing ownership note */}
      <div className="flex items-start gap-3 rounded-xl border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-white/[0.02] px-4 py-3">
        <AlertCircle className="h-5 w-5 text-gray-500 dark:text-gray-400 shrink-0 mt-0.5" />
        <div className="text-sm text-gray-600 dark:text-gray-400">
          <p className="font-semibold text-gray-800 dark:text-gray-200">{t('recruiter.billing.managedByCompany')}</p>
          <p className="mt-0.5">
            {t('recruiter.billing.managedByCompanyDesc')}
          </p>
        </div>
      </div>
    </div>
  );
}