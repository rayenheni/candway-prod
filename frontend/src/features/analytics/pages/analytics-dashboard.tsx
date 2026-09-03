import { useState } from 'react';
import { motion } from 'framer-motion';
import { useLanguage } from '@/contexts/language-context';
import { useAnalyticsDashboard } from '@/shared/hooks';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import { Download, ArrowUpRight, ArrowDownRight, BarChart3, MapPin, Loader2 } from 'lucide-react';
import { analyticsService } from '@/services/analytics.service';

export default function AnalyticsDashboard() {
  const { t } = useLanguage();
  const { data, isLoading } = useAnalyticsDashboard();
  const [exporting, setExporting] = useState(false);

  const kpi = (data as any)?.kpi || {};
  const funnel = (data as any)?.funnel || {};
  const rawSources = (data as any)?.sources;
  const sources: { source: string; count: number }[] = Array.isArray(rawSources)
    ? rawSources
    : Object.entries(rawSources || {}).map(([source, count]) => ({ source, count: Number(count) }));
  const trends: number[] = Array.isArray((data as any)?.trends) ? (data as any).trends : [];
  const totalApplicants = (data as any)?.total_applications ?? funnel.applied ?? '—';

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await analyticsService.exportReport({ format: 'csv', days: 30 });
      if (!(blob instanceof Blob)) {
        throw new Error(t('analytics.export_invalid_response'));
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `candway-analytics-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      customToast({ type: 'success', title: t('analytics.export_complete_title'), message: t('analytics.export_complete_message') });
    } catch (err: any) {
      customToast({ type: 'error', title: t('analytics.export_failed_title'), message: err?.message || t('analytics.export_failed_message') });
    } finally {
      setExporting(false);
    }
  };

  const metrics = [
    { label: t('analytics.metrics.total_applicants'), value: String(totalApplicants), change: '', trend: 'up' as const, sub: t('analytics.metrics.total_applicants_sub') },
    { label: t('analytics.metrics.avg_time_to_hire'), value: kpi.time_to_hire ? `${kpi.time_to_hire} ${t('analytics.metrics.days')}` : '—', change: '', trend: 'up' as const, sub: t('analytics.metrics.avg_time_to_hire_sub') },
    { label: t('analytics.metrics.avg_score'), value: kpi.avg_score ? `${kpi.avg_score}%` : '—', change: '', trend: 'up' as const, sub: t('analytics.metrics.avg_score_sub') },
    { label: t('analytics.metrics.hired'), value: String(kpi.hired ?? '—'), change: '', trend: 'up' as const, sub: t('analytics.metrics.hired_sub') },
  ];

  const now = new Date();
  const trendDays = trends.map((_, i) => {
    const d = new Date(now);
    d.setDate(d.getDate() - (trends.length - 1 - i));
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('analytics.dashboard')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('analytics.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="primary" leftIcon={exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />} onClick={handleExport} disabled={exporting}>
            {exporting ? t('analytics.exporting') : t('analytics.export_csv')}
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-purple-600" /></div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {metrics.map((metric, i) => (
              <motion.div key={metric.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.05 }}>
                <Card hoverable className="p-5 border-purple-200/70 dark:border-purple-500/20">
                  <div className="text-xs font-bold uppercase tracking-wider text-purple-700 dark:text-purple-300">{metric.label}</div>
                  <div className="flex items-baseline justify-between mt-2.5">
                    <div className="text-2xl sm:text-3xl font-black text-gray-900 dark:text-white">{metric.value}</div>
                    {metric.change && (
                      <div className={cn('flex items-center gap-1 text-xs font-extrabold px-2 py-0.5 rounded-full', metric.trend === 'up' ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700')}>
                        {metric.trend === 'up' ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
                        {metric.change}
                      </div>
                    )}
                  </div>
                  <p className="mt-2 text-xs font-medium text-gray-500 dark:text-gray-400">{metric.sub}</p>
                </Card>
              </motion.div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.2 }} className="lg:col-span-7">
              <Card className="h-full p-6">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2"><BarChart3 className="h-5 w-5 text-purple-600" /> {t('analytics.trends.title')}</CardTitle>
                  <CardDescription>{t('analytics.trends.description')}</CardDescription>
                </CardHeader>
                <CardContent className="mt-6">
                  {trends.length === 0 ? (
                    <p className="py-10 text-center text-sm text-gray-500 dark:text-gray-400">
                      {t('analytics.trends.no_data')}
                    </p>
                  ) : (
                    <div className="h-64 flex items-end justify-between gap-3 px-2">
                      {trends.map((value, i) => (
                        <div key={i} className="flex-1 flex flex-col items-center gap-2">
                          <div className="w-full flex items-end justify-center h-[200px]">
                            <div className="w-full flex flex-col items-center justify-end h-full group">
                              <span className="text-[10px] font-bold text-gray-600 dark:text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity mb-1">{value}</span>
                              <motion.div initial={{ height: 0 }} animate={{ height: `${(value / Math.max(...trends, 1)) * 100}%` }} transition={{ duration: 0.8, delay: 0.2 + i * 0.08 }}
                                className="w-full rounded-t-xl bg-gradient-to-t from-purple-700 via-purple-600 to-violet-500 shadow-md shadow-purple-500/30" />
                            </div>
                          </div>
                          <div className="text-xs font-bold text-gray-700 dark:text-gray-300 mt-1">{trendDays[i] || ''}</div>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="flex items-center justify-center gap-6 mt-6 pt-4 border-t border-purple-100/60 dark:border-white/10 text-xs font-bold text-gray-600 dark:text-gray-300">
                    <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-full bg-purple-600" /> {t('analytics.applications')}</span>
                  </div>
                </CardContent>
              </Card>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.3 }} className="lg:col-span-5">
              <Card className="h-full p-6">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2"><MapPin className="h-5 w-5 text-indigo-600" /> {t('analytics.sources.title')}</CardTitle>
                  <CardDescription>{t('analytics.sources.description')}</CardDescription>
                </CardHeader>
                <CardContent className="mt-6">
                  {sources.length === 0 ? (
                    <p className="py-10 text-center text-sm text-gray-500 dark:text-gray-400">
                      {t('analytics.sources.no_data')}
                    </p>
                  ) : (
                    <div className="space-y-5">
                      {sources.map((source, i) => {
                        const total = sources.reduce((s, x) => s + x.count, 0) || 1;
                        const pct = Math.round((source.count / total) * 100);
                        return (
                          <div key={source.source} className="space-y-1.5">
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-extrabold text-gray-900 dark:text-white">{source.source}</span>
                              <span className="text-xs font-bold text-purple-700 dark:text-purple-300">{source.count} ({pct}%)</span>
                            </div>
                            <div className="h-2.5 rounded-full bg-purple-100/70 dark:bg-purple-950/40 overflow-hidden border border-purple-200/50 dark:border-white/5">
                              <motion.div initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.8, delay: 0.3 + i * 0.1 }}
                                className="h-full rounded-full bg-purple-600" />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.4 }}>
            <Card className="p-6">
              <CardHeader>
                <CardTitle>{t('analytics.funnel.title')}</CardTitle>
                <CardDescription>{t('analytics.funnel.description')}</CardDescription>
              </CardHeader>
              <CardContent className="mt-4">
                {Object.keys(funnel).length === 0 ? (
                  <p className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                    {t('analytics.funnel.no_data')}
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-purple-100 dark:border-white/[0.08] text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          <th className="text-left py-3.5 pr-4">{t('analytics.funnel.stage')}</th>
                          <th className="text-left py-3.5 pr-4">{t('analytics.funnel.candidates')}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-purple-100/60 dark:divide-white/[0.04]">
                        {[
                          { key: 'applied', label: t('analytics.funnel.applied') },
                          { key: 'screened', label: t('analytics.funnel.screened') },
                          { key: 'interview', label: t('analytics.funnel.interview') },
                          { key: 'offer', label: t('analytics.funnel.offer') },
                          { key: 'hired', label: t('analytics.funnel.hired') },
                          { key: 'rejected', label: t('analytics.funnel.rejected') },
                        ].map(({ key, label }) => (
                          <tr key={key} className="hover:bg-purple-50/40 dark:hover:bg-white/[0.01] transition-colors">
                            <td className="py-4 pr-4 text-sm font-extrabold text-gray-900 dark:text-white">{label}</td>
                            <td className="py-4 text-sm font-bold text-purple-600 dark:text-purple-400">{funnel[key] ?? 0}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </>
      )}
    </div>
  );
}