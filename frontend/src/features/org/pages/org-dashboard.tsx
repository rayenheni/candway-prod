import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { useLanguage } from '@/contexts/language-context';
import { cn } from '@/utils/cn';
import {
  Briefcase, Users, UserCheck, BarChart3, Loader2, Plus, ArrowRight, DollarSign, Cpu,
} from 'lucide-react';
import { orgService, type OrgOverview } from '@/services/org.service';
import { customToast } from '@/shared/components/ui/toast';

export default function OrgDashboard() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [data, setData] = useState<OrgOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    orgService.getOverview()
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => { if (!cancelled) customToast({ type: 'error', title: t('common.status') }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [t]);

  const statCards = [
    { label: t('org.members'), value: data?.recruiters ?? '—', icon: Users, color: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400' },
    { label: t('nav.jobs'), value: data?.total_jobs ?? '—', icon: Briefcase, color: 'bg-purple-50 text-purple-600 dark:bg-purple-500/10 dark:text-purple-400' },
    { label: t('candidates.candidatesLabel'), value: data?.total_applications ?? '—', icon: UserCheck, color: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400' },
    { label: t('org.hired'), value: data?.hired ?? '—', icon: BarChart3, color: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400' },
  ];

  const funnel = data?.funnel ?? { applied: 0, screening: 0, interview: 0, offer: 0, hired: 0 };
  const pipelineStages = [
    { name: t('org.applied'), count: funnel.applied, color: 'bg-gray-500' },
    { name: t('org.screening'), count: funnel.screening, color: 'bg-blue-500' },
    { name: t('org.interview'), count: funnel.interview, color: 'bg-purple-500' },
    { name: t('org.offer'), count: funnel.offer, color: 'bg-amber-500' },
    { name: t('org.hired'), count: funnel.hired, color: 'bg-emerald-500' },
  ];
  const maxFunnel = Math.max(...pipelineStages.map((s) => s.count), 1);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('org.overviewTitle')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {t('org.overviewSubtitle')}
          </p>
        </div>
        <Button id="org-add-member-btn" variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => navigate('/org/members')}>{t('org.members')}</Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-purple-600" /></div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {statCards.map((stat, i) => (
              <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.05 }}>
                <Card hoverable>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.color)}><stat.icon className="h-5 w-5" /></div>
                    </div>
                    <div className="mt-4">
                      <div className="text-2xl font-bold text-gray-900 dark:text-white">{stat.value}</div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">{stat.label}</div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2">
              <CardContent>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{t('org.recruiterPerformance')}</h3>
                  <button className="text-sm text-purple-600 dark:text-purple-400 font-medium flex items-center gap-1" onClick={() => navigate('/org/analytics')}>
                    {t('nav.analytics')} <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                </div>
                {!data?.recruiter_kpis?.length ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400 py-8 text-center">{t('common.noData')}</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                          <th className="py-2 font-medium">{t('role.recruiter')}</th>
                          <th className="py-2 font-medium text-right">{t('nav.jobs')}</th>
                          <th className="py-2 font-medium text-right">{t('candidates.candidatesLabel')}</th>
                          <th className="py-2 font-medium text-right">{t('nav.interviews')}</th>
                          <th className="py-2 font-medium text-right">{t('org.hired')}</th>
                          <th className="py-2 font-medium text-right">{t('candidates.col.score')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.recruiter_kpis.map((r) => (
                          <tr key={r.user_id} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer" onClick={() => navigate(`/org/analytics/${r.user_id}`)}>
                            <td className="py-3">
                              <div className="font-medium text-gray-900 dark:text-white">{r.name || '—'}</div>
                              <div className="text-xs text-gray-400">{r.email}</div>
                            </td>
                            <td className="py-3 text-right">{r.active_jobs}</td>
                            <td className="py-3 text-right">{r.total_applications}</td>
                            <td className="py-3 text-right">{r.interviews?.total ?? 0}</td>
                            <td className="py-3 text-right">{r.hired}</td>
                            <td className="py-3 text-right">{r.avg_score || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">{t('org.companyPipeline')}</h3>
                <div className="space-y-3">
                  {pipelineStages.map((stage) => (
                    <div key={stage.name} className="flex items-center gap-3">
                      <span className="w-20 text-sm text-gray-500 dark:text-gray-400">{stage.name}</span>
                      <div className="flex-1 h-2 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
                        <div className={cn('h-full rounded-full transition-all duration-500', stage.color)} style={{ width: `${(stage.count / maxFunnel) * 100}%` }} />
                      </div>
                      <span className="text-sm font-semibold text-gray-900 dark:text-white">{stage.count}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-6 grid grid-cols-2 gap-3">
                  <div className="rounded-xl bg-gray-50 dark:bg-gray-800/60 p-3">
                    <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400"><DollarSign className="h-3.5 w-3.5" /> AI Cost</div>
                    <div className="mt-1 text-lg font-bold text-gray-900 dark:text-white">${(data?.ai?.cost_usd ?? 0).toFixed(2)}</div>
                  </div>
                  <div className="rounded-xl bg-gray-50 dark:bg-gray-800/60 p-3">
                    <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400"><Cpu className="h-3.5 w-3.5" /> AI Calls</div>
                    <div className="mt-1 text-lg font-bold text-gray-900 dark:text-white">{data?.ai?.calls ?? 0}</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
