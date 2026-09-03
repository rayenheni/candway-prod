import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { motion } from 'framer-motion';
import { publicService, type PublicPlan } from '@/services/public.service';
import { Check, Zap } from 'lucide-react';
import { cn } from '@/utils/cn';
import { useLanguage } from '@/contexts/language-context';


const FALLBACK_PLANS: Array<{
  name: string; monthly: number; yearly: number; slug: string; audience: string; features: string[];
}> = [
  {
    name: 'Free', slug: 'free', audience: 'candidate', monthly: 0, yearly: 0,
    features: ['CV review', 'Apply to jobs', 'Basic AI analysis', 'Community access'],
  },
  {
    name: 'Candidate Pro', slug: 'candidate-pro', audience: 'candidate', monthly: 29, yearly: 0,
    features: ['Advanced CV analysis', 'Career roadmap', 'Priority support', 'Interview practice'],
  },
  {
    name: 'Candidate Premium', slug: 'candidate-premium', audience: 'candidate', monthly: 49, yearly: 0,
    features: ['Everything in Pro', 'Unlimited CV analyses', 'AI interview practice', 'Priority support'],
  },
  {
    name: 'Recruiter Starter', slug: 'recruiter-starter', audience: 'recruiter', monthly: 49, yearly: 0,
    features: ['3 active jobs', 'AI candidate ranking', 'Basic analytics', '1 seat'],
  },
  {
    name: 'Recruiter Professional', slug: 'recruiter-professional', audience: 'recruiter', monthly: 149, yearly: 0,
    features: ['Unlimited jobs', 'Ghost reports', 'AI interviews', '5 seats', 'Bias analytics'],
  },
  {
    name: 'Recruiter Enterprise', slug: 'recruiter-enterprise', audience: 'recruiter', monthly: 499, yearly: 0,
    features: ['Everything in Professional', 'Custom integrations', 'Dedicated CSM', 'Unlimited seats', 'SSO & audit'],
  },
];

export default function PricingPage() {
  const { t } = useLanguage();
  const [cycle, setCycle] = useState<'monthly' | 'yearly'>('yearly');
  const [plans, setPlans] = useState<PublicPlan[]>([]);

  useEffect(() => {
    document.title = t('marketing.pricing.documentTitle');
    publicService
      .getPlans()
      .then(setPlans)
      .catch(() => setPlans([]));
  }, []);

  const planPrice = (monthly: number, yearly: number) => {
    if (cycle === 'monthly') return monthly;
    return yearly || monthly * 12 * 0.9;
  };

  const featured = (slug: string) => slug.includes('professional');

  return (
    <div>
      <div className="text-center mb-12">
        <div className="inline-flex items-center gap-2 rounded-full bg-purple-500/10 border border-purple-500/20 px-4 py-1.5 text-xs font-semibold text-purple-600 dark:text-purple-300 mb-6">
          <Zap className="h-3.5 w-3.5" /> {t('marketing.pricing.badge')}
        </div>
        <h1 className="text-4xl md:text-5xl font-black tracking-tight text-gray-950 dark:text-white">
          {t('marketing.pricing.title1')} <span className="bg-gradient-to-r from-purple-600 to-indigo-500 bg-clip-text text-transparent">{t('marketing.pricing.title2')}</span>
        </h1>
        <p className="mt-4 text-lg text-gray-500 dark:text-slate-400 max-w-2xl mx-auto">
          {t('marketing.pricing.subtitle')}
        </p>

        <div className="mt-8 inline-flex items-center rounded-full border border-purple-200/60 dark:border-white/10 p-1.5 bg-white/70 dark:bg-white/5 backdrop-blur-sm">
          <button
            onClick={() => setCycle('monthly')}
            className={cn('rounded-full px-6 py-2 text-sm font-semibold transition-all', cycle === 'monthly' ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg shadow-purple-500/30' : 'text-gray-600 dark:text-slate-300')}
          >
            {t('landing.monthly')}
          </button>
          <button
            onClick={() => setCycle('yearly')}
            className={cn('rounded-full px-6 py-2 text-sm font-semibold transition-all', cycle === 'yearly' ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg shadow-purple-500/30' : 'text-gray-600 dark:text-slate-300')}
          >
            {t('landing.annually')} <span className="ml-1 text-xs opacity-80">-10%</span>
          </button>
        </div>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {(plans.length > 0 ? plans : FALLBACK_PLANS).map((plan, idx) => {
          const slug = typeof plan.slug === 'string' ? plan.slug : '';
          const monthly = typeof (plan as any).price_monthly === 'number' ? (plan as any).price_monthly : (plan as any).monthly || 0;
          const yearly = typeof (plan as any).price_yearly === 'number' ? (plan as any).price_yearly : (plan as any).yearly || 0;
          const name = typeof plan.name === 'string' ? plan.name : (plan as any).name;
          const features = Array.isArray((plan as any).features) ? (plan as any).features : FALLBACK_PLANS[idx]?.features || [];
          const isFeatured = featured(slug);
          return (
            <motion.div
              key={slug || idx}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: idx * 0.08 }}
              className={cn(
                'relative rounded-3xl border p-7 flex flex-col transition-all hover:-translate-y-1',
                isFeatured
                  ? 'border-purple-500/50 bg-gradient-to-b from-purple-600/10 to-indigo-600/5 shadow-2xl shadow-purple-500/20'
                  : 'border-purple-200/50 dark:border-white/10 bg-white/70 dark:bg-white/5 backdrop-blur-sm'
              )}
            >
              {isFeatured && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-1 text-xs font-bold text-white shadow-lg shadow-purple-500/30">
                  {t('marketing.pricing.mostPopular')}
                </span>
              )}
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">{name}</h3>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-4xl font-black text-gray-950 dark:text-white">
                  {planPrice(monthly, yearly) === 0 ? t('marketing.pricing.free') : `${planPrice(monthly, yearly).toLocaleString()} TND`}
                </span>
                {planPrice(monthly, yearly) !== 0 && <span className="text-sm text-gray-500">/{cycle === 'yearly' ? t('marketing.pricing.yr') : t('marketing.pricing.mo')}</span>}
              </div>
              <ul className="mt-6 space-y-3 flex-1">
                {features.map((feature: string, i: number) => (
                  <li key={i} className="flex items-start gap-2.5 text-sm text-gray-600 dark:text-slate-300">
                    <span className={cn('mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full', isFeatured ? 'bg-purple-600/20 text-purple-600 dark:text-purple-300' : 'bg-emerald-500/15 text-emerald-600')}>
                      <Check className="h-3 w-3" />
                    </span>
                    {feature}
                  </li>
                ))}
              </ul>
              <Link
                to={`/auth/register${slug.includes('recruiter') ? '?role=recruiter' : ''}`}
                className={cn(
                  'mt-8 rounded-full py-3 text-center text-sm font-semibold transition-all',
                  isFeatured
                    ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg shadow-purple-500/30 hover:shadow-purple-500/50'
                    : 'border border-purple-300/60 dark:border-white/15 text-purple-700 dark:text-purple-300 hover:bg-purple-50 dark:hover:bg-white/5'
                )}
              >
                {t('auth.getStarted')}
              </Link>
            </motion.div>
          );
        })}
      </div>

      <p className="mt-12 text-center text-sm text-gray-500 dark:text-slate-400">
        {t('marketing.pricing.customPlan')} <Link to="/auth/register?role=recruiter" className="text-purple-600 hover:text-purple-700 dark:text-purple-400 font-medium">{t('marketing.pricing.contactSales')}</Link>
      </p>
    </div>
  );
}
